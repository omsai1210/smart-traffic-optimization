import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, G
from traffic_logic import (
    get_tomtom_call_log,
    reset_tomtom_call_log,
    get_targeted_polled_edges,
    reset_targeted_polled_edges
)

class TestPhase4TargetedTomTomPolling(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        reset_tomtom_call_log()
        reset_targeted_polled_edges()

    def test_targeted_tomtom_polling_along_route_only(self):
        print("\n--- Running TEST 4: Two-Tier Targeted TomTom Traffic Polling Verification ---")

        # Swargate to Viman Nagar coordinates
        payload = {
            "source": {"lat": 18.5018, "lng": 73.8584},
            "destination": {"lat": 18.5679, "lng": 73.9143}
        }

        # Mock TomTom response to simulate active live traffic flow responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flowSegmentData": {
                "currentSpeed": 35,
                "freeFlowSpeed": 50,
                "currentTravelTime": 60,
                "freeFlowTravelTime": 42
            }
        }

        # Mock requests.get when querying TomTom
        with patch.dict(os.environ, {"TOMTOM_API_KEY": "test_tomtom_api_key_valid"}):
            with patch("requests.get", return_value=mock_response) as mock_get:
                response = self.client.post("/route", json=payload)
                self.assertEqual(response.status_code, 200, f"Expected 200 OK, got: {response.data}")

                data = response.get_json()
                total_pune_edges = len(G.edges)
                candidate_edges_count = data.get("candidate_edges_count")
                polled_edges = get_targeted_polled_edges()
                tomtom_calls = get_tomtom_call_log()

                print(f"Total Edges in Pune City Grid: {total_pune_edges:,}")
                print(f"Candidate Path Edges:          {candidate_edges_count}")
                print(f"Total Targeted Polled Edges:   {len(polled_edges)}")
                print(f"Total TomTom API Calls Made:   {len(tomtom_calls)}")

                # TEST 4 Core Assertions:
                # 1. Candidate route must have ~50-150 edges
                self.assertGreaterEqual(candidate_edges_count, 30, "Candidate path edges should be >= 30")
                self.assertLessEqual(candidate_edges_count, 200, "Candidate path edges should be <= 200")
                self.assertLessEqual(len(polled_edges), 400, "Polled edges along candidate/rerouted route should be <= 400")

                # 2. Must NEVER query all 320,000+ edges in Pune
                self.assertLess(
                    len(polled_edges),
                    total_pune_edges * 0.01,
                    f"Queried edges ({len(polled_edges)}) must be < 1% of total Pune edges ({total_pune_edges:,})"
                )

                # 3. TomTom API calls must match the targeted polled count
                self.assertEqual(
                    len(tomtom_calls),
                    len(polled_edges),
                    "TomTom API calls should match the targeted polled edges count"
                )

                # 4. Verify candidate path exists and matches targeted segments
                self.assertIn("candidate_path", data)
                self.assertIn("path", data)
                self.assertIn("rerouted", data)
                print(f"Route selected (rerouted={data.get('rerouted')}), path length: {len(data['path'])} nodes")
                print("Sample TomTom polled coordinates (first 3):")
                for call in tomtom_calls[:3]:
                    print(f"  -> GPS Point: ({call['lat']:.5f}, {call['lon']:.5f})")

                print("--- TEST 4 PASSED: Targeted TomTom Polling Verified Successfully! ---\n")

if __name__ == "__main__":
    unittest.main()

