@echo off
chcp 65001 >nul
title 停止所有服务

echo.
echo  ========================================
echo   正在停止因子量化交易系统所有服务...
echo  ========================================
echo.

echo [1/8] 停止 Flower (端口 5555)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5555 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo [√]

echo [2/8] 停止 Django (端口 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo [√]

echo [3/8] 停止前端 Vite (端口 5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo [√]

echo [4/8] 停止前端 Vite (端口 5174)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo [√]

echo [5/8] 停止 Celery Worker...
taskkill /f /im "celery.exe" >nul 2>&1
echo [√]

echo [6/8] 停止 Celery Beat...
taskkill /f /im "celery.exe" >nul 2>&1
echo [√]

echo [7/8] 清理残留 Python 进程...
taskkill /f /im "python.exe" >nul 2>&1
echo [√]

echo [8/8] 清理残留 Node.js 进程...
taskkill /f /im "node.exe" >nul 2>&1
echo [√]

echo.
echo  ========================================
echo   所有服务已停止。
echo  ========================================
echo.
pause
