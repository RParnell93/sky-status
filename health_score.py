"""Traffic Health Score for US airports.

Inspired by Whoop's recovery score: 0-100 scale where 100 = healthy/free-flowing
and 0 = severely congested.

The score combines three independent signals:
  1. Ground Ratio (50% weight) - What fraction of active aircraft are stuck on the ground?
     High ground ratio = surface congestion (taxi delays, gate holds, runway queues).
  2. Flow Balance (25% weight) - Are arrivals and departures balanced?
     Imbalance = arrival waves overwhelming capacity or departure holds backing up gates.
  3. Low Altitude Density (25% weight) - How crowded is the airspace below 10,000ft?
     High density relative to airport capacity = sequencing delays, holding patterns.

Each component produces a 0-100 sub-score, then they're combined with weights.

Normalization uses per-airport historical baselines when available, falling back to
fixed thresholds derived from the top-30 US airports.
"""

from __future__ import annotations

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Fixed reference thresholds (calibrated for top-30 US airports)
# These are used when no historical baseline is available.
# ---------------------------------------------------------------------------

# Ground ratio: fraction of active aircraft on the ground.
# Healthy airport: ~40-55% on ground (normal turnover at gates).
# Congested: >75% on ground (planes sitting, not moving).
GROUND_RATIO_HEALTHY = 0.45   # at or below this -> score 100
GROUND_RATIO_CRITICAL = 0.85  # at or above this -> score 0

# Flow balance: |descending - climbing| / (descending + climbing).
# 0.0 = perfectly balanced, 1.0 = all traffic in one direction.
FLOW_IMBALANCE_HEALTHY = 0.15
FLOW_IMBALANCE_CRITICAL = 0.80

# Low altitude density: low_altitude / active.
# This measures how much of the active traffic is airborne at low alt vs. on ground.
# Counter-intuitive: HIGH low-alt ratio means planes are circling/stacking, not landing.
# Normal: ~30-50% of active count is low-altitude airborne.
# When it gets very high (>70%), planes are likely holding or sequencing.
LOW_ALT_RATIO_HEALTHY = 0.35
LOW_ALT_RATIO_CRITICAL = 0.75


# Component weights
W_GROUND = 0.40
W_FLOW = 0.25
W_LOW_ALT = 0.35


# ---------------------------------------------------------------------------
# Color thresholds
# ---------------------------------------------------------------------------
THRESHOLD_GREEN = 70    # >= 70: healthy, free-flowing
THRESHOLD_YELLOW = 40   # >= 40: moderate, some congestion
# < 40: critical


def _linear_score(value: float, healthy: float, critical: float) -> float:
    """Map a metric value to 0-100 where healthy=100 and critical=0.

    Values beyond the endpoints are clamped to [0, 100].
    """
    if critical == healthy:
        return 50.0
    # Normalize so that healthy -> 1.0, critical -> 0.0
    t = (value - healthy) / (critical - healthy)
    t = max(0.0, min(1.0, t))
    return round((1.0 - t) * 100, 1)


