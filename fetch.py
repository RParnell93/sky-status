"""Fetch live aircraft data and calculate airport congestion."""

import math
import time
from datetime import datetime, timezone

import requests

from airports import AIRPORTS

# Radius in km to count aircraft around an airport
AIRPORT_RADIUS_KM = 20  # ~10.8 nautical miles
LOW_ALT_METERS = 3048   # 10,000 feet - aircraft likely arriving/departing

# ICAO callsign prefix -> airline name
# Major US carriers
AIRLINE_PREFIXES = {
    "AAL": "American", "DAL": "Delta", "UAL": "United", "SWA": "Southwest",
    "JBU": "JetBlue", "NKS": "Spirit", "FFT": "Frontier", "ASA": "Alaska",
    "HAL": "Hawaiian", "AAY": "Allegiant", "SCX": "Sun Country",
    # US regional / feeder
    "SKW": "SkyWest", "RPA": "Republic", "ENY": "Envoy", "PDT": "Piedmont",
    "MES": "Mesa", "GJS": "GoJet", "CPZ": "Compass", "AIP": "Alpine Air",
    "BTA": "Horizon Air", "QXE": "Horizon Air", "JIA": "PSA Airlines",
    "EDV": "Endeavor", "OPT": "CommutAir", "BRE": "Breeze",
    # Cargo / freight
    "FDX": "FedEx", "UPS": "UPS", "GTI": "Atlas Air", "ABX": "ABX Air",
    "ATN": "ATSG", "KFS": "Kalitta", "PAC": "Polar Air", "CLX": "Cargolux",
    "GEC": "Lufthansa Cargo", "BOX": "Aerologic", "MPH": "Amerijet",
    "STZ": "Silverback Cargo",
    # Private / charter / business
    "EJA": "NetJets", "LXJ": "Flexjet", "XOJ": "XOJET", "TWY": "Wheels Up",
    "VNR": "VistaJet", "TCF": "Shuttle America", "JTL": "Jet Linx",
    # International (common at US airports)
    "ACA": "Air Canada", "WJA": "WestJet", "BAW": "British Airways",
    "DLH": "Lufthansa", "AFR": "Air France", "UAE": "Emirates",
    "JAL": "JAL", "ANA": "ANA", "QFA": "Qantas", "KLM": "KLM",
    "ETH": "Ethiopian", "AAR": "Asiana", "KAL": "Korean Air",
    "CPA": "Cathay Pacific", "SIA": "Singapore", "THY": "Turkish",
    "QTR": "Qatar", "ETD": "Etihad", "TAP": "TAP Portugal",
    "SAS": "SAS", "FIN": "Finnair", "AUA": "Austrian", "SWR": "Swiss",
    "IBE": "Iberia", "EIN": "Aer Lingus", "ICE": "Icelandair",
    "VOI": "Volaris", "VIV": "VivaAerobus", "AMX": "Aeromexico",
    "CMP": "Copa", "AVA": "Avianca", "ARE": "Aires",
    "AZU": "Azul", "GLO": "GOL", "TAM": "LATAM",
    "WZZ": "Wizz Air", "RYR": "Ryanair", "EZY": "easyJet",
    "VRD": "Virgin Atlantic", "CCA": "Air China", "CES": "China Eastern",
    "CSN": "China Southern", "EVA": "EVA Air", "CAL": "China Airlines",
    "PAL": "Philippine", "MAS": "Malaysia",
    # US military (common over US airspace)
    "RCH": "USAF", "AIO": "USAF", "CNV": "USAF", "DUKE": "USAF",
}


def parse_airline(callsign):
    """Extract airline name from ICAO callsign prefix (first 3 chars)."""
    if not callsign or len(callsign) < 3:
        return "Other"
    prefix = callsign[:3].upper()
    match = AIRLINE_PREFIXES.get(prefix)
    if match:
        return match
    # N-registered aircraft are US private / general aviation
    if callsign[0] == "N" and callsign[1:2].isdigit():
        return "Private/GA"
    return "Other"


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_us_aircraft():
    """Fetch all aircraft over the US from OpenSky Network."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retries = Retry(total=3, backoff_factor=10, status_forcelist=[429, 500, 502, 503])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    r = session.get("https://opensky-network.org/api/states/all", params={
        "lamin": 24, "lamax": 50,
        "lomin": -125, "lomax": -66,
    }, timeout=(10, 30))
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

        # Count aircraft by airline (total + per-status breakdown)
        airline_counts = {}
        airline_status = {}
        for ac in nearby:
            airline = parse_airline(ac.get("callsign", ""))
            airline_counts[airline] = airline_counts.get(airline, 0) + 1
            if airline not in airline_status:
                airline_status[airline] = {"on_ground": 0, "descending": 0, "climbing": 0, "low_alt": 0}
            if ac["on_ground"]:
                airline_status[airline]["on_ground"] += 1
            elif ac.get("vertical_rate") is not None and ac["vertical_rate"] < -1:
                airline_status[airline]["descending"] += 1
            elif ac.get("vertical_rate") is not None and ac["vertical_rate"] > 1:
                airline_status[airline]["climbing"] += 1
            elif ac.get("alt_m") is not None and ac["alt_m"] < LOW_ALT_METERS:
                airline_status[airline]["low_alt"] += 1

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
            "airline_status": airline_status,
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
