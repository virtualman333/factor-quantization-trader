@echo off
chcp 65001 >nul
title 因子量化交易系统 - 快速启动
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"
if not exist "logs" mkdir logs

echo.
echo  ========================================
echo   因子量化交易系统 - 快速启动
echo   所有服务后台运行，不弹出新窗口
echo  ========================================
echo.

::: ========== 1. Redis ==========
echo [1/5] 检查 Redis...
set "REDIS_STATUS=stopped"
for /f "delims=" %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',6379); $c.Close(); 'running' } catch { 'stopped' }"') do set "REDIS_STATUS=%%i"
if "!REDIS_STATUS!"=="running" (
    echo   [OK] Redis 已在运行
) else (
    set "REDIS_EXE="
    set "REDIS_CONF="
    if exist "C:\Program Files\Redis\redis-server.exe" (
        set "REDIS_EXE=C:\Program Files\Redis\redis-server.exe"
        if exist "C:\Program Files\Redis\redis.windows.conf" set "REDIS_CONF=C:\Program Files\Redis\redis.windows.conf"
    ) else (
        where redis-server >nul 2>&1 && set "REDIS_EXE=redis-server"
    )
    if not defined REDIS_EXE (
        echo   [!!] 未找到 redis-server，请先安装 Redis 或检查 PATH
    ) else (
        echo   [..] 正在后台启动 Redis...
        if defined REDIS_CONF (
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '!REDIS_EXE!' -ArgumentList '!REDIS_CONF!' -WindowStyle Hidden"
        ) else (
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '!REDIS_EXE!' -WindowStyle Hidden"
        )
        timeout /t 2 /nobreak >nul
    )
)

::: ========== 2. 环境检查 ==========
echo [2/5] 检查环境...
if not exist "%ROOT%venv\Scripts\python.exe" (
    echo   [..] 未找到虚拟环境，正在创建...
    python -m venv "%ROOT%venv"
)
if not exist "%ROOT%frontend\node_modules" (
    echo   [!!] 前端依赖未安装，请先在 frontend 目录运行 npm install
)
echo   [OK] 环境检查完成

::: ========== 3. 启动 Celery Worker ==========
echo [3/5] 启动 Celery Worker...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','worker','-l','info','--pool=solo' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\celery_worker.log' -RedirectStandardError '%ROOT%logs\celery_worker_err.log'"

::: ========== 4. 启动 Celery Beat ==========
echo [4/5] 启动 Celery Beat...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','beat','-l','info','--scheduler','django_celery_beat.schedulers:DatabaseScheduler' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\celery_beat.log' -RedirectStandardError '%ROOT%logs\celery_beat_err.log'"

::: ========== 5. 启动 Django 后端 ==========
echo [5/5] 启动 Django 后端 (端口 8000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\python.exe' -ArgumentList 'manage.py','runserver','0.0.0.0:8000','--noreload' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\django.log' -RedirectStandardError '%ROOT%logs\django_err.log'"

::: ========== 6. 启动前端 Vite ==========
echo [6/6] 启动 Flower Celery 监控 (端口 5555)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','flower','--port=5555' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\flower.log' -RedirectStandardError '%ROOT%logs\flower_err.log'"

echo [7/6] 启动前端 Vite (端口 5173)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\vite.log' -RedirectStandardError '%ROOT%logs\vite_err.log'"

echo.
echo 等待服务启动...
timeout /t 6 /nobreak >nul

echo.
echo  ========================================
echo   快速启动完成！
echo.
echo   前端:       http://localhost:5173
echo   后端 API:   http://localhost:8000/api/
echo   Admin:      http://localhost:8000/admin/
echo   Silk 分析:  http://localhost:8000/silk/
echo   Flower 监控: http://localhost:5555/
echo.
echo   日志目录: %ROOT%logs
echo   停止服务: 运行 stop.bat
echo  ========================================
echo.
pause
