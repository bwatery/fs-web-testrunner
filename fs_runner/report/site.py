# -*- coding: utf-8 -*-
"""
fs_runner.report.site
=====================
静态报告网页生成器（基于 reports/ 下的既有 JSON 报告生成只读展示页面）。
"""
from pathlib import Path


def generate_static_site(output_dir: Path) -> None:
    """生成静态 HTML 报告。"""
    output_dir.mkdir(parents=True, exist_ok=True)
