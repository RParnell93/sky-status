"""Daily snapshot - fetches earthquake, wildfire, air quality, and campaign finance data into MotherDuck.

Usage:
    python pipelines/data_viz_snapshot.py              # Daily refresh (all sources)
    python pipelines/data_viz_snapshot.py --setup      # Create all MotherDuck tables
    python pipelines/data_viz_snapshot.py --check      # Show what's in the DB
    python pipelines/data_viz_snapshot.py --only earthquakes  # Run just one source

Requires:
    - MOTHERDUCK_TOKEN env var
    - DuckDB pinned to v1.4.4
"""

import csv
import io
import os
import sys
import time
from datetime import datetime, timezone

import duckdb
import requests

MOTHERDUCK_TOKEN = os.environ.get("MOTHERDUCK_TOKEN", "")
DB_URL = f"md:data_viz?motherduck_token={MOTHERDUCK_TOKEN}"

AQ_CITIES = [
    ("New York", 40.71, -74.01),
    ("Los Angeles", 34.05, -118.24),
    ("Chicago", 41.88, -87.63),
    ("Houston", 29.76, -95.37),
    ("Phoenix", 33.45, -112.07),
    ("Philadelphia", 39.95, -75.17),
    ("San Antonio", 29.42, -98.49),
    ("San Diego", 32.72, -117.16),
    ("Dallas", 32.78, -96.80),
    ("Austin", 30.27, -97.74),
    ("San Francisco", 37.77, -122.42),
    ("Seattle", 47.61, -122.33),
    ("Denver", 39.74, -104.99),
    ("Portland", 45.52, -122.68),
    ("Atlanta", 33.75, -84.39),
    ("Miami", 25.76, -80.19),
    ("Minneapolis", 44.98, -93.27),
    ("Detroit", 42.33, -83.05),
    ("Boston", 42.36, -71.06),
    ("Nashville", 36.16, -86.78),
    ("Salt Lake City", 40.76, -111.89),
    ("Sacramento", 38.58, -121.49),
    ("Boise", 43.62, -116.21),
    ("Reno", 39.53, -119.81),
    ("Fresno", 36.74, -119.77),
]


def get_connection():
    return duckdb.connect(DB_URL)


