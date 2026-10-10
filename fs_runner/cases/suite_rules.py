# -*- coding: utf-8 -*-
"""
fs_runner.cases.suite_rules
===========================
非闭环套件/工具任务（L0/L1/L2/L3）依赖的口径与规则声明。
"""
from typing import Dict, List

SUITE_RULES: Dict[str, List[str]] = {
    "L0-013": ["CONV_PRIMARY_KEY_CROSS_TABLE"],
    "L1-001": ["CONV_PROBE_4XX_DOWNGRADE"],
    "L2-001": ["CONV_HASH_NAV"],
    "L3-001": ["CONV_HASH_NAV"],
}
