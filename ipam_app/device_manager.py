"""
设备管理模块
负责设备/IP 的增删改查
"""
import ipaddress
from typing import List, Dict, Optional
from pathlib import Path
import data_manager
import config


def add_device(biz_name: str, data: Dict) -> Dict:
    """
    新增设备到指定业务表
    返回: {"success": True/False, "message": "..."}
    """
    if biz_name not in config.BUSINESS_FILES:
        return {"success": False, "message": f"业务 {biz_name} 不存在"}

    file_path = config.BUSINESS_FILES[biz_name]
    columns = config.BUSINESS_COLUMNS.get(biz_name, [])

    device_name = data.get("设备名称", "").strip()
    ip = data.get("地址段", "").strip()

    if not device_name:
        return {"success": False, "message": "设备名称不能为空"}

    if ip:
        conflict = check_ip_conflict(ip)
        if conflict:
            return {"success": False, "message": f"IP 冲突：{ip} 已被 {conflict} 使用"}

    existing = data_manager.read_csv(file_path)
    for row in existing:
        if row.get("设备名称", "").strip() == device_name:
            return {"success": False, "message": f"设备 {device_name} 已存在"}

    new_row = {}
    for col in columns:
        new_row[col] = data.get(col, "").strip()
    data_manager.append_csv(file_path, new_row, columns)

    return {"success": True, "message": f"设备 {device_name} 添加成功"}


def update_device(biz_name: str, device_name: str, updates: Dict) -> Dict:
    """
    修改设备信息
    返回: {"success": True/False, "message": "..."}
    """
    if biz_name not in config.BUSINESS_FILES:
        return {"success": False, "message": f"业务 {biz_name} 不存在"}

    file_path = config.BUSINESS_FILES[biz_name]
    if not file_path.exists():
        return {"success": False, "message": "数据文件不存在"}

    new_ip = updates.get("地址段", "").strip()
    if new_ip:
        existing = data_manager.read_csv(file_path)
        for row in existing:
            if row.get("设备名称", "").strip() != device_name and row.get("地址段", "").strip() == new_ip:
                return {"success": False, "message": f"IP 冲突：{new_ip} 已被 {row.get('设备名称')} 使用"}

    success = data_manager.update_csv(file_path, "设备名称", device_name, updates)
    if success:
        return {"success": True, "message": f"设备 {device_name} 修改成功"}
    return {"success": False, "message": f"未找到设备 {device_name}"}


def delete_device(biz_name: str, device_name: str) -> Dict:
    """删除设备"""
    if biz_name not in config.BUSINESS_FILES:
        return {"success": False, "message": f"业务 {biz_name} 不存在"}

    file_path = config.BUSINESS_FILES[biz_name]
    removed = data_manager.delete_from_csv(file_path, "设备名称", device_name)
    if removed > 0:
        return {"success": True, "message": f"设备 {device_name} 已删除"}
    return {"success": False, "message": f"未找到设备 {device_name}"}


def check_ip_conflict(ip: str) -> Optional[str]:
    """
    检查 IP 是否冲突
    返回: 冲突的设备名，无冲突返回 None
    """
    ip = ip.strip()
    if not ip:
        return None
    for biz_name, file_path in config.BUSINESS_FILES.items():
        if not file_path.exists():
            continue
        for row in data_manager.read_csv(file_path):
            if row.get("地址段", "").strip() == ip:
                return row.get("设备名称", f"{biz_name}表中的设备")
    return None


def query_device_by_name(device_name: str) -> Dict:
    """
    按设备名查询
    返回: {"found": True/False, "results": [...], "message": "..."}
    """
    results = data_manager.search_device_by_name(device_name)
    if results:
        return {"found": True, "results": results, "message": f"找到 {len(results)} 条记录"}
    return {"found": False, "results": [], "message": "未找到匹配设备"}


def query_device_by_ip(ip: str) -> Dict:
    """按IP查询"""
    results = data_manager.search_device_by_ip(ip)
    if results:
        return {"found": True, "results": results, "message": f"找到 {len(results)} 条记录"}
    return {"found": False, "results": [], "message": "未找到匹配IP"}


def query_account_password(device_name: str) -> Dict:
    """
    隐藏功能：查询设备账号密码
    """
    results = data_manager.search_device_by_name(device_name)
    if not results:
        return {"found": False, "results": [], "message": "未找到设备"}

    secret_results = []

    for row in results:
        biz_name = row.get("_业务", "")
        account = row.get("登录账号", "") or row.get("账号", "")
        password = row.get("密码", "")
        method = row.get("登录方式", "")
        if account or password or method:
            secret_results.append({
                "_业务": biz_name,
                "设备名称": row.get("设备名称", ""),
                "登录账号": account,
                "登录密码": password,
                "登录方式": method,
            })

    loopbacks = data_manager.get_router_loopbacks()
    for lb in loopbacks:
        if lb.get("设备名称", "").strip() == device_name.strip():
            secret_results.append({
                    "_业务": "路由器Loopback",
                    "设备名称": lb.get("设备名称", ""),
                    "登录账号": lb.get("登录账号", ""),
                    "登录密码": lb.get("密码", ""),
                    "登录方式": lb.get("登录方式", ""),
            })

    if secret_results:
        return {"found": True, "results": secret_results, "message": "查询成功"}

    return {
        "found": True,
        "results": results,
        "message": "该设备未在路由器表中，请查看业务表数据"
    }


def update_router_loopback(device_name: str, updates: Dict) -> Dict:
    """更新路由器 loopback 信息"""
    success = data_manager.update_csv(config.ROUTER_LOOPBACK_FILE, "设备名称", device_name, updates)
    if success:
        return {"success": True, "message": f"{device_name} 修改成功"}
    return {"success": False, "message": f"未找到设备 {device_name}"}


