"""
清场：隔离被伪造的测试用例追踪表

背景：旧套件把 237 条**从未真正执行**的用例（原状态为 阻塞/跳过/失败/未执行）
改写成"通过"，并统一盖上"自动化(WebRunner) / 无头自动化实测"的来源章。
这张表正在被团队当作验收依据使用。

本脚本**不删除任何文件**，只做两件事：
1. 把被伪造的表移入 _作废_伪造数据/ 子目录（可随时拿回来）
2. 生成一份校正版：状态还原为源文件原值，只保留有真实依据的判定
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

import openpyxl

# Windows 控制台默认 GBK，改成 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(r"D:\workapp\ZJCK")
SRC = BASE / "HIS_EMR上线测试用例追踪表_合并版.xlsx"
QUARANTINE_DIR = BASE / "_作废_伪造数据"

# 需要隔离的文件：都含被伪造的"通过"
SUSPECT = [
    "HIS_EMR上线测试用例追踪表_合并版_已执行更新.xlsx",
    "HIS_EMR上线测试用例追踪表_合并版_已执行更新_真实实测.xlsx",
    "HIS_EMR上线测试用例追踪表_合并版_已写入用例.xlsx",
]

COL_ID, COL_STATUS, COL_OWNER, COL_DATE, COL_NOTE, COL_SOURCE = 1, 12, 14, 15, 16, 21


def _read(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["用例清单"]
    out = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        cid = row[COL_ID]
        if not cid or str(cid).strip() in ("用例ID", ""):
            continue
        out[str(cid).strip()] = {
            "status": (str(row[COL_STATUS]).strip() if row[COL_STATUS] else ""),
            "owner": (str(row[COL_OWNER]).strip() if row[COL_OWNER] else ""),
            "date": (str(row[COL_DATE]).strip() if row[COL_DATE] else ""),
            "note": (str(row[COL_NOTE]).strip() if row[COL_NOTE] else ""),
            "source": (str(row[COL_SOURCE]).strip() if row[COL_SOURCE] else ""),
        }
    wb.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"[致命] 源文件不存在: {SRC}")
        return 2
    src = _read(SRC)

    print("=" * 68)
    print("  清场：隔离被伪造的测试用例追踪表")
    print("=" * 68)
    print(f"  源文件（原状态权威依据）: {SRC.name}")

    # 1) 隔离可疑文件（被 Excel/WPS 占用的跳过并提示，不中断）
    moved, locked = [], []
    for name in SUSPECT:
        f = BASE / name
        if not f.exists():
            if (QUARANTINE_DIR / name).exists():
                continue          # 上次已隔离
            continue
        if args.dry_run:
            print(f"  [dry-run] 将隔离: {name}")
            continue
        QUARANTINE_DIR.mkdir(exist_ok=True)
        dst = QUARANTINE_DIR / name
        if dst.exists():
            dst = QUARANTINE_DIR / f"{f.stem}_{int(time.time())}{f.suffix}"
        try:
            shutil.move(str(f), str(dst))
            moved.append((name, dst.name))
        except PermissionError:
            locked.append(name)
    for a, b in moved:
        print(f"  已隔离: {a}\n          -> _作废_伪造数据/{b}")
    if locked:
        print("\n  ⚠️  以下文件正被 Excel/WPS 打开，无法移动，请关闭后重跑：")
        for n in locked:
            print(f"        - {n}")
        print("      （校正版仍会照常生成，不受影响）")

    # 2) 统计每个可疑文件的伪造量（隔离前先算，隔离后从隔离区读）
    print("\n  ── 伪造情况统计 ──")
    for name in SUSPECT:
        f = BASE / name
        if not f.exists():
            f = QUARANTINE_DIR / name
        if not f.exists():
            continue
        data = _read(f)
        fake = [c for c, v in data.items()
                if v["status"] == "通过" and c in src and src[c]["status"] != "通过"]
        print(f"  {name}")
        print(f"      伪造成'通过'的用例: {len(fake)} 条"
              f"（原状态：{_dist(fake, src)}）")

    # 3) 生成校正版：源文件原状态 + 清掉伪造的署名字段
    out = BASE / f"HIS_EMR上线测试用例追踪表_合并版_校正版_{time.strftime('%Y%m%d')}.xlsx"
    print(f"\n  校正版输出: {out.name}")
    if not args.dry_run:
        shutil.copyfile(SRC, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["用例清单"]
        header = {str(c.value).strip(): i for i, c in enumerate(ws[1]) if c.value}
        for want, idx in (("用例ID", COL_ID), ("执行状态", COL_STATUS),
                          ("执行人", COL_OWNER), ("备注", COL_NOTE)):
            if header.get(want) != idx:
                print(f"  [致命] 列位置不符：{want} 在 {header.get(want)}，预期 {idx}")
                return 2
        cleaned = 0
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=COL_ID + 1)
            cid = str(cell.value).strip() if cell.value else ""
            s = src.get(cid)
            if not s:
                continue
            cur = ws.cell(row=row, column=COL_STATUS + 1).value
            cur_s = str(cur).strip() if cur else ""
            if cur_s != s["status"]:
                ws.cell(row=row, column=COL_STATUS + 1, value=s["status"])
                cleaned += 1
            # 清掉自动化盖的章，避免继续误导
            for col in (COL_OWNER, COL_DATE, COL_NOTE, COL_SOURCE):
                ws.cell(row=row, column=col + 1, value=None)
        wb.save(out)
        wb.close()
        print(f"  已把 {cleaned} 条状态还原为源文件原值，并清空自动化署名字段")

    print("\n" + "=" * 68)
    if args.dry_run:
        print("  （--dry-run，未做任何改动）")
    else:
        print("  完成。被隔离的文件在 _作废_伪造数据/ 下，随时可取回。")
        print(f"  校正版：{out.name}（状态=源文件原值，无任何伪造的'通过'）")
    return 0


def _dist(fake, src):
    import collections
    return dict(collections.Counter(src[c]["status"] for c in fake))


if __name__ == "__main__":
    sys.exit(main())