def airport_health_score(
    active: int,
    on_ground: int,
    airborne: int,
    low_altitude: int,
    descending: int,
    climbing: int,
    total_nearby: int,
    *,
    hist_avg_ground_ratio: Optional[float] = None,
    hist_avg_flow_imbalance: Optional[float] = None,
    hist_avg_low_alt_ratio: Optional[float] = None,
) -> dict:
    """Compute the Traffic Health Score for a single airport snapshot.

    Args:
        active: aircraft on ground + airborne below 10,000ft within 20km
        on_ground: aircraft at gates/taxiways/runways
        airborne: aircraft in the air within 20km
        low_altitude: airborne below 10,000ft
        descending: aircraft descending (arriving)
        climbing: aircraft departing
        total_nearby: all aircraft within 20km regardless of altitude
        hist_avg_ground_ratio: historical average ground ratio for this airport
            (used to set per-airport baseline instead of fixed thresholds)
        hist_avg_flow_imbalance: historical average flow imbalance
        hist_avg_low_alt_ratio: historical average low-altitude ratio

    Returns:
        dict with keys:
            score: int 0-100
            color: "green" | "yellow" | "red"
            label: "Healthy" | "Moderate" | "Congested"
            components: dict of sub-scores and raw values
    """
    # Handle airports with no activity
    if active <= 0:
        return {
            "score": 100,
            "color": "green",
            "label": "Inactive",
            "components": {
                "ground_ratio": {"raw": 0.0, "score": 100.0},
                "flow_balance": {"raw": 0.0, "score": 100.0},
                "low_alt_density": {"raw": 0.0, "score": 100.0},
            },
        }

    # --- Component 1: Ground Ratio (50% weight) ---
    ground_ratio = on_ground / active

    # If historical baseline is available, shift thresholds relative to it.
    # The idea: if ATL normally has 60% ground ratio, that's its baseline,
    # and "critical" is baseline + 0.25.
    if hist_avg_ground_ratio is not None:
        gr_healthy = hist_avg_ground_ratio - 0.05
        gr_critical = hist_avg_ground_ratio + 0.25
    else:
        gr_healthy = GROUND_RATIO_HEALTHY
        gr_critical = GROUND_RATIO_CRITICAL

    ground_score = _linear_score(ground_ratio, gr_healthy, gr_critical)

    # --- Component 2: Flow Balance (25% weight) ---
    flow_total = descending + climbing
    if flow_total >= 2:
        flow_imbalance = abs(descending - climbing) / flow_total
    else:
        # Too few moving aircraft to judge flow - assume neutral
        flow_imbalance = 0.0

    if hist_avg_flow_imbalance is not None:
        fi_healthy = hist_avg_flow_imbalance
        fi_critical = min(hist_avg_flow_imbalance + 0.50, 1.0)
    else:
        fi_healthy = FLOW_IMBALANCE_HEALTHY
        fi_critical = FLOW_IMBALANCE_CRITICAL

    flow_score = _linear_score(flow_imbalance, fi_healthy, fi_critical)

    # --- Component 3: Low Altitude Density (25% weight) ---
    low_alt_ratio = low_altitude / active

    if hist_avg_low_alt_ratio is not None:
        la_healthy = hist_avg_low_alt_ratio
        la_critical = min(hist_avg_low_alt_ratio + 0.30, 0.95)
    else:
        la_healthy = LOW_ALT_RATIO_HEALTHY
        la_critical = LOW_ALT_RATIO_CRITICAL

    low_alt_score = _linear_score(low_alt_ratio, la_healthy, la_critical)

    # --- Composite Score ---
    raw_score = (
        W_GROUND * ground_score
        + W_FLOW * flow_score
        + W_LOW_ALT * low_alt_score
    )

    # Also apply a "worst component drag" penalty: if any single component
    # is very low, the overall score can't stay high. This prevents a perfect
    # ground ratio from masking terrible airspace congestion (or vice versa).
    # Penalty kicks in when any component drops below 30.
    worst_component = min(ground_score, flow_score, low_alt_score)
    if worst_component < 30:
        # Drag the composite down by up to 20 points when worst = 0
        drag = (30 - worst_component) / 30 * 20
        raw_score = max(0, raw_score - drag)

    score = max(0, min(100, round(raw_score)))

    # Color and label
    if score >= THRESHOLD_GREEN:
        color, label = "green", "Healthy"
    elif score >= THRESHOLD_YELLOW:
        color, label = "yellow", "Moderate"
    else:
        color, label = "red", "Congested"

    return {
        "score": score,
        "color": color,
        "label": label,
        "components": {
            "ground_ratio": {"raw": round(ground_ratio, 3), "score": round(ground_score, 1)},
            "flow_balance": {"raw": round(flow_imbalance, 3), "score": round(flow_score, 1)},
            "low_alt_density": {"raw": round(low_alt_ratio, 3), "score": round(low_alt_score, 1)},
        },
    }


def system_health_score(airport_scores: list[dict], airport_data: list[dict]) -> dict:
    """Compute system-wide health score from individual airport scores.

    Uses activity-weighted average: busier airports count more. This prevents
    a bunch of quiet airports with perfect scores from masking a few congested
    hubs.

    Args:
        airport_scores: list of dicts from airport_health_score()
        airport_data: list of airport data dicts (must have "active" key),
            in the same order as airport_scores

    Returns:
        dict with score, color, label, plus airport_count and breakdown stats
    """
    if not airport_scores:
        return {"score": 100, "color": "green", "label": "No Data",
                "airport_count": 0, "healthy": 0, "moderate": 0, "congested": 0}

    total_weight = 0
    weighted_sum = 0
    healthy_count = 0
    moderate_count = 0
    congested_count = 0

    for sc, apt in zip(airport_scores, airport_data):
        weight = max(apt.get("active", 0), 1)  # min weight of 1
        weighted_sum += sc["score"] * weight
        total_weight += weight

        if sc["color"] == "green":
            healthy_count += 1
        elif sc["color"] == "yellow":
            moderate_count += 1
        else:
            congested_count += 1

    score = round(weighted_sum / total_weight) if total_weight else 100
    score = max(0, min(100, score))

    if score >= THRESHOLD_GREEN:
        color, label = "green", "Healthy"
    elif score >= THRESHOLD_YELLOW:
        color, label = "yellow", "Moderate"
    else:
        color, label = "red", "Congested"

    return {
        "score": score,
        "color": color,
        "label": label,
        "airport_count": len(airport_scores),
        "healthy": healthy_count,
        "moderate": moderate_count,
        "congested": congested_count,
    }


