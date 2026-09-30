@echo off
chcp 65001 >nul
title FS.TestRunner CLI
echo 正在执行病历元素自动化测试...
python "%~dp0run_cli_tests.py" --headless
pause
