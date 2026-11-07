import os
import random
import requests
from dotenv import load_dotenv
from cachetools import TTLCache

# Load environment variables from .env
load_dotenv()

# =====================================================
# OPENWEATHERMAP LIVE WEATHER IMPACT & ZONAL CACHING
# =====================================================

# 15-minute TTL cache (900 seconds) for up to 1000 coordinate zones
_weather_cache = TTLCache(maxsize=1000, ttl=900)
_owm_call_log = []

def get_zone_key(lat, lon):
    """
    Rounds latitude and longitude to 2 decimal places to create a zonal key.
    E.g. (18.5018, 73.8584) -> (18.50, 73.86)
    """
    return (round(float(lat), 2), round(float(lon), 2))

def get_weather_cache():
    return _weather_cache

def reset_weather_cache():
    _weather_cache.clear()

def get_owm_call_log():
    return list(_owm_call_log)

def reset_owm_call_log():
    global _owm_call_log
    _owm_call_log = []

def get_weather(lat=18.5088, lon=73.9250):

    """
    Queries OpenWeatherMap Current Weather API for the corridor zone.
    Uses a TTLCache with a 15-minute TTL keyed by coordinate zone
    (lat/lon rounded to 2 decimal places) to eliminate redundant external calls.
    Detects adverse weather conditions (rain, drizzle, storms, fog, snow)
    and computes a dynamic impact multiplier (1.15x - 1.25x) affecting braking/delays.
    Falls back safely to clear sky simulated conditions on any failure or missing key.
    """

    zone_key = get_zone_key(lat, lon)

    # Return cached zonal weather if still within the 15-minute TTL
    if zone_key in _weather_cache:
        cached_result = dict(_weather_cache[zone_key])
        cached_result["cached"] = True
        return cached_result

    # Record API call attempt in the audit log
    _owm_call_log.append({
        "lat": lat,
        "lon": lon,
        "zone_key": zone_key
    })

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:

        fallback = {
            "condition": "Clear",
            "description": "Clear Sky (Simulated)",
            "temp": 28.0,
            "impact_multiplier": 1.0,
            "is_live": False,
            "zone_key": list(zone_key),
            "cached": False
        }
        _weather_cache[zone_key] = fallback
        return fallback

    try:

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )

        response = requests.get(url, timeout=3.5)

        if response.status_code == 200:

            data = response.json()
            weather_list = data.get("weather", [])
            weather_entry = weather_list[0] if weather_list else {}

            condition = weather_entry.get("main", "Clear")
            description = weather_entry.get(
                "description",
                "clear sky"
            ).capitalize()

            temp = round(
                data.get("main", {}).get("temp", 28.0),
                1
            )

            # Adverse precipitation / atmosphere conditions
            adverse_set = {
                "rain",
                "drizzle",
                "thunderstorm",
                "snow",
                "fog",
                "mist"
            }

            is_adverse = condition.lower() in adverse_set

            # 1.20x modifier during adverse weather events
            impact_multiplier = 1.20 if is_adverse else 1.0

            result = {
                "condition": condition,
                "description": description,
                "temp": temp,
                "impact_multiplier": impact_multiplier,
                "is_live": True,
                "zone_key": list(zone_key),
                "cached": False
            }
            _weather_cache[zone_key] = result
            return result

    except Exception as error:

        print(f"[OpenWeatherMap API Warning] {error}")

    fallback = {
        "condition": "Clear",
        "description": "Clear Sky (Simulated)",
        "temp": 28.0,
        "impact_multiplier": 1.0,
        "is_live": False,
        "zone_key": list(zone_key),
        "cached": False
    }
    _weather_cache[zone_key] = fallback
    return fallback

# =====================================================
# TOMTOM LIVE TRAFFIC FLOW & CALL LOGGING
# =====================================================

_tomtom_disabled_until_restart = False
_tomtom_call_log = []
_targeted_polled_edges = []

def get_tomtom_call_log():
    return list(_tomtom_call_log)

def reset_tomtom_call_log():
    global _tomtom_call_log
    _tomtom_call_log = []

def get_targeted_polled_edges():
    return list(_targeted_polled_edges)

def reset_targeted_polled_edges():
    global _targeted_polled_edges
    _targeted_polled_edges = []

