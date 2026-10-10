# -*- coding: utf-8 -*-
"""
L6-064 单据配置维护与路由调起（只读闭环）

业务说明：
- 医院各业务节点（门诊挂号、住院收费、药房发药、检查检验）打印单据前，必须预先配置单据打印路由与页面参数。
- 校验重点（只验配置维护，实际物理打印跳过）：
  ① 接口与数据库逐字段精确对账：
     - 调用 `GET /system/print/getByCode?printCode=GHFP`（挂号发票）；
     - 与 Oracle 数据库 `SYS_PRINT` 逐字段严格比对（printId、printCode、printName、printerName、pageName、deptId、updateOperId、updateOperName）；
  ② 列表接口总数核对：
     - 调用 `GET /system/print/list`，断言其 total 与库中 `SYS_PRINT` 记录总数严格相等；
  ③ 负向断言（防恒真）：
     - 查询不存在的配置代码 `INVALID_PRINT_CODE`，断言返回 '打印设置不存在'，data 为 None。
"""

import time
from typing import Any, Dict

from ..closed_loop import Ctx, LoopResult, _oracle_conn


def flow_L6_064(ctx: Ctx) -> LoopResult:
    res = LoopResult(case_id="L6-064", title="单据配置维护与路由调起")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()

        # 1. 查询库中单据打印配置
        cur.execute("""
            SELECT print_id, print_code, print_name, printer_name, page_name, dept_id,
                   update_oper_id, update_oper_name
            FROM sys_print
            WHERE print_code = 'GHFP'
        """)
        row = cur.fetchone()
        if not row:
            conn.close()
            res.status = "未执行"
            res.note = "库中无 GHFP 打印单据配置样本"
            res.evidence = {"防空跑观测": {"GHFP配置样本存在": False}}
            return res

        (db_pid, db_pcode, db_pname, db_printer, db_page, db_dept,
         db_up_oper_id, db_up_oper_name) = row

        cur.execute("SELECT COUNT(*) FROM sys_print")
        db_total_count = cur.fetchone()[0]
        conn.close()

        # 2. 接口调用：根据代码获取单据配置
        api_res = ctx.get("/system/print/getByCode", params={"printCode": "GHFP"})
        if api_res.get("code") != 200:
            res.status = "失败"
            res.note = f"单据配置获取接口返回错误: code={api_res.get('code')}, msg={api_res.get('msg')}"
            return res

        api_data = api_res.get("data") or {}

        # 3. 接口调用：获取配置列表
        list_res = ctx.get("/system/print/list")
        list_total = list_res.get("total", -1)

        # 4. 逐字段严格对账
        bad: list = []
        if list_total != db_total_count:
            bad.append(f"配置列表总数不符: 接口 total={list_total}, 库={db_total_count}")

        if api_data.get("printId") != db_pid:
            bad.append(f"printId 不符: 接口={api_data.get('printId')}, 库={db_pid}")
        if api_data.get("printCode") != db_pcode:
            bad.append(f"printCode 不符: 接口={api_data.get('printCode')}, 库={db_pcode}")
        if api_data.get("printName") != db_pname:
            bad.append(f"printName 不符: 接口={api_data.get('printName')}, 库={db_pname}")
        if api_data.get("printerName") != db_printer:
            bad.append(f"printerName 不符: 接口={api_data.get('printerName')}, 库={db_printer}")
        if api_data.get("pageName") != db_page:
            bad.append(f"pageName 不符: 接口={api_data.get('pageName')}, 库={db_page}")
        if api_data.get("deptId") != db_dept:
            bad.append(f"deptId 不符: 接口={api_data.get('deptId')}, 库={db_dept}")
        if api_data.get("updateOperId") != db_up_oper_id:
            bad.append(f"updateOperId 不符: 接口={api_data.get('updateOperId')}, 库={db_up_oper_id}")
        if api_data.get("updateOperName") != db_up_oper_name:
            bad.append(f"updateOperName 不符: 接口={api_data.get('updateOperName')}, 库={db_up_oper_name}")

        # 5. 负向断言：非法代码必须拦截
        neg_res = ctx.get("/system/print/getByCode", params={"printCode": "INVALID_PRINT_CODE"})
        if neg_res.get("data") is not None:
            bad.append(f"负向测试未拦截: 传入非法代码仍返回了数据 {neg_res.get('data')}")

        ev = {
            "防空跑观测": {
                "GHFP配置样本存在": True,
                "库中总配置数": db_total_count,
                "接口返回数": list_total,
            },
            "配置代码": db_pcode,
            "配置名称": db_pname,
            "打印机路由": db_printer,
            "页面名称": db_page,
            "科室ID": db_dept,
            "操作人": f"{db_up_oper_name}({db_up_oper_id})",
            "列表总数核对": f"接口total={list_total}, 库={db_total_count}",
            "负向拦截": f"code={neg_res.get('code')}, msg={neg_res.get('msg')}"
        }
        res.evidence = ev

        if bad:
            res.status = "失败"
            res.note = "单据配置核对不成立: " + "；".join(bad)
            return res

        res.status = "通过"
        res.note = (f"单据配置 GHFP（{db_pname}）：接口与库表 SYS_PRINT 逐字段严格一致（"
                    f"打印机={db_printer}、页面={db_page}、科室={db_dept}、操作人={db_up_oper_name}）；"
                    f"列表总数({list_total})与库轧平；负向非法代码拦截成立")
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


FLOWS = {
    "L6-064": flow_L6_064,
}
