# -*- coding: utf-8 -*-
"""
fs_runner.env.base
==================
环境接口基类：定义内网连通性、数据库连接能力与真实性门禁策略。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple


class BaseEnv(ABC):
    """环境抽象：定义执行环境特性与结果判定门禁。"""

    name: str = "base"

    @abstractmethod
    def is_real(self) -> bool:
        """是否为真实环境（仅真实环境允许产出「通过」）。"""
        pass

    @abstractmethod
    def can_connect_oracle(self) -> bool:
        """能否连通 Oracle 数据库。"""
        pass

    @abstractmethod
    def can_connect_gateway(self) -> bool:
        """能否连通 HIS 网关。"""
        pass

    @abstractmethod
    def filter_result_status(self, raw_status: str, note: str = "") -> Tuple[str, str]:
        """根据当前环境门禁策略过滤判定状态与说明（沙盒环境强制不产出「通过」）。"""
        pass

    @abstractmethod
    def wrap_evidence(self, evidence: Any) -> Dict[str, Any]:
        """将当前环境标记注入 evidence。"""
        pass
