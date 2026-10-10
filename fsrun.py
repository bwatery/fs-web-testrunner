# -*- coding: utf-8 -*-
"""
fsrun.py - FS.TestRunner 统一入口脚本
====================================
支持 python -I（隔离模式）执行，自动注入根目录到 sys.path。

用法示例：
    python -I fsrun.py run --suite closed-loop
    python -I fsrun.py run --suite api --limit 100
    python -I fsrun.py regression
    python -I fsrun.py selfcheck --mutation
    python -I fsrun.py serve --port 8990
    python -I fsrun.py rules --check
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fs_runner.cli import main

if __name__ == "__main__":
    sys.exit(main())