def fetch_tomtom_flow(lat, lon, api_key):

    """
    Queries TomTom Traffic Flow API for a given coordinate point.
    Calculates congestion index c in [1, 10] using the speed drop ratio:
    (freeFlowSpeed - currentSpeed) / freeFlowSpeed.
    Returns None if the request fails, times out, or encounters errors.
    """

    global _tomtom_disabled_until_restart, _tomtom_call_log

    # Log every single call attempt to TomTom
    _tomtom_call_log.append({
        "lat": lat,
        "lon": lon
    })

    if _tomtom_disabled_until_restart:

        return None

    try:

        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point={lat},{lon}&key={api_key}"
        )

        response = requests.get(url, timeout=2.5)

        if response.status_code == 200:

            data = response.json().get("flowSegmentData", {})
            current_speed = data.get("currentSpeed", 0)
            free_flow_speed = data.get("freeFlowSpeed", 0)

            if free_flow_speed > 0:

                speed_drop = max(
                    0.0,
                    min(
                        1.0,
                        (free_flow_speed - current_speed) / free_flow_speed
                    )
                )

                # Linear mapping: speed_drop 0.0 -> 1, 1.0 -> 10
                congestion = max(
                    1,
                    min(10, int(round(1 + 9 * speed_drop)))
                )

                return congestion

        elif response.status_code in (401, 403):

            # Avoid repeated failing network roundtrips for all edges
            _tomtom_disabled_until_restart = True

    except Exception as error:

        print(f"[TomTom Flow Warning] {error}")

    return None

# =====================================================
# TRAFFIC GENERATION (TWO-TIER TARGETED POLLING)
# =====================================================

def generate_traffic(
    G,
    edges=None,
    node_coords=None,
    weather=None
):

    """
    Generates real-time traffic density strictly for specified edges.
    Guards against polling all 320,000+ edges in the city grid.
    Queries TomTom live flow at road midpoints with simulated fallback.
    """
    global _targeted_polled_edges

    traffic = {}
    tomtom_key = os.getenv("TOMTOM_API_KEY")
    weather_multiplier = (
        weather.get("impact_multiplier", 1.0)
        if weather
        else 1.0
    )

    if edges is None:
        if hasattr(G, "edges") and len(G.edges) > 500:
            print("[Rate-Limit Guard]: Refusing to query TomTom for all 320,000+ edges on city-wide grid. Pass explicit edges.")
            return {}
        edge_list = G.edges()
    else:
        edge_list = edges

    for edge in edge_list:

        u, v = edge[0], edge[1]
        _targeted_polled_edges.append((u, v))
        congestion = None

        # Query midpoint if node coordinates and TomTom API key are provided
        if node_coords and u in node_coords and v in node_coords and tomtom_key:

            mid_lat = (
                node_coords[u][0] + node_coords[v][0]
            ) / 2.0

            mid_lon = (
                node_coords[u][1] + node_coords[v][1]
            ) / 2.0

            congestion = fetch_tomtom_flow(
                mid_lat,
                mid_lon,
                tomtom_key
            )
        elif hasattr(G, "nodes") and u in G.nodes and v in G.nodes and tomtom_key:
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            if "y" in u_data and "x" in u_data and "y" in v_data and "x" in v_data:
                mid_lat = (u_data["y"] + v_data["y"]) / 2.0
                mid_lon = (u_data["x"] + v_data["x"]) / 2.0
                congestion = fetch_tomtom_flow(mid_lat, mid_lon, tomtom_key)

        # Fallback to simulated congestion
        if congestion is None:

            congestion = random.randint(1, 10)

        # Apply weather modifier if adverse weather is active
        if weather_multiplier > 1.0:

            congestion = max(
                1,
                min(
                    10,
                    int(round(congestion * weather_multiplier))
                )
            )

        traffic[(u, v)] = congestion

    return traffic

# =====================================================
# DYNAMIC PENALTIES & TWO-TIER TARGETED ROUTING
# =====================================================

def apply_targeted_penalties(G, candidate_edges, traffic):
    """
    Applies quadratic congestion penalty to targeted candidate edges:
    dynamic_cost = base_weight * (1 + 0.15 * congestion^2)
    """
    for u, v in candidate_edges:
        congestion = traffic.get((u, v), traffic.get((v, u), 1))
        edge_dict = G.get_edge_data(u, v)
        if edge_dict:
            for k, data in edge_dict.items():
                base_cost = data.get("base_weight", data.get("travel_time", data.get("length", 1.0)))
                dyn_cost = round(base_cost * (1 + 0.15 * (congestion ** 2)), 2)
                data["dynamic_weight"] = dyn_cost
                data["congestion"] = congestion

def two_tier_traffic_routing(
    G,
    src_node,
    dst_node,
    weather=None,
    congestion_reroute_threshold=6
):
    """
    Two-Tier Targeted TomTom Routing:
    Tier 1: Compute candidate path via A* using baseline travel_time.
    Tier 2: Poll TomTom live flow ONLY for the candidate path edges (~50-100 edges).
    Penalize candidate edges and rerun A* on dynamic weights if alternate routing is beneficial.
    """
    from graph import shortest_path

    # Tier 1: Baseline candidate route via A* (travel_time)
    candidate_path = shortest_path(G, src_node, dst_node, weight="travel_time")
    if not candidate_path:
        return None, None, {}, False

    candidate_edges = [
        (candidate_path[i], candidate_path[i + 1])
        for i in range(len(candidate_path) - 1)
    ]

    # Tier 2: Targeted polling ONLY for candidate edges
    traffic = generate_traffic(G, edges=candidate_edges, weather=weather)

    # Apply dynamic penalties to the candidate segments in the graph
    apply_targeted_penalties(G, candidate_edges, traffic)

    # Check if alternate routing is needed (e.g. heavy congestion detected)
    has_heavy_congestion = any(
        traffic.get(e, 1) >= congestion_reroute_threshold
        for e in candidate_edges
    )

    final_path = candidate_path
    rerouted = False

    if has_heavy_congestion:
        alternate_path = shortest_path(G, src_node, dst_node, weight="dynamic_weight")
        if alternate_path and alternate_path != candidate_path:
            final_path = alternate_path
            rerouted = True
            # Fetch traffic for any new edges introduced in the alternate route
            alt_edges = [
                (final_path[i], final_path[i + 1])
                for i in range(len(final_path) - 1)
                if (final_path[i], final_path[i + 1]) not in traffic
            ]
            if alt_edges:
                alt_traffic = generate_traffic(G, edges=alt_edges, weather=weather)
                traffic.update(alt_traffic)

    return final_path, candidate_path, traffic, rerouted



