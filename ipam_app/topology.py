import math
from typing import Dict, List, Optional, Tuple

import config
import data_manager

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


FONT_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
]


def _configure_plot_style() -> None:
    if not HAS_MATPLOTLIB:
        return
    plt.rcParams["font.sans-serif"] = FONT_CANDIDATES
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "#f7fafc"
    plt.rcParams["axes.facecolor"] = "#f7fafc"


def _wrap_label(text: str, width: int = 8) -> str:
    text = (text or "").strip()
    if len(text) <= width:
        return text
    return "\n".join(text[i:i + width] for i in range(0, len(text), width))


def _component_layout(component: "nx.Graph", seed: int) -> Dict[str, Tuple[float, float]]:
    size = component.number_of_nodes()
    if size == 1:
        node = next(iter(component.nodes()))
        return {node: (0.0, 0.0)}
    if size <= 4:
        return nx.circular_layout(component, scale=1.0)
    if size <= 12:
        return nx.kamada_kawai_layout(component)
    if size > 20:
        return _hub_component_layout(component)
    return nx.spring_layout(component, seed=seed, k=max(1.2, 2.8 / math.sqrt(size)), iterations=300)


def _hub_component_layout(component: "nx.Graph") -> Dict[str, Tuple[float, float]]:
    degrees = sorted(component.degree(), key=lambda item: (-item[1], item[0]))
    core_nodes = [node for node, _ in degrees[: min(4, len(degrees))]]
    positions: Dict[str, Tuple[float, float]] = {}

    if len(core_nodes) == 1:
        positions[core_nodes[0]] = (0.0, 0.0)
    else:
        core_circle = nx.circular_layout(component.subgraph(core_nodes), scale=1.2)
        for node, point in core_circle.items():
            positions[node] = (float(point[0]), float(point[1]))

    distances = nx.multi_source_dijkstra_path_length(component, core_nodes)
    layers: Dict[int, List[str]] = {}
    for node in component.nodes():
        if node in positions:
            continue
        layer = max(1, int(distances.get(node, 1)))
        layers.setdefault(layer, []).append(node)

    for layer, nodes in sorted(layers.items()):
        nodes.sort()
        radius = 2.3 + (layer - 1) * 1.9
        count = len(nodes)
        for idx, node in enumerate(nodes):
            angle = (2 * math.pi * idx / max(count, 1)) + (layer * 0.35)
            positions[node] = (radius * math.cos(angle), radius * math.sin(angle))

    return positions


def _pack_component_positions(G: "nx.Graph") -> Dict[str, Tuple[float, float]]:
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    if not components:
        return {}

    columns = 2 if len(components) > 1 else 1
    cell_width = 8.0
    cell_height = 6.0
    positions: Dict[str, Tuple[float, float]] = {}

    for idx, nodes in enumerate(components):
        subgraph = G.subgraph(nodes).copy()
        local_pos = _component_layout(subgraph, seed=42 + idx)

        xs = [point[0] for point in local_pos.values()]
        ys = [point[1] for point in local_pos.values()]
        center_x = (min(xs) + max(xs)) / 2 if xs else 0.0
        center_y = (min(ys) + max(ys)) / 2 if ys else 0.0

        col = idx % columns
        row = idx // columns
        offset_x = col * cell_width
        offset_y = -row * cell_height

        for node, (x, y) in local_pos.items():
            positions[node] = (x - center_x + offset_x, y - center_y + offset_y)

    return positions


def _node_sizes(G: "nx.Graph") -> List[float]:
    sizes = []
    for node in G.nodes():
        degree = G.degree(node)
        sizes.append(620 + min(degree, 12) * 95)
    return sizes


def _label_positions(pos: Dict[str, Tuple[float, float]], G: "nx.Graph") -> Dict[str, Tuple[float, float]]:
    label_pos = {}
    for node, (x, y) in pos.items():
        radius = math.sqrt((x * x) + (y * y))
        offset = 0.22 + min(G.degree(node), 10) * 0.012
        if radius < 0.001:
            label_pos[node] = (x, y + offset)
        else:
            label_pos[node] = (x + (x / radius) * offset, y + (y / radius) * offset)
    return label_pos


