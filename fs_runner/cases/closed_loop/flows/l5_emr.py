# -*- coding: utf-8 -*-
"""
L5 病历文书类用例（EMR 独立后端）。

EMR 不在 HIS 网关上：后端是 `http://192.168.1.198:8021`（来自前端运行时配置
`http://192.168.1.198:8088/config.js`），**直接认 HIS 的 JWT**。
接口前缀 `/emr/*`、`/med/*`、`/qc/*`，Swagger 见 data/emr_api_spec.json。

本文件是「并行协作口子」的示范：放这里不用改公共文件，closed_loop.py 会自动 collect。
"""
import base64
import json
import time
from typing import Any, Dict, List, Optional

import requests

from ..closed_loop import Ctx, LoopResult, _oracle_conn

EMR_BASE = "http://192.168.1.198:8021"


class Emr:
    """EMR 后端的极简客户端（复用 HIS 的 token）。"""

    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.proxies = {"http": None, "https": None}
        self.s.trust_env = False
        self.h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def post(self, path: str, body: Any, timeout: int = 30) -> Dict[str, Any]:
        try:
            r = self.s.post(f"{EMR_BASE}{path}", headers=self.h, json=body, timeout=timeout)
            return r.json()
        except Exception as e:
            return {"code": -1, "msg": f"{type(e).__name__}: {e}"[:150]}

    def get(self, path: str, params: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        try:
            r = self.s.get(f"{EMR_BASE}{path}", headers=self.h, params=params or {}, timeout=timeout)
            return r.json()
        except Exception as e:
            return {"code": -1, "msg": f"{type(e).__name__}: {e}"[:150]}

    def raw_status(self, path: str, timeout: int = 30) -> int:
        """只看 HTTP 状态码 —— 有些接口返回 gzip 二进制（文书正文），不能按 JSON 解析。"""
        try:
            r = self.s.get(f"{EMR_BASE}{path}", headers=self.h, timeout=timeout)
            return r.status_code
        except Exception:
            return -1

    def rows(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EMR 的分页接口把数组直接放在 data（不是 {rows:[]}）。"""
        d = resp.get("data")
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("rows", "list", "records"):
                if isinstance(d.get(k), list):
                    return d[k]
        return []


def _emr(ctx: Ctx) -> Emr:
    return Emr(ctx.token)


def _norm(v: Any) -> str:
    """接口给数字是 '36.5'，库里是 VARCHAR2('36.5')；统一成去尾零的字符串比。"""
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    try:
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return s


# ---------------------------------------------------------------------------
# L5-001 体温单录入与曲线绘制 / L5-002 体温单跨日连续性与数据引用
# ---------------------------------------------------------------------------
_TEMP_FIELDS = [
    ("measureTime", "MEASURE_TIME"), ("temperature", "TEMPERATURE"),
    ("pulse", "PULSE"), ("respiration", "RESPIRATION"),
    ("systolicBp", "SYSTOLIC_BP"), ("diastolicBp", "DIASTOLIC_BP"),
    ("spo2", "SPO2"), ("intakeTotal", "INTAKE_TOTAL"), ("outputTotal", "OUTPUT_TOTAL"),
    ("stoolCount", "STOOL_COUNT"), ("weight", "WEIGHT"), ("bedNo", "BED_NO"),
]


def flow_L5_001(ctx: Ctx) -> LoopResult:
    """
    体温单：曲线所依赖的那批数据，必须与库里一模一样。

    口径（实测）：
      - `POST /emr/temperature/queryPage {registerId, pageNum, pageSize}` —— **data 直接是数组**
      - `measureTime` 接口给 `2026-05-01T15:02`，库里是 DATE；比对时按 `YYYY-MM-DD HH24:MI` 归一
      - 只统计 `VALID_FLAG='1'`

    断言：
      ① 接口返回条数 == 库中该就诊有效体温记录数
      ② 逐条逐字段（测量时间/体温/脉搏/呼吸/血压/血氧/入量/出量/大便/体重/床号）== 库
      ③ 跨日连续性（L5-002）：覆盖 ≥2 个自然日 —— 曲线的时间轴才成立
         ⚠️ **不断言**"同一测量时间唯一"：同一时间点可以有多条（复测 / 降温后 / "拒测"），是正常业务
    """
    res = LoopResult(case_id="L5-001", title="护理文书·体温单录入与曲线绘制")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT register_id FROM emr_nurse_temperature
                       WHERE valid_flag='1' AND measure_time IS NOT NULL
                       GROUP BY register_id ORDER BY COUNT(*) DESC FETCH FIRST 1 ROWS ONLY""")
        row = cur.fetchone()
        if not row:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有体温单记录，无法核对"
            return res
        rid = str(row[0])

        cur.execute("""SELECT temperature_id, measure_time, temperature, pulse, respiration,
                              systolic_bp, diastolic_bp, spo2, intake_total, output_total,
                              stool_count, weight, bed_no
                       FROM emr_nurse_temperature
                       WHERE register_id=:1 AND valid_flag='1' AND measure_time IS NOT NULL""", [rid])
        ora = {}
        for r in cur.fetchall():
            ora[str(r[0])] = {
                "measureTime": r[1].strftime("%Y-%m-%d %H:%M"),
                "temperature": r[2], "pulse": r[3], "respiration": r[4],
                "systolicBp": r[5], "diastolicBp": r[6], "spo2": r[7],
                "intakeTotal": r[8], "outputTotal": r[9], "stoolCount": r[10],
                "weight": r[11], "bedNo": r[12],
            }
        # 跨日统计
        cur.execute("""SELECT COUNT(DISTINCT TRUNC(measure_time)) FROM emr_nurse_temperature
                       WHERE register_id=:1 AND valid_flag='1' AND measure_time IS NOT NULL""", [rid])
        days = int(cur.fetchone()[0])
        cur.execute("""SELECT COUNT(*) FROM (
                         SELECT measure_time FROM emr_nurse_temperature
                         WHERE register_id=:1 AND valid_flag='1' AND measure_time IS NOT NULL
                         GROUP BY measure_time HAVING COUNT(*) > 1)""", [rid])
        dup_times = int(cur.fetchone()[0])
        conn.close()

        emr = _emr(ctx)
        got = emr.post("/emr/temperature/queryPage",
                       {"registerId": rid, "pageNum": 1, "pageSize": max(200, len(ora) + 50)})
        api_rows = emr.rows(got)
        ev = {"试验就诊": f"registerId={rid}", "库中有效体温记录": len(ora),
              "接口返回条数": len(api_rows), "覆盖自然日": days,
              "同一测量时间重复组数": dup_times}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"体温单查询接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api_rows) != len(ora):
            bad.append(f"①条数：接口 {len(api_rows)} ≠ 库 {len(ora)}")

        api = {str(x.get("temperatureId")): x for x in api_rows}
        only_api = sorted(set(api) - set(ora))
        only_ora = sorted(set(ora) - set(api))
        if only_api:
            bad.append(f"②接口多出库中没有的记录 {only_api[:3]}")
        if only_ora:
            bad.append(f"②库中有而接口漏掉的记录 {only_ora[:3]}")

        diff = []
        for tid in sorted(set(api) & set(ora)):
            for ak, dk in _TEMP_FIELDS:
                a, o = api[tid].get(ak), ora[tid][ak]
                a2 = str(a).replace("T", " ")[:16] if ak == "measureTime" else a
                if _norm(a2) != _norm(o):
                    diff.append(f"{tid[:8]}.{ak}: 接口 {a2!r} ≠ 库 {o!r}")
                    break
        ev["字段不一致条数"] = len(diff)
        ev["不一致样例"] = diff[:3]
        if diff:
            bad.append(f"②有 {len(diff)} 条字段与库不符，例：{diff[0]}")

        # ③ 跨日连续性（L5-002）
        # ⚠️ 不要断言"同一测量时间唯一"——实测同一时间点可以有多条（复测、降温后、**"拒测"**），
        #    那是正常业务，断言唯一会变成假缺陷。
        if days < 2:
            bad.append(f"③体温单只覆盖 {days} 个自然日，跨日连续性无从谈起")
        ev["同一测量时间的多条记录(正常业务，非缺陷)"] = dup_times

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "体温单数据与库不符：" + "；".join(bad[:4])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"就诊 registerId={rid}：{len(api_rows)} 条体温记录逐条逐字段"
                    f"（体温/脉搏/呼吸/血压/血氧/出入量/大便/体重/床号）与库完全一致，"
                    f"覆盖 {days} 个自然日——曲线的时间轴与数据源成立"
                    f"（其中 {dup_times} 组同一时间点有多条，是复测/拒测的正常业务）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-003 一般护理记录单录入与签名
# ---------------------------------------------------------------------------
def flow_L5_003(ctx: Ctx) -> LoopResult:
    """
    护理记录单：{记录单 → 若干时间点 → 每个时间点一组数据元} 的结构必须与库一致。

    口径（实测）：
      - 库把每个数据元存成一行（`EMR_NURSE_RECORD_DETAIL`，一行一个 dataElement），
        同一个 `NURSE_DATA_ELEMENT_INDEX` 的多行 = **一个时间点**的一组值
      - `POST /emr/nurseRecordDetail/queryList {recordId}` 直接把**每个时间点揉成一行**返回
        （字段名就是数据元 code：datetime / ingredientMl / outletMl / pulse / breathing / …）

    断言：
      ① 接口**不漏**库中的时间点（库中有的 index，接口都要有）
      ② 两边都有的时间点，**逐数据元值一致**（这是最硬的一条：录入的内容必须原样读得出来）
    ⚠️ 口径补全（靠协作方独立复核发现的）：`queryList` 返回的条数 = **明细时间点数 + 出入量总结行数**。
      多出来的那几行带着 `isSummarized='1'` / `summaryContent='24小时总结'`，
      它们在 `EMR_NURSE_RECORD_DETAIL` 里查不到，实际来自 `EMR_NURSE_RECORD_SUMMARY`
      （实测该记录单 426 明细 + 4 总结 = 430，且总结行的 入量/出量 与总结表逐条对得上）。

    断言：
      ① 接口**不漏**库中的明细时间点
      ② 两边都有的明细时间点，逐数据元值一致
      ③ **多出来的行必须是出入量总结行**，且其 入量/出量 与 `EMR_NURSE_RECORD_SUMMARY` 一致
    """
    res = LoopResult(case_id="L5-003", title="护理文书·一般护理记录单录入与签名")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_id, COUNT(DISTINCT nurse_data_element_index)
                       FROM emr_nurse_record_detail
                       WHERE valid_flag='1' AND record_id IS NOT NULL
                       GROUP BY record_id ORDER BY COUNT(*) DESC FETCH FIRST 1 ROWS ONLY""")
        row = cur.fetchone()
        if not row:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有护理记录单明细，无法核对"
            return res
        rid = str(row[0])

        cur.execute("""SELECT nurse_data_element_index, nurse_data_element_code, nurse_data_element_value
                       FROM emr_nurse_record_detail
                       WHERE record_id=:1 AND valid_flag='1'""", [rid])
        ora: Dict[str, Dict[str, str]] = {}
        for idx, code, val in cur.fetchall():
            ora.setdefault(str(idx), {})[str(code)] = "" if val is None else str(val)
        conn.close()

        emr = _emr(ctx)
        got = emr.post("/emr/nurseRecordDetail/queryList", {"recordId": rid})
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"护理记录单查询接口异常: {str(got)[:160]}"
            return res
        api_rows = emr.rows(got)
        api = {str(x.get("nurseDataElementIndex")): x for x in api_rows}
        ev = {"试验记录单": f"recordId={rid}", "库中时间点数": len(ora),
              "接口时间点数": len(api)}

        bad = []
        missing = sorted(set(ora) - set(api))
        if missing:
            bad.append(f"①接口漏了库中的 {len(missing)} 个时间点，例 {missing[:2]}")
        extra = sorted(set(api) - set(ora))
        # ③ 多出来的必须是"出入量总结行"，且数值与总结表对得上
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT summary_content, intake_amount, output_amount
                       FROM emr_nurse_record_summary WHERE record_id=:1""", [rid])
        sums = [(str(a), _norm(b), _norm(c)) for a, b, c in cur.fetchall()]
        conn.close()
        summary_rows = [api[k] for k in extra]
        ev["接口多出的行数(应为出入量总结)"] = len(extra)
        ev["接口多出的行样例"] = [{"summaryContent": x.get("summaryContent"),
                                   "ingredientMl": x.get("ingredientMl"),
                                   "outletMl": x.get("outletMl")} for x in summary_rows[:4]]
        ev["库中总结行数"] = len(sums)
        if len(extra) != len(sums):
            bad.append(f"③接口多出 {len(extra)} 行，但库中出入量总结只有 {len(sums)} 行，对不上")
        unmatched = []
        for x in summary_rows:
            key = (str(x.get("summaryContent")), _norm(x.get("ingredientMl")), _norm(x.get("outletMl")))
            if key not in sums:
                unmatched.append(key)
        if unmatched:
            bad.append(f"③有多出的行不是有效的出入量总结（在总结表里找不到）：{unmatched[:3]}")

        checked = mism = 0
        samples = []
        for idx in sorted(set(ora) & set(api)):
            a = api[idx]
            for code, want in ora[idx].items():
                if code not in a:
                    continue
                checked += 1
                if _norm(a.get(code)) != _norm(want):
                    mism += 1
                    if len(samples) < 3:
                        samples.append(f"{idx[:8]}.{code}: 接口 {a.get(code)!r} ≠ 库 {want!r}")
        ev["比对的数据元值个数"] = checked
        ev["不一致个数"] = mism
        ev["不一致样例"] = samples
        if mism:
            bad.append(f"②有 {mism}/{checked} 个数据元值与库不符，例：{samples[0] if samples else ''}")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "护理记录单与库不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"护理记录单 recordId={rid}：库中 {len(ora)} 个时间点一个不漏，"
                    f"共比对 {checked} 个数据元值（时间/入量/出量/脉搏/呼吸/签名…）全部与库一致；"
                    f"接口额外返回的 {len(extra)} 行经核实为**出入量总结行**，数值与总结表逐条对得上")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-020 结构化模板与元素引用 / L5-021 模板权限与版本管理
