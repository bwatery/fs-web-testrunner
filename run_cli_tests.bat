@echo off
chcp 65001 >nul
title HIS WebRunner - CLI 命令行全量快速测试
echo ========================================================
echo   正在执行全量自动化测试 (47 项用例)...
echo ========================================================
python run_cli_tests.py
pause