def setup_tables():
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS earthquakes (
            event_id VARCHAR PRIMARY KEY,
            magnitude DOUBLE,
            place VARCHAR,
            event_time TIMESTAMP,
            updated TIMESTAMP,
            latitude DOUBLE,
            longitude DOUBLE,
            depth_km DOUBLE,
            felt INTEGER,
            significance INTEGER,
            mag_type VARCHAR,
            event_type VARCHAR,
            tsunami INTEGER,
            alert VARCHAR,
            status VARCHAR,
            net VARCHAR,
            snapshot_date DATE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS wildfires (
            latitude DOUBLE,
            longitude DOUBLE,
            brightness DOUBLE,
            scan DOUBLE,
            track DOUBLE,
            acq_date DATE,
            acq_time VARCHAR,
            satellite VARCHAR,
            confidence VARCHAR,
            version VARCHAR,
            bright_ti5 DOUBLE,
            frp DOUBLE,
            daynight VARCHAR,
            snapshot_date DATE,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time, satellite)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS air_quality (
            city VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            pm2_5 DOUBLE,
            pm10 DOUBLE,
            us_aqi INTEGER,
            measure_time TIMESTAMP,
            snapshot_date DATE,
            PRIMARY KEY (city, snapshot_date)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS fec_donations (
            sub_id VARCHAR PRIMARY KEY,
            contribution_receipt_date DATE,
            contribution_receipt_amount DOUBLE,
            contributor_name VARCHAR,
            contributor_city VARCHAR,
            contributor_state VARCHAR,
            contributor_zip VARCHAR,
            contributor_employer VARCHAR,
            contributor_occupation VARCHAR,
            committee_id VARCHAR,
            committee_name VARCHAR,
            candidate_name VARCHAR,
            candidate_office VARCHAR,
            candidate_office_state VARCHAR,
            candidate_party VARCHAR,
            is_individual BOOLEAN,
            receipt_type_desc VARCHAR,
            two_year_transaction_period INTEGER,
            snapshot_date DATE
        )
    """)
    print("All tables created (or already exist).")
    con.close()


def fetch_earthquakes():
    print("\n=== Earthquakes (USGS) ===")
    r = requests.get(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    features = data["features"]
    print(f"  Fetched {len(features)} events")

    con = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inserted = 0

    for f in features:
        p = f["properties"]
        coords = f["geometry"]["coordinates"]
        try:
            con.execute("""
                INSERT OR IGNORE INTO earthquakes
                (event_id, magnitude, place, event_time, updated, latitude, longitude,
                 depth_km, felt, significance, mag_type, event_type, tsunami, alert,
                 status, net, snapshot_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                f["id"],
                p.get("mag"),
                p.get("place"),
                datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if p.get("time") else None,
                datetime.fromtimestamp(p["updated"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if p.get("updated") else None,
                coords[1], coords[0], coords[2],
                p.get("felt"), p.get("sig"), p.get("magType"), p.get("type"),
                p.get("tsunami"), p.get("alert"), p.get("status"), p.get("net"),
                today,
            ])
            inserted += 1
        except Exception:
            pass

    con.close()
    print(f"  Inserted {inserted} new events (dupes skipped)")


def fetch_wildfires():
    print("\n=== Wildfires (NASA FIRMS) ===")
    r = requests.get(
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
        timeout=30,
    )
    r.raise_for_status()

    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    print(f"  Fetched {len(rows)} fire detections (USA)")

    con = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    batch = []
    for row in rows:
        try:
            batch.append((
                float(row["latitude"]), float(row["longitude"]),
                float(row["bright_ti4"]), float(row["scan"]), float(row["track"]),
                row["acq_date"], row["acq_time"], row["satellite"],
                row["confidence"], row["version"],
                float(row["bright_ti5"]) if row.get("bright_ti5") else None,
                float(row["frp"]) if row.get("frp") else None,
                row["daynight"], today,
            ))
        except (ValueError, KeyError):
            pass

    if batch:
        con.execute("CREATE OR REPLACE TEMP TABLE _wf_staging AS SELECT * FROM wildfires WHERE 1=0")
        con.executemany("INSERT INTO _wf_staging VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
        con.execute("INSERT OR IGNORE INTO wildfires SELECT * FROM _wf_staging")
        con.execute("DROP TABLE IF EXISTS _wf_staging")

    con.close()
    print(f"  Inserted {len(batch)} fire detections (dupes skipped)")


def fetch_air_quality():
    print("\n=== Air Quality (Open-Meteo) ===")
    con = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    lats = ",".join(str(c[1]) for c in AQ_CITIES)
    lons = ",".join(str(c[2]) for c in AQ_CITIES)

    r = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
        "latitude": lats, "longitude": lons, "current": "pm2_5,pm10,us_aqi",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = data if isinstance(data, list) else [data]

    for i, city_data in enumerate(results):
        city_name = AQ_CITIES[i][0]
        current = city_data.get("current", {})
        try:
            con.execute("""
                INSERT OR REPLACE INTO air_quality
                (city, latitude, longitude, pm2_5, pm10, us_aqi, measure_time, snapshot_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                city_name, AQ_CITIES[i][1], AQ_CITIES[i][2],
                current.get("pm2_5"), current.get("pm10"), current.get("us_aqi"),
                now_str, today,
            ])
            inserted += 1
            print(f"  {city_name}: AQI={current.get('us_aqi', '?')}")
        except Exception as e:
            print(f"  {city_name}: error - {e}")

    con.close()
    print(f"  Inserted {inserted} city readings")


def fetch_fec_donations():
    print("\n=== Campaign Finance (FEC) ===")
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    con = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_inserted = 0
    page = 1
    last_index = None
    last_date = None

    while page <= 10:
        params = {
            "api_key": api_key, "per_page": 20,
            "sort": "-contribution_receipt_date",
            "min_amount": 10000, "two_year_transaction_period": 2026,
        }
        if last_index and last_date:
            params["last_index"] = last_index
            params["last_contribution_receipt_date"] = last_date

        try:
            r = requests.get("https://api.open.fec.gov/v1/schedules/schedule_a/", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  Page {page} error: {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        inserted = 0
        for item in results:
            sub_id = str(item.get("sub_id", ""))
            if not sub_id:
                continue
            committee = item.get("committee", {})
            try:
                con.execute("""
                    INSERT OR IGNORE INTO fec_donations
                    (sub_id, contribution_receipt_date, contribution_receipt_amount,
                     contributor_name, contributor_city, contributor_state, contributor_zip,
                     contributor_employer, contributor_occupation,
                     committee_id, committee_name,
                     candidate_name, candidate_office, candidate_office_state,
                     candidate_party, is_individual, receipt_type_desc,
                     two_year_transaction_period, snapshot_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    sub_id, item.get("contribution_receipt_date"),
                    item.get("contribution_receipt_amount"),
                    item.get("contributor_name"), item.get("contributor_city"),
                    item.get("contributor_state"), item.get("contributor_zip"),
                    item.get("contributor_employer"), item.get("contributor_occupation"),
                    item.get("committee_id"),
                    committee.get("name") or item.get("committee_name"),
                    item.get("candidate_name"), item.get("candidate_office"),
                    item.get("candidate_office_state"), committee.get("party"),
                    item.get("is_individual"), item.get("receipt_type_desc"),
                    item.get("two_year_transaction_period"), today,
                ])
                inserted += 1
            except Exception:
                pass

        total_inserted += inserted
        pagination = data.get("pagination", {})
        last_index = pagination.get("last_indexes", {}).get("last_index")
        last_date = pagination.get("last_indexes", {}).get("last_contribution_receipt_date")
        if not last_index:
            break
        page += 1
        time.sleep(0.5)

    con.close()
    print(f"  Inserted {total_inserted} new donations across {page} pages")


if __name__ == "__main__":
    if not MOTHERDUCK_TOKEN:
        print("ERROR: Set MOTHERDUCK_TOKEN env var.")
        sys.exit(1)

    if "--setup" in sys.argv:
        setup_tables()
    elif "--check" in sys.argv:
        from datetime import datetime
        con = get_connection()
        for table, query in [
            ("earthquakes", "SELECT COUNT(*) as n, MIN(event_time) as earliest, MAX(event_time) as latest, COUNT(DISTINCT snapshot_date) as days FROM earthquakes"),
            ("wildfires", "SELECT COUNT(*) as n, MIN(acq_date) as earliest, MAX(acq_date) as latest, COUNT(DISTINCT snapshot_date) as days FROM wildfires"),
            ("air_quality", "SELECT COUNT(*) as n, COUNT(DISTINCT city) as cities, COUNT(DISTINCT snapshot_date) as days FROM air_quality"),
            ("fec_donations", "SELECT COUNT(*) as n, SUM(contribution_receipt_amount) as total_dollars, COUNT(DISTINCT committee_name) as committees FROM fec_donations"),
        ]:
            try:
                row = con.execute(query).fetchone()
                print(f"\n=== {table} ===\n  {row}")
            except Exception as e:
                print(f"\n=== {table} === (not found: {e})")
        con.close()
    else:
        only = None
        if "--only" in sys.argv:
            idx = sys.argv.index("--only")
            only = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

        sources = {
            "earthquakes": fetch_earthquakes,
            "wildfires": fetch_wildfires,
            "air_quality": fetch_air_quality,
            "fec": fetch_fec_donations,
        }

        if only and only in sources:
            sources[only]()
        else:
            for name, func in sources.items():
                try:
                    func()
                except Exception as e:
                    print(f"\n  ERROR in {name}: {e}")

        print("\nSnapshot complete!")