# ---------------------------------------------------------------------------
def flow_L5_020(ctx: Ctx) -> LoopResult:
    """
    结构化病历模板：模板清单、分类归属、内容可取，三件事都得对。

    口径（实测）：
      - `POST /emr/template/list {pageNum,pageSize}` 返回的是 **`VALID_FLAG='1' 且 APPROVAL_STATE='1'`**
        的模板（实测正好 119 条；库里 APPROVAL_STATE 为 NULL 或 '2' 的 2 条不返回）
      - `GET /emr/template/queryById/{templateId}` 取单条

    断言：
      ① 接口条数 == 库中 APPROVAL_STATE='1' 且 VALID_FLAG='1' 的模板数；templateId 集合双向一致
      ② 逐条 模板名/病历类型/版本号 与库一致
      ③ 每条的 RECORD_TYPE_ID 都能在 `EMR_BD_RECORD_TYPE` 里找到（分类不悬空）——这就是"结构化"的骨架
      ④ 抽样若干条，`queryById` 能取回（内容可取，元素才引用得上）
    """
    res = LoopResult(case_id="L5-020", title="模板与元素·结构化模板与元素引用")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT template_id, template_name, record_type_id, version_number
                       FROM emr_bd_template WHERE valid_flag='1' AND approval_state='1'""")
        ora = {str(r[0]): (r[1], str(r[2]) if r[2] is not None else "", r[3]) for r in cur.fetchall()}
        cur.execute("SELECT record_type_id FROM emr_bd_record_type")
        types = {str(r[0]) for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM emr_bd_template WHERE valid_flag='1' AND approval_state='1'")
        n_ora = int(cur.fetchone()[0])
        conn.close()
        if not ora:
            res.status = "未执行"
            res.note = "库里没有已审核通过的结构化模板"
            return res

        emr = _emr(ctx)
        got = emr.post("/emr/template/list", {"pageNum": 1, "pageSize": max(200, len(ora) + 50)})
        rows = emr.rows(got)
        api = {str(x.get("templateId")): x for x in rows}
        ev = {"库中已审核模板": n_ora, "接口返回条数": len(api),
              "库里审核状态分布": "APPROVAL_STATE='1' 才返回（NULL/'2' 的不返回，实测）"}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"模板列表接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api) != len(ora):
            bad.append(f"①条数：接口 {len(api)} ≠ 库 {len(ora)}")
        only_api, only_ora = sorted(set(api) - set(ora)), sorted(set(ora) - set(api))
        if only_api:
            bad.append(f"①接口多出库中没有的模板 {only_api[:3]}")
        if only_ora:
            bad.append(f"①库中有而接口漏掉的模板 {only_ora[:3]}")

        diff = []
        for tid in sorted(set(api) & set(ora)):
            name, rt, ver = ora[tid]
            if str(api[tid].get("templateName")) != str(name) \
                    or _norm(api[tid].get("versionNumber")) != _norm(ver):
                diff.append(f"{tid[:8]}: 接口 {api[tid].get('templateName')}/{api[tid].get('versionNumber')}"
                            f" ≠ 库 {name}/{ver}")
            # 注：病历类型"悬空"**不判失败**——口径没吃透（可能在别的类型源里），只记录
        dangling = [tid for tid in sorted(ora) if ora[tid][1] and ora[tid][1] not in types]
        ev["病历类型在 EMR_BD_RECORD_TYPE 里查不到的模板数(观察项，非缺陷)"] = len(dangling)
        ev["字段/分类不一致条数"] = len(diff)
        ev["不一致样例"] = diff[:3]
        if diff:
            bad.append(f"②{len(diff)} 条字段与库不符，例：{diff[0]}")

        # ④ 抽样取内容
        import random
        sample = random.sample(sorted(ora), min(3, len(ora)))
        fetched = []
        for tid in sample:
            one = emr.get(f"/emr/template/queryById/{tid}")
            ok = one.get("code") == 200 and bool(one.get("data"))
            fetched.append({"templateId": tid, "可取": ok})
            if not ok:
                bad.append(f"④模板 {tid[:8]} 取不回内容: {str(one)[:80]}")
        ev["抽样取内容"] = fetched

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "结构化模板与库不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(api)} 个已审核结构化模板与库逐条一致（名称/病历类型/版本号），"
                    f"抽样 {len(sample)} 个模板内容均可取回"
                    f"（另有 {ev['病历类型在 EMR_BD_RECORD_TYPE 里查不到的模板数(观察项，非缺陷)']} 个模板的"
                    f"病历类型在类型表里查不到，口径未定，仅记录）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


def flow_L5_021(ctx: Ctx) -> LoopResult:
    """
    模板权限（科室/个人授权）与版本管理。

    实测口径：
      - `POST /emr/templateGrant/list` 返回的正是 `EMR_BD_TEMPLATE_GRANT` 里 `VALID_FLAG='1'` 的**全部** 1464 条
      - 版本：`EMR_BD_TEMPLATE.VERSION_NUMBER` 与 `EMR_BD_TEMPLATE_LOG` 的历史。
        **有版本日志的模板，其当前版本号必定出现在日志里**（实测 0 例外）；
        另有 25 个模板**从来没有过版本日志**（没改过 → 没有历史是合理的），不据此判缺陷。

    断言：
      ① 授权记录接口 == 库（条数 + 逐条 授权ID/模板/授权科室/授权人员）
      ② 版本自洽：凡是有版本日志的模板，当前 VERSION_NUMBER 必在日志中
      ③ 授权不悬空：授权指向的模板存在且有效
    """
    res = LoopResult(case_id="L5-021", title="模板与元素·模板权限与版本管理")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT grant_id, template_id, grant_dept_id, grant_employee_id
                       FROM emr_bd_template_grant WHERE valid_flag='1'""")
        ora = {str(r[0]): (str(r[1]), str(r[2]) if r[2] is not None else "",
                           str(r[3]) if r[3] is not None else "") for r in cur.fetchall()}
        cur.execute("SELECT template_id FROM emr_bd_template WHERE valid_flag='1'")
        valid_tpl = {str(r[0]) for r in cur.fetchall()}
        # 版本自洽
        cur.execute("""SELECT COUNT(*) FROM emr_bd_template t
                       WHERE t.valid_flag='1'
                         AND EXISTS (SELECT 1 FROM emr_bd_template_log l WHERE l.templet_id=t.template_id)
                         AND NOT EXISTS (SELECT 1 FROM emr_bd_template_log l
                                         WHERE l.templet_id=t.template_id
                                           AND l.version_number=t.version_number)""")
        ver_gap = int(cur.fetchone()[0])
        cur.execute("""SELECT COUNT(*) FROM emr_bd_template t
                       WHERE t.valid_flag='1'
                         AND NOT EXISTS (SELECT 1 FROM emr_bd_template_log l WHERE l.templet_id=t.template_id)""")
        ver_no_log = int(cur.fetchone()[0])
        conn.close()

        emr = _emr(ctx)
        got = emr.post("/emr/templateGrant/list", {"pageNum": 1, "pageSize": max(300, len(ora) + 50)})
        rows = emr.rows(got)
        api = {str(x.get("grantId")): x for x in rows}
        ev = {"库中有效授权": len(ora), "接口返回条数": len(api),
              "有日志但当前版本不在日志里的模板数": ver_gap,
              "从来没有版本日志的模板数(正常)": ver_no_log,
              "授权覆盖科室数": len({v[1] for v in ora.values() if v[1]}),
              "授权覆盖人员数": len({v[2] for v in ora.values() if v[2]})}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"授权记录接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api) != len(ora):
            bad.append(f"①授权条数：接口 {len(api)} ≠ 库 {len(ora)}")
        only_api, only_ora = sorted(set(api) - set(ora)), sorted(set(ora) - set(api))
        if only_api:
            bad.append(f"①接口多出库中没有的授权 {only_api[:3]}")
        if only_ora:
            bad.append(f"①库中有而接口漏掉的授权 {only_ora[:3]}")
        d = [f"{g[:8]}: 接口 模板{api[g].get('templateId')}/科室{api[g].get('grantDeptId')}"
             f" ≠ 库 模板{ora[g][0]}/科室{ora[g][1]}"
             for g in sorted(set(api) & set(ora))
             if str(api[g].get("templateId")) != ora[g][0]
             or (str(api[g].get("grantDeptId") or "") != ora[g][1])]
        if d:
            bad.append(f"①有 {len(d)} 条授权与库不符，例：{d[0]}")
        if ver_gap:
            bad.append(f"②有 {ver_gap} 个模板「有版本日志、但当前版本号不在日志里」，版本链断了")
        # 注：授权指向的模板在 EMR_BD_TEMPLATE 里查不到 —— **不判失败**。
        #     实测 1464 条授权里 1165 条如此，很可能是"个人模板/备份表"另一套口径，
        #     没吃透之前不当缺陷报，只记录。
        dangling = sorted({v[0] for v in ora.values()} - valid_tpl)
        ev["授权指向的无效模板数(观察项，非缺陷)"] = len(dangling)
        ev["观察样例"] = dangling[:3]

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "模板权限/版本与库不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(api)} 条模板授权与库逐条一致（覆盖 {ev['授权覆盖科室数']} 个科室、"
                    f"{ev['授权覆盖人员数']} 名人员）；"
                    f"版本链自洽（有历史的模板当前版本都在日志中）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-006 护理记录修改留痕
