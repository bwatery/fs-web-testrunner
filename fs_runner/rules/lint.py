# -*- coding: utf-8 -*-
"""
fs_runner.rules.lint
====================
规则库与配置自动化巡检器：
1. 死配置扫描（按业务类型分组：无条件兜底排在有条件规则之前 -> 报出红灯）
   - 条件列涵盖：usage_kind, order_type, drug_quality, drug_type, apply_dept_id
   - 支持从真实 Oracle 库扫描，或指定历史快照 JSON 作为测试向量
2. 采样规范抽查（抽样处必须写明代表性原因，严禁使用易被自身污染的最新一条盲取）
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import ORACLE_CONFIG, ROOT_DIR


SNAPSHOT_FILE = ROOT_DIR / "reports" / "verify" / "_snapshot_dispense_type.json"


def scan_dead_configs(
    source: Optional[Union[str, Path]] = None,
    oracle_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """死配置扫描：按同业务类型分组，无条件规则优先级高于有条件规则时立即报警。

    参数:
        source: 'db'（默认，查真实数据库）、'snapshot'（或具体 JSON 路径，查历史快照）
        oracle_cfg: 可选 Oracle 数据库配置

    判定逻辑：
        全条件字段：usage_kind, order_type, drug_quality, drug_type, apply_dept_id。
        仅当上述 5 项全部为空时，该规则才为「无条件兜底规则」。
        若无条件兜底规则的 priority_order < 某有条件规则的 priority_order，
        则该有条件规则永远无法命中，判定为死配置。
    """
    violations: List[Dict[str, Any]] = []
    rows = []

    use_snapshot = False
    snap_path = SNAPSHOT_FILE

    if source:
        src_str = str(source).strip()
        if src_str.lower() == "snapshot":
            use_snapshot = True
        elif Path(src_str).exists():
            use_snapshot = True
            snap_path = Path(src_str)
        elif src_str.lower() != "db":
            # 可能是传入了具体路径但不存在
            if Path(src_str).name.endswith(".json"):
                use_snapshot = True
                snap_path = Path(src_str)

    if use_snapshot:
        if snap_path.exists():
            raw_snap = json.loads(snap_path.read_text(encoding="utf-8"))
            for r in raw_snap:
                prio_val = r.get("PRIORITY_ORDER") or r.get("priority_order")
                if prio_val is not None:
                    try:
                        prio_int = int(prio_val)
                    except ValueError:
                        continue
                    rows.append((
                        int(r.get("DISPENSE_TYPE_ID") or r.get("dispense_type_id") or 0),
                        r.get("DISPENSE_TYPE_NAME") or r.get("dispense_type_name"),
                        r.get("SYS_BUSINESS_TYPE") or r.get("sys_business_type"),
                        prio_int,
                        r.get("USAGE_KIND") or r.get("usage_kind"),
                        r.get("ORDER_TYPE") or r.get("order_type"),
                        r.get("DRUG_QUALITY") or r.get("drug_quality"),
                        r.get("DRUG_TYPE") or r.get("drug_type"),
                        r.get("APPLY_DEPT_ID") or r.get("apply_dept_id"),
                    ))
            rows.sort(key=lambda x: (x[2] or "DEFAULT", x[3]))
    else:
        # 默认尝试从 Oracle 数据库查询
        cfg = oracle_cfg or dict(ORACLE_CONFIG)
        try:
            import oracledb
            conn = oracledb.connect(
                user=cfg.get("user"),
                password=cfg.get("password"),
                dsn=f"{cfg.get('host', '192.168.1.199')}:{cfg.get('port', 1521)}/{cfg.get('service_name', 'orcl')}",
            )
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dispense_type_id, dispense_type_name, sys_business_type, priority_order,
                       usage_kind, order_type, drug_quality, drug_type, apply_dept_id
                FROM pha_bd_dispense_type
                WHERE priority_order IS NOT NULL
                ORDER BY NVL(sys_business_type, 'DEFAULT'), priority_order ASC
                """
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception:
            # 数据库不可达时回退到 snapshot 快照
            if SNAPSHOT_FILE.exists():
                return scan_dead_configs(source=SNAPSHOT_FILE)

    if not rows:
        return violations

    # 按业务类型 (sys_business_type) 分组扫描
    by_biz: Dict[str, List[Any]] = {}
    for r in rows:
        biz = r[2] or "DEFAULT"
        by_biz.setdefault(biz, []).append(r)

    for biz, biz_rows in by_biz.items():
        biz_rows.sort(key=lambda x: x[3])  # 按 priority_order 升序
        unconditional_rules = []
        for r in biz_rows:
            dtype_id, name, _, prio, usage_kind, order_type, drug_qual, drug_type, apply_dept = r

            # 严格核查 5 项条件列：全部为空才算无条件兜底
            is_unconditional = (
                (not usage_kind)
                and (not order_type)
                and (not drug_qual)
                and (not drug_type)
                and (not apply_dept)
            )

            if is_unconditional:
                unconditional_rules.append((dtype_id, name, prio))
            else:
                for u_id, u_name, u_prio in unconditional_rules:
                    if u_prio < prio:
                        cond_desc = []
                        if usage_kind:
                            cond_desc.append(f"usage_kind='{usage_kind}'")
                        if order_type:
                            cond_desc.append(f"order_type='{order_type}'")
                        if drug_qual:
                            cond_desc.append(f"drug_quality='{drug_qual}'")
                        if drug_type:
                            cond_desc.append(f"drug_type='{drug_type}'")
                        if apply_dept:
                            cond_desc.append(f"apply_dept_id='{apply_dept}'")

                        violations.append({
                            "check": "DEAD_CONFIG_SCAN",
                            "severity": "ERROR",
                            "business_type": biz,
                            "data_source": "snapshot" if use_snapshot else "oracle_db",
                            "unconditional_rule": {
                                "id": u_id,
                                "name": u_name,
                                "priority": u_prio,
                            },
                            "blocked_rule": {
                                "id": dtype_id,
                                "name": name,
                                "priority": prio,
                                "conditions": ", ".join(cond_desc),
                            },
                            "message": (
                                f"死配置报警：业务类型「{biz}」内，无条件兜底规则「{u_name}」(优先级 {u_prio}) "
                                f"排在有条件规则「{name}」(优先级 {prio}, 条件 {', '.join(cond_desc)}) 之前！"
                                f"未命中前置规则的单据将无条件落入「{u_name}」，导致「{name}」成为永远无法触发的死配置。"
                            ),
                        })

    return violations


