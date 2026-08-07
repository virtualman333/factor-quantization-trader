@echo off
chcp 65001 >nul
title 因子量化交易系统

echo.
echo  ========================================
echo   因子量化交易系统 - 一键启动
echo  ========================================
echo.

:: ========== 环境检查 ==========
echo [1/6] 检查环境...

:: Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

:: Redis
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] Redis 未运行，正在启动 Redis...
    start "Redis" redis-server
    timeout /t 3 /nobreak >nul
)

:: 检查虚拟环境
set VENV_DIR=venv
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [提示] 未找到虚拟环境，正在创建...
    python -m venv %VENV_DIR%
)
call "%VENV_DIR%\Scripts\activate.bat"

:: 检查依赖
pip show django >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 Python 依赖...
    pip install -r requirements.txt
)

:: 检查前端 node_modules
if not exist "frontend\node_modules" (
    echo [提示] 正在安装前端依赖...
    cd frontend
    npm install
    cd ..
)

echo [√] 环境检查通过
echo.

:: ========== 数据库迁移 ==========
echo [2/6] 数据库迁移...
python manage.py migrate --noinput
echo [√] 迁移完成
echo.

:: ========== 启动 Celery Worker ==========
echo [3/6] 启动 Celery Worker...
start "Celery Worker" cmd /c "title Celery Worker && venv\Scripts\activate.bat && celery -A config worker -l info --pool=solo"
echo [√] Celery Worker 已启动
echo.

:: ========== 启动 Celery Beat ==========
echo [4/6] 启动 Celery Beat...
start "Celery Beat" cmd /c "title Celery Beat && venv\Scripts\activate.bat && celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"
echo [√] Celery Beat 已启动
echo.

:: ========== 启动 Django 后端 ==========
echo [5/6] 启动 Django 后端 (端口 8000)...
start "Django Server" cmd /c "title Django Server && venv\Scripts\activate.bat && python manage.py runserver 0.0.0.0:8000"
echo [√] Django 后端已启动
echo.

:: 等待 Django 就绪
timeout /t 3 /nobreak >nul

:: ========== 启动前端 ==========
echo [6/6] 启动前端 Vite (端口 5173)...
start "Vite Frontend" cmd /c "title Vite Frontend && cd frontend && npm run dev"
echo [√] 前端已启动
echo.

:: ========== 完成 ==========
echo.
echo  ========================================
echo   启动完成！
echo.
echo   前端:     http://localhost:5173
echo   后端 API: http://localhost:8000/api/
echo   Admin:   http://localhost:8000/admin/
echo.
echo   按任意键停止所有服务...
echo  ========================================
echo.

pause >nul

:: ========== 清理 ==========
echo.
echo 正在停止所有服务...

taskkill /f /im "celery.exe" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Django Server" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Vite Frontend" >nul 2>&1

echo 所有服务已停止。
pause
