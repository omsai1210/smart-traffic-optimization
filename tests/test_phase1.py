import os
import sys
import unittest
import networkx as nx

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import create_graph

class TestPhase1GraphIngestion(unittest.TestCase):
    def test_load_pune_graph(self):
        print("\n--- Running TEST 1: Pune City-Wide Graph Ingestion Verification ---")
        G = create_graph()

        # Check graph type
        self.assertIsInstance(G, nx.MultiDiGraph, "Graph should be an instance of nx.MultiDiGraph")

        node_count = len(G.nodes)
        edge_count = len(G.edges)

        print(f"Graph Type: {type(G)}")
        print(f"Total Nodes: {node_count:,}")
        print(f"Total Edges: {edge_count:,}")

        # Check node and edge volume for city-wide Pune network
        self.assertGreater(node_count, 100000, "Node count should exceed 100,000 for Pune city")
        self.assertGreater(edge_count, 200000, "Edge count should exceed 200,000 for Pune city")

        # Inspect a sample node
        sample_node = next(iter(G.nodes))
        node_data = G.nodes[sample_node]
        self.assertIn("x", node_data, "Node must have longitude 'x'")
        self.assertIn("y", node_data, "Node must have latitude 'y'")

        # Inspect a sample edge
        sample_edge = next(iter(G.edges(keys=True, data=True)))
        edge_data = sample_edge[3]
        self.assertIn("travel_time", edge_data, "Edge must have 'travel_time'")
        self.assertIn("length", edge_data, "Edge must have 'length'")

        print(f"Sample Node {sample_node}: (lat: {node_data['y']}, lng: {node_data['x']})")
        print(f"Sample Edge {sample_edge[0]} -> {sample_edge[1]}: length={edge_data['length']}m, travel_time={edge_data['travel_time']}s")
        print("--- TEST 1 PASSED: City-Wide Graph Verified Successfully! ---\n")

if __name__ == "__main__":
    unittest.main()