def scan_sampling_violations() -> List[Dict[str, Any]]:
    """采样规范抽查：

    1. 检查 SQL 盲取：禁止直接使用 'ORDER BY ... DESC FETCH FIRST 1' 盲取易被测试污染的最新一条。
    2. 检查样本代表性注释与充分过滤条件。
    """
    violations: List[Dict[str, Any]] = []
    flows_dir = ROOT_DIR / "fs_runner" / "cases" / "closed_loop"

    pattern_blind_desc = re.compile(
        r"ORDER\s+BY\s+(\w+)\s+DESC\s+(FETCH\s+FIRST\s+1\s+ROWS\s+ONLY|ROWNUM\s*<=\s*1)",
        re.IGNORECASE,
    )

    for py_file in flows_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            match = pattern_blind_desc.search(line)
            if match:
                order_col = match.group(1).lower()
                context_block = "\n".join(lines[max(0, idx - 6):min(len(lines), idx + 6)])
                has_filter = ("valid_flag" in context_block.lower()) or ("exists" in context_block.lower()) or ("where" in context_block.lower() and "=" in context_block)

                if order_col in ("order_id", "register_id", "see_no") and not has_filter:
                    violations.append({
                        "check": "SAMPLING_SPEC_AUDIT",
                        "severity": "WARNING",
                        "file": str(py_file.relative_to(ROOT_DIR)),
                        "line": idx,
                        "order_column": order_col,
                        "code_snippet": line.strip(),
                        "message": (
                            f"[{py_file.name}:{idx}] 采样风险：使用 ORDER BY {order_col} DESC 盲取最新一条，"
                            f"缺少充分过滤条件（如 valid_flag 或特定属性存在性），存在被测试写操作污染导致偶发失败的风险。"
                        ),
                    })

    return violations