def score_snapshot(airports: list[dict], historical: Optional[dict] = None) -> dict:
    """Score an entire snapshot at once.

    Args:
        airports: list of airport dicts from get_congestion_snapshot()["airports"]
        historical: optional dict mapping ICAO code -> {
            "avg_ground_ratio": float,
            "avg_flow_imbalance": float,
            "avg_low_alt_ratio": float,
        }

    Returns:
        dict with:
            system: system-level score dict
            airports: list of (airport_data, score_dict) tuples, sorted by score ascending (worst first)
    """
    historical = historical or {}
    results = []

    for apt in airports:
        hist = historical.get(apt.get("icao", ""), {})
        sc = airport_health_score(
            active=apt.get("active", 0),
            on_ground=apt.get("on_ground", 0),
            airborne=apt.get("airborne", 0),
            low_altitude=apt.get("low_altitude", 0),
            descending=apt.get("descending", 0),
            climbing=apt.get("climbing", 0),
            total_nearby=apt.get("total_nearby", 0),
            hist_avg_ground_ratio=hist.get("avg_ground_ratio"),
            hist_avg_flow_imbalance=hist.get("avg_flow_imbalance"),
            hist_avg_low_alt_ratio=hist.get("avg_low_alt_ratio"),
        )
        results.append((apt, sc))

    scores_only = [sc for _, sc in results]
    data_only = [apt for apt, _ in results]
    sys_score = system_health_score(scores_only, data_only)

    # Sort worst-first for the leaderboard
    results.sort(key=lambda x: x[1]["score"])

    return {
        "system": sys_score,
        "airports": results,
    }


def compute_historical_baselines(rows: list[tuple]) -> dict:
    """Compute per-airport historical baselines from MotherDuck query results.

    Args:
        rows: list of tuples from a query like:
            SELECT icao, AVG(on_ground), AVG(active), AVG(low_altitude),
                   AVG(descending), AVG(climbing)
            FROM airport_congestion
            WHERE snapshot_time >= now() - INTERVAL '7 days'
            GROUP BY icao

    Returns:
        dict mapping ICAO -> baseline dict for use with score_snapshot()
    """
    baselines = {}
    for row in rows:
        icao = row[0]
        avg_ground = row[1] or 0
        avg_active = row[2] or 0
        avg_low_alt = row[3] or 0
        avg_descending = row[4] or 0
        avg_climbing = row[5] or 0

        if avg_active < 1:
            continue

        flow_total = avg_descending + avg_climbing
        baselines[icao] = {
            "avg_ground_ratio": avg_ground / avg_active,
            "avg_flow_imbalance": abs(avg_descending - avg_climbing) / flow_total if flow_total >= 2 else 0.0,
            "avg_low_alt_ratio": avg_low_alt / avg_active,
        }

    return baselines


# ---------------------------------------------------------------------------
# Color values for UI integration
# ---------------------------------------------------------------------------
SCORE_COLORS = {
    "green": "#22c55e",   # healthy
    "yellow": "#eab308",  # moderate
    "red": "#ef4444",     # congested
}


def score_color_hex(color: str) -> str:
    """Get hex color for a score color name."""
    return SCORE_COLORS.get(color, "#8B9DAF")


# ---------------------------------------------------------------------------
# Demo / sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Traffic Health Score - Test Cases ===\n")

    cases = [
        ("Healthy hub (ATL-like)", dict(
            active=45, on_ground=20, airborne=25, low_altitude=18,
            descending=10, climbing=9, total_nearby=60)),
        ("Ground-congested (delays)", dict(
            active=40, on_ground=35, airborne=5, low_altitude=4,
            descending=1, climbing=1, total_nearby=55)),
        ("Arrival wave (JFK evening)", dict(
            active=30, on_ground=10, airborne=20, low_altitude=18,
            descending=15, climbing=2, total_nearby=40)),
        ("Quiet airport (PDX morning)", dict(
            active=8, on_ground=3, airborne=5, low_altitude=4,
            descending=2, climbing=2, total_nearby=12)),
        ("Holding pattern hell", dict(
            active=35, on_ground=8, airborne=27, low_altitude=25,
            descending=5, climbing=3, total_nearby=50)),
        ("Perfectly balanced", dict(
            active=30, on_ground=14, airborne=16, low_altitude=10,
            descending=7, climbing=7, total_nearby=38)),
        ("Empty airport", dict(
            active=0, on_ground=0, airborne=0, low_altitude=0,
            descending=0, climbing=0, total_nearby=0)),
    ]

    all_scores = []
    all_data = []
    for name, data in cases:
        sc = airport_health_score(**data)
        all_scores.append(sc)
        all_data.append(data)
        comps = sc["components"]
        print(f"{name}")
        print(f"  Score: {sc['score']} ({sc['label']}, {sc['color']})")
        print(f"  Ground Ratio: {comps['ground_ratio']['raw']:.0%} -> {comps['ground_ratio']['score']}")
        print(f"  Flow Balance: {comps['flow_balance']['raw']:.0%} -> {comps['flow_balance']['score']}")
        print(f"  Low Alt Density: {comps['low_alt_density']['raw']:.0%} -> {comps['low_alt_density']['score']}")
        print()

    sys = system_health_score(all_scores, all_data)
    print(f"System Score: {sys['score']} ({sys['label']})")
    print(f"  {sys['healthy']} healthy, {sys['moderate']} moderate, {sys['congested']} congested")