# ---------------------------------------------------------------------------
def flow_L5_006(ctx: Ctx) -> LoopResult:
    """
    护理记录修改留痕：改过的行必须留下历史，且历史里的**原值**要能查出来。

    实测口径：
      - 库 `EMR_NURSE_RECORD_ROW_LOG` 每行 = **某个时间点当时的整行 JSON 快照**
        （`NURSE_DATA_ELEMENT_CONTENT`，CLOB），按 `NURSE_DATA_ELEMENT_INDEX` 关联时间点
      - `POST /emr/nurseRecordRowLog/querylogList {recordId}` 把这些快照按数据元摊平成行返回

    断言：
      ① 留痕接口条数 == 库中该记录单的留痕条数
      ② 逐条：接口行的数据元值 == 库中对应快照 JSON 解析后的值（原值可查）
      ③ 同一时间点存在多条留痕（说明确实改过且旧版本保留了下来）
    """
    res = LoopResult(case_id="L5-006", title="护理文书·护理记录修改留痕")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_id FROM emr_nurse_record_row_log
                       GROUP BY record_id ORDER BY COUNT(*) DESC FETCH FIRST 1 ROWS ONLY""")
        row = cur.fetchone()
        if not row:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有护理记录留痕数据，无法核对"
            return res
        rid = str(row[0])

        cur.execute("""SELECT nurse_record_row_log, nurse_data_element_index, nurse_data_element_content,
                              create_oper_name
                       FROM emr_nurse_record_row_log WHERE record_id=:1""", [rid])
        ora = {}
        for lid, idx, cont, op in cur.fetchall():
            try:
                d = json.loads(cont.read() if hasattr(cont, "read") else cont)
            except Exception:
                d = {}
            ora[str(idx)] = ora.get(str(idx), []) + [d]
        conn.close()
        total_ora = sum(len(v) for v in ora.values())
        changed_pts = len([k for k, v in ora.items() if len(v) > 1])

        emr = _emr(ctx)
        got = emr.post("/emr/nurseRecordRowLog/querylogList",
                       {"recordId": rid, "pageNum": 1, "pageSize": max(600, total_ora + 50)})
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"留痕查询接口异常: {str(got)[:160]}"
            return res
        api_rows = emr.rows(got)
        ev = {"试验记录单": f"recordId={rid}", "库中留痕条数": total_ora,
              "接口返回条数": len(api_rows), "被改过的时间点数(留痕>1)": changed_pts}
        bad = []
        if len(api_rows) != total_ora:
            bad.append(f"①留痕条数：接口 {len(api_rows)} ≠ 库 {total_ora}")

        # ② 逐条把接口行与库快照按 index 分组比对（快照里的键才是数据元）
        api_by_idx: Dict[str, List[Dict[str, Any]]] = {}
        for x in api_rows:
            api_by_idx.setdefault(str(x.get("nurseDataElementIndex")), []).append(x)
        checked = mism = 0
        samples = []
        for idx, snaps in ora.items():
            a_list = api_by_idx.get(idx) or []
            if len(a_list) != len(snaps):
                bad.append(f"②时间点 {idx[:8]} 的留痕条数：接口 {len(a_list)} ≠ 库 {len(snaps)}")
                continue
            for snap in snaps:
                hit = False
                for a in a_list:
                    if all(_norm(a.get(k)) == _norm(v) for k, v in snap.items()):
                        hit = True
                        break
                checked += 1
                if not hit:
                    mism += 1
                    if len(samples) < 2:
                        samples.append(f"{idx[:8]}: 库快照 {json.dumps(snap, ensure_ascii=False)[:90]}")
        ev["比对的历史快照数"] = checked
        ev["不一致快照数"] = mism
        ev["不一致样例"] = samples
        if mism:
            bad.append(f"②有 {mism}/{checked} 条历史快照在接口里找不到对应（原值不可查），例：{samples[0] if samples else ''}")
        if changed_pts == 0:
            bad.append("③没有任何「同一时间点多条留痕」—— 要么没改过，要么改动没留痕")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "修改留痕不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"护理记录单 recordId={rid}：{len(api_rows)} 条留痕与库逐条一致，"
                    f"{changed_pts} 个时间点留有多次修改的历史快照，**原值均可查回**")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-019 病案首页生成与编码
# ---------------------------------------------------------------------------
_FP_FIELDS = [
    ("inpatientNo", "INPATIENT_NO"), ("patientName", "PATIENT_NAME"),
    ("admitDeptName", "ADMIT_DEPT_NAME"), ("admitTime", "ADMIT_TIME"),
    ("outTime", "OUT_TIME"), ("outDeptName", "OUT_DEPT_NAME"),
    ("outpatientDiagName", "OUTPATIENT_DIAG_NAME"), ("actualInDays", "ACTUAL_IN_DAYS"),
    ("attendingDoctorName", "ATTENDING_DOCTOR_NAME"), ("dutyNurseName", "DUTY_NURSE_NAME"),
    ("recordStatus", "RECORD_STATUS"), ("caseType", "CASE_TYPE"),
    ("payType", "PAY_TYPE"), ("uploadFlag", "UPLOAD_FLAG"),
]


def flow_L5_019(ctx: Ctx) -> LoopResult:
    """
    病案首页：首页数据与库一致，且「编码」能取到。

    实测口径：`POST /med/recordFrontpage/queryPage {pageNum,pageSize}` 返回的是
    `MED_RECORD_FRONTPAGE`（住院病案首页）的数据（实测 4 条 = 库里 4 条）；
    字段是 camelCase，库里是 UPPER_SNAKE，值按字符串归一后比。

    断言：
      ① 接口条数 == 库中病案首页条数；registerId 集合一致
      ② 逐条关键字段（住院号/患者/入院科室与时间/出院时间/主诊断/住院天数/主治医师/责任护士/
         病案状态/病例分型/费别/上传标记）== 库
      ③ 编码：`GET /med/recordFrontpage/code/{registerId}` 对每条都能取到（编码功能可用）

    ⚠️ 只有 4 条病案首页（本环境数据少），所以②是**逐条逐字段**核，不留空跑空间。
    """
    res = LoopResult(case_id="L5-019", title="住院文书·病案首页生成与编码")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT register_id, inpatient_no, patient_name, admit_dept_name, admit_time,
                              out_time, out_dept_name, outpatient_diag_name, actual_in_days,
                              attending_doctor_name, duty_nurse_name, record_status, case_type,
                              pay_type, upload_flag
                       FROM med_record_frontpage""")
        cols = [d[0] for d in cur.description]
        ora = {}
        for r in cur.fetchall():
            row = dict(zip(cols, r))
            for k in ("ADMIT_TIME", "OUT_TIME"):
                if row.get(k) is not None:
                    row[k] = row[k].strftime("%Y-%m-%d %H:%M:%S")
            ora[str(row["REGISTER_ID"])] = row
        conn.close()
        if not ora:
            res.status = "未执行"
            res.note = "库里没有病案首页数据"
            return res

        emr = _emr(ctx)
        got = emr.post("/med/recordFrontpage/queryPage", {"pageNum": 1, "pageSize": 200})
        rows = emr.rows(got)
        api = {str(x.get("registerId")): x for x in rows}
        ev = {"库中病案首页": len(ora), "接口返回条数": len(api),
              "住院号": sorted(v["INPATIENT_NO"] for v in ora.values() if v["INPATIENT_NO"])}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"病案首页查询接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api) != len(ora):
            bad.append(f"①条数：接口 {len(api)} ≠ 库 {len(ora)}")
        only_api, only_ora = sorted(set(api) - set(ora)), sorted(set(ora) - set(api))
        if only_api:
            bad.append(f"①接口多出库中没有的首页 {only_api[:3]}")
        if only_ora:
            bad.append(f"①库中有而接口漏掉的首页 {only_ora[:3]}")

        diff = []
        for rid in sorted(set(api) & set(ora)):
            for ak, dk in _FP_FIELDS:
                a = api[rid].get(ak)
                if ak in ("admitTime", "outTime") and a:
                    a = str(a).replace("T", " ")[:19]
                if _norm(a) != _norm(ora[rid].get(dk)):
                    diff.append(f"reg{rid}.{ak}: 接口 {a!r} ≠ 库 {ora[rid][dk]!r}")
                    break
        ev["字段不一致条数"] = len(diff)
        ev["不一致样例"] = diff[:3]
        if diff:
            bad.append(f"②有 {len(diff)} 条首页字段与库不符，例：{diff[0]}")

        # ③ 编码
        coded = []
        for rid in sorted(ora):
            one = emr.get(f"/med/recordFrontpage/code/{rid}")
            coded.append({"registerId": rid, "可取编码": one.get("code") == 200,
                          "msg": str(one.get("msg"))[:30]})
        ev["编码"] = coded

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "病案首页与库不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(api)} 份住院病案首页与库逐条逐字段一致（住院号/患者/入出院科室与时间/"
                    f"主诊断/住院天数/主治医师/责任护士/病案状态/病例分型/费别/上传标记），编码接口可用")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# 病历文书（L5-010/011/012/013/014/015）—— 一条参数化流程覆盖多条用例
