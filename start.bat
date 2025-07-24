@echo off
chcp 65001
echo 正在启动智能文档爬虫系统...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

REM 检查Chrome浏览器
where chrome >nul 2>&1
if errorlevel 1 (
    echo 警告: 未找到Chrome浏览器，请确保已安装Chrome
)

REM 安装依赖包
echo 正在检查并安装依赖包...
pip install -r requirements.txt

REM 启动应用
echo.
echo 正在启动Web服务...
python run.py

pause 