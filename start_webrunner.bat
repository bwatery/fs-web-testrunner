@echo off
chcp 65001 >nul
title HIS WebRunner - 医院信息系统自动化测试平台
echo ========================================================
echo   HIS WebRunner 自动化测试控制台正在启动...
echo   访问地址: http://127.0.0.1:8989
echo ========================================================
python run_runner.py
pause
