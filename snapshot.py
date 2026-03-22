"""Save airport congestion snapshots to MotherDuck for historical analysis.

Usage:
    python snapshot.py              # Take a snapshot now
    python snapshot.py --setup      # Create MotherDuck table
    python snapshot.py --check      # Show what's in the DB
"""

import os
import sys
from datetime import datetime, timezone

import duckdb

from fetch import get_congestion_snapshot

# Load env
def load_env():
    for env_path in [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", "baseball-analytics", ".env"),
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"'))

load_env()
MOTHERDUCK_TOKEN = os.environ.get("MOTHERDUCK_TOKEN", "")
DB_URL = f"md:data_viz?motherduck_token={MOTHERDUCK_TOKEN}"


def get_connection():
    return duckdb.connect(DB_URL)


def setup_tables():
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS airport_congestion (
            snapshot_time TIMESTAMP,
            total_us_aircraft INTEGER,
            icao VARCHAR,
            iata VARCHAR,
            airport_name VARCHAR,
            active INTEGER,
            on_ground INTEGER,
            airborne INTEGER,
            low_altitude INTEGER,
            descending INTEGER,
            climbing INTEGER,
            total_nearby INTEGER,
            PRIMARY KEY (snapshot_time, icao)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS airport_airlines (
            snapshot_time TIMESTAMP,
            icao VARCHAR,
            iata VARCHAR,
            airline VARCHAR,
            count INTEGER,
            PRIMARY KEY (snapshot_time, icao, airline)
        )
    """)
    print("Tables created (or already exist).")
    con.close()


def take_snapshot():
    if not MOTHERDUCK_TOKEN:
        print("ERROR: Set MOTHERDUCK_TOKEN")
        return

    print("Fetching live data...")
    data = get_congestion_snapshot()
    ts = data["timestamp"]
    total = data["total_us_aircraft"]

    con = get_connection()
    inserted = 0
    errors = []
    for apt in data["airports"]:
        if apt["total_nearby"] == 0:
            continue
        try:
            con.execute("""
                INSERT OR IGNORE INTO airport_congestion
                (snapshot_time, total_us_aircraft, icao, iata, airport_name,
                 active, on_ground, airborne, low_altitude, descending, climbing, total_nearby)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ts, total, apt["icao"], apt["iata"], apt["name"],
                apt["active"], apt["on_ground"], apt["airborne"],
                apt["low_altitude"], apt["descending"], apt["climbing"], apt["total_nearby"],
            ])
            inserted += 1
        except Exception as e:
            errors.append(f"{apt['icao']}: {e}")

    # Save airline breakdown
    airline_inserted = 0
    for apt in data["airports"]:
        for airline, count in apt.get("airlines", {}).items():
            try:
                con.execute("""
                    INSERT OR IGNORE INTO airport_airlines
                    (snapshot_time, icao, iata, airline, count)
                    VALUES (?, ?, ?, ?, ?)
                """, [ts, apt["icao"], apt["iata"], airline, count])
                airline_inserted += 1
            except Exception as e:
                errors.append(f"{apt['icao']}/{airline}: {e}")

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for err in errors[:10]:
            print(f"  {err}")
        sys.exit(1)

    con.close()
    print(f"Saved {inserted} airport readings + {airline_inserted} airline rows at {ts}")
    print(f"Total US aircraft: {total}")
    top5 = sorted(data["airports"], key=lambda x: x["active"], reverse=True)[:5]
    for i, a in enumerate(top5, 1):
        airlines_str = ", ".join(f"{k}:{v}" for k, v in sorted(a.get("airlines", {}).items(), key=lambda x: -x[1])[:3])
        print(f"  {i}. {a['iata']} {a['name']}: {a['active']} active ({airlines_str})")


def check_db():
    con = get_connection()
    row = con.execute("""
        SELECT COUNT(*) as rows,
               COUNT(DISTINCT snapshot_time) as snapshots,
               MIN(snapshot_time) as earliest,
               MAX(snapshot_time) as latest
        FROM airport_congestion
    """).fetchone()
    print(f"Rows: {row[0]}, Snapshots: {row[1]}")
    print(f"Range: {row[2]} to {row[3]}")

    # Busiest airport across all snapshots
    top = con.execute("""
        SELECT iata, airport_name, AVG(active) as avg_active, MAX(active) as max_active,
               COUNT(*) as observations
        FROM airport_congestion
        GROUP BY iata, airport_name
        ORDER BY avg_active DESC
        LIMIT 10
    """).fetchall()
    if top:
        print(f"\nTop airports by avg congestion:")
        for r in top:
            print(f"  {r[0]} {r[1]}: avg={r[2]:.1f} max={r[3]} ({r[4]} obs)")
    con.close()


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup_tables()
    elif "--check" in sys.argv:
        check_db()
    else:
        take_snapshot()
