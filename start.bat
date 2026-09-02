@echo off
chcp 65001 >nul
echo ========================================
echo   Quant Cache Service 启动脚本
echo ========================================
echo.

REM 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    echo [INFO] 使用虚拟环境 .venv
    set PYTHON=.venv\Scripts\python.exe
) else (
    echo [INFO] 使用系统 Python
    set PYTHON=python
)

REM 检查 .env
if not exist ".env" (
    echo [WARN] 未找到 .env 文件，使用默认配置（CACHE_ROOT 指向原量化项目）
    echo [INFO] 可复制 .env.example 为 .env 自定义路径
    echo.
)

echo [INFO] 启动服务...
echo [INFO] 文档地址: http://localhost:8100/docs
echo [INFO] 按 Ctrl+C 停止
echo.

%PYTHON% -m app.main

pause
