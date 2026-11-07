import os
import math
import networkx as nx
import osmnx as ox

# =====================================================
# PUNE CITY-WIDE ROAD NETWORK GRAPH
# =====================================================

GRAPHML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "pune_drive_network.graphml"
)

_GRAPH_CACHE = None
EARTH_RADIUS_M = 6371000.0  # Earth radius in meters

def create_graph(graphml_path=None):
    """
    Loads the Pune city-wide road network from GraphML into memory
    as an nx.MultiDiGraph. Caches the loaded graph in memory for fast access.
    """
    global _GRAPH_CACHE

    if _GRAPH_CACHE is not None and graphml_path is None:
        return _GRAPH_CACHE

    target_path = graphml_path or GRAPHML_PATH
    if not os.path.exists(target_path):
        if os.path.exists(target_path + ".gz"):
            target_path = target_path + ".gz"
        elif target_path.endswith(".gz") and os.path.exists(target_path[:-3]):
            target_path = target_path[:-3]
        else:
            alt_gz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pune_drive_network.graphml.gz")
            if os.path.exists(alt_gz):
                target_path = alt_gz
            else:
                raise FileNotFoundError(
                    f"GraphML file not found at: {target_path} (or {target_path}.gz). "
                    "Please run 'python scripts/build_pune_graph.py' to generate it."
                )

    print(f"Loading Pune city road network from {target_path}...")
    G = ox.load_graphml(target_path)

    # Validate that G is nx.MultiDiGraph
    if not isinstance(G, nx.MultiDiGraph):
        G = nx.MultiDiGraph(G)

    # Ensure all edges have length, travel_time, and base_weight
    for u, v, k, data in G.edges(keys=True, data=True):
        if "length" not in data or data["length"] is None:
            data["length"] = 50.0
        else:
            data["length"] = float(data["length"])

        if "travel_time" not in data or data["travel_time"] is None:
            length = data["length"]
            speed_mps = (float(data.get("speed_kph", 30.0)) * 1000.0) / 3600.0
            data["travel_time"] = round(length / max(speed_mps, 1.0), 2)
        else:
            data["travel_time"] = float(data["travel_time"])

        data["base_weight"] = data["length"]
        data["weight"] = data["length"]

    if graphml_path is None:
        _GRAPH_CACHE = G

    return G

# =====================================================
# HAVERSINE DISTANCE HEURISTIC (FOR A* SEARCH)
# =====================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes great-circle distance between two GPS coordinates in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c

def make_haversine_heuristic(G, weight="length"):
    """
    Factory creating an admissible Haversine heuristic function for nx.astar_path.
    If weight is 'travel_time', divides distance by max velocity (~100 km/h = 27.78 m/s).
    """
    nodes = G.nodes

    if weight in ("travel_time", "dynamic_weight"):
        max_speed_mps = 27.78  # 100 km/h upper bound
        def heuristic(u, v):
            u_d = nodes[u]
            v_d = nodes[v]
            lat1, lon1 = u_d["y"], u_d["x"]
            lat2, lon2 = v_d["y"], v_d["x"]
            p1 = math.radians(lat1)
            p2 = math.radians(lat2)
            dp = math.radians(lat2 - lat1)
            dl = math.radians(lon2 - lon1)
            a = (
                math.sin(dp / 2.0) ** 2
                + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
            )
            dist_m = EARTH_RADIUS_M * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            return dist_m / max_speed_mps
        return heuristic
    else:
        def heuristic(u, v):
            u_d = nodes[u]
            v_d = nodes[v]
            lat1, lon1 = u_d["y"], u_d["x"]
            lat2, lon2 = v_d["y"], v_d["x"]
            p1 = math.radians(lat1)
            p2 = math.radians(lat2)
            dp = math.radians(lat2 - lat1)
            dl = math.radians(lon2 - lon1)
            a = (
                math.sin(dp / 2.0) ** 2
                + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
            )
            return EARTH_RADIUS_M * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return heuristic

def haversine_heuristic(u, v, G=None):
    """
    Standard Haversine heuristic between two nodes in G.
    """
    target_graph = G if G is not None else _GRAPH_CACHE
    if target_graph is None:
        raise ValueError("Graph must be provided or initialized via create_graph()")
    u_d = target_graph.nodes[u]
    v_d = target_graph.nodes[v]
    return haversine_distance(
        float(u_d["y"]), float(u_d["x"]),
        float(v_d["y"]), float(v_d["x"])
    )

# =====================================================
# DYNAMIC TRAFFIC COST CALCULATION
# =====================================================

def calculate_dynamic_cost(base_weight, congestion):
    """
    Combines base road cost with quadratic congestion penalty:
    dynamic_cost = base_weight * (1 + 0.15 * congestion^2)
    """
    return round(base_weight * (1 + 0.15 * (congestion ** 2)), 2)

def apply_dynamic_weights(G, traffic):
    """
    Updates graph edge weights dynamically based on traffic density.
    Higher congestion significantly increases the traversal cost.
    """
    for u, v, k, data in G.edges(keys=True, data=True):
        base_weight = data.get("base_weight", data.get("length", 1.0))
        congestion = traffic.get(
            (u, v),
            traffic.get((v, u), 1)
        )
        dyn_cost = calculate_dynamic_cost(base_weight, congestion)
        data["weight"] = dyn_cost
        data["dynamic_weight"] = dyn_cost
        data["congestion"] = congestion

# =====================================================
# PATHFINDING: A* SEARCH WITH HAVERSINE HEURISTIC
# =====================================================

def shortest_path(G, source, destination, traffic=None, weight="length"):
    """
    Computes optimal path between source and destination nodes using A* search
    guided by an admissible Haversine distance heuristic.
    Replaces standard Dijkstra for accelerated performance on city-wide graphs.
    """
    try:
        if traffic is not None:
            apply_dynamic_weights(G, traffic)
            weight_attr = "dynamic_weight"
        else:
            weight_attr = weight

        heuristic_fn = make_haversine_heuristic(G, weight=weight_attr)

        path = nx.astar_path(
            G,
            source=source,
            target=destination,
            heuristic=heuristic_fn,
            weight=weight_attr
        )
        return path
    except nx.NetworkXNoPath:
        return None
    except Exception as error:
        print(f"[Graph A* Path Error]: {error}")
        return None

# =====================================================
# PATH COST
# =====================================================

def path_cost(G, path, weight="weight"):
    """
    Calculates total cost along a path sequence.
    """
    try:
        total = 0.0
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            edge_data = G.get_edge_data(u, v)
            if edge_data:
                min_w = min(
                    d.get(weight, d.get("length", 1.0))
                    for d in edge_data.values()
                )
                total += min_w
        return round(total, 2)
    except Exception:
        return 0.0

if __name__ == "__main__":
    G = create_graph()
    print(f"Loaded Pune Graph: Type={type(G)}, Nodes={len(G.nodes):,}, Edges={len(G.edges):,}")
