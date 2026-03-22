"""Fetch live aircraft data and calculate airport congestion."""

import math
import time
from datetime import datetime, timezone

import requests

from airports import AIRPORTS

# Radius in km to count aircraft around an airport
AIRPORT_RADIUS_KM = 20  # ~10.8 nautical miles
LOW_ALT_METERS = 3048   # 10,000 feet - aircraft likely arriving/departing

# ICAO callsign prefix -> airline name (major US + international carriers)
AIRLINE_PREFIXES = {
    "AAL": "American", "DAL": "Delta", "UAL": "United", "SWA": "Southwest",
    "JBU": "JetBlue", "NKS": "Spirit", "FFT": "Frontier", "ASA": "Alaska",
    "HAL": "Hawaiian", "SKW": "SkyWest", "RPA": "Republic", "ENY": "Envoy",
    "PDT": "Piedmont", "MES": "Mesa", "GJS": "GoJet", "CPZ": "Compass",
    "EJA": "NetJets", "FDX": "FedEx", "UPS": "UPS", "GTI": "Atlas Air",
    "ACA": "Air Canada", "BAW": "British Airways", "DLH": "Lufthansa",
    "AFR": "Air France", "UAE": "Emirates", "JAL": "JAL", "ANA": "ANA",
    "QFA": "Qantas", "KLM": "KLM", "ETH": "Ethiopian",
}


def parse_airline(callsign):
    """Extract airline name from ICAO callsign prefix (first 3 chars)."""
    if not callsign or len(callsign) < 3:
        return "Other"
    prefix = callsign[:3].upper()
    return AIRLINE_PREFIXES.get(prefix, "Other")


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_us_aircraft():
    """Fetch all aircraft over the US from OpenSky Network."""
    r = requests.get("https://opensky-network.org/api/states/all", params={
        "lamin": 24, "lamax": 50,
        "lomin": -125, "lomax": -66,
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    states = data.get("states", [])
    timestamp = data.get("time", int(time.time()))

    aircraft = []
    for s in states:
        if s[6] is None or s[5] is None:
            continue
        aircraft.append({
            "icao24": s[0],
            "callsign": (s[1] or "").strip(),
            "origin_country": s[2],
            "lat": s[6],
            "lon": s[5],
            "alt_m": s[7],  # barometric altitude in meters
            "on_ground": s[8],
            "velocity": s[9],  # m/s
            "heading": s[10],
            "vertical_rate": s[11],  # m/s
        })

    return aircraft, timestamp


def calculate_congestion(aircraft):
    """For each airport, count nearby aircraft and classify them."""
    results = []

    for apt in AIRPORTS:
        nearby = []
        for ac in aircraft:
            dist = haversine_km(apt["lat"], apt["lon"], ac["lat"], ac["lon"])
            if dist <= AIRPORT_RADIUS_KM:
                nearby.append({**ac, "dist_km": dist})

        on_ground = [a for a in nearby if a["on_ground"]]
        airborne = [a for a in nearby if not a["on_ground"]]
        low_alt = [a for a in airborne if a["alt_m"] is not None and a["alt_m"] < LOW_ALT_METERS]
        descending = [a for a in airborne if a["vertical_rate"] is not None and a["vertical_rate"] < -1]
        climbing = [a for a in airborne if a["vertical_rate"] is not None and a["vertical_rate"] > 1]

        # Count aircraft by airline
        airline_counts = {}
        for ac in nearby:
            airline = parse_airline(ac.get("callsign", ""))
            airline_counts[airline] = airline_counts.get(airline, 0) + 1

        results.append({
            "icao": apt["icao"],
            "iata": apt["iata"],
            "name": apt["name"],
            "city": apt["city"],
            "lat": apt["lat"],
            "lon": apt["lon"],
            "total_nearby": len(nearby),
            "on_ground": len(on_ground),
            "airborne": len(airborne),
            "low_altitude": len(low_alt),
            "descending": len(descending),
            "climbing": len(climbing),
            "active": len(low_alt) + len(on_ground),
            "airlines": airline_counts,
            "aircraft": nearby,
        })

    results.sort(key=lambda x: x["active"], reverse=True)
    return results


def get_congestion_snapshot():
    """Full pipeline: fetch + calculate + return ranked results."""
    aircraft, timestamp = fetch_us_aircraft()
    congestion = calculate_congestion(aircraft)
    ts = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return {
        "timestamp": ts.isoformat(),
        "total_us_aircraft": len(aircraft),
        "airports": congestion,
    }


if __name__ == "__main__":
    snapshot = get_congestion_snapshot()
    print(f"Time: {snapshot['timestamp']}")
    print(f"Total US aircraft: {snapshot['total_us_aircraft']}")
    print(f"\n{'Rank':<5} {'Airport':<25} {'Active':<8} {'Ground':<8} {'Low Alt':<8} {'Descend':<8} {'Climb':<8}")
    print("-" * 78)
    for i, apt in enumerate(snapshot["airports"][:15], 1):
        print(f"{i:<5} {apt['iata']} {apt['name']:<20} {apt['active']:<8} {apt['on_ground']:<8} {apt['low_altitude']:<8} {apt['descending']:<8} {apt['climbing']:<8}")
