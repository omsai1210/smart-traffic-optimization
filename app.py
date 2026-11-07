import os
from flask import Flask, render_template, request, jsonify
import requests
import osmnx as ox
from dotenv import load_dotenv

from graph import create_graph, shortest_path
from traffic_logic import (
    generate_traffic,
    get_weather,
    get_zone_key,
    get_weather_cache,
    reset_weather_cache,
    get_owm_call_log,
    reset_owm_call_log,
    dynamic_signal,
    dynamic_time,
    compare_modes,
    two_tier_traffic_routing,
    get_tomtom_call_log,
    get_targeted_polled_edges,
    reset_tomtom_call_log,
    reset_targeted_polled_edges
)

# Load environment variables (.env)
load_dotenv()

app = Flask(__name__)

# ================= GRAPH =================

G = create_graph()

def parse_coordinate(val):
    """
    Parses a coordinate from dict {lat, lng}, tuple/list [lat, lng],
    or string.
    """
    if isinstance(val, dict):
        lat = val.get("lat") if val.get("lat") is not None else val.get("latitude")
        lng = val.get("lng") if val.get("lng") is not None else (
            val.get("lon") if val.get("lon") is not None else val.get("longitude")
        )
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    elif isinstance(val, (list, tuple)) and len(val) >= 2:
        return float(val[0]), float(val[1])
    return None

def snap_coordinate_to_node(G, lat, lng):
    """
    Snaps arbitrary GPS coordinate to nearest graph node using OSMnx spatial indexing.
    """
    nearest_node = ox.distance.nearest_nodes(G, X=float(lng), Y=float(lat))
    return int(nearest_node)

# ================= HOME =================

@app.route('/')
def index():
    mapbox_token = os.getenv('MAPBOX_API_KEY', '')
    return render_template(
        'index.html',
        mapbox_token=mapbox_token
    )

# ================= ROUTE API =================

