#!/usr/bin/env python3
"""
IPAM 网络地址管理助手 - 启动入口
调用 web 模块启动 Flask 服务
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from web.app import app
import config
import data_manager

if __name__ == "__main__":
    print("=" * 50)
    print("  IPAM - 网络地址管理助手 (离线版)")
    print("  Version 1.0")
    print("=" * 50)
    print(f"  数据目录: {config.DATA_DIR}")
    print(f"  备份目录: {config.BACKUP_DIR}")
    print(f"  日志目录: {config.LOG_DIR}")
    print("=" * 50)
    print()
    print("  启动服务...")
    print(f"  浏览器打开: http://127.0.0.1:5000")
    print()
    print("  管理员密码: admin123")
    print("  查询模式密码: query123")
    print()
    print("  按 Ctrl+C 停止服务")
    print("=" * 50)

    data_manager.initialize_data_files()
    app.run(host="127.0.0.1", port=5000, debug=False)
