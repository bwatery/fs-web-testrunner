# -*- coding: utf-8 -*-
"""
fs_runner.report
================
报告持久化与展示生成。
"""
from .json_writer import write_json_report
from .site import generate_static_site

__all__ = ["write_json_report", "generate_static_site"]
