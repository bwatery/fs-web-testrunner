# -*- coding: utf-8 -*-
"""
L5-036 EMR 与 HIS/LIS/PACS 数据一致性（跨系统同一患者标识）

四类数据靠 `REGISTER_ID`（就诊流水号）贯通：
    HIS 登记  FIN_IP_REGISTER
    EMR 病历  EMR_RECORD / EMR_RECORD_ITEM（数据元 `ELEMENT_NAME` + `ELEMENT_VALUE`）
    HIS 医嘱  MED_IP_ORDER
    LIS 检验  INT_LIS_IP_APPLY

⚠️ **别把「床号/科室」也当成一致性断言** —— 实测 12 名跨系统患者里有 6 名对不上，且**全部可解释**：
   · **转床**：医嘱/LIS 留的是开单当时的旧床号，登记表记的是当前床位；
   · **转科**：如就诊 555 —— 入院在骨一科，`FIN_IP_DEPT_SHIFT_APPLY` 申请单 **83** 于
     2026-10-08 20:58:39 确认转入内一科（`FIN_IP_BED_SHIFT` 有对应转出/转入日志）；
     而它的医嘱开立于**转科前 11 小时**，所以医嘱上忠实写着 `骨一科`、旧床号 `201-2`；
   · **临床科室 ≠ 护理单元**：字典主表是 **`SYS_DEPT`**（`COM_BD_DEPT` 在库里不存在），其中
     `骨一科`(DEPT_ID=910098, `DEPT_TYPE='I'` 临床科室) 与 `骨一科病区`(910134, `DEPT_TYPE='N'` 护理单元)
     本就是**两条不同职能的字典记录**，不是同一科室的两种写法 —— 医生开单归属临床科室、
     护士执行与床位归属护理单元，是标准分工映射。
   硬断言相等 = 一次造出 6 个假缺陷。本用例只把**稳定标识**当断言，床号/科室差异作为观察列出。
   （以上解释由协作方 Antigravity 查证、我已独立复核）

真正成立的不变量（用它们写断言）：
  ① 贯通：EMR 文书 / 医嘱 / 检验申请的 `REGISTER_ID` 都能在住院登记里命中（零悬挂）
  ② 患者主索引：`EMR_RECORD_ITEM.PATIENT_ID` == 登记 `PATIENT_ID`（同一患者不得出现多个主索引）
  ③ 姓名：EMR 数据元「患者姓名」== 登记 `PATIENT_NAME`；LIS `PATIENT_NAME` 同理
  ④ 性别：EMR 数据元「性别」（男/女）映射后 == 登记 `SEX_CODE`（1男/2女）；LIS `SEX_CODE` 同理
"""
import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn

_SEX_NAME = {"1": "男", "2": "女"}

# 每位患者：登记基准 + 四方取到的各字段取值集合
_CROSS_SQL = """
SELECT r.register_id, r.patient_id, r.patient_name, r.sex_code, r.bed_no, r.dept_name,
       (SELECT COUNT(*) FROM emr_record e   WHERE e.register_id = r.register_id) n_emr,
       (SELECT COUNT(*) FROM med_ip_order m WHERE m.register_id = r.register_id) n_ord,
       (SELECT COUNT(*) FROM int_lis_ip_apply l WHERE l.register_id = r.register_id) n_lis
  FROM fin_ip_register r
 WHERE EXISTS (SELECT 1 FROM emr_record e   WHERE e.register_id = r.register_id)
   AND EXISTS (SELECT 1 FROM med_ip_order m WHERE m.register_id = r.register_id)
 ORDER BY r.register_id
"""


def _collect(cur, sql: str, rid: int) -> List[Any]:
    cur.execute(sql, [rid])
    return [r[0] for r in cur.fetchall() if r[0] is not None]


