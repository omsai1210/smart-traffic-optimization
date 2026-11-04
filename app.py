from flask import Flask, render_template, request, jsonify
import requests

from graph import create_graph, shortest_path
from traffic_logic import (
    generate_traffic,
    dynamic_signal,
    dynamic_time,
    compare_modes
)

app = Flask(__name__)

# ================= GRAPH =================

G = create_graph()

# ================= NODE COORDINATES =================

NODE_COORDS = {

    # Hadapsar Main Junction
    "Hadapsar_Main": (
        18.5088,
        73.9250
    ),

    # Gadital Chowk
    "Gadital_Chowk": (
        18.5015,
        73.9384
    ),

    # Fatima Nagar Junction
    "FatimaNagar_Junction": (
        18.5097,
        73.9018
    ),

    # Magarpatta Main Entry
    "Magarpatta_Junction": (
        18.5164,
        73.9320
    ),

    # Amanora Entry
    "Amanora_Entry": (
        18.5186,
        73.9365
    )
}

# ================= HOME =================

@app.route('/')
def index():

    return render_template('index.html')

# ================= ROUTE API =================

@app.route('/route', methods=['POST'])
def route():

    try:

        data = request.json

        source = data.get('source')
        destination = data.get('destination')

        # ================= VALIDATION =================

        if not source or not destination:

            return jsonify({

                "error":
                    "Source and destination required"

            }), 400

        if source == destination:

            return jsonify({

                "error":
                    "Source and destination cannot be same"

            }), 400

        if source not in NODE_COORDS:

            return jsonify({

                "error":
                    f"Invalid source node: {source}"

            }), 400

        if destination not in NODE_COORDS:

            return jsonify({

                "error":
                    f"Invalid destination node: {destination}"

            }), 400

        # ================= TRAFFIC SIMULATION =================

        traffic = generate_traffic(G)

        # ================= TRAFFIC-AWARE DIJKSTRA =================

        path = shortest_path(
            G,
            source,
            destination,
            traffic=traffic
        )

        if not path:

            return jsonify({

                "error":
                    "No shortest path found"

            }), 400

        # ================= OSRM ROUTE =================

        source_lat, source_lng = \
            NODE_COORDS[source]

        dest_lat, dest_lng = \
            NODE_COORDS[destination]

        osrm_url = (

            "http://router.project-osrm.org/route/v1/driving/"

            f"{source_lng},{source_lat};"

            f"{dest_lng},{dest_lat}"

            "?overview=full"

            "&geometries=geojson"
        )

        response = requests.get(
            osrm_url,
            timeout=10
        )

        if response.status_code != 200:

            return jsonify({

                "error":
                    "OSRM routing service failed"

            }), 500

        route_data = response.json()

        if (
            "routes" not in route_data or
            len(route_data["routes"]) == 0
        ):

            return jsonify({

                "error":
                    "No drivable route found"

            }), 400

        # ================= ROUTE COORDS =================

        geometry = \
            route_data["routes"][0]["geometry"]

        coordinates = geometry["coordinates"]

        # convert [lng, lat] → [lat, lng]
        real_route = [

            [coord[1], coord[0]]

            for coord in coordinates
        ]

        # ================= SIGNALS =================

        signals = {}

        for node in G.nodes():

            green_edge = dynamic_signal(
                node,
                G,
                traffic
            )

            if green_edge:

                traffic_value = \
                    traffic[green_edge]

                signals[node] = {

                    "green": green_edge,

                    "time":
                        dynamic_time(
                            traffic_value
                        ),

                    "traffic":
                        traffic_value
                }

            else:

                signals[node] = {

                    "green": None,

                    "time": 5,

                    "traffic": 1
                }

        # ================= COMPARISON =================

        comparison = compare_modes(
            path,
            traffic
        )

        # ================= METRICS =================

        avg_traffic = round(

            sum(traffic.values()) /

            len(traffic),

            2
        )

        metrics = {

            "signals":
                len(signals),

            "avg_delay":
                round(
                    comparison["fixed"] -
                    comparison["dynamic"],
                    2
                ),

            "traffic_load":
                avg_traffic
        }

        # ================= RESPONSE =================

        return jsonify({

            "path": path,

            "route": real_route,

            "coords": {

                node: G.nodes[node]['pos']

                for node in G.nodes()
            },

            "signals": signals,

            "comparison": comparison,

            "metrics": metrics
        })

    # ================= ERROR =================

    except requests.exceptions.Timeout:

        return jsonify({

            "error":
                "OSRM request timeout"

        }), 504

    except requests.exceptions.RequestException:

        return jsonify({

            "error":
                "OSRM network error"

        }), 500

    except Exception as error:

        print("\n===== BACKEND ERROR =====")
        print(error)
        print("=========================\n")

        return jsonify({

            "error":
                "Internal server error"

        }), 500

# ================= MAIN =================

if __name__ == '__main__':

    app.run(
        debug=True,
        host='127.0.0.1',
        port=5000
    )