import os
import sys
import unittest
import random

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, G

class TestPhase2InputSnapping(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_snap_arbitrary_pune_coordinates(self):
        print("\n--- Running TEST 2: KD-Tree Spatial Indexing & Input Snapping Verification ---")

        # 1. Test known landmarks in Pune
        payload_landmarks = {
            "source": {"lat": 18.5196, "lng": 73.8553},       # Shaniwar Wada / Center
            "destination": {"lat": 18.5088, "lng": 73.9250}  # Hadapsar
        }

        print(f"Testing landmark payload: {payload_landmarks}")
        response = self.client.post("/route", json=payload_landmarks)
        self.assertEqual(response.status_code, 200, f"Expected 200 OK, got {response.status_code}: {response.data}")

        data = response.get_json()
        src_node = data.get("source_node")
        dst_node = data.get("destination_node")

        print(f"Resolved source_node: {src_node} (Type: {type(src_node)})")
        print(f"Resolved destination_node: {dst_node} (Type: {type(dst_node)})")

        self.assertIsNotNone(src_node, "Response must include 'source_node'")
        self.assertIsNotNone(dst_node, "Response must include 'destination_node'")
        self.assertIn(src_node, G.nodes, "Resolved source_node must be a valid node in G")
        self.assertIn(dst_node, G.nodes, "Resolved destination_node must be a valid node in G")
        self.assertNotEqual(src_node, dst_node, "Source and destination nodes should be distinct")

        # Verify snapped coordinates
        src_snapped = data.get("source_snapped_coords")
        dst_snapped = data.get("destination_snapped_coords")
        print(f"Source Snapped GPS: {src_snapped}")
        print(f"Destination Snapped GPS: {dst_snapped}")
        self.assertIsNotNone(src_snapped)
        self.assertIsNotNone(dst_snapped)

        # Verify path
        path = data.get("path")
        self.assertIsInstance(path, list)
        self.assertGreater(len(path), 1)
        print(f"Calculated path length: {len(path)} nodes")

        # 2. Test randomized arbitrary coordinates within Pune bounds
        # Pune latitude: ~18.48 to 18.56, longitude: ~73.80 to 73.92
        rand_src_lat = round(random.uniform(18.5100, 18.5400), 5)
        rand_src_lng = round(random.uniform(73.8200, 73.8600), 5)
        rand_dst_lat = round(random.uniform(18.5000, 18.5300), 5)
        rand_dst_lng = round(random.uniform(73.8700, 73.9200), 5)

        payload_random = {
            "source": {"lat": rand_src_lat, "lng": rand_src_lng},
            "destination": {"lat": rand_dst_lat, "lng": rand_dst_lng}
        }

        print(f"\nTesting randomized coordinates: {payload_random}")
        rand_resp = self.client.post("/route", json=payload_random)
        self.assertIn(rand_resp.status_code, [200, 400])

        rand_data = rand_resp.get_json()
        rand_src_node = rand_data.get("source_node")
        rand_dst_node = rand_data.get("destination_node")

        print(f"Random Source Snapped -> Node ID: {rand_src_node}")
        print(f"Random Destination Snapped -> Node ID: {rand_dst_node}")

        self.assertIn(rand_src_node, G.nodes, "Random source must snap to valid node in G")
        self.assertIn(rand_dst_node, G.nodes, "Random destination must snap to valid node in G")
        if rand_resp.status_code == 200:
            print(f"Random Path Sequence ({len(rand_data.get('path', []))} nodes): {rand_data.get('path', [])[:5]}...")
        else:
            print(f"Path between random components: {rand_data.get('error')}")

        print("--- TEST 2 PASSED: KD-Tree Input Snapping Successfully Verified! ---\n")

if __name__ == "__main__":
    unittest.main()

