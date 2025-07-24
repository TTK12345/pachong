#!/bin/bash

echo "正在启动智能文档爬虫系统..."
echo "======================================"

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.7+"
    exit 1
fi

# 检查Chrome浏览器
if ! command -v google-chrome &> /dev/null && ! command -v chromium-browser &> /dev/null; then
    echo "警告: 未找到Chrome浏览器，请确保已安装Chrome或Chromium"
fi

# 创建虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 安装依赖包
echo "正在安装依赖包..."
pip install -r requirements.txt

# 启动应用
echo "正在启动Web服务..."
echo "服务地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo "======================================"

python run.py 