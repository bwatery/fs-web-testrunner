# -*- coding: utf-8 -*-
"""
run_verify.py - 薄转发至 fs_runner.cli（保持历史脚本与命令行入口兼容）
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fs_runner.cli import main

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["--api"]
    sys.exit(main(args))
