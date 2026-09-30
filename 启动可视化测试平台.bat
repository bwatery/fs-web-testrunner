@echo off
chcp 65001 >nul
title FS.TestRunner Web - 电子病历自动化测试平台
echo 正在启动 FS.TestRunner Web 控制台...
python "%~dp0run_runner.py"
pause
