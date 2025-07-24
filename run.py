#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from app import app, socketio
from config import config

def main():
    """主函数"""
    # 设置环境
    env = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config.get(env, config['default']))
    
    # 创建必要的目录
    for path in app.config['DOWNLOAD_PATHS'].values():
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"已创建目录: {path}")
    
    print("=" * 60)
    print("智能文档爬虫系统")
    print("=" * 60)
    print(f"环境: {env}")
    print(f"调试模式: {app.config['DEBUG']}")
    print("服务地址: http://0.0.0.0:5000")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    try:
        # 启动服务
        socketio.run(
            app, 
            debug=app.config['DEBUG'],
            host='0.0.0.0', 
            port=5000,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动服务时出错: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 