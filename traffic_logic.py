import os
import random
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# =====================================================
# OPENWEATHERMAP LIVE WEATHER IMPACT
# =====================================================

def get_weather(lat=18.5088, lon=73.9250):

    """
    Queries OpenWeatherMap Current Weather API for the corridor.
    Detects adverse weather conditions (rain, drizzle, storms, fog, snow)
    and computes a dynamic impact multiplier (1.15x - 1.25x) affecting braking/delays.
    Falls back safely to clear sky simulated conditions on any failure or missing key.
    """

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:

        return {
            "condition": "Clear",
            "description": "Clear Sky (Simulated)",
            "temp": 28.0,
            "impact_multiplier": 1.0,
            "is_live": False
        }

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

            return {
                "condition": condition,
                "description": description,
                "temp": temp,
                "impact_multiplier": impact_multiplier,
                "is_live": True
            }

    except Exception as error:

        print(f"[OpenWeatherMap API Warning] {error}")

    return {
        "condition": "Clear",
        "description": "Clear Sky (Simulated)",
        "temp": 28.0,
        "impact_multiplier": 1.0,
        "is_live": False
    }

# =====================================================
# TOMTOM LIVE TRAFFIC FLOW
# =====================================================

_tomtom_disabled_until_restart = False

def fetch_tomtom_flow(lat, lon, api_key):

    """
    Queries TomTom Traffic Flow API for a given coordinate point.
    Calculates congestion index c in [1, 10] using the speed drop ratio:
    (freeFlowSpeed - currentSpeed) / freeFlowSpeed.
    Returns None if the request fails, times out, or encounters errors.
    """

    global _tomtom_disabled_until_restart

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
# TRAFFIC GENERATION (LIVE + SAFE FALLBACK)
# =====================================================

def generate_traffic(
    G,
    node_coords=None,
    weather=None
):

    """
    Generates real-time traffic density for each road edge.
    Attempts live queries to TomTom Traffic Flow API at the midpoint of each road segment.
    Falls back gracefully to simulated values if TomTom is unreachable or unauthorized.
    Compounded with adverse weather multiplier if precipitation or fog is detected.
    """

    traffic = {}
    tomtom_key = os.getenv("TOMTOM_API_KEY")
    weather_multiplier = (
        weather.get("impact_multiplier", 1.0)
        if weather
        else 1.0
    )

    for edge in G.edges():

        u, v = edge
        congestion = None

        # Query midpoint if node coordinates and TomTom API key are provided
        if (
            node_coords
            and u in node_coords
            and v in node_coords
            and tomtom_key
        ):

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

        traffic[edge] = congestion

    return traffic

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
