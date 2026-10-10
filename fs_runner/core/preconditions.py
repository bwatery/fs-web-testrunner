# -*- coding: utf-8 -*-
"""
fs_runner.core.preconditions
============================
声明式前置条件层。
严格区分「数据补齐回读」与「有害自愈」，补齐失败直接判「阻塞」或「未执行」，绝不判通过。
"""
import os
from typing import Any, Dict, List, Optional, Tuple


class PreconditionManager:
    """前置条件管理器。"""

    def __init__(self):
        self.created_entities: List[Dict[str, Any]] = []

    def ensure(self, requirement: str) -> bool:
        """检查并尝试补齐前置条件。"""
        # 在本阶段作为骨架模型，后续阶段接入真实接口造数与回读
        return True

    def check_oracle_precondition(self, env_obj: Optional[Any] = None) -> Tuple[bool, str]:
        """
        检查 Oracle 数据库前置连接条件。
        若环境对象声明无法连接 Oracle (can_connect_oracle() is False) 或运行于沙盒环境，
        前置门禁直接拦截并声明「未执行」，避免向被测业务流程注入假数据源或无库空跑。
        """
        if env_obj is not None:
            if hasattr(env_obj, "can_connect_oracle") and not env_obj.can_connect_oracle():
                return False, "沙盒模式：未连接数据库，无法验证业务"
        if os.environ.get("FS_RUNNER_ENV") == "sandbox":
            return False, "沙盒模式：未连接数据库，无法验证业务"
        return True, ""


precondition_manager = PreconditionManager()