@app.route('/route', methods=['POST'])
def route():
    try:
        data = request.get_json(force=True, silent=True) or {}

        # ================= EXTRACT COORDINATES =================
        source_val = data.get('source')
        dest_val = data.get('destination')

        source_coord = parse_coordinate(source_val)
        dest_coord = parse_coordinate(dest_val)

        # Fallback to flat parameters if not parsed from source/destination dicts
        if source_coord is None:
            s_lat = data.get('source_lat') or data.get('src_lat')
            s_lng = data.get('source_lng') or data.get('src_lng') or data.get('source_lon')
            if s_lat is not None and s_lng is not None:
                source_coord = (float(s_lat), float(s_lng))

        if dest_coord is None:
            d_lat = data.get('dest_lat') or data.get('destination_lat') or data.get('dst_lat')
            d_lng = data.get('dest_lng') or data.get('destination_lng') or data.get('dst_lng') or data.get('dest_lon')
            if d_lat is not None and d_lng is not None:
                dest_coord = (float(d_lat), float(d_lng))

        # Check if direct node IDs were supplied
        src_node = None
        dst_node = None

        if source_coord is None and source_val is not None:
            try:
                cand = int(source_val)
                if cand in G.nodes:
                    src_node = cand
                    source_coord = (float(G.nodes[cand]["y"]), float(G.nodes[cand]["x"]))
            except (ValueError, TypeError):
                pass

        if dest_coord is None and dest_val is not None:
            try:
                cand = int(dest_val)
                if cand in G.nodes:
                    dst_node = cand
                    dest_coord = (float(G.nodes[cand]["y"]), float(G.nodes[cand]["x"]))
            except (ValueError, TypeError):
                pass

        if source_coord is None or dest_coord is None:
            return jsonify({
                "error": "Source and destination coordinates {lat, lng} required"
            }), 400

        src_lat, src_lng = source_coord
        dst_lat, dst_lng = dest_coord

        # ================= INPUT SNAPPING VIA OSMNX =================
        if src_node is None:
            src_node = snap_coordinate_to_node(G, lat=src_lat, lng=src_lng)

        if dst_node is None:
            dst_node = snap_coordinate_to_node(G, lat=dst_lat, lng=dst_lng)

        if src_node == dst_node:
            return jsonify({
                "error": "Source and destination snapped to the same road node",
                "source_node": src_node,
                "destination_node": dst_node
            }), 400

        # Snapped coordinates from graph
        src_snapped = [float(G.nodes[src_node]["y"]), float(G.nodes[src_node]["x"])]
        dst_snapped = [float(G.nodes[dst_node]["y"]), float(G.nodes[dst_node]["x"])]

        # ================= LIVE WEATHER & DYNAMIC TRAFFIC =================
        weather = get_weather(lat=src_snapped[0], lon=src_snapped[1])

        # ================= TWO-TIER TARGETED TRAFFIC ROUTING =================
        path, candidate_path, traffic, rerouted = two_tier_traffic_routing(
            G,
            src_node,
            dst_node,
            weather=weather
        )

        if not path:
            return jsonify({
                "error": "No drivable path found between snapped nodes",
                "source_node": src_node,
                "destination_node": dst_node
            }), 400

        # Baseline real road geometry along the path
        real_route = [
            [float(G.nodes[n]["y"]), float(G.nodes[n]["x"])]
            for n in path
        ]

        # ================= OSRM MULTI-WAYPOINT ENHANCEMENT =================
        # Sample waypoints along path (max 25 to avoid URL overflow)
        if len(path) <= 25:
            sampled_nodes = path
        else:
            step = max(1, len(path) // 20)
            sampled_nodes = [path[0]] + path[step:-1:step] + [path[-1]]

        try:
            waypoints_str = ";".join(
                f"{G.nodes[n]['x']},{G.nodes[n]['y']}"
                for n in sampled_nodes
            )
            osrm_url = (
                f"http://router.project-osrm.org/route/v1/driving/{waypoints_str}"
                "?overview=full&geometries=geojson"
            )
            osrm_resp = requests.get(osrm_url, timeout=3.5)
            if osrm_resp.status_code == 200:
                route_data = osrm_resp.json()
                if "routes" in route_data and len(route_data["routes"]) > 0:
                    coords = route_data["routes"][0]["geometry"]["coordinates"]
                    real_route = [[c[1], c[0]] for c in coords]
        except Exception as osrm_err:
            # Fallback cleanly to graph geometry if OSRM is busy/times out
            print(f"[OSRM Warning]: {osrm_err}. Using graph node coordinates.")

        # ================= SIGNALS (ALONG PATH) =================
        signals = {}
        for node in path:
            green_edge = dynamic_signal(node, G, traffic)
            if green_edge and green_edge in traffic:
                traffic_val = traffic[green_edge]
                signals[str(node)] = {
                    "green": [str(green_edge[0]), str(green_edge[1])],
                    "time": dynamic_time(traffic_val),
                    "traffic": traffic_val
                }
            else:
                signals[str(node)] = {
                    "green": None,
                    "time": 5,
                    "traffic": 1
                }

        # ================= COMPARISON =================
        comparison = compare_modes(
            path,
            traffic,
            weather_modifier=weather.get("impact_multiplier", 1.0)
        )

        # ================= METRICS =================
        avg_traffic = round(
            sum(traffic.values()) / max(len(traffic), 1),
            2
        )

        metrics = {
            "signals": len(signals),
            "avg_delay": round(
                comparison["fixed"] - comparison["dynamic"],
                2
            ),
            "traffic_load": avg_traffic,
            "weather": weather.get("description", "Clear"),
            "weather_condition": weather.get("condition", "Clear"),
            "weather_temp": weather.get("temp", 28.0),
            "weather_impact": weather.get("impact_multiplier", 1.0),
            "weather_cached": weather.get("cached", False),
            "weather_zone": weather.get("zone_key")
        }

        # ================= RESPONSE =================
        return jsonify({
            "source_node": src_node,
            "destination_node": dst_node,
            "source_coords": [src_lat, src_lng],
            "destination_coords": [dst_lat, dst_lng],
            "source_snapped_coords": src_snapped,
            "destination_snapped_coords": dst_snapped,
            "rerouted": rerouted,
            "candidate_edges_count": len(candidate_path) - 1,
            "targeted_polled_count": len(traffic),
            "weather": weather,
            "path": [int(n) for n in path],
            "candidate_path": [int(n) for n in candidate_path],
            "route": real_route,
            "coords": {
                str(node): [float(G.nodes[node]["y"]), float(G.nodes[node]["x"])]
                for node in path
            },
            "signals": signals,
            "comparison": comparison,
            "metrics": metrics
        })

    except Exception as error:
        print("\n===== BACKEND ERROR =====")
        print(error)
        print("=========================\n")
        return jsonify({
            "error": "Internal server error",
            "details": str(error)
        }), 500

# ================= MAIN =================

if __name__ == '__main__':
    app.run(
        debug=True,
        host='127.0.0.1',
        port=5000
    )
