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

:: ========== 1. Redis ==========
echo [1/7] 检查 Redis (端口 6379)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',6379); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
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
        echo   [!!] 未找到 redis-server
    ) else (
        echo   [..] 正在后台启动 Redis...
        if defined REDIS_CONF (
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '!REDIS_EXE!' -ArgumentList '!REDIS_CONF!' -WindowStyle Hidden"
        ) else (
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '!REDIS_EXE!' -WindowStyle Hidden"
        )
        timeout /t 2 /nobreak >nul
        echo   [OK] Redis 已启动
    )
)

:: ========== 2. 环境检查 ==========
echo [2/7] 检查环境...
if not exist "%ROOT%venv\Scripts\python.exe" (
    echo   [!!] 未找到虚拟环境
    pause & exit /b 1
)
if not exist "%ROOT%frontend\node_modules" (
    echo   [!!] 前端依赖未安装，请运行: cd frontend ^&^& npm install
    pause & exit /b 1
)
echo   [OK] 环境检查通过

:: ========== 3. Celery Worker ==========
echo [3/7] 启动 Celery Worker...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','worker','-l','info','--pool=solo' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\celery_worker.log' -RedirectStandardError '%ROOT%logs\celery_worker_err.log'"
echo   [OK] Celery Worker 已启动

:: ========== 4. Celery Beat ==========
echo [4/7] 启动 Celery Beat...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','beat','-l','info','--scheduler','django_celery_beat.schedulers:DatabaseScheduler' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\celery_beat.log' -RedirectStandardError '%ROOT%logs\celery_beat_err.log'"
echo   [OK] Celery Beat 已启动

:: ========== 5. Django 后端 ==========
echo [5/7] 启动 Django 后端 (端口 8000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8000); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo   [..] 端口 8000 被占用，正在释放...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=(Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue|Select-Object -First 1).OwningProcess; if($p){Stop-Process -Id $p -Force}"
    timeout /t 1 /nobreak >nul
    echo   [OK] 已释放
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\python.exe' -ArgumentList 'manage.py','runserver','0.0.0.0:8000','--noreload' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\django.log' -RedirectStandardError '%ROOT%logs\django_err.log'"
echo   [OK] Django 后端已启动

:: ========== 6. Flower 监控 ==========
echo [6/7] 启动 Flower 监控 (端口 5555)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5555); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo   [..] 端口 5555 被占用，正在释放...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=(Get-NetTCPConnection -LocalPort 5555 -ErrorAction SilentlyContinue|Select-Object -First 1).OwningProcess; if($p){Stop-Process -Id $p -Force}"
    timeout /t 1 /nobreak >nul
    echo   [OK] 已释放
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ROOT%venv\Scripts\celery.exe' -ArgumentList '-A','config','flower','--port=5555' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%ROOT%logs\flower.log' -RedirectStandardError '%ROOT%logs\flower_err.log'"
echo   [OK] Flower 监控已启动

:: ========== 7. 前端 Vite ==========
echo [7/7] 启动前端 Vite (端口 5173)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5173); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo   [..] 端口 5173 被占用，正在释放...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=(Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue|Select-Object -First 1).OwningProcess; if($p){Stop-Process -Id $p -Force}"
    timeout /t 1 /nobreak >nul
    echo   [OK] 已释放
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5174); $c.Close(); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo   [..] 端口 5174 被占用，正在释放...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=(Get-NetTCPConnection -LocalPort 5174 -ErrorAction SilentlyContinue|Select-Object -First 1).OwningProcess; if($p){Stop-Process -Id $p -Force}"
    timeout /t 1 /nobreak >nul
    echo   [OK] 已释放
)

:: ========== 完成 ==========
echo.
echo 等待服务就绪...
timeout /t 6 /nobreak >nul

echo.
echo  ========================================
echo   全部服务已启动！
echo.
echo   前端:       http://localhost:5173
echo   后端 API:   http://localhost:8000/api/
echo   管理端:     http://localhost:5173/admin
echo   Silk 分析:  http://localhost:8000/silk/
echo   Flower:     http://localhost:5555/
echo.
echo   日志: %ROOT%logs
echo   停止: 运行 stop.bat
echo  ========================================
echo.
pause
