# -*- coding: utf-8 -*-
"""
导出「医保相关、本环境验不了」的用例为独立 Excel（保持源表格式）。

做法：复制源文件 -> 在"用例清单"里删掉不需要的行 -> 备注写清依赖 -> 另存。
这样列结构、样式、其余工作表与源表完全一致。
"""
import shutil
from pathlib import Path

import openpyxl

SRC = Path(r"D:\workapp\ZJCK\HIS_EMR上线测试用例追踪表_合并版.xlsx")
DST = Path(r"D:\workapp\ZJCK\HIS_EMR上线测试用例追踪表_医保待测_交接_20261009.xlsx")

# 备注：写清"为什么本环境验不了"
REASON = {
    "L0-010": "需医保三大目录对照与限价数据，须医保侧配合",
    "L1-003": "需读卡器硬件（就诊卡/医保卡/身份证）",
    "L1-004": "需医保电子凭证介质与扫码环境",
    "L2-007": "医保与公医身份挂号，需医保前置机与对应身份数据",
    "L2-038": "医保限制/限价/PASS 审方，需医保前置机与合理用药库",
    "L4-046": "代煎配送与医保限制，需医保前置机",
    "L6-026": "自费收银部分本环境已验证；医保收银需医保前置机",
    "L6-068": "医保结算单/异地单需医保前置机；另需打印设备",
    "L7-001": "医保前置机调用与超时兜底，本环境无前置机",
    "L7-004": "需窗口外设硬件（读卡器/扫码枪/高拍仪/叫号屏）",
}
GENERIC_INSURANCE = "国家医保子系统：需医保前置机/医保接口联通，本环境无对应通道，无法验证"


def is_insurance(v) -> bool:
    sub = str(v[3] or "")
    tp = str(v[5] or "")
    feat = str(v[4] or "")
    st = str(v[12] or "")
    if sub == "国家医保":
        return True
    return st != "通过" and ("医保" in tp or "医保" in feat or "读卡" in tp or "前置机" in tp)


def main() -> int:
    if not SRC.exists():
        print(f"[致命] 源文件不存在: {SRC}")
        return 2
    shutil.copyfile(SRC, DST)

    wb = openpyxl.load_workbook(DST)
    ws = wb["用例清单"]
    header = [c.value for c in ws[1]]
    print("表头:", header)

    keep_rows, cids = [], []
    for r in range(2, ws.max_row + 1):
        v = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if is_insurance(v):
            keep_rows.append(r)
            cids.append(str(v[1]))

    # 倒着删，避免行号漂移
    keep = set(keep_rows)
    for r in range(ws.max_row, 1, -1):
        if r not in keep:
            ws.delete_rows(r)

    # 备注：写清依赖（保留原有文字）
    for r in range(2, ws.max_row + 1):
        cid = str(ws.cell(row=r, column=2).value or "").strip()
        sub = str(ws.cell(row=r, column=4).value or "")
        why = REASON.get(cid) or (GENERIC_INSURANCE if sub == "国家医保"
                                  else "涉及医保前置机/读卡介质，本环境不具备")
        old = str(ws.cell(row=r, column=17).value or "").strip()
        note = f"本环境未验：{why}"
        if old and old not in note:
            note = f"{note}（原备注：{old}）"
        ws.cell(row=r, column=17, value=note)
        ws.cell(row=r, column=1, value=r - 1)          # 序号重编 1..N，方便交接填写

    # 门禁看板是**全项目**的公式看板，在只剩 17 行的副本里会算出误导性数字；
    # 缺陷追踪是全项目缺陷清单，与本次交接无关 —— 一并去掉，只留用例清单与枚举说明。
    for name in ("门禁看板", "缺陷追踪"):
        if name in wb.sheetnames:
            del wb[name]

    wb.save(DST)
    wb.close()

    print(f"\n导出 {len(cids)} 条：{', '.join(cids)}")
    print(f"文件：{DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
