import ipaddress
from typing import Dict, Iterable, List, Optional, Tuple, Union

import config
import data_manager


FIELD_BUSINESS = "\u4e1a\u52a1\u540d\u79f0"
FIELD_ADDRESS = "\u5730\u5740\u6bb5"
FIELD_MASK = "\u63a9\u7801"


Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def _get_first(row: Dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_network(address: str, mask: str = "") -> Optional[Network]:
    address = (address or "").strip()
    mask = (mask or "").strip().lstrip("/")
    if not address:
        return None

    try:
        if "/" in address:
            return ipaddress.ip_network(address, strict=False)
        if mask:
            return ipaddress.ip_network(f"{address}/{mask}", strict=False)
        return ipaddress.ip_network(f"{address}/32", strict=False)
    except ValueError:
        return None


def _parse_address_or_network(value: str) -> Optional[Union[Address, Network]]:
    value = (value or "").strip()
    if not value:
        return None

    try:
        if "/" in value:
            return ipaddress.ip_network(value, strict=False)
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _business_used_networks(biz_name: str) -> List[Network]:
    file_path = config.BUSINESS_FILES.get(biz_name)
    if not file_path or not file_path.exists():
        return []

    networks: List[Network] = []
    for row in data_manager.read_csv(file_path):
        network = _parse_network(
            _get_first(row, FIELD_ADDRESS),
            _get_first(row, FIELD_MASK),
        )
        if network is not None:
            networks.append(network)
    return networks


def _ranges_overlap(left: Tuple[int, int], right: Tuple[int, int]) -> bool:
    return left[0] <= right[1] and right[0] <= left[1]


def _network_range(network: Network) -> Tuple[int, int]:
    return int(network.network_address), int(network.broadcast_address)


def _dedupe_networks(networks: List[Network]) -> List[Network]:
    seen = set()
    result: List[Network] = []
    for network in networks:
        key = (network.version, int(network.network_address), network.prefixlen)
        if key in seen:
            continue
        seen.add(key)
        result.append(network)
    return result


def _preferred_pools_from_used(pools: List[Network], used_networks: List[Network]) -> List[Network]:
    preferred: List[Network] = []
    for pool in pools:
        if pool.version != 4:
            continue

        window_prefix = max(pool.prefixlen, 24)
        for used in used_networks:
            if used.version != pool.version:
                continue
            if not used.subnet_of(pool):
                continue

            local_pool = ipaddress.ip_network(
                f"{used.network_address}/{window_prefix}",
                strict=False,
            )
            if local_pool.subnet_of(pool):
                preferred.append(local_pool)

    return _dedupe_networks(preferred)


def _used_ranges(biz_name: str = "") -> List[Tuple[int, int]]:
    if biz_name:
        return [_network_range(network) for network in _business_used_networks(biz_name)]

    ranges: List[Tuple[int, int]] = []
    for name in config.BUSINESS_FILES:
        ranges.extend(_used_ranges(name))
    return ranges


def _candidate_pools(biz_name: str = "") -> List[Network]:
    pool_rows = data_manager.get_master_pool()
    named_pools: List[Network] = []
    all_pools: List[Network] = []

    for row in pool_rows:
        network = _parse_network(
            _get_first(row, FIELD_ADDRESS),
            _get_first(row, FIELD_MASK),
        )
        if network is None:
            continue

        all_pools.append(network)
        if biz_name and _get_first(row, FIELD_BUSINESS) == biz_name:
            named_pools.append(network)

    if named_pools:
        used_networks = _business_used_networks(biz_name)
        preferred = _preferred_pools_from_used(named_pools, used_networks)
        return preferred + named_pools

    if not biz_name:
        return all_pools

    used_networks = _business_used_networks(biz_name)
    if not used_networks:
        return all_pools

    inferred_pools: List[Network] = []
    for pool in all_pools:
        pool_range = _network_range(pool)
        if any(_ranges_overlap(pool_range, _network_range(used)) for used in used_networks):
            inferred_pools.append(pool)

    if not inferred_pools:
        return all_pools

    preferred = _preferred_pools_from_used(inferred_pools, used_networks)
    return preferred + inferred_pools


def _is_range_used(candidate: Tuple[int, int], used: List[Tuple[int, int]]) -> bool:
    return any(_ranges_overlap(candidate, item) for item in used)


def get_network_range(network_str: str) -> Tuple[int, int]:
    network = _parse_network(network_str)
    if network is None:
        raise ValueError(f"Invalid network: {network_str}")
    return _network_range(network)


def get_available_ips(biz_name: str, count: int = 10) -> Dict:
    pools = _candidate_pools(biz_name)
    if not pools:
        return {
            "success": False,
            "available": [],
            "message": "\u5730\u5740\u603b\u8868\u4e3a\u7a7a\uff0c\u6216\u672a\u627e\u5230\u53ef\u7528\u5730\u5740\u6c60",
        }

    used = _used_ranges(biz_name)
    available: List[str] = []

    for pool in pools:
        for address in pool.hosts():
            if len(available) >= count:
                break
            point = int(address)
            if not _is_range_used((point, point), used):
                available.append(str(address))
        if len(available) >= count:
            break

    return {
        "success": True,
        "available": available,
        "message": (
            f"\u627e\u5230 {len(available)} \u4e2a\u7a7a\u95f2IP"
            if available
            else "\u672a\u627e\u5230\u7a7a\u95f2IP"
        ),
    }


def _get_available_subnets(biz_name: str, count: int, subnet_mask: int) -> Dict:
    pools = _candidate_pools(biz_name)
    if not pools:
        return {
            "success": False,
            "allocated": [],
            "message": "\u5730\u5740\u603b\u8868\u4e3a\u7a7a\uff0c\u6216\u672a\u627e\u5230\u53ef\u7528\u5730\u5740\u6c60",
        }

    used = _used_ranges(biz_name)
    allocated: List[str] = []

    for pool in pools:
        if subnet_mask < pool.prefixlen:
            continue

        for subnet in pool.subnets(new_prefix=subnet_mask):
            if len(allocated) >= count:
                break
            if not _is_range_used(_network_range(subnet), used):
                allocated.append(str(subnet))

        if len(allocated) >= count:
            break

    if not allocated:
        return {
            "success": False,
            "allocated": [],
            "message": "\u672a\u627e\u5230\u7a7a\u95f2IP",
        }

    if len(allocated) < count:
        return {
            "success": False,
            "allocated": [],
            "message": f"\u7a7a\u95f2\u5730\u5740\u4e0d\u8db3\uff0c\u4ec5\u627e\u5230 {len(allocated)} \u4e2a",
        }

    return {
        "success": True,
        "allocated": allocated,
        "message": f"\u6210\u529f\u5206\u914d {len(allocated)} \u4e2a\u5730\u5740\u5757",
    }


def allocate_ips(biz_name: str, count: int, subnet_mask: int = 32) -> Dict:
    if count <= 0:
        return {
            "success": False,
            "allocated": [],
            "message": "\u7533\u8bf7\u6570\u91cf\u5fc5\u987b\u5927\u4e8e0",
        }

    if subnet_mask < 32:
        return _get_available_subnets(biz_name, count, subnet_mask)

    result = get_available_ips(biz_name, count)
    if not result["success"] or not result["available"]:
        return {"success": False, "allocated": [], "message": result["message"]}

    if len(result["available"]) < count:
        return {
            "success": False,
            "allocated": [],
            "message": f"\u7a7a\u95f2IP\u4e0d\u8db3\uff0c\u4ec5\u627e\u5230 {len(result['available'])} \u4e2a",
        }

    allocated = result["available"][:count]
    return {
        "success": True,
        "allocated": allocated,
        "message": f"\u6210\u529f\u5206\u914d {len(allocated)} \u4e2aIP",
    }