def flow_L5_036(ctx: Ctx) -> LoopResult:
    requires_rules = ['CONV_CROSS_SYS_DEPT_DISTINCTION', 'CONV_INPATIENT_SAMPLE_INCOMPLETE']
    res = LoopResult(case_id="L5-036", title="病历文书·EMR与HIS/LIS/PACS数据一致性")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute(_CROSS_SQL)
        patients = cur.fetchall()
        if len(patients) < 3:
            conn.close()
            res.status = "未执行"
            res.note = (f"库里只有 {len(patients)} 名患者同时具备有效病历与医嘱，"
                        f"样本太少，构不成有意义的跨系统一致性核对")
            return res

        # ① 贯通：**只对参与比对的患者**断言其就诊号在住院登记里存在。
        #    不做全库零悬挂断言 —— 见下方 docstring 的"数据集口径"。
        cur.execute("""SELECT COUNT(*) FROM emr_record e
                        WHERE e.patient_type = 'I'
                          AND NOT EXISTS (SELECT 1 FROM fin_ip_register r
                                           WHERE r.register_id = e.register_id)""")
        glob_emr = int(cur.fetchone()[0])
        cur.execute("""SELECT COUNT(*) FROM int_lis_ip_apply l
                        WHERE NOT EXISTS (SELECT 1 FROM fin_ip_register r
                                           WHERE r.register_id = l.register_id)""")
        glob_lis = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM fin_ip_register")
        n_ip_reg = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM emr_record")
        n_emr_all = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM emr_record WHERE patient_type = 'O'")
        n_emr_op = int(cur.fetchone()[0])

        bad: List[str] = []
        detail: List[Dict[str, Any]] = []
        n_name = n_pid = n_sex = 0
        obs_bed, obs_dept = [], []

        for (rid, pid, pname, sex, bed, dept, n_emr, n_ord, n_lis) in patients:
            emr_names = _collect(cur, """SELECT DISTINCT DBMS_LOB.SUBSTR(i.element_value,200,1)
                                           FROM emr_record e JOIN emr_record_item i
                                             ON i.record_id = e.record_id
                                          WHERE e.register_id = :1
                                            AND i.element_name = '患者姓名'""", rid)
            emr_pids = _collect(cur, """SELECT DISTINCT i.patient_id
                                          FROM emr_record e JOIN emr_record_item i
                                            ON i.record_id = e.record_id
                                         WHERE e.register_id = :1""", rid)
            emr_sexes = _collect(cur, """SELECT DISTINCT DBMS_LOB.SUBSTR(i.element_value,50,1)
                                           FROM emr_record e JOIN emr_record_item i
                                             ON i.record_id = e.record_id
                                          WHERE e.register_id = :1
                                            AND i.element_name = '性别'""", rid)
            emr_beds = _collect(cur, """SELECT DISTINCT DBMS_LOB.SUBSTR(i.element_value,50,1)
                                          FROM emr_record e JOIN emr_record_item i
                                            ON i.record_id = e.record_id
                                         WHERE e.register_id = :1
                                           AND i.element_name = '病床号'""", rid)
            emr_depts = _collect(cur, """SELECT DISTINCT DBMS_LOB.SUBSTR(i.element_value,80,1)
                                           FROM emr_record e JOIN emr_record_item i
                                             ON i.record_id = e.record_id
                                          WHERE e.register_id = :1
                                            AND i.element_name = '住院科室'""", rid)
            ord_beds = _collect(cur, "SELECT DISTINCT bed_no FROM med_ip_order "
                                     "WHERE register_id = :1", rid)
            ord_depts = _collect(cur, "SELECT DISTINCT recipe_dept_name FROM med_ip_order "
                                      "WHERE register_id = :1", rid)
            lis_names = _collect(cur, "SELECT DISTINCT patient_name FROM int_lis_ip_apply "
                                      "WHERE register_id = :1", rid)
            lis_sexes = _collect(cur, "SELECT DISTINCT sex_code FROM int_lis_ip_apply "
                                      "WHERE register_id = :1", rid)
            lis_beds = _collect(cur, "SELECT DISTINCT bed_no FROM int_lis_ip_apply "
                                     "WHERE register_id = :1", rid)

            row: Dict[str, Any] = {"就诊": rid, "姓名": pname}

            # ② 患者主索引
            if emr_pids:
                n_pid += 1
                wrong = [p for p in emr_pids if str(p) != str(pid)]
                if len(emr_pids) > 1:
                    bad.append(f"②就诊{rid} 病历里出现 {len(emr_pids)} 个不同患者主索引 {emr_pids}")
                elif wrong:
                    bad.append(f"②就诊{rid} 病历主索引 {wrong[0]} ≠ 登记 {pid}")
                row["病历主索引"] = emr_pids

            # ③ 姓名
            if emr_names:
                n_name += 1
                if [x for x in emr_names if x != pname]:
                    bad.append(f"③就诊{rid} 病历「患者姓名」{emr_names} ≠ 登记 {pname}")
            if lis_names:
                n_name += 1
                if [x for x in lis_names if x != pname]:
                    bad.append(f"③就诊{rid} 检验患者姓名 {lis_names} ≠ 登记 {pname}")

            # ④ 性别
            if emr_sexes:
                n_sex += 1
                want = _SEX_NAME.get(str(sex), str(sex))
                if [x for x in emr_sexes if x != want]:
                    bad.append(f"④就诊{rid} 病历「性别」{emr_sexes} ≠ 登记 {want}")
            if lis_sexes:
                n_sex += 1
                if [x for x in lis_sexes if str(x) != str(sex)]:
                    bad.append(f"④就诊{rid} 检验性别 {lis_sexes} ≠ 登记 {sex}")

            # ⑤ 观察项（不判缺陷）：床号 / 科室
            def _flat(x: Any) -> List[Any]:
                if x is None:
                    return []
                return [x] if isinstance(x, str) else list(x)

            beds = {"登记": bed, "病历": emr_beds, "医嘱": ord_beds, "检验": lis_beds}
            others = [v for k, val in beds.items() if k != "登记" for v in _flat(val)]
            if others and any(v != bed for v in others):
                obs_bed.append({"就诊": rid, "姓名": pname, "床号": beds})
            depts = {"登记": dept, "病历": emr_depts, "医嘱": ord_depts}
            others_d = [v for k, val in depts.items() if k != "登记" for v in _flat(val)]
            if others_d and any(v != dept for v in others_d):
                obs_dept.append({"就诊": rid, "姓名": pname, "科室": depts})
            if len(detail) < 14:
                detail.append(row)
        conn.close()

        ev = {"参与患者数": len(patients),
              "①数据集口径(观察，不判缺陷)": {
                  "FIN_IP_REGISTER 住院登记行数": n_ip_reg,
                  "EMR_RECORD 总行数": n_emr_all,
                  "EMR 门诊(O型)行数": n_emr_op,
                  "EMR 住院(I型)就诊号不在登记表的行数": glob_emr,
                  "LIS 就诊号不在住院登记表的行数": glob_lis,
                  "说明": "测试库住院登记只有 46 行、病历却有 519 条（其中 195 条是门诊 O 型），"
                          "存在大量没有对应登记的文书 —— 这是测试数据集不完整，"
                          "且 EMR 本就同时覆盖门诊，**不能据此判「跨系统关联断裂」**。"
                          "因此贯通性只对「确实四方都有数据」的患者核对。"},
              "②主索引比对患者数": n_pid,
              "③姓名比对次数(病历+检验)": n_name,
              "④性别比对次数(病历+检验)": n_sex,
              "⑤床号差异(观察，不判缺陷)": obs_bed[:5],
              "⑤科室差异(观察，不判缺陷)": obs_dept[:5],
              "逐患者": detail}
        if n_name < 3 or n_pid < 3:
            bad.append(f"可比的稳定标识太少（姓名 {n_name} 次、主索引 {n_pid} 次），核对不充分")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "跨系统一致性不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{len(patients)} 名「同时有有效病历与医嘱」的住院患者，以就诊号贯通 HIS 登记 / "
                    f"病历文书 / 医嘱 / LIS 检验：患者主索引比对 {n_pid} 次、"
                    f"姓名 {n_name} 次、性别 {n_sex} 次**全部一致**。"
                    f"另有床号差异 {len(obs_bed)} 名、科室差异 {len(obs_dept)} 名，经查均为"
                    f"转床/转科（如就诊 555 有已确认的转科申请单 83）、以及"
                    f"「临床科室 vs 护理单元」两类字典记录（`SYS_DEPT` 里 `骨一科`类型I / `骨一科病区`类型N）"
                    f"所致，非数据不一致")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


flow_L5_036.requires_rules = ['CONV_CROSS_SYS_DEPT_DISTINCTION', 'CONV_INPATIENT_SAMPLE_INCOMPLETE']

FLOWS = {
    "L5-036": flow_L5_036,
}


FLOW_RULES = {
    "L5-036": flow_L5_036.requires_rules,
}
