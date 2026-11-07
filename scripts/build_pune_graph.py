import os
import sys

def main():
    import osmnx as ox
    from osmnx import distance
    print("OSMnx version:", ox.__version__)

    # Fast and reliable Overpass settings
    ox.settings.overpass_url = "https://overpass.openstreetmap.fr/api"
    ox.settings.overpass_rate_limit = False
    ox.settings.http_referer = "https://openstreetmap.org"
    ox.settings.http_user_agent = "SMTTraffic/1.0"
    ox.settings.requests_timeout = 600
    ox.settings.overpass_memory = 2147483648  # 2 GB
    ox.settings.use_cache = True
    ox.settings.log_console = True

    # Safely handle boundary nodes/edges in multi-chunk partition downloads
    orig_add_edge_lengths = distance.add_edge_lengths

    def safe_add_edge_lengths(G, edges=None):
        invalid_nodes = [
            n for n, data in G.nodes(data=True)
            if "x" not in data or "y" not in data or data["x"] is None or data["y"] is None
        ]
        if invalid_nodes:
            print(f"Pruning {len(invalid_nodes)} boundary nodes missing coordinates (and incident edges)...")
            G.remove_nodes_from(invalid_nodes)
        return orig_add_edge_lengths(G, edges=edges)

    distance.add_edge_lengths = safe_add_edge_lengths

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    graphml_path = os.path.join(data_dir, "pune_drive_network.graphml")

    print("Fetching Pune drive network from OSMnx (using cache)...")
    G = ox.graph_from_place("Pune, Maharashtra, India", network_type="drive", simplify=True)
    print(f"Graph loaded with {len(G.nodes):,} nodes and {len(G.edges):,} edges.")

    print("Adding edge speeds and travel times...")
    if hasattr(ox, "routing") and hasattr(ox.routing, "add_edge_speeds"):
        G = ox.routing.add_edge_speeds(G)
        G = ox.routing.add_edge_travel_times(G)
    elif hasattr(ox, "add_edge_speeds"):
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
    else:
        import osmnx.routing as ox_routing
        G = ox_routing.add_edge_speeds(G)
        G = ox_routing.add_edge_travel_times(G)

    print(f"Saving graphml to {graphml_path}...")
    ox.save_graphml(G, filepath=graphml_path)
    print("Successfully built and saved Pune drive network!")

if __name__ == "__main__":
    main()
