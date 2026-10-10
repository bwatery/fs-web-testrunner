"""
把体检结论写回《HIS_EMR上线测试用例追踪表》的新副本。

原则：
1. **绝不覆盖原文件**——始终另存为新副本
2. 状态列只用原表的既有用词：通过 / 失败 / 阻塞 / 跳过 / 未执行
3. 只有**真正跑完业务闭环**的用例才写"通过"；没验的一律保持"未执行"，
   并在备注里说明未验的原因，绝不无据盖"通过"
4. 备注只客观说明做了什么，不写"自动化测试"之类的标签

用法：
    python update_tracking_excel.py                 # 用最近一次闭环结果
    python update_tracking_excel.py --dry-run       # 只看会改什么，不落盘
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import openpyxl

# Windows 控制台默认 GBK，改成 UTF-8 以免中文与符号打印报错
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SRC_EXCEL = Path(r"D:\workapp\ZJCK\HIS_EMR上线测试用例追踪表_合并版.xlsx")
RESULT_JSON = Path(__file__).resolve().parent / "reports" / "verify" / "closed_loop_latest.json"

# 列索引（0-based，取自表头）
COL_ID, COL_STATUS, COL_OWNER, COL_DATE, COL_NOTE = 1, 12, 14, 15, 16

# 需要处理的用例：这 87 条是源表里状态为"未执行"的
TARGETED = "reports/verify/pending_87.json"


def _load_targets() -> dict:
    p = Path(__file__).resolve().parent / TARGETED
    rows = json.loads(p.read_text(encoding="utf-8"))
    return {r["case_id"]: r for r in rows}


_ABSENCE_RULES = [
    ("读卡", "需医保读卡器硬件"),
    ("前置机", "需医保前置机等外部系统"),
    ("医保", "需医保前置机等外部系统"),
    ("电子发票", "需电子发票平台等外部系统"),
    ("发票", "需电子发票平台等外部系统"),
    ("打印", "需打印设备与打印控件"),
    ("CA", "需数字证书介质"),
    ("手术", "需已排台的手术业务数据"),
    ("出院", "需已出院患者数据"),
    ("欠费", "需欠费、转科等特定在院状态"),
    ("皮试", "需皮试、过敏等特定患者状态"),
    ("归档", "需已归档病历"),
    ("封存", "需病历封存业务前置"),
]


_STATUS_ORDER = ("失败", "通过", "阻塞", "跳过")   # 优先级：失败最优先


def _decide(cid: str, verified: dict, overrides: dict, recon: dict, handoff: dict):
    """
    合并四个来源，返回 (status, note)；无任何来源意见时返回 (None, None)。

    规则：**任一实测通道报失败 → 该用例就是失败**（哪怕别的通道通过）；
          否则任一报通过 → 通过；再否则 阻塞 > 跳过 > 未执行。

    为什么"失败优先"：一条用例只要**任何一半**实测失败，它就不算通过。
    实例：L6-050 预交金日结 —— 闭环验的"日结数据"通过，但打印交回来说"报表被截断"，
    整体必须记「失败」。

    备注把各来源拼起来并标明出处（`[闭环真验证] …[打印交接实测] …`），保证不丢信息。
    """
    srcs = (("闭环真验证", verified.get(cid)),
            ("打印交接实测", handoff.get(cid)),
            ("人工覆盖", overrides.get(cid)),
            ("专项侦察", recon.get(cid)))
    cands = []
    for name, v in srcs:
        if not isinstance(v, dict):
            continue
        s = v.get("status")
        if s not in ("通过", "失败", "阻塞", "跳过", "未执行"):
            continue
        cands.append((name, s, str(v.get("note") or "").strip()))
    if not cands:
        return None, None
    for want in _STATUS_ORDER:
        hits = [c for c in cands if c[1] == want]
        if hits:
            parts = [f"[{n}] {t}" if t else f"[{n}] {s}" for n, s, t in hits]
            note = "；".join(parts)
            # 其他来源的结论也要留痕 —— 例如 L6-064 打印实测失败、但闭环那边数据是对的，
            # 只写"失败"会让接手的人以为这块完全没验过。
            others = [f"{n}={s}" for n, s, _ in cands if s != want]
            if others:
                note = f"{note}（另据：{'，'.join(others)}）"
            return want, note
    return "未执行", (cands[0][2] or "")


def _absence_reason(case: dict) -> str:
    """
    给"未验"的用例生成一句客观的未执行说明。
    先按前置条件匹配（最贴近该用例真正的拦路虎），匹配不到再看步骤，
    避免步骤里顺带提到的关键词把原因带偏。
    """
    pre = (case.get("precond") or "").strip()
    steps = (case.get("steps") or "").strip()
    point = (case.get("test_point") or "").strip()

    for scope in (pre, point, steps):
        for kw, why in _ABSENCE_RULES:
            if kw in scope:
                return f"本轮未验：{why}"
    if pre:
        return f"本轮未验：需真实业务前置（{pre[:22]}）"
    return "本轮未验：该用例尚未实现业务闭环校验"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--results", default=str(RESULT_JSON))
    args = ap.parse_args()

    if not SRC_EXCEL.exists():
        print(f"[致命] 源文件不存在: {SRC_EXCEL}")
        return 2

    targets = _load_targets()

    # 读取闭环校验结果（只有这里列出的用例才可能被写成"通过"）
    verified = {}
    try:
        payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
        for r in payload.get("results") or []:
            verified[r["case_id"]] = r
    except Exception as e:
        print(f"[提示] 未读到闭环结果 ({e})，本次只会把目标用例标注为未验。")

    stamp = time.strftime("%Y%m%d")
    dst = SRC_EXCEL.with_name(
        f"{SRC_EXCEL.stem}_本轮已验_{stamp}{SRC_EXCEL.suffix}")

    print("=" * 64)
    print("  写回测试用例追踪表（新副本）")
    print("=" * 64)
    print(f"  源文件 : {SRC_EXCEL.name}")
    print(f"  新副本 : {dst.name}")
    print(f"  目标用例: {len(targets)} 条（源表中状态为「未执行」）")
    print(f"  其中已完成真实闭环校验: {len([c for c in verified if c in targets])} 条")

    if not args.dry_run:
        shutil.copyfile(SRC_EXCEL, dst)

    wb = openpyxl.load_workbook(dst if not args.dry_run else SRC_EXCEL)
    if "用例清单" not in wb.sheetnames:
        print(f"[致命] 未找到「用例清单」工作表，实际有: {wb.sheetnames}")
        return 2
    ws = wb["用例清单"]

    # 表头校验：列位置错了就会写错地方，先确认
    header = {str(c.value).strip(): i for i, c in enumerate(ws[1]) if c.value}
    for want, idx in (("用例ID", COL_ID), ("执行状态", COL_STATUS),
                      ("执行人", COL_OWNER), ("执行日期", COL_DATE), ("备注", COL_NOTE)):
        got = header.get(want)
        if got != idx:
            print(f"[致命] 列位置与预期不符：{want} 在 {got}，预期 {idx}。已中止，避免写错列。")
            return 2

    today = time.strftime("%Y-%m-%d")
    changed_pass = changed_hold = 0
    details = []

    # 人工状态覆盖（如「医保待测交接表」里用户更新的状态）。
    # 优先级：闭环真验证结果 > 人工覆盖 > 源表原状态。
    overrides = {}
    ov_path = Path(__file__).resolve().parent / "reports" / "verify" / "manual_status.json"
    if ov_path.exists():
        try:
            overrides = json.loads(ov_path.read_text(encoding="utf-8"))
            print(f"  人工覆盖: 读入 {len(overrides)} 条（{ov_path.name}）")
        except Exception as e:
            print(f"  [提示] 人工覆盖读取失败，忽略: {e}")

    # 专项侦察判定（如"本环境功能未上线/无数据"，无法写成闭环用例的）。
    # 与 manual_status.json 分开存放，因为 sync_insurance_status.py 会整体重写后者。
    recon = {}
    rv_path = Path(__file__).resolve().parent / "reports" / "verify" / "recon_verdicts.json"
    if rv_path.exists():
        try:
            raw = json.loads(rv_path.read_text(encoding="utf-8"))
            recon = {k: v for k, v in raw.items() if not k.startswith("_")}
            print(f"  侦察判定: 读入 {len(recon)} 条（{rv_path.name}）")
        except Exception as e:
            print(f"  [提示] 侦察判定读取失败，忽略: {e}")

    # 交接表实测回填（如《打印待测_交接》里外部测试员真测出的结果）。
    # 来源文件由 export_print_excel.py 导出的表格反向抽取，见 handoff_status.json。
    handoff = {}
    ho_path = Path(__file__).resolve().parent / "reports" / "verify" / "handoff_status.json"
    if ho_path.exists():
        try:
            handoff = json.loads(ho_path.read_text(encoding="utf-8"))
            print(f"  交接表实测: 读入 {len(handoff)} 条（{ho_path.name}）")
        except Exception as e:
            print(f"  [提示] 交接表实测读取失败，忽略: {e}")

    for row in range(2, ws.max_row + 1):
        cid_cell = ws.cell(row=row, column=COL_ID + 1)
        cid = str(cid_cell.value).strip() if cid_cell.value else ""
        if not cid:
            continue
        # ── 统一判定 ──────────────────────────────────────────────────────────
        # 规则：**任一实测通道报失败 → 该用例就是失败**（哪怕别的通道通过）；
        #      否则任一报通过 → 通过；再否则 阻塞 > 跳过 > 未执行。
        # 为什么"失败优先"：一条用例只要**任何一半**实测失败，它就不算通过。
        # 实例：L6-050 预交金日结 —— 闭环验的"日结数据"是通过的，但打印交回来说
        #       "日结报表被截断"，整体必须记「失败」，不能被闭环的"通过"盖掉。
        st, note = _decide(cid, verified, overrides, recon, handoff)
        if st is None:
            if cid not in targets:
                continue          # 目标集外、又没有任何来源给出结论 → 保持源表原状态
            st, note = "未执行", _absence_reason(targets[cid])
        ws.cell(row=row, column=COL_STATUS + 1, value=st)
        ws.cell(row=row, column=COL_NOTE + 1, value=note)
        ws.cell(row=row, column=COL_DATE + 1, value=today)
        if st == "通过":
            changed_pass += 1
        else:
            changed_hold += 1
        details.append((cid, st, note[:70]))

    if not args.dry_run:
        wb.save(dst)
    wb.close()

    print(f"\n  ── 写回明细（{len(details)} 条）──")
    for cid, st, note in details[:12]:
        print(f"  [{st:4s}] {cid:9s} {note}")
    if len(details) > 12:
        print(f"  ... 其余 {len(details) - 12} 条见新副本")
    print(f"\n  ✅ 判定为通过 {changed_pass} 条")
    print(f"  ⚪ 保持未执行 {changed_hold} 条（已在备注说明未验原因）")
    if args.dry_run:
        print("\n  （--dry-run 模式，未生成副本）")
    else:
        print(f"\n  新副本已生成: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