def build_topology_graph() -> Optional["nx.Graph"]:
    if not HAS_NETWORKX:
        return None

    links = data_manager.get_router_links()
    if not links:
        return None

    G = nx.Graph()
    for link in links:
        local = link.get("本端设备名", "").strip()
        remote = link.get("对端设备名", "").strip()
        cost_str = link.get("cost", "1").strip()
        try:
            cost = int(cost_str) if cost_str else 1
        except ValueError:
            cost = 1

        if local and remote:
            G.add_edge(
                local,
                remote,
                weight=cost,
                local_ip=link.get("本端IP", ""),
                remote_ip=link.get("对端IP", ""),
                local_intf=link.get("本端接口", ""),
                remote_intf=link.get("对端接口", ""),
            )

    return G if G.number_of_nodes() > 0 else None


def generate_topology_image() -> Dict:
    if not HAS_NETWORKX or not HAS_MATPLOTLIB:
        return {"success": False, "path": "", "message": "缺少 networkx 或 matplotlib"}

    G = build_topology_graph()
    if G is None:
        return {"success": False, "path": "", "message": "没有链路数据"}

    _configure_plot_style()
    fig, ax = plt.subplots(figsize=(24, 18), dpi=160)
    pos = _pack_component_positions(G)

    nx.draw_networkx_edges(
        G,
        pos,
        width=1.35,
        alpha=0.42,
        edge_color="#64748b",
        ax=ax,
    )
    nx.draw_networkx_nodes(
        G,
        pos,
        node_color="#b9e3f5",
        node_size=_node_sizes(G),
        edgecolors="#0f172a",
        linewidths=1.0,
        ax=ax,
    )
    nx.draw_networkx_labels(
        G,
        _label_positions(pos, G),
        labels={node: _wrap_label(node, 6) for node in G.nodes()},
        font_size=7,
        font_weight="bold",
        bbox={"facecolor": "#f8fafc", "edgecolor": "none", "alpha": 0.82, "pad": 0.12},
        ax=ax,
    )

    ax.set_title("路由器拓扑图", fontsize=18, fontweight="bold", pad=18)
    ax.text(
        0.01,
        0.015,
        "全量拓扑默认隐藏链路 IP 标签，避免图面过度拥挤。",
        transform=ax.transAxes,
        fontsize=9,
        color="#475569",
    )
    ax.axis("off")
    fig.tight_layout()

    config.TOPOLOGY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(config.TOPOLOGY_OUTPUT), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return {"success": True, "path": str(config.TOPOLOGY_OUTPUT), "message": "拓扑图生成成功"}


def analyze_path(source: str, target: str) -> Dict:
    if not HAS_NETWORKX:
        return {"success": False, "primary": [], "backup": [], "message": "缺少 networkx 依赖"}

    G = build_topology_graph()
    if G is None:
        return {"success": False, "primary": [], "backup": [], "message": "没有链路数据"}

    if source not in G or target not in G:
        missing = []
        if source not in G:
            missing.append(source)
        if target not in G:
            missing.append(target)
        return {"success": False, "primary": [], "backup": [], "message": f"设备不存在: {', '.join(missing)}"}

    if source == target:
        return {"success": True, "primary": [source], "backup": [], "message": "源和目标设备相同"}

    try:
        primary_path = nx.shortest_path(G, source=source, target=target, weight="weight")
    except nx.NetworkXNoPath:
        return {"success": False, "primary": [], "backup": [], "message": f"{source} 到 {target} 不存在路径"}

    backup_path: List[str] = []
    if len(primary_path) > 2:
        H = G.copy()
        for u, v in zip(primary_path[:-1], primary_path[1:]):
            if H.has_edge(u, v):
                H.remove_edge(u, v)
        try:
            backup_path = nx.shortest_path(H, source=source, target=target, weight="weight")
        except nx.NetworkXNoPath:
            pass

    primary_cost = sum(G[u][v].get("weight", 1) for u, v in zip(primary_path[:-1], primary_path[1:]))
    backup_cost = (
        sum(G[u][v].get("weight", 1) for u, v in zip(backup_path[:-1], backup_path[1:]))
        if backup_path else None
    )

    return {
        "success": True,
        "primary": primary_path,
        "primary_cost": primary_cost,
        "backup": backup_path,
        "backup_cost": backup_cost,
        "message": "路径分析成功",
    }