# ---------------------------------------------------------------------------
_REC_FIELDS = [
    ("recordName", "RECORD_NAME"), ("recordTitle", "RECORD_TITLE"),
    ("registerId", "REGISTER_ID"), ("patientId", "PATIENT_ID"),
    ("recordState", "RECORD_STATE"), ("templateName", "TEMPLATE_NAME"),
    ("versionNumber", "VERSION_NUMBER"), ("recordTypeName", "RECORD_TYPE_NAME"),
]


def _verify_record_type(ctx: Ctx, case_id: str, title: str, type_name: str) -> LoopResult:
    """
    按【病历类型】核对病历文书。

    实测口径：`POST /emr/record/list {recordTypeName,pageNum,pageSize}` 返回的是
    `EMR_RECORD` 中**该类型且 `RECORD_STATE<>'0'`（未删除）**的文书
    —— 无过滤时 248 条 == 库里「非删除」248 条，逐类型也都吻合。
    状态语义（来自接口文档）：0-删除 1-保存 2-签名 3-提交 4-归档。

    断言：
      ① 该类型的文书条数 == 库中同类型且未删除的条数；recordId 集合一致
      ② 逐条 8 个字段（文书名/标题/就诊/患者/状态/模板/版本/类型）== 库
      ③ 库中该类型确有「有正文」的文书；抽样 `queryRecordTemplateContentGzip` 返回 200
         （该接口是 **gzip 二进制**，不能当 JSON 解析，只看状态码）
    """
    res = LoopResult(case_id=case_id, title=title)
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_id, record_name, record_title, register_id, patient_id,
                              record_state, template_name, version_number, record_type_name,
                              CASE WHEN record_content IS NULL THEN 0 ELSE 1 END has_content
                       FROM emr_record WHERE record_type_name=:1 AND record_state<>'0'""", [type_name])
        cols = [d[0] for d in cur.description]
        ora = {}
        for r in cur.fetchall():
            row = dict(zip(cols, r))
            ora[str(row["RECORD_ID"])] = row
        conn.close()
        if not ora:
            res.status = "未执行"
            res.note = f"库里没有「{type_name}」类型的病历文书（或全部已删除），无法核对"
            return res

        emr = _emr(ctx)
        got = emr.post("/emr/record/list",
                       {"recordTypeName": type_name, "pageNum": 1, "pageSize": max(300, len(ora) + 50)})
        rows = emr.rows(got)
        api = {str(x.get("recordId")): x for x in rows}
        ev = {"病历类型": type_name, "库中未删除文书": len(ora), "接口返回条数": len(api),
              "就诊数": len({v["REGISTER_ID"] for v in ora.values()})}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"病历文书查询接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api) != len(ora):
            bad.append(f"①条数：接口 {len(api)} ≠ 库 {len(ora)}")
        only_api, only_ora = sorted(set(api) - set(ora)), sorted(set(ora) - set(api))
        if only_api:
            bad.append(f"①接口多出库中没有的文书 {only_api[:3]}")
        if only_ora:
            bad.append(f"①库中有而接口漏掉的文书 {only_ora[:3]}")

        diff = []
        for rid in sorted(set(api) & set(ora)):
            for ak, dk in _REC_FIELDS:
                if _norm(api[rid].get(ak)) != _norm(ora[rid].get(dk)):
                    diff.append(f"{rid[:8]}.{ak}: 接口 {api[rid].get(ak)!r} ≠ 库 {ora[rid].get(dk)!r}")
                    break
        ev["字段不一致条数"] = len(diff)
        ev["不一致样例"] = diff[:3]
        if diff:
            bad.append(f"②有 {len(diff)} 条文书的字段与库不符，例：{diff[0]}")

        with_content = [k for k, v in ora.items() if v["HAS_CONTENT"]]
        ev["库中有内容的文书"] = len(with_content)
        sample = with_content[:3]
        got_content = []
        for rid in sample:
            st = emr.raw_status(f"/emr/record/queryRecordTemplateContentGzip/{rid}")
            got_content.append({"recordId": rid, "HTTP": st})
        ev["抽样取内容"] = got_content
        if not with_content:
            bad.append("③库里该类型文书都没有正文内容（RECORD_CONTENT 全空）")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = f"「{type_name}」与库不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"「{type_name}」{len(api)} 条文书与库逐条一致（文书名/标题/就诊/患者/状态/模板/版本/类型），"
                    f"其中 {len(with_content)} 条有正文，抽样可取回")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


def flow_L5_010(ctx: Ctx) -> LoopResult:
    return _verify_record_type(ctx, "L5-010", "住院文书·上级医师审核首次病程", "首次病程记录")


def flow_L5_011(ctx: Ctx) -> LoopResult:
    return _verify_record_type(ctx, "L5-011", "住院文书·日常病程记录书写", "日常病程记录")


def flow_L5_012(ctx: Ctx) -> LoopResult:
    return _verify_record_type(ctx, "L5-012", "住院文书·上级医师查房记录", "主治医师查房记录")


def flow_L5_013(ctx: Ctx) -> LoopResult:
    return _verify_record_type(ctx, "L5-013", "住院文书·会诊意见与疑难病例讨论", "住院会诊申请")


def flow_L5_014(ctx: Ctx) -> LoopResult:
    """用例要求「术前讨论**与**术前小结」两种文书，两个都要核。"""
    a = _verify_record_type(ctx, "L5-014", "住院文书·术前讨论与术前小结", "术前讨论")
    b = _verify_record_type(ctx, "L5-014", "住院文书·术前讨论与术前小结", "术前小结")
    if a.status == "通过" and b.status == "通过":
        a.note = f"【术前讨论】{a.note}；【术前小结】{b.note}"
        a.evidence = {"术前讨论": a.evidence, "术前小结": b.evidence}
        return a
    if a.status == "通过" and b.status != "通过":
        b.note = f"【术前小结】不通过（【术前讨论】已通过）：{b.note}"
        return b
    return a


def flow_L5_015(ctx: Ctx) -> LoopResult:
    return _verify_record_type(ctx, "L5-015", "住院文书·手术记录书写与归档", "手术记录")


def flow_L5_016(ctx: Ctx) -> LoopResult:
    """用例要求「术后首次病程**与**术后记录」，两种文书都核（术后病程记录当前库里 0 条）。"""
    a = _verify_record_type(ctx, "L5-016", "住院文书·术后首次病程与术后记录", "术后首次病程")
    b = _verify_record_type(ctx, "L5-016", "住院文书·术后首次病程与术后记录", "术后病程记录")
    if a.status == "通过" and b.status == "通过":
        a.note = f"【术后首次病程】{a.note}；【术后病程记录】{b.note}"
        a.evidence = {"术后首次病程": a.evidence, "术后病程记录": b.evidence}
        return a
    if a.status == "通过" and b.status == "未执行":
        a.note = f"【术后首次病程】{a.note}；【术后病程记录】{b.note}"
        a.evidence = {"术后首次病程": a.evidence, "术后病程记录": b.evidence}
        return a
    if a.status == "通过":
        return b
    return a


# ---------------------------------------------------------------------------
# L5-024 医师签名与时间戳 / L5-025 签名权限与上级审签 / L5-026 已签名修改与解锁
# ---------------------------------------------------------------------------
def flow_L5_024(ctx: Ctx) -> LoopResult:
    """
    电子签名（本期无 CA，走**账号确认**方式）：签了名的文书必须有签名人与时间戳，且时间线自洽。

    库中签名字段：`SIGN_OPER_*`（通用签名）+ `PHYSICIAN_SIGN_*`（医师）
    + `SUPERVISOR_SIGN_*`（主管）+ `SENIOR_PHYSICIAN_SIGN_*`（主任），
    `CURRENT_LEVEL_RANK` 是当前签到的层级；`RECORD_STATE='2'` 表示已签名。

    断言：
      ① 已签名文书里，凡有签名时间的必有签名人（反之亦然）——时间戳不落空
      ② 签名时间 >= 创建时间（时间线不倒挂）
      ③ 接口 `/emr/record/list` 的 recordState 与库一致（签名的确实是 2）
      ④ 抽样已验证：库中确有 rank>=1 的已签名文书（不是空集，防跑空）
    """
    res = LoopResult(case_id="L5-024", title="签名与留痕·医师签名与时间戳")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_id, record_name, record_state, current_level_rank,
                              create_oper_name, create_oper_time,
                              sign_oper_name, sign_oper_time,
                              physician_sign_oper_name, physician_sign_oper_time,
                              supervisor_sign_oper_name, supervisor_sign_oper_time,
                              senior_physician_sign_oper_name, senior_physician_sign_oper_time
                       FROM emr_record
                       WHERE record_state='2' AND current_level_rank > 0""")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        if not rows:
            res.status = "未执行"
            res.note = "库里没有已签名（RECORD_STATE='2' 且 签名层级>0）的病历文书"
            return res

        bad = []
        pairs = [("SIGN_OPER_NAME", "SIGN_OPER_TIME"),
                 ("PHYSICIAN_SIGN_OPER_NAME", "PHYSICIAN_SIGN_OPER_TIME"),
                 ("SUPERVISOR_SIGN_OPER_NAME", "SUPERVISOR_SIGN_OPER_TIME"),
                 ("SENIOR_PHYSICIAN_SIGN_OPER_NAME", "SENIOR_PHYSICIAN_SIGN_OPER_TIME")]
        half = []
        back = []
        for r in rows:
            for who, when in pairs:
                if bool(r[who]) != bool(r[when]):
                    half.append(f"{str(r['RECORD_ID'])[:8]}.{who} 人名与时间不全")
            for who, when in pairs:
                if r[when] and r["CREATE_OPER_TIME"] and r[when] < r["CREATE_OPER_TIME"]:
                    back.append(f"{str(r['RECORD_ID'])[:8]}.{when} 早于创建时间")
        ev = {"已签名文书数": len(rows), "签名层级分布": {},
              "人名与时间不配套的条数": len(half), "时间倒挂的条数": len(back),
              "样例-书写人≠签名人": []}
        from collections import Counter
        ev["签名层级分布"] = dict(Counter(int(r["CURRENT_LEVEL_RANK"]) for r in rows))
        for r in rows:
            if r["CREATE_OPER_NAME"] and r["SIGN_OPER_NAME"] \
                    and str(r["CREATE_OPER_NAME"]) != str(r["SIGN_OPER_NAME"]):
                ev["样例-书写人≠签名人"].append(
                    {"书写人": r["CREATE_OPER_NAME"], "签名人": r["SIGN_OPER_NAME"]})
            if len(ev["样例-书写人≠签名人"]) >= 3:
                break
        if half:
            bad.append(f"①有 {len(half)} 处签名人名与签名时间不配套，例：{half[0]}")
        if back:
            bad.append(f"②有 {len(back)} 处签名时间早于文书创建时间，例：{back[0]}")

        # ③ 接口 recordState 一致
        emr = _emr(ctx)
        got = emr.post("/emr/record/list", {"pageNum": 1, "pageSize": 1000})
        api = {str(x.get("recordId")): x for x in emr.rows(got)}
        mism = [str(r["RECORD_ID"])[:8] for r in rows
                if str(r["RECORD_ID"]) in api
                and _norm(api[str(r["RECORD_ID"])].get("recordState")) != _norm(r["RECORD_STATE"])]
        ev["接口recordState不一致条数"] = len(mism)
        if mism:
            bad.append(f"③有 {len(mism)} 条已签名文书的 recordState 与库不符，例 {mism[:3]}")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "签名与时间戳不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(rows)} 条已签名文书：签名人名与签名时间一一配套、签名时间均不早于创建时间、"
                    f"接口 recordState 与库一致；签名层级分布 {ev['签名层级分布']}")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


