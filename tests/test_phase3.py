import os
import sys
import unittest
import time
import osmnx as ox
import networkx as nx

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import create_graph, shortest_path, make_haversine_heuristic
from app import app

class TestPhase3AStarPathfinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\nLoading Pune City Graph for TEST 3...")
        cls.G = create_graph()
        cls.client = app.test_client()

    def test_swargate_to_viman_nagar_astar_vs_dijkstra(self):
        print("\n--- Running TEST 3: Swargate to Viman Nagar (A* vs Dijkstra) ---")

        # Swargate and Viman Nagar coordinates
        swargate_coord = (18.5018, 73.8584)
        viman_nagar_coord = (18.5679, 73.9143)

        src_node = int(ox.distance.nearest_nodes(self.G, X=swargate_coord[1], Y=swargate_coord[0]))
        dst_node = int(ox.distance.nearest_nodes(self.G, X=viman_nagar_coord[1], Y=viman_nagar_coord[0]))

        print(f"Swargate Snapped Node: {src_node}")
        print(f"Viman Nagar Snapped Node: {dst_node}")
        self.assertIn(src_node, self.G.nodes)
        self.assertIn(dst_node, self.G.nodes)

        # 1. Benchmark Standard Dijkstra
        t0 = time.time()
        dijkstra_path = nx.shortest_path(self.G, source=src_node, target=dst_node, weight="length")
        dijkstra_duration = time.time() - t0

        # 2. Benchmark A* Search with Haversine Heuristic
        t0 = time.time()
        astar_path = shortest_path(self.G, source=src_node, destination=dst_node, weight="length")
        astar_duration = time.time() - t0

        speedup = dijkstra_duration / max(astar_duration, 0.0001)

        print(f"Dijkstra Execution Time: {dijkstra_duration * 1000:.2f} ms | Path Nodes: {len(dijkstra_path)}")
        print(f"A* Search Execution Time: {astar_duration * 1000:.2f} ms | Path Nodes: {len(astar_path)}")
        print(f"Performance Speedup: {speedup:.2f}x faster")

        # Validations
        self.assertIsNotNone(astar_path, "A* must return a valid path")
        self.assertIsInstance(astar_path, list)
        self.assertGreater(len(astar_path), 50, "Route from Swargate to Viman Nagar should span > 50 nodes")
        self.assertEqual(astar_path[0], src_node, "A* path must start at source node")
        self.assertEqual(astar_path[-1], dst_node, "A* path must terminate at target node")
        self.assertEqual(dijkstra_path, astar_path, "A* must find the exact optimal shortest path matching Dijkstra")
        self.assertGreater(speedup, 1.5, f"A* ({astar_duration:.4f}s) should be significantly faster than Dijkstra ({dijkstra_duration:.4f}s)")

        # 3. Verify End-to-End API endpoint with Swargate to Viman Nagar
        print("\nVerifying /route API with Swargate -> Viman Nagar...")
        payload = {
            "source": {"lat": swargate_coord[0], "lng": swargate_coord[1]},
            "destination": {"lat": viman_nagar_coord[0], "lng": viman_nagar_coord[1]}
        }
        resp = self.client.post("/route", json=payload)
        self.assertEqual(resp.status_code, 200)
        api_data = resp.get_json()
        self.assertEqual(api_data["source_node"], src_node)
        self.assertEqual(api_data["destination_node"], dst_node)
        # In baseline or dynamic mode, candidate_path matches the optimal baseline A* path (weight='travel_time')
        astar_travel_time_path = shortest_path(self.G, source=src_node, destination=dst_node, weight="travel_time")
        candidate = api_data.get("candidate_path") or api_data.get("path")
        self.assertEqual(len(candidate), len(astar_travel_time_path))
        print(f"API successfully returned route: candidate={len(candidate)} nodes, final={len(api_data['path'])} nodes (rerouted={api_data.get('rerouted')})")
        print("--- TEST 3 PASSED: A* Pathfinding Successfully Verified! ---\n")

if __name__ == "__main__":
    unittest.main()