def add_router_loopback(data: Dict) -> Dict:
    """新增路由器 loopback"""
    device_name = data.get("设备名称", "").strip()
    if not device_name:
        return {"success": False, "message": "设备名称不能为空"}
    existing = data_manager.read_csv(config.ROUTER_LOOPBACK_FILE)
    for row in existing:
        if row.get("设备名称", "").strip() == device_name:
            return {"success": False, "message": f"{device_name} 已存在"}
    columns = config.BUSINESS_COLUMNS["router_loopback"]
    new_row = {col: data.get(col, "") for col in columns}
    data_manager.append_csv(config.ROUTER_LOOPBACK_FILE, new_row, columns)
    return {"success": True, "message": f"{device_name} 添加成功"}


def add_router_link(data: Dict) -> Dict:
    """新增路由链路"""
    columns = config.BUSINESS_COLUMNS["router_link"]
    new_row = {col: data.get(col, "") for col in columns}
    data_manager.append_csv(config.ROUTER_LINK_FILE, new_row, columns)
    return {"success": True, "message": "链路添加成功"}


def update_router_link(local_device: str, local_interface: str, updates: Dict) -> Dict:
    """更新路由链路"""
    rows = data_manager.get_router_links()
    for row in rows:
        if row.get("本端设备名", "").strip() == local_device.strip() and \
           row.get("本端接口", "").strip() == local_interface.strip():
            row.update(updates)
            columns = config.BUSINESS_COLUMNS["router_link"]
            data_manager.write_csv(config.ROUTER_LINK_FILE, rows, columns)
            return {"success": True, "message": "链路修改成功"}
    return {"success": False, "message": "未找到匹配链路"}


def add_master_pool_row(data: Dict) -> Dict:
    """新增地址总表记录"""
    columns = config.BUSINESS_COLUMNS["master_pool"]
    new_row = {col: data.get(col, "") for col in columns}
    data_manager.append_csv(config.MASTER_POOL_FILE, new_row, columns)
    return {"success": True, "message": "地址总表记录添加成功"}


def batch_query_ips(ip_list: List[str]) -> List[Dict]:
    """
    批量查询 IP 归属
    输入: IP 地址列表 (支持单个IP 和 CIDR 段)
    返回: 每个IP的查询结果
    """
    all_devices = []
    for biz_name, file_path in config.BUSINESS_FILES.items():
        if not file_path.exists():
            continue
        for row in data_manager.read_csv(file_path):
            row["_业务"] = biz_name
            addr = row.get("地址段", "").strip()
            mask = row.get("掩码", "").strip()
            if addr:
                try:
                    if "/" in addr:
                        net = ipaddress.ip_network(addr, strict=False)
                    elif mask:
                        net = ipaddress.ip_network(f"{addr}/{mask}", strict=False)
                    else:
                        net = ipaddress.ip_network(f"{addr}/32", strict=False)
                    row["_network"] = net
                except ValueError:
                    row["_network"] = None
            else:
                row["_network"] = None
            all_devices.append(row)

    # 路由器 Loopback 表
    if config.ROUTER_LOOPBACK_FILE.exists():
        for row in data_manager.read_csv(config.ROUTER_LOOPBACK_FILE):
            row["_业务"] = "路由器Loopback"
            row["_networks"] = []
            for field in ("loopback0", "loopback1"):
                addr = row.get(field, "").strip()
                if addr:
                    try:
                        if "/" in addr:
                            net = ipaddress.ip_network(addr, strict=False)
                        else:
                            net = ipaddress.ip_network(f"{addr}/32", strict=False)
                        row["_networks"].append(net)
                    except ValueError:
                        pass
            all_devices.append(row)

    # 路由器链路表
    if config.ROUTER_LINK_FILE.exists():
        for row in data_manager.read_csv(config.ROUTER_LINK_FILE):
            row["_业务"] = "路由器链路"
            row["_networks"] = []
            for field in ("本端IP", "对端IP"):
                addr = row.get(field, "").strip()
                if addr:
                    try:
                        if "/" in addr:
                            net = ipaddress.ip_network(addr, strict=False)
                        else:
                            net = ipaddress.ip_network(f"{addr}/32", strict=False)
                        row["_networks"].append(net)
                    except ValueError:
                        pass
            all_devices.append(row)

    results = []
    for ip_str in ip_list:
        ip_str = ip_str.strip()
        if not ip_str:
            continue

        try:
            if "/" in ip_str:
                search_ip = ipaddress.ip_network(ip_str, strict=False).network_address
            else:
                search_ip = ipaddress.ip_address(ip_str)
        except ValueError:
            results.append({"查询IP": ip_str, "归属设备": "无效IP", "所属业务": "", "备注": "格式错误"})
            continue

        found = False
        for dev in all_devices:
            net = dev.get("_network")
            if net and search_ip in net:
                results.append({
                    "查询IP": ip_str,
                    "归属设备": dev.get("设备名称", dev.get("本端设备名", "")),
                    "所属业务": dev.get("_业务", ""),
                    "地址段": dev.get("地址段", ""),
                    "网关": dev.get("网关", ""),
                    "掩码": dev.get("掩码", ""),
                    "备注": "已分配"
                })
                found = True
                break
            nets = dev.get("_networks", [])
            for net in nets:
                if search_ip in net:
                    results.append({
                        "查询IP": ip_str,
                        "归属设备": dev.get("设备名称", dev.get("本端设备名", "")),
                        "所属业务": dev.get("_业务", ""),
                        "地址段": str(net),
                        "备注": "已分配"
                    })
                    found = True
                    break
            if found:
                break

        if not found:
            results.append({"查询IP": ip_str, "归属设备": "无归属", "所属业务": "", "备注": "未分配"})

    return results
