# -*- coding: utf-8 -*-
"""GTFS (General Transit Feed Specification) integration.

Downloads and parses a real transit feed (default: MBTA — Boston), extracts
the ordered stop sequence of one route and turns it into a scenario for the
voice announcer, so "next stop" announcements follow a *real* city's stop
order instead of the built-in demo route.

GTFS reference: https://gtfs.org/schedule/reference/

Files used
----------
stops.txt      stop_id, stop_name, stop_lat, stop_lon
routes.txt     route_id, route_short_name, route_long_name, route_type
trips.txt      route_id, trip_id, direction_id, trip_headsign
stop_times.txt trip_id, stop_id, stop_sequence, arrival_time

``stop_times`` carries no distance column in the MBTA feed, so inter-stop
distances are accumulated from stop coordinates (haversine) — good enough
for approach announcements (600 m / 300 m).

A compact JSON *snapshot* of the chosen route is written to ``data/`` so the
demo also runs fully offline (and the snapshot is small enough to commit).
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import zipfile
from dataclasses import dataclass, field, asdict
from urllib.request import urlopen

DEFAULT_FEED_URL = "https://cdn.mbta.com/MBTA_GTFS.zip"
DEFAULT_FEED_PATH = os.path.join("data", "mbta_gtfs.zip")

ROUTE_TYPE_NAMES = {
    "0": "Tram", "1": "Subway", "2": "Rail", "3": "Bus",
    "4": "Ferry", "5": "Cable tram", "6": "Aerial lift", "7": "Funicular",
    "11": "Trolleybus", "12": "Monorail",
}


# ----------------------------------------------------------------------
# feed access
# ----------------------------------------------------------------------
def ensure_feed(path: str = DEFAULT_FEED_PATH, url: str = DEFAULT_FEED_URL) -> str:
    """Download the GTFS zip once; return its path."""
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    print(f"[gtfs] downloading {url} ...")
    with urlopen(url, timeout=180) as resp, open(path, "wb") as out:
        out.write(resp.read())
    print(f"[gtfs] saved {path} ({os.path.getsize(path)/1e6:.1f} MB)")
    return path


def _rows(zf: zipfile.ZipFile, name: str):
    """Stream one GTFS csv out of the zip (handles BOM)."""
    with zf.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ----------------------------------------------------------------------
# data model
# ----------------------------------------------------------------------
@dataclass
class GtfsRouteStop:
    stop_id: str
    name: str
    lat: float
    lon: float
    distance_m: float          # cumulative distance along the route (m)
    arrival_time: str = ""
    stop_sequence: int = 0


@dataclass
class GtfsRouteInfo:
    feed_path: str
    route_id: str
    route_name: str
    route_type: str
    direction_id: str
    trip_id: str
    headsign: str
    stops: list = field(default_factory=list)   # list[GtfsRouteStop]

    @property
    def total_distance_m(self) -> float:
        return self.stops[-1].distance_m if self.stops else 0.0


# ----------------------------------------------------------------------
# parsing
# ----------------------------------------------------------------------
def list_routes(feed_path: str = DEFAULT_FEED_PATH, route_type: str | None = None,
                limit: int = 25) -> list[tuple[str, str, str]]:
    """Return [(route_id, short_name, long_name)] for a quick overview."""
    zf = zipfile.ZipFile(feed_path)
    out = []
    for r in _rows(zf, "routes.txt"):
        if route_type and r["route_type"] != route_type:
            continue
        out.append((r["route_id"], r["route_short_name"], r["route_long_name"]))
        if len(out) >= limit:
            break
    return out


def build_route(feed_path: str, route_id: str, direction_id: str = "0") -> GtfsRouteInfo:
    """Extract the longest trip of a route/direction as the canonical stop sequence."""
    zf = zipfile.ZipFile(feed_path)

    # route meta
    route_name = route_id
    route_type = "3"
    for r in _rows(zf, "routes.txt"):
        if r["route_id"] == route_id:
            route_name = (r["route_long_name"] or r["route_short_name"]).strip()
            route_type = r["route_type"]
            break

    # trips of this route/direction
    trip_ids: dict[str, str] = {}          # trip_id -> headsign
    for t in _rows(zf, "trips.txt"):
        if t["route_id"] == route_id and t.get("direction_id", "0") == direction_id:
            trip_ids[t["trip_id"]] = t.get("trip_headsign", "")

    if not trip_ids:
        raise ValueError(f"route {route_id} direction {direction_id}: no trips in feed")

    # single pass over stop_times: keep rows of this route's trips
    per_trip: dict[str, list[dict]] = {}
    for st in _rows(zf, "stop_times.txt"):
        tid = st["trip_id"]
        if tid in trip_ids:
            per_trip.setdefault(tid, []).append(st)

    # canonical trip = the one serving the most stops
    best_tid = max(per_trip, key=lambda k: len(per_trip[k]))
    rows = sorted(per_trip[best_tid], key=lambda s: int(s["stop_sequence"]))

    # stop master data
    stops_meta = {}
    for s in _rows(zf, "stops.txt"):
        stops_meta[s["stop_id"]] = s

    info = GtfsRouteInfo(
        feed_path=feed_path, route_id=route_id, route_name=route_name,
        route_type=route_type, direction_id=direction_id,
        trip_id=best_tid, headsign=trip_ids.get(best_tid, ""),
    )

    dist = 0.0
    prev = None
    for row in rows:
        meta = stops_meta.get(row["stop_id"], {})
        lat, lon = float(meta.get("stop_lat", 0)), float(meta.get("stop_lon", 0))
        if prev is not None:
            dist += _haversine(prev[0], prev[1], lat, lon)
        prev = (lat, lon)
        info.stops.append(GtfsRouteStop(
            stop_id=row["stop_id"],
            name=(meta.get("stop_name") or row["stop_id"]).strip(),
            lat=lat, lon=lon, distance_m=round(dist, 1),
            arrival_time=row.get("arrival_time", ""),
            stop_sequence=int(row["stop_sequence"]),
        ))
    return info


# ----------------------------------------------------------------------
# snapshot (offline demo support)
# ----------------------------------------------------------------------
def save_snapshot(info: GtfsRouteInfo, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"route": {k: v for k, v in asdict(info).items() if k != "stops"},
                   "stops": [asdict(s) for s in info.stops]}, f, ensure_ascii=False, indent=1)
    return path


def load_snapshot(path: str) -> GtfsRouteInfo:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    info = GtfsRouteInfo(**data["route"])
    info.stops = [GtfsRouteStop(**s) for s in data["stops"]]
    return info


def get_route(route_id: str, direction_id: str = "0",
              feed_path: str = DEFAULT_FEED_PATH, url: str = DEFAULT_FEED_URL,
              refresh: bool = False) -> GtfsRouteInfo:
    """Feed if available, otherwise fall back to the committed snapshot."""
    snap = os.path.join(os.path.dirname(feed_path) or ".",
                        f"gtfs_route_{route_id}_dir{direction_id}_snapshot.json")
    if not refresh and os.path.exists(snap):
        print(f"[gtfs] using snapshot {snap}")
        return load_snapshot(snap)
    ensure_feed(feed_path, url)
    info = build_route(feed_path, route_id, direction_id)
    save_snapshot(info, snap)
    print(f"[gtfs] snapshot saved {snap}")
    return info
