"""
test_phase5.py - Verification for Phase 5: Caching & Zonal Weather (OpenWeatherMap)

Validates:
1. Coordinates within the same 0.01 degree zone (lat/lon rounded to 2 decimals)
   share the same zone key.
2. Direct get_weather calls within the same zone use cachetools.TTLCache (15-min TTL)
   and do not hit the OpenWeatherMap API redundantly.
3. Multiple rapid route API requests (/route) only hit the OpenWeatherMap API once
   per zone.
4. Requests from different zones trigger a separate lookup for that zone.
5. TTL cache configuration confirms 900-second (15-minute) lifespan.
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from traffic_logic import (
    get_weather,
    get_zone_key,
    get_weather_cache,
    reset_weather_cache,
    get_owm_call_log,
    reset_owm_call_log
)


class TestPhase5CachingAndZonalWeather(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        reset_weather_cache()
        reset_owm_call_log()

    def test_step1_zonal_key_generation(self):
        print("\n" + "=" * 60)
        print("STEP 1: Testing Zonal Key Generation")
        print("=" * 60)

        # Swargate area coords
        pt1 = (18.5018, 73.8584)
        pt2 = (18.5042, 73.8591)
        pt3 = (18.4981, 73.8620)

        zk1 = get_zone_key(pt1[0], pt1[1])
        zk2 = get_zone_key(pt2[0], pt2[1])
        zk3 = get_zone_key(pt3[0], pt3[1])

        print(f"Point 1 {pt1} -> Zone Key: {zk1}")
        print(f"Point 2 {pt2} -> Zone Key: {zk2}")
        print(f"Point 3 {pt3} -> Zone Key: {zk3}")

        self.assertEqual(zk1, (18.50, 73.86))
        self.assertEqual(zk2, (18.50, 73.86))
        self.assertEqual(zk3, (18.50, 73.86))
        self.assertEqual(zk1, zk2)
        self.assertEqual(zk2, zk3)

        # Different zone: Viman Nagar
        viman_pt = (18.5679, 73.9143)
        zk_viman = get_zone_key(viman_pt[0], viman_pt[1])
        print(f"Viman Nagar Point {viman_pt} -> Zone Key: {zk_viman}")
        self.assertEqual(zk_viman, (18.57, 73.91))
        self.assertNotEqual(zk_viman, zk1)

        print("[PASS] Zonal key generation verified.\n")

    def test_step2_direct_weather_caching(self):
        print("=" * 60)
        print("STEP 2: Testing Direct Weather Caching & TTLCache")
        print("=" * 60)

        cache = get_weather_cache()
        print(f"TTLCache maxsize: {cache.maxsize}, ttl: {cache.ttl}s ({cache.ttl / 60} mins)")
        self.assertEqual(cache.ttl, 900)

        # Call 1: New zone (Swargate)
        print("\nCall 1: Requesting weather for Swargate (18.5018, 73.8584)...")
        w1 = get_weather(18.5018, 73.8584)
        calls_after_1 = len(get_owm_call_log())
        print(f"Result 1: temp={w1.get('temp')}C, condition={w1.get('condition')}, cached={w1.get('cached')}")
        print(f"OWM Call Log Count: {calls_after_1}")
        self.assertEqual(calls_after_1, 1)
        self.assertFalse(w1.get("cached"))

        # Call 2: Slightly different coords in same zone (18.5042, 73.8591)
        print("\nCall 2: Requesting weather for same zone (18.5042, 73.8591)...")
        w2 = get_weather(18.5042, 73.8591)
        calls_after_2 = len(get_owm_call_log())
        print(f"Result 2: temp={w2.get('temp')}C, condition={w2.get('condition')}, cached={w2.get('cached')}")
        print(f"OWM Call Log Count: {calls_after_2}")
        self.assertEqual(calls_after_2, 1)
        self.assertTrue(w2.get("cached"))

        # Call 3: Third point in same zone
        print("\nCall 3: Requesting weather for 3rd point in same zone (18.4981, 73.8620)...")
        w3 = get_weather(18.4981, 73.8620)
        calls_after_3 = len(get_owm_call_log())
        print(f"Result 3: temp={w3.get('temp')}C, condition={w3.get('condition')}, cached={w3.get('cached')}")
        print(f"OWM Call Log Count: {calls_after_3}")
        self.assertEqual(calls_after_3, 1)
        self.assertTrue(w3.get("cached"))

        # Call 4: Different zone (Viman Nagar)
        print("\nCall 4: Requesting weather for new zone Viman Nagar (18.5679, 73.9143)...")
        w4 = get_weather(18.5679, 73.9143)
        calls_after_4 = len(get_owm_call_log())
        print(f"Result 4: temp={w4.get('temp')}C, condition={w4.get('condition')}, cached={w4.get('cached')}")
        print(f"OWM Call Log Count: {calls_after_4}")
        self.assertEqual(calls_after_4, 2)
        self.assertFalse(w4.get("cached"))

        # Call 5: Same Viman Nagar zone again
        print("\nCall 5: Requesting weather for Viman Nagar again...")
        w5 = get_weather(18.5679, 73.9143)
        calls_after_5 = len(get_owm_call_log())
        print(f"Result 5: temp={w5.get('temp')}C, condition={w5.get('condition')}, cached={w5.get('cached')}")
        print(f"OWM Call Log Count: {calls_after_5}")
        self.assertEqual(calls_after_5, 2)
        self.assertTrue(w5.get("cached"))

        print("[PASS] Direct weather caching and zonal partitioning verified.\n")

    def test_step3_rapid_route_api_caching(self):
        print("=" * 60)
        print("STEP 3: Testing Rapid Route API Calls (/route)")
        print("=" * 60)

        # Swargate -> Viman Nagar
        swargate_coords = [18.5018, 73.8584]
        viman_coords = [18.5679, 73.9143]

        payload = {
            "source": {"lat": swargate_coords[0], "lng": swargate_coords[1]},
            "destination": {"lat": viman_coords[0], "lng": viman_coords[1]}
        }

        num_rapid_requests = 5
        print(f"Firing {num_rapid_requests} rapid route requests with source={swargate_coords}...")

        # Mock TomTom flow to keep testing focused purely on OWM caching without network lag
        mock_tomtom = MagicMock()
        mock_tomtom.status_code = 200
        mock_tomtom.json.return_value = {
            "flowSegmentData": {
                "currentSpeed": 40,
                "freeFlowSpeed": 50
            }
        }

        # Keep original requests.get for OpenWeatherMap, mock only TomTom
        real_requests_get = __import__("requests").get

        def smart_get(url, *args, **kwargs):
            if "api.tomtom.com" in url:
                return mock_tomtom
            return real_requests_get(url, *args, **kwargs)

        with patch("requests.get", side_effect=smart_get):
            responses = []
            for i in range(1, num_rapid_requests + 1):
                start_t = time.perf_counter()
                resp = self.client.post("/route", json=payload)
                elapsed_ms = (time.perf_counter() - start_t) * 1000

                self.assertEqual(resp.status_code, 200, f"Request {i} failed: {resp.data}")
                json_data = resp.get_json()
                weather_meta = json_data.get("weather", {})
                metrics = json_data.get("metrics", {})

                is_cached = weather_meta.get("cached", metrics.get("weather_cached"))
                zone = weather_meta.get("zone_key", metrics.get("weather_zone"))
                owm_calls = len(get_owm_call_log())

                print(
                    f"  Request {i}: Status={resp.status_code} ({elapsed_ms:.1f}ms) | "
                    f"Weather Zone={zone} | Cached={is_cached} | "
                    f"Total OWM API Hits={owm_calls}"
                )
                responses.append((json_data, is_cached, owm_calls))

            # Request 1: cached=False, 1 OWM call
            self.assertFalse(responses[0][1], "Request 1 must have cached=False")

            # Requests 2 to 5: cached=True
            for idx, (data, cached, calls) in enumerate(responses[1:], start=2):
                self.assertTrue(cached, f"Request {idx} must have cached=True")

            # Overall OWM API call count MUST be exactly 1
            total_owm_hits = len(get_owm_call_log())
            print(f"\nTotal OWM API calls recorded across {num_rapid_requests} rapid route queries: {total_owm_hits}")
            self.assertEqual(total_owm_hits, 1, f"Expected 1 OWM call for zone, got {total_owm_hits}")

            # Request 6: Different zone (Kothrud: 18.5074, 73.8077 -> zone 18.51, 73.81)
            kothrud_coords = [18.5074, 73.8077]
            payload_new_zone = {
                "source": {"lat": kothrud_coords[0], "lng": kothrud_coords[1]},
                "destination": {"lat": viman_coords[0], "lng": viman_coords[1]}
            }
            print(f"\nFiring request 6 with new origin in Kothrud zone {kothrud_coords}...")
            resp_new = self.client.post("/route", json=payload_new_zone)
            self.assertEqual(resp_new.status_code, 200)
            data_new = resp_new.get_json()
            new_weather = data_new.get("weather", {})
            new_zone = new_weather.get("zone_key")
            new_cached = new_weather.get("cached")
            total_owm_hits_new = len(get_owm_call_log())

            print(
                f"  Request 6: Status={resp_new.status_code} | "
                f"Weather Zone={new_zone} | Cached={new_cached} | "
                f"Total OWM API Hits={total_owm_hits_new}"
            )

            self.assertFalse(new_cached, "Request in new zone must trigger fresh fetch")
            self.assertEqual(total_owm_hits_new, 2, "Expected 2 total OWM calls (1 per zone)")

        print("[PASS] Rapid route API verification passed: OWM API called exactly once per zone!\n")


if __name__ == "__main__":
    unittest.main()
