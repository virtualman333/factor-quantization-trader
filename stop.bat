@echo off
chcp 65001 >nul
title 停止所有服务

echo.
echo  ========================================
echo   正在停止因子量化交易系统所有服务...
echo  ========================================
echo.

echo [1/4] 停止 Celery Worker...
taskkill /f /fi "WINDOWTITLE eq Celery Worker" >nul 2>&1
taskkill /f /im "celery.exe" >nul 2>&1
echo [√] 已停止

echo [2/4] 停止 Celery Beat...
taskkill /f /fi "WINDOWTITLE eq Celery Beat" >nul 2>&1
echo [√] 已停止

echo [3/4] 停止 Django 后端...
:: 杀掉占用 8000 端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [√] 已停止

echo [4/4] 停止前端 Vite...
:: 杀掉占用 5173 端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [√] 已停止

echo.
echo  ========================================
echo   所有服务已停止。
echo  ========================================
echo.
pause
