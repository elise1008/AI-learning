"""
日志模块
记录系统操作日志
"""
from datetime import datetime
import config


def log(user: str, operation: str):
    """写入操作日志"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} | {user} | {operation}\n"
        config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def get_logs(lines: int = 200) -> str:
    """读取最近 N 行日志"""
    try:
        if not config.LOG_FILE.exists():
            return "暂无日志"
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception:
        return "读取日志失败"
