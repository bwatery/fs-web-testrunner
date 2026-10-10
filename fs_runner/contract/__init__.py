# -*- coding: utf-8 -*-
"""
fs_runner.contract
==================
自研接口契约校验引擎（Schemathesis 等价自研实现）：
基于 OpenAPI / Swagger 规范执行契约与边界自检。
"""
from .runner import run_api_contract

__all__ = ["run_api_contract"]