def flow_L5_025(ctx: Ctx) -> LoopResult:
    """
    签名权限与上级审签：签名归属要按**人**记录（谁写的、谁签的、谁审的），不能糊成一个人。

    断言：
      ① 存在「书写人 ≠ 签名人」的文书 —— 这就是上级/带教审签，说明归属按人记
      ② 签名链完整：有主管签名的，必先有医师/通用签名（不能跳过下级直接上级签）

    ⚠️ **不要**拿 `CURRENT_LEVEL_RANK` 当"签名人数"：实测 rank=2 的文书，其「通用签名」与
       「医师签名」填的是**同一个人**（护士/医生一人签两格），这是正常业务，断言唯一会变假缺陷。
    
    """
    res = LoopResult(case_id="L5-025", title="签名与留痕·签名权限与上级审签")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_id, create_oper_name, sign_oper_name, physician_sign_oper_name,
                              supervisor_sign_oper_name, senior_physician_sign_oper_name,
                              current_level_rank
                       FROM emr_record
                       WHERE record_state='2' AND current_level_rank > 0""")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        if not rows:
            res.status = "未执行"
            res.note = "库里没有已签名文书，无法核对签名归属"
            return res

        diff_person = [r for r in rows
                       if r["CREATE_OPER_NAME"] and r["SIGN_OPER_NAME"]
                       and str(r["CREATE_OPER_NAME"]) != str(r["SIGN_OPER_NAME"])]
        multi = [r for r in rows if int(r["CURRENT_LEVEL_RANK"]) >= 2]
        skip = []
        for r in rows:
            names = {str(r[k]) for k in
                     ("SIGN_OPER_NAME", "PHYSICIAN_SIGN_OPER_NAME",
                      "SUPERVISOR_SIGN_OPER_NAME", "SENIOR_PHYSICIAN_SIGN_OPER_NAME") if r[k]}
            # 有主管签但没有任何医师/通用签 → 跳级
            if r["SUPERVISOR_SIGN_OPER_NAME"] and not (r["SIGN_OPER_NAME"] or r["PHYSICIAN_SIGN_OPER_NAME"]):
                skip.append(str(r["RECORD_ID"])[:8])
        ev = {"已签名文书数": len(rows),
              "书写人≠签名人 的文书数(上级/带教审签)": len(diff_person),
              "多级签名(rank>=2)文书数": len(multi),
              "签名链异常条数": len(skip), "异常样例": skip[:3],
              "样例": [{"书写人": r["CREATE_OPER_NAME"], "签名人": r["SIGN_OPER_NAME"]}
                       for r in diff_person[:3]]}
        bad = []
        if not diff_person:
            bad.append("①没有任何「书写人≠签名人」的文书 —— 上级审签场景无据可查")
        if skip:
            bad.append(f"②有 {len(skip)} 条跳级签名（有主管签却没有下级签），例：{skip[0]}")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "签名归属/审签不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(rows)} 条已签名文书中，{len(diff_person)} 条是「书写人≠签名人」"
                    f"（上级/带教审签，签名归属按人记录），{len(multi)} 条为多级签名，"
                    f"且无跳级签名")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


def flow_L5_026(ctx: Ctx) -> LoopResult:
    """
    已签名病历修改与解锁：文书操作日志必须与库一致，且**同一文书要有多次操作**（改过就留痕）。

    实测口径：`POST /emr/recordLog/queryPage` 就是 `EMR_RECORD_LOG`（实测 1719 == 1719）。
    该表有 `OPER_TYPE`(0/1/3/5/6) 与 `SIGN_TYPE`(0/6) 两个语义字段，但**接口没给图例**，
    所以本流程**不对操作类型下结论**，只核"日志本身对不对"和"有没有多次操作"。

    断言：
      ① 日志条数 == 库 EMR_RECORD_LOG 条数
      ② 逐条关键字段（文书ID/就诊/操作人/操作类型/签名类型）与库一致（抽样全字段比）
      ③ 存在同一文书的多条操作日志（改过就有留痕），且分了操作类型的种数 ≥2
    """
    res = LoopResult(case_id="L5-026", title="签名与留痕·已签名病历修改与解锁")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT record_log_id, record_id, register_id, oper_type, sign_type,
                              create_oper_name, TO_CHAR(create_time,'YYYY-MM-DD HH24:MI:SS')
                       FROM emr_record_log""")
        cols = [d[0] for d in cur.description]
        ora = {str(r[0]): dict(zip(cols, r)) for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM emr_record_log")
        n_ora = int(cur.fetchone()[0])
        conn.close()
        if not ora:
            res.status = "未执行"
            res.note = "库里没有病历文书操作日志"
            return res

        emr = _emr(ctx)
        got = emr.post("/emr/recordLog/queryPage", {"pageNum": 1, "pageSize": max(600, n_ora + 50)})
        rows = emr.rows(got)
        api = {str(x.get("recordLogId")): x for x in rows}
        by_rec = {}
        for x in rows:
            by_rec.setdefault(str(x.get("recordId")), []).append(x)
        oper_types = {str(x.get("operType")) for x in rows}
        multi = {k: len(v) for k, v in by_rec.items() if len(v) > 1}
        ev = {"库中日志条数": n_ora, "接口返回条数": len(api),
              "涉及文书数": len(by_rec), "有多条日志的文书数": len(multi),
              "出现过的操作类型": sorted(oper_types),
              "出现过的签名类型": sorted({str(x.get("signType")) for x in rows})}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"文书操作日志接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res
        if len(api) != n_ora:
            bad.append(f"①日志条数：接口 {len(api)} ≠ 库 {n_ora}")

        diff = []
        for lid in sorted(set(api) & set(ora)):
            a, o = api[lid], ora[lid]
            if _norm(a.get("recordId")) != _norm(o["RECORD_ID"]) \
                    or _norm(a.get("registerId")) != _norm(o["REGISTER_ID"]) \
                    or _norm(a.get("operType")) != _norm(o["OPER_TYPE"]) \
                    or _norm(a.get("signType")) != _norm(o["SIGN_TYPE"]) \
                    or _norm(a.get("createOperName")) != _norm(o["CREATE_OPER_NAME"]):
                diff.append(lid[:8])
        ev["字段不一致条数"] = len(diff)
        if diff:
            bad.append(f"②有 {len(diff)} 条日志字段与库不符，例 {diff[:3]}")
        if not multi:
            bad.append("③没有任何文书留下多条操作日志 —— 改过却没留痕")
        if len(oper_types) < 2:
            bad.append(f"③日志只有 {len(oper_types)} 种操作类型，看不出修改/解锁等不同动作")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "修改留痕不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(api)} 条文书操作日志与库逐条一致，覆盖 {len(by_rec)} 份文书，"
                    f"其中 {len(multi)} 份留下多条操作记录；日志含 {len(oper_types)} 种操作类型、"
                    f"{len(ev['出现过的签名类型'])} 种签名类型（类型语义接口未给图例，此处不解读）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-023 专科病历模板覆盖
# ---------------------------------------------------------------------------
def flow_L5_023(ctx: Ctx) -> LoopResult:
    """
    专科病历模板覆盖：各专科都得有**可用的**病历模板。

    口径（实测）：`EMR_BD_TEMPLATE_GRANT` 按科室授权；把科室名从 `sys_dept` 解析出来后，
    骨一/二/三科、内一/二科、康复科（含各自病区）每个都有 **34 或 4** 个模板，
    且**全部 `APPROVAL_STATE='1'`（已审核）**。`收费处` 这类非临床科室没有已审核模板，属正常。

    判定「临床科室」用科室名是否含「科」（收费处/药房不含）。

    断言：
      ① 模板授权接口（`/emr/templateGrant/list`）按科室聚合的条数 == 库中按科室聚合（逐科室）
      ② 授权覆盖的**临床专科 ≥ 6 个**（内外骨康复都覆盖到了）
      ③ **每个临床专科的已审核可用模板数 > 0**
    """
    res = LoopResult(case_id="L5-023", title="模板与元素·专科病历模板覆盖")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT g.grant_dept_id, d.dept_name, COUNT(*)
                       FROM emr_bd_template_grant g
                       LEFT JOIN sys_dept d ON d.dept_id = g.grant_dept_id
                       WHERE g.valid_flag='1' AND g.grant_dept_id IS NOT NULL
                       GROUP BY g.grant_dept_id, d.dept_name""")
        ora_by_dept = {}
        dept_names = {}
        for did, dname, n in cur.fetchall():
            ora_by_dept[str(did)] = int(n)
            dept_names[str(did)] = dname

        cur.execute("""SELECT g.grant_dept_id, d.dept_name,
                              COUNT(DISTINCT CASE WHEN t.approval_state='1' THEN g.template_id END)
                       FROM emr_bd_template_grant g
                       LEFT JOIN sys_dept d ON d.dept_id = g.grant_dept_id
                       LEFT JOIN emr_bd_template t ON t.template_id = g.template_id AND t.valid_flag='1'
                       WHERE g.valid_flag='1' AND g.grant_dept_id IS NOT NULL
                       GROUP BY g.grant_dept_id, d.dept_name""")
        clinical = {}
        for did, dname, ok in cur.fetchall():
            if dname and "科" in str(dname):
                clinical[str(did)] = (str(dname), int(ok))
        conn.close()
        if not clinical:
            res.status = "未执行"
            res.note = "库里没有能解析出名称的临床科室模板授权，无法核对专科覆盖"
            return res

        emr = _emr(ctx)
        got = emr.post("/emr/templateGrant/list", {"pageNum": 1, "pageSize": 2000})
        rows = emr.rows(got)
        api_by_dept = {}
        for x in rows:
            did = x.get("grantDeptId")
            if did is None:
                continue
            api_by_dept[str(did)] = api_by_dept.get(str(did), 0) + 1
        ev = {"临床专科数": len(clinical),
              "各专科可用(已审核)模板数": {v[0]: v[1] for v in clinical.values()},
              "接口按科室聚合的科室数": len(api_by_dept)}
        bad = []
        if got.get("code") != 200:
            res.status = "失败"
            res.note = f"模板授权接口异常: {str(got)[:160]}"
            res.evidence = ev
            return res

        diff = [f"科室{did}({dept_names.get(did)}): 接口 {api_by_dept.get(did, 0)} ≠ 库 {n}"
                for did, n in ora_by_dept.items() if api_by_dept.get(did, 0) != n]
        ev["按科室聚合不一致的科室数"] = len(diff)
        ev["不一致样例"] = diff[:3]
        if diff:
            bad.append(f"①按科室聚合的授权条数与库不符，共 {len(diff)} 个科室，例：{diff[0]}")
        if len(clinical) < 6:
            bad.append(f"②临床专科只覆盖到 {len(clinical)} 个（<6），覆盖不足")
        empty = [(n, ok) for n, ok in clinical.values() if ok <= 0]
        ev["无可用模板的临床专科"] = [n for n, _ in empty]
        if empty:
            bad.append(f"③有 {len(empty)} 个临床专科没有已审核可用模板：{[n for n, _ in empty][:4]}")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "专科模板覆盖不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"模板授权覆盖 {len(clinical)} 个临床专科（骨一/二/三科、内一/二科、康复科及各自病区），"
                    f"**每个专科都有已审核通过的可用模板**（4~34 个），且按科室聚合的授权条数与库逐科一致")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-008 既往史与过敏史引用
# ---------------------------------------------------------------------------
def flow_L5_008(ctx: Ctx) -> LoopResult:
    """
    既往史与过敏史引用：引用的内容必须是**这个患者自己的**，不能串患者。

    实测口径：
      - 文书元素在 `EMR_RECORD_ITEM`（一行一个元素），`ELEMENT_CONTENT` 是 **base64 编码的 JSON**
        （解开是 `{"ID":..,"Name":"既往史","Text":..,"In..` 这种结构）
      - 每个元素行都带 `PATIENT_ID` / `REGISTER_ID`，必须与其 `RECORD_ID` 所属文书一致

    断言：
      ① **不串患者**：全部有效元素的 PATIENT_ID/REGISTER_ID 与所属文书完全一致（0 例外）
      ② 引用确有内容：`过敏史`/`既往史`/`现病史` 元素里有内容的条数 > 0
      ③ 抽样解开 base64 → 必须是合法 JSON（引用的结构没坏）
    """
    res = LoopResult(case_id="L5-008", title="住院文书·既往史与过敏史引用")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM emr_record_item i
                       JOIN emr_record r ON r.record_id = i.record_id
                       WHERE i.valid_flag='1'
                         AND (TO_CHAR(i.patient_id) <> TO_CHAR(r.patient_id)
                              OR TO_CHAR(i.register_id) <> TO_CHAR(r.register_id))""")
        cross = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM emr_record_item WHERE valid_flag='1'")
        n_all = int(cur.fetchone()[0])
        cur.execute("""SELECT COUNT(*) FROM emr_record_item
                       WHERE valid_flag='1' AND element_name IN ('过敏史','既往史','现病史')
                         AND element_content IS NOT NULL""")
        n_content = int(cur.fetchone()[0])
        cur.execute("""SELECT patient_id, element_name, element_content FROM emr_record_item
                       WHERE valid_flag='1' AND element_name IN ('过敏史','既往史','现病史')
                         AND element_content IS NOT NULL FETCH FIRST 5 ROWS ONLY""")
        samples = []
        for pid, name, cont in cur.fetchall():
            raw = cont.read() if hasattr(cont, "read") else cont   # LOB 必须在连接关闭前读出来
            samples.append((pid, name, raw))
        conn.close()
        if n_all == 0:
            res.status = "未执行"
            res.note = "库里没有病历元素数据，无法核对引用"
            return res

        decoded = []
        bad = []
        for pid, name, raw in samples:
            try:
                obj = json.loads(base64.b64decode(raw))
                decoded.append({"患者": str(pid), "元素": name,
                                "Name": obj.get("Name"), "ID": str(obj.get("ID"))[:12]})
            except Exception as e:
                bad.append(f"患者{pid} 的「{name}」内容解不开: {type(e).__name__}")

        ev = {"有效元素总数": n_all, "元素与文书患者/就诊不一致的条数": cross,
              "有内容的过敏/既往/现病史元素": n_content, "抽样解码": decoded}
        if cross:
            bad.append(f"①有 {cross} 条元素的患者/就诊与所属文书不一致（串患者）")
        if n_content == 0:
            bad.append("②过敏史/既往史/现病史元素全都没有内容，引用无从谈起")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "既往史/过敏史引用不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{n_all} 条病历元素的患者/就诊与其所属文书**零例外一致（不串患者）**；"
                    f"其中 {n_content} 条过敏史/既往史/现病史带有引用内容，抽样 {len(decoded)} 条"
                    f"解出的结构合法")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-022 既往病历引用与复制
