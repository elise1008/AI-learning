"""
数据管理模块
负责所有 CSV 文件的读写、缓存管理
"""
import csv
import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import config


def read_csv(file_path: Path) -> List[Dict]:
    """读取 CSV 文件，返回字典列表"""
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return [row for row in reader]
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="gbk", newline="") as f:
            reader = csv.DictReader(f)
            return [row for row in reader]
    except Exception:
        return []


def write_csv(file_path: Path, rows: List[Dict], columns: List[str]):
    """写入 CSV 文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_csv(file_path: Path, row: Dict, columns: List[str]):
    """追加一行到 CSV"""
    rows = read_csv(file_path)
    rows.append(row)
    write_csv(file_path, rows, columns)


def delete_from_csv(file_path: Path, key: str, value: str) -> int:
    """按 key=value 删除行，返回删除数量"""
    rows = read_csv(file_path)
    new_rows = [r for r in rows if r.get(key, "").strip() != value.strip()]
    removed = len(rows) - len(new_rows)
    if removed > 0:
        columns = config.BUSINESS_COLUMNS.get(file_path.stem, list(rows[0].keys()) if rows else [])
        write_csv(file_path, new_rows, columns)
    return removed


def update_csv(file_path: Path, key: str, value: str, updates: Dict) -> bool:
    """按 key=value 更新行"""
    rows = read_csv(file_path)
    updated = False
    for row in rows:
        if row.get(key, "").strip() == value.strip():
            row.update(updates)
            updated = True
    if updated:
        columns = config.BUSINESS_COLUMNS.get(file_path.stem, list(rows[0].keys()) if rows else [])
        write_csv(file_path, rows, columns)
    return updated


def find_row(file_path: Path, key: str, value: str) -> Optional[Dict]:
    """按 key=value 查找单行"""
    rows = read_csv(file_path)
    for row in rows:
        if row.get(key, "").strip() == value.strip():
            return row
    return None


def list_all_business_files() -> Dict[str, Path]:
    """返回所有存在的业务 CSV 文件"""
    return {name: path for name, path in config.BUSINESS_FILES.items() if path.exists()}


def initialize_data_files():
    """初始化所有数据文件（如果不存在则创建空文件）"""
    for name, columns in config.BUSINESS_COLUMNS.items():
        if name == "master_pool":
            file_path = config.MASTER_POOL_FILE
        elif name == "router_loopback":
            file_path = config.ROUTER_LOOPBACK_FILE
        elif name == "router_link":
            file_path = config.ROUTER_LINK_FILE
        else:
            file_path = config.BUSINESS_FILES.get(name)
            if not file_path:
                continue
        if not file_path.exists():
            write_csv(file_path, [], columns)


def get_all_devices() -> List[Dict]:
    """从所有业务表中获取设备列表（统一格式）"""
    devices = []
    for biz_name, file_path in config.BUSINESS_FILES.items():
        if not file_path.exists():
            continue
        for row in read_csv(file_path):
            row["_业务"] = biz_name
            devices.append(row)
    return devices


def search_device_by_name(device_name: str) -> List[Dict]:
    """按设备名称搜索（跨所有业务表）"""
    results = []
    for biz_name, file_path in config.BUSINESS_FILES.items():
        if not file_path.exists():
            continue
        for row in read_csv(file_path):
            if device_name.lower() in row.get("设备名称", "").lower():
                row["_业务"] = biz_name
                results.append(row)
    return results


def search_device_by_ip(ip: str) -> List[Dict]:
    """按 IP 地址搜索（支持 CIDR 和纯 IP）"""
    import ipaddress
    results = []

    def _ip_matches(cell_value: str, search_ip: str) -> bool:
        """判断 cell IP（可能带 /mask）是否匹配搜索 IP"""
        cell = cell_value.strip()
        if not cell:
            return False
        try:
            if "/" in cell:
                net = ipaddress.ip_network(cell, strict=False)
            else:
                net = ipaddress.ip_network(f"{cell}/32", strict=False)
        except ValueError:
            return False
        try:
            if "/" in search_ip:
                search_addr = ipaddress.ip_network(search_ip, strict=False).network_address
            else:
                search_addr = ipaddress.ip_address(search_ip)
        except ValueError:
            return search_ip in cell
        return search_addr in net

    # 搜索所有业务表
    for biz_name, file_path in config.BUSINESS_FILES.items():
        if not file_path.exists():
            continue
        for row in read_csv(file_path):
            addr = row.get("地址段", "").strip()
            gateway = row.get("网关", "").strip()
            mask = row.get("掩码", "").strip()
            combined = f"{addr}/{mask}" if addr and mask else addr
            if _ip_matches(addr, ip) or _ip_matches(combined, ip) or _ip_matches(gateway, ip):
                row["_业务"] = biz_name
                results.append(row)

    # 搜索路由器 Loopback 表
    if config.ROUTER_LOOPBACK_FILE.exists():
        for row in read_csv(config.ROUTER_LOOPBACK_FILE):
            lb0 = row.get("loopback0", "").strip()
            lb1 = row.get("loopback1", "").strip()
            if _ip_matches(lb0, ip) or _ip_matches(lb1, ip):
                row["_业务"] = "路由器Loopback"
                results.append(row)

    # 搜索路由器链路表
    if config.ROUTER_LINK_FILE.exists():
        for row in read_csv(config.ROUTER_LINK_FILE):
            local_ip = row.get("本端IP", "").strip()
            remote_ip = row.get("对端IP", "").strip()
            if _ip_matches(local_ip, ip) or _ip_matches(remote_ip, ip):
                row["_业务"] = "路由器链路"
                results.append(row)

    return results


def get_used_ips_by_business(biz_name: str) -> List[str]:
    """获取某个业务下所有已用的 IP 地址段"""
    file_path = config.BUSINESS_FILES.get(biz_name)
    if not file_path or not file_path.exists():
        return []
    ips = []
    for row in read_csv(file_path):
        addr = row.get("地址段", "").strip()
        if addr:
            ips.append(addr)
    return ips


def get_master_pool() -> List[Dict]:
    """读取地址总表"""
    return read_csv(config.MASTER_POOL_FILE)


def get_router_links() -> List[Dict]:
    """读取路由链路表"""
    return read_csv(config.ROUTER_LINK_FILE)


def get_router_loopbacks() -> List[Dict]:
    """读取路由器 Loopback 表"""
    return read_csv(config.ROUTER_LOOPBACK_FILE)
