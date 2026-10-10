# -*- coding: utf-8 -*-
"""
fs_runner.__main__
==================
命令行入口主函数：python -m fs_runner <subcommand>
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fs_runner.cli import main

if __name__ == "__main__":
    sys.exit(main())