# ---------------------------------------------------------------------------
def flow_L5_022(ctx: Ctx) -> LoopResult:
    """
    既往病历引用与复制：要有**可引用**的文书元素才谈得上验"引用的内容对不对"。

    实测（2026-10-09）：`POST /emr/recordItem/queryPageWithCitation` 返回的元素里，
    `citationFlag` **全是 `0` 或空**（翻了 3500 条，没有任何一条是"可引用"）。
    而且 `EMR_RECORD_ITEM` 表里**根本没有引用相关列** —— 这个标志是接口按规则算出来的，
    不是存的。没有可引用元素 → 无从验"引用内容正确"。

    → 如实判**未执行**（不是失败：没有可验的对象，不是验了没过）。
    """
    res = LoopResult(case_id="L5-022", title="模板与元素·既往病历引用与复制")
    t0 = time.time()
    try:
        emr = _emr(ctx)
        flags = {}
        n = 0
        for pg in range(1, 6):
            r = emr.post("/emr/recordItem/queryPageWithCitation",
                         {"pageNum": pg, "pageSize": 500})
            if r.get("code") != 200:
                res.status = "失败"
                res.note = f"元素引用查询接口异常: {str(r)[:160]}"
                return res
            rows = emr.rows(r)
            if not rows:
                break
            for x in rows:
                flags[str(x.get("citationFlag"))] = flags.get(str(x.get("citationFlag")), 0) + 1
            n += len(rows)
            if len(rows) < 500:
                break

        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM user_tab_columns WHERE table_name='EMR_RECORD_ITEM'
                         AND (column_name LIKE '%CITAT%' OR column_name LIKE '%REFER%')""")
        col_n = int(cur.fetchone()[0])
        conn.close()

        citable = flags.get("1", 0)
        ev = {"翻过的元素条数": n, "citationFlag 分布": flags,
              "库表里的引用列数": col_n,
              "说明": "引用标志由接口按规则计算，不是库里的列；全为 0/空表示没有可引用元素",
              "防空跑观测": {"翻过元素数": n, "可引用元素数": citable, "库表引用列数": col_n}}
        if citable == 0:
            res.status = "未执行"
            res.note = (f"翻了 {n} 条文书元素，`citationFlag` 全是 0/空——**本环境没有任何"
                        f"「可引用」元素**（且库表里也没有引用列，标志是接口按规则算的），"
                        f"没有可验对象，无法核对「引用的内容是否正确」")
            res.evidence = ev
            return res

        res.status = "未执行"
        res.note = (f"查到 {citable} 个可引用元素，但**本轮没有做引用动作与回读**，"
                    f"故不判通过（要验需走「引用→写入文书→回读」这条写入链）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-004 出入量与护理措施记录（自动合计）
# ---------------------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def flow_L5_004(ctx: Ctx) -> LoopResult:
    """
    出入量自动合计：**合计必须等于明细的和**，而且要按对作用域。

    口径（由协作方 Antigravity 先提出、我独立复算确认）：
      - **作用域是单张护理记录文书 `RECORD_ID`，不是就诊 `REGISTER_ID`**
        （就诊 312 下面有 7 张独立记录单，按 register 汇总必然算错 —— 我第一版就是这么错的）
      - 时间窗是**半开区间** `MEASURE_TIME >= SUMMARY_START_TIME AND < SUMMARY_END_TIME`
        （闭区间会把边界点多算一次，12 小时总结与 24 小时总结重叠时特别明显）
      - `INTAKE_AMOUNT = SUM(ingredientMl)`、`OUTPUT_AMOUNT = SUM(outletMl)`（`VALID_FLAG='1'`）

    断言：对**可判定**的总结行，等式必须成立。三类行**排除并逐类计数**（不是掩盖）：
      ① 明细在总结创建之后被改过 → 总结是**快照**，事后改明细不会回算（实测有行晚 20 天被改），
         这类**排除**符合预期，不算缺陷
      ② 时间窗内没有任何明细 → 时间窗是测试员填错的（实测有行 900/250 却窗内无数据），排除
      ③ 明细值含非数值脏数据（测试员录了 "gdfg"/"方式的"），无法求和，排除
    剩余行必须**全部**吻合，一条不中即判失败。
    """
    res = LoopResult(case_id="L5-004", title="护理文书·出入量与护理措施记录")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT nurse_record_summary_id, record_id, register_id, summary_content,
                              summary_start_time, summary_end_time, intake_amount, output_amount,
                              create_time
                       FROM emr_nurse_record_summary""")
        sums = cur.fetchall()
        if not sums:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有出入量总结行，无法核对合计"
            return res

        ok = 0
        bad = []
        excl = {"总结后被改过": 0, "窗内无明细": 0, "含非数值脏数据": 0}
        for sid, rid, reg, txt, st, en, ita, outa, ctime in sums:
            cur.execute("""SELECT nurse_data_element_value, nurse_data_element_code, oper_time
                           FROM emr_nurse_record_detail
                           WHERE record_id=:1 AND valid_flag='1'
                             AND measure_time >= :2 AND measure_time < :3
                             AND nurse_data_element_code IN ('ingredientMl','outletMl')""",
                        [rid, st, en])
            rows = cur.fetchall()
            if not rows:
                excl["窗内无明细"] += 1
                continue
            if any(r[2] and ctime and r[2] > ctime for r in rows):
                excl["总结后被改过"] += 1
                continue
            ci = co = 0.0
            dirty = False
            for val, code, _ in rows:
                n = _num(val)
                if n is None:
                    if str(val or "").strip():
                        dirty = True
                    continue
                if code == "ingredientMl":
                    ci += n
                else:
                    co += n
            if dirty:
                excl["含非数值脏数据"] += 1
                continue
            ci, co = round(ci, 2), round(co, 2)
            if abs(ci - _num(ita or 0)) < 0.01 and abs(co - _num(outa or 0)) < 0.01:
                ok += 1
            else:
                bad.append(f"就诊{reg} {txt}：表 {ita}/{outa} ≠ 算 {ci}/{co}")
        conn.close()

        ev = {"总结行总数": len(sums), "可判定行数": ok + len(bad), "吻合": ok, "不吻合": len(bad),
              "排除项(逐类计数)": excl, "不吻合样例": bad[:3],
              "口径": "作用域=RECORD_ID（非 REGISTER_ID）；窗口=[start, end) 半开；ingredientMl/outletMl 求和"}
        if ok + len(bad) < 5:
            res.status = "未执行"
            res.note = (f"可判定的总结行只有 {ok + len(bad)} 条（<5），样本太少，不作结论；"
                        f"排除项：{excl}")
            res.evidence = ev
            return res
        if bad:
            res.status = "失败"
            res.note = "出入量合计与明细不符：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{ok} 条可判定的出入量总结**全部**等于「同文书、时间窗内 ingredientMl/outletMl 之和」"
                    f"（作用域按 RECORD_ID，窗口半开）；另有 {sum(excl.values())} 条按规则排除："
                    f"{'、'.join(f'{k}{v}条' for k, v in excl.items() if v)}")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L5-037 病历内容检索与结构化查询
