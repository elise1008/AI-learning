"""
备份模块
自动备份所有数据文件，支持手动备份和7天自动备份
"""
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import config
import logger as app_logger


def manual_backup() -> str:
    """手动备份"""
    return _do_backup()


def _do_backup() -> str:
    """执行备份操作"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = config.BACKUP_DIR / timestamp
    backup_path.mkdir(parents=True, exist_ok=True)

    backed_up = []
    for csv_file in config.DATA_DIR.glob("*.csv"):
        dest = backup_path / csv_file.name
        shutil.copy2(csv_file, dest)
        backed_up.append(csv_file.name)

    log_file = config.LOG_FILE
    if log_file.exists():
        shutil.copy2(log_file, backup_path / log_file.name)

    app_logger.log("backup", f"手动备份到 {timestamp}")
    return backup_path.name


def auto_backup_check():
    """检查是否需要自动备份（每7天）"""
    last_backup_file = config.BACKUP_DIR / ".last_backup"

    try:
        if last_backup_file.exists():
            last_time = datetime.fromisoformat(last_backup_file.read_text().strip())
            if datetime.now() - last_time < timedelta(days=config.BACKUP_INTERVAL_DAYS):
                return
    except Exception:
        pass

    backup_name = _do_backup()
    last_backup_file.write_text(datetime.now().isoformat())
    app_logger.log("system", f"自动备份完成: {backup_name}")


def list_backups() -> list:
    """列出所有备份"""
    backups = []
    for d in sorted(config.BACKUP_DIR.iterdir(), reverse=True):
        if d.is_dir() and not d.name.startswith("."):
            files = [f.name for f in d.glob("*.csv")]
            backups.append({
                "name": d.name,
                "file_count": len(files),
                "files": files
            })
    return backups


def restore_backup(backup_name: str) -> bool:
    """恢复备份"""
    backup_path = config.BACKUP_DIR / backup_name
    if not backup_path.exists():
        return False
    for csv_file in backup_path.glob("*.csv"):
        shutil.copy2(csv_file, config.DATA_DIR / csv_file.name)
    app_logger.log("backup", f"恢复备份: {backup_name}")
    return True


def start_auto_backup():
    """启动自动备份后台线程"""
    def _loop():
        while True:
            time.sleep(3600)
            try:
                auto_backup_check()
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
