@echo off
chcp 65001 >nul
title 智能简历优化工具 - 前端页面
cd /d %~dp0frontend
echo ============================================
echo  智能简历优化工具 - 前端  http://127.0.0.1:5173
echo ============================================
python -m http.server 5173
pause