# =====================================================
# GREEDY DYNAMIC SIGNAL SELECTION
# =====================================================

def dynamic_signal(
    node,
    G,
    traffic
):

    """
    Greedy approach:
    Select edge with highest congestion around current node.
    This signal gets highest green light priority.
    """

    connected_edges = []

    for neighbor in G.neighbors(node):

        edge = (node, neighbor)
        reverse_edge = (neighbor, node)

        if edge in traffic:

            connected_edges.append(edge)

        elif reverse_edge in traffic:

            connected_edges.append(reverse_edge)

    if not connected_edges:

        return None

    # Greedy choice: maximum congestion among incident edges
    best_edge = max(
        connected_edges,
        key=lambda e: traffic[e]
    )

    return best_edge

# =====================================================
# DYNAMIC GREEN SIGNAL TIME
# =====================================================

def dynamic_time(traffic_value):

    """
    Dynamically allocate green signal timing based on congestion.
    More congestion = longer green clearance duration.
    """

    base_time = 5
    extension = traffic_value * 2

    return base_time + extension

# =====================================================
# DELAY CALCULATION & MODE COMPARISON
# =====================================================

def calculate_segment_delay(
    congestion,
    mode="dynamic",
    weather_modifier=1.0
):

    """
    Computes realistic intersection delay (in seconds) based on congestion (1-10)
    and adverse weather braking modifier.
    Higher congestion strictly increases delay in both modes.
    """

    if mode == "fixed":

        base_delay = 15.0 + 4.5 * congestion

    else:

        base_delay = 8.0 + 1.8 * congestion

    return round(base_delay * weather_modifier, 2)

def compare_modes(
    path,
    traffic,
    weather_modifier=1.0
):

    """
    Compare fixed signal system vs dynamic greedy system along the given path.
    Includes adverse weather multiplier on delay calculations.
    """

    fixed_total = 0.0
    dynamic_total = 0.0

    for i in range(len(path) - 1):

        edge = (
            path[i],
            path[i + 1]
        )

        reverse_edge = (
            path[i + 1],
            path[i]
        )

        if edge in traffic:

            congestion = traffic[edge]

        else:

            congestion = traffic.get(
                reverse_edge,
                5
            )

        fixed_delay = calculate_segment_delay(
            congestion,
            mode="fixed",
            weather_modifier=weather_modifier
        )

        dynamic_delay = calculate_segment_delay(
            congestion,
            mode="dynamic",
            weather_modifier=weather_modifier
        )

        fixed_total += fixed_delay
        dynamic_total += dynamic_delay

    fixed_total = round(fixed_total, 2)
    dynamic_total = round(dynamic_total, 2)

    if fixed_total == 0:

        efficiency = 0

    else:

        efficiency = round(
            (
                (fixed_total - dynamic_total)
                / fixed_total
            ) * 100,
            2
        )

    return {
        "fixed": fixed_total,
        "dynamic": dynamic_total,
        "efficiency": efficiency
    }

# =====================================================
# OPTIONAL DEBUG
# =====================================================

if __name__ == "__main__":

    from graph import create_graph

    graph = create_graph()
    weather_sample = get_weather()
    print("Weather:", weather_sample)

    coords = {
        "Hadapsar_Main": (18.5088, 73.9250),
        "Gadital_Chowk": (18.5015, 73.9384),
        "FatimaNagar_Junction": (18.5097, 73.9018),
        "Magarpatta_Junction": (18.5164, 73.9320),
        "Amanora_Entry": (18.5186, 73.9365)
    }

    traffic_data = generate_traffic(
        graph,
        node_coords=coords,
        weather=weather_sample
    )

    print("\n===== TRAFFIC DENSITY =====")

    for edge, value in traffic_data.items():

        print(edge, "->", value)

    sample_path = [
        "Magarpatta_Junction",
        "Gadital_Chowk"
    ]

    result = compare_modes(
        sample_path,
        traffic_data,
        weather_modifier=weather_sample["impact_multiplier"]
    )

    print("\n===== COMPARISON =====")
    print(result)
