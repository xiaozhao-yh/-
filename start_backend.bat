@echo off
chcp 65001 >nul
title 智能简历优化工具 - 后端服务
cd /d %~dp0backend
echo ============================================
echo  智能简历优化工具 - 后端 API  http://127.0.0.1:8000
echo  首次使用请先执行: python init_db.py
echo ============================================
python run.py
pause
