# -*- coding: utf-8 -*-
"""GTFS parsing tests using a tiny synthetic feed — no network required."""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from announcer import gtfs as G                                             # noqa: E402
from announcer.scenario import BusScenario                                  # noqa: E402

MINI_FEED = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\n1,Demo,http://x,UTC\n",
    "routes.txt": ("route_id,agency_id,route_short_name,route_long_name,route_type\n"
                   "R1,1,1,Demo Crosstown,3\n"),
    "trips.txt": ("route_id,service_id,trip_id,direction_id,trip_headsign\n"
                  "R1,S1,T1,0,Uptown\n"
                  "R1,S1,T2,0,Uptown\n"
                  "R1,S1,T3,1,Downtown\n"),
    # T1 serves 4 stops, T2 only 2 -> T1 must win as canonical trip
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,08:00:00,08:00:00,S1,1\n"
        "T1,08:03:00,08:03:00,S2,2\n"
        "T1,08:06:00,08:06:00,S3,3\n"
        "T1,08:10:00,08:10:00,S4,4\n"
        "T2,09:00:00,09:00:00,S1,1\n"
        "T2,09:05:00,09:05:00,S4,2\n"
        "T3,10:00:00,10:00:00,S4,1\n"),
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S1,Alpha Stop,42.000,−71.000\n".replace("−", "-") +
        "S2,Beta Stop,42.010,-71.000\n"
        "S3,Gamma Stop,42.020,-71.005\n"
        "S4,Delta Stop,42.030,-71.010\n"),
}


def make_feed(path):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in MINI_FEED.items():
            z.writestr(name, content)
    return path


class TestGtfs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = make_feed(os.path.join(tempfile.gettempdir(), "mini_gtfs.zip"))
        cls.info = G.build_route(cls.feed, "R1", "0")

    def test_canonical_trip_is_longest(self):
        self.assertEqual(self.info.trip_id, "T1")
        self.assertEqual(len(self.info.stops), 4)

    def test_stop_order_follows_stop_sequence(self):
        names = [s.name for s in self.info.stops]
        self.assertEqual(names, ["Alpha Stop", "Beta Stop", "Gamma Stop", "Delta Stop"])

    def test_distances_monotonic_and_positive(self):
        dists = [s.distance_m for s in self.info.stops]
        self.assertEqual(dists[0], 0)
        for a, b in zip(dists, dists[1:]):
            self.assertGreater(b, a)
        # Alpha->Beta is 0.01 deg latitude ~= 1112 m
        self.assertAlmostEqual(dists[1], 1112, delta=5)

    def test_direction_filter(self):
        info = G.build_route(self.feed, "R1", "1")
        self.assertEqual(info.trip_id, "T3")
        self.assertEqual(info.headsign, "Downtown")

    def test_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "snap.json")
            G.save_snapshot(self.info, path)
            info2 = G.load_snapshot(path)
            self.assertEqual(info2.trip_id, "T1")
            self.assertEqual([s.name for s in info2.stops],
                             [s.name for s in self.info.stops])
            self.assertAlmostEqual(info2.total_distance_m, self.info.total_distance_m, delta=0.5)

    def test_bus_scenario_accepts_gtfs_stops(self):
        from announcer.scenario import Stop
        stops = [Stop(s.name, s.name, int(s.distance_m)) for s in self.info.stops]
        scenario = BusScenario(seed=1, stops=stops, line="R1",
                               destination_en="Delta Stop", destination_zh="Delta Stop")
        result = scenario.run()
        kinds = {e.kind for e in result.events}
        self.assertIn("departure", kinds)
        self.assertIn("trip_summary", kinds)
        announced_stops = [e.params.get("stop") for e in result.events
                           if e.kind == "arriving"]
        self.assertEqual(announced_stops, ["Beta Stop", "Gamma Stop", "Delta Stop"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