def generate_path_image(source: str, target: str) -> Dict:
    if not HAS_NETWORKX or not HAS_MATPLOTLIB:
        return {"success": False, "path": "", "message": "缺少 networkx 或 matplotlib"}

    analysis = analyze_path(source, target)
    if not analysis["success"]:
        return {"success": False, "path": "", "message": analysis["message"]}

    G = build_topology_graph()
    if G is None:
        return {"success": False, "path": "", "message": "没有链路数据"}

    primary_path = analysis["primary"]
    backup_path = analysis.get("backup", [])
    primary_edges = list(zip(primary_path[:-1], primary_path[1:]))
    backup_edges = list(zip(backup_path[:-1], backup_path[1:])) if backup_path else []

    _configure_plot_style()
    fig, ax = plt.subplots(figsize=(18, 12), dpi=160)
    pos = _pack_component_positions(G)

    highlighted = set(primary_edges + backup_edges + [(v, u) for u, v in primary_edges + backup_edges])
    other_edges = [edge for edge in G.edges() if edge not in highlighted]

    nx.draw_networkx_edges(
        G, pos, edgelist=other_edges, width=1.4, alpha=0.22, edge_color="#94a3b8", ax=ax
    )
    if primary_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=primary_edges, width=3.0, alpha=0.95, edge_color="#16a34a", ax=ax
        )
    if backup_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=backup_edges, width=3.0, alpha=0.9, style="dashed", edge_color="#f59e0b", ax=ax
        )

    path_nodes = set(primary_path + backup_path)
    other_nodes = [node for node in G.nodes() if node not in path_nodes]
    primary_mid_nodes = [node for node in primary_path if node not in (source, target)]
    backup_only_nodes = [node for node in backup_path if node not in primary_path and node not in (source, target)]

    nx.draw_networkx_nodes(G, pos, nodelist=other_nodes, node_color="#dbe4ee", node_size=900, edgecolors="#94a3b8", ax=ax)
    if backup_only_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=backup_only_nodes, node_color="#fde68a", node_size=1100, edgecolors="#b45309", ax=ax)
    if primary_mid_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=primary_mid_nodes, node_color="#bbf7d0", node_size=1150, edgecolors="#15803d", ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=[source], node_color="#22c55e", node_size=1500, edgecolors="#166534", ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=[target], node_color="#ef4444", node_size=1500, edgecolors="#991b1b", ax=ax)

    shown_nodes = set(other_nodes + backup_only_nodes + primary_mid_nodes + [source, target])
    nx.draw_networkx_labels(
        G,
        _label_positions(pos, G),
        labels={node: _wrap_label(node, 6) for node in shown_nodes},
        font_size=8,
        font_weight="bold",
        bbox={"facecolor": "#f8fafc", "edgecolor": "none", "alpha": 0.78, "pad": 0.2},
        ax=ax,
    )

    ax.set_title(f"路径分析: {source} -> {target}", fontsize=18, fontweight="bold", pad=18)
    ax.axis("off")
    fig.tight_layout()

    config.PATH_ANALYSIS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(config.PATH_ANALYSIS_OUTPUT), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return {"success": True, "path": str(config.PATH_ANALYSIS_OUTPUT), "message": "路径图生成成功"}