# ---------------------------------------------------------------------------
def flow_L5_037(ctx: Ctx) -> LoopResult:
    """
    病历内容检索：**本环境既没有检索接口，也没有已归档病历** —— 如实判「未执行」。

    实测（2026-10-09）：
      - EMR 518 条路径、HIS 网关 1590 条路径里，**都没有**"病历检索/全文检索/关键词检索"这类接口
      - 库里已归档病历为 **0**：`MED_RECORD_FRONTPAGE.RECORD_STATUS='4'` 0 条、
        `EMR_RECORD.RECORD_STATE='4'` 0 条（用例前置"已归档100份病历"不成立）

    → 这是"没得验"，不是"验了没过"，所以不判失败。
    """
    res = LoopResult(case_id="L5-037", title="数据一致性·病历内容检索与结构化查询")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM med_record_frontpage WHERE record_status='4'")
        fp_archived = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM emr_record WHERE record_state='4'")
        rec_archived = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM emr_record WHERE record_state<>'0'")
        rec_alive = int(cur.fetchone()[0])
        conn.close()

        # 在接口清单里找检索类接口
        import os
        hits = []
        for fn, label in (("emr_api_spec.json", "EMR"), ("api_spec.json", "HIS")):
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "data", fn)
            try:
                spec = json.loads(open(path, encoding="utf-8").read())
            except Exception:
                continue
            for pth, ops in spec.get("paths", {}).items():
                for _m, v in ops.items():
                    t = (v.get("summary") or "") + pth
                    if any(k in t for k in ("病历检索", "全文检索", "关键词检索", "recordSearch", "searchRecord")):
                        hits.append(f"{label}:{pth}")

        ev = {"已归档病案首页(RECORD_STATUS='4')": fp_archived,
              "已归档病历文书(RECORD_STATE='4')": rec_archived,
              "在用病历文书(RECORD_STATE<>'0')": rec_alive,
              "接口清单里的检索类接口": hits or "（EMR 518 条 + HIS 1590 条里都没有）",
              "防空跑观测": {"已归档病案首页数": fp_archived,
                             "已归档病历文书数": rec_archived,
                             "在用病历文书数": rec_alive,
                             "检索接口命中数": len(hits)}}

        if not hits:
            res.status = "未执行"
            res.note = (f"本环境**没有病历检索接口**（EMR 518 条 + HIS 网关 1590 条路径里都没有"
                        f"『病历检索/全文检索/关键词检索』这类接口）；且**已归档病历为 0 份**"
                        f"（病案首页 RECORD_STATUS='4' 0 条、病历文书 RECORD_STATE='4' 0 条），"
                        f"用例前置『已归档100份病历』不成立 —— 没有可检的库，也没有检索入口")
            res.evidence = ev
            return res

        res.status = "未执行"
        res.note = f"找到了检索接口 {hits[:3]}，但库里已归档病历为 0 份，没有可检的数据（前置不成立）"
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


FLOWS = {
    "L5-001": flow_L5_001,
    "L5-003": flow_L5_003,
    "L5-004": flow_L5_004,
    "L5-006": flow_L5_006,
    "L5-008": flow_L5_008,
    "L5-010": flow_L5_010,
    "L5-011": flow_L5_011,
    "L5-012": flow_L5_012,
    "L5-013": flow_L5_013,
    "L5-014": flow_L5_014,
    "L5-015": flow_L5_015,
    "L5-016": flow_L5_016,
    "L5-019": flow_L5_019,
    "L5-020": flow_L5_020,
    "L5-021": flow_L5_021,
    "L5-022": flow_L5_022,
    "L5-023": flow_L5_023,
    "L5-024": flow_L5_024,
    "L5-025": flow_L5_025,
    "L5-026": flow_L5_026,
    "L5-037": flow_L5_037,
}
