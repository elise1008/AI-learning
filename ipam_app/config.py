"""
全局配置模块
管理所有路径、常量、业务定义
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller exe mode
    BASE_DIR = Path(sys.executable).parent
    _MEIPASS = Path(sys._MEIPASS)  # Embedded files
else:
    BASE_DIR = Path(__file__).resolve().parent
    _MEIPASS = BASE_DIR

DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backup"
EXPORT_DIR = BASE_DIR / "export"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
MATPLOTLIB_CACHE_DIR = EXPORT_DIR / "matplotlib"
MATPLOTLIB_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CACHE_DIR))

MASTER_POOL_FILE = DATA_DIR / "master_pool.csv"
ROUTER_LOOPBACK_FILE = DATA_DIR / "router_loopback.csv"
ROUTER_LINK_FILE = DATA_DIR / "router_link.csv"

BUSINESS_FILES = {
    "SPI":     DATA_DIR / "SPI.csv",
    "sczndw":  DATA_DIR / "sczndw.csv",
    "spd":     DATA_DIR / "spd.csv",
    "IMS":     DATA_DIR / "IMS.csv",
    "xxnw":    DATA_DIR / "xxnw.csv",
    "xxww":    DATA_DIR / "xxww.csv",
    "scspjk":  DATA_DIR / "scspjk.csv",
    "spvv":    DATA_DIR / "spvv.csv",
    "vlan300": DATA_DIR / "vlan300.csv",
}

BUSINESS_COLUMNS = {
    "master_pool":     ["业务名称", "地址段", "掩码"],
    "router_loopback": ["设备名称", "loopback0", "loopback1", "登录账号", "密码", "登录方式"],
    "router_link":     ["本端设备名", "本端接口", "本端IP", "掩码", "对端设备名", "对端接口", "对端IP", "掩码", "cost"],

    "SPI":     ["设备名称", "地址段", "掩码"],
    "sczndw":  ["设备名称", "地址段", "掩码", "网关", "接入终端地址", "接入交换机端口"],
    "spd":     ["设备名称", "地址段", "掩码", "网关", "接入终端地址", "接入交换机端口"],
    "IMS":     ["设备名称", "地址段", "掩码", "网关", "接入终端地址", "接入交换机端口"],
    "xxnw":    ["设备名称", "所属单位", "地址段", "掩码"],
    "xxww":    ["设备名称", "所属单位", "地址段", "掩码"],
    "scspjk":  ["设备名称", "地址段", "掩码", "网关"],
    "spvv":    ["设备名称", "地址段", "掩码", "网关"],
    "vlan300": ["设备名称", "地址段", "掩码", "登录方式", "账号", "密码"],
}

ADMIN_PASSWORD = "admin123"
QUERY_PASSWORD = "query123"

BACKUP_INTERVAL_DAYS = 7
LOG_FILE = LOG_DIR / "operation.log"

TOPOLOGY_OUTPUT = EXPORT_DIR / "topology.png"
PATH_ANALYSIS_OUTPUT = EXPORT_DIR / "path_analysis.png"
