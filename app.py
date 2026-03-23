import os
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from fetch import get_congestion_snapshot

st.set_page_config(page_title="Sky Status", page_icon="favicon.svg", layout="wide")

# Detect browser timezone via JS, default to US Eastern
import streamlit.components.v1 as _components

if "tz" not in st.query_params:
    _components.html("""<script>
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const url = new URL(window.parent.location);
    url.searchParams.set('tz', tz);
    window.parent.location.replace(url.toString());
    </script>""", height=0)
    st.stop()

_tz_name = st.query_params.get("tz", "America/New_York")
try:
    USER_TZ = ZoneInfo(_tz_name)
except Exception:
    USER_TZ = ZoneInfo("America/New_York")
_tz_abbr = datetime.now(timezone.utc).astimezone(USER_TZ).strftime("%Z")

# Delta-inspired palette
# Navy: #003366 / #00234B  Red: #C8102E  White  Silver: #8B9DAF  Light gray: #E8ECF0
NAVY = "#00234B"
NAVY_MID = "#003366"
NAVY_LIGHT = "#0A4A7A"
RED = "#C8102E"
RED_LIGHT = "#E8354A"
SILVER = "#8B9DAF"
SILVER_DARK = "#94A5B7"
WHITE = "#FFFFFF"
GRAY_BG = "#F0F2F5"

CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
    html, body, [class*="css"], .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}
    h1, h2, h3 {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 800 !important; letter-spacing: -0.5px;
    }}
    .stApp {{ background: {NAVY}; }}

    /* Header bar */
    .sky-header {{
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY_MID} 100%);
        padding: 20px 0 12px 0;
        border-bottom: 3px solid {RED};
        margin-bottom: 20px;
    }}
    .sky-title {{
        font-size: 2.2em; font-weight: 900; color: {WHITE};
        letter-spacing: 2px; text-transform: uppercase;
        display: flex; align-items: center; gap: 14px;
    }}
    .sky-title .delta-widget {{
        background: {RED}; color: white; font-size: 0.35em;
        padding: 4px 10px; border-radius: 4px; font-weight: 700;
        letter-spacing: 1px; vertical-align: middle;
    }}
    .sky-subtitle {{
        font-size: 0.8em; color: {SILVER}; margin-top: 2px;
        font-weight: 500; letter-spacing: 0.5px;
    }}

    /* Metric cards */
    .metric-card {{
        background: linear-gradient(135deg, {NAVY_MID} 0%, {NAVY} 100%);
        border-radius: 10px; padding: 18px 14px; text-align: center;
        border: 1px solid rgba(255,255,255,0.06);
        border-top: 3px solid {RED};
    }}
    .metric-value {{ font-size: 2em; font-weight: 900; color: {WHITE}; font-family: 'JetBrains Mono', monospace !important; }}
    .metric-label {{ font-size: 0.65em; color: {SILVER}; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 4px; font-weight: 600; }}
    .metric-sub {{ font-size: 0.55em; color: {SILVER_DARK}; margin-top: 5px; line-height: 1.3; }}

    /* Leaderboard */
    .leaderboard-row {{
        display: flex; align-items: center; padding: 10px 16px; margin: 3px 0;
        background: linear-gradient(135deg, {NAVY_MID}cc 0%, {NAVY}ee 100%);
        border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);
        gap: 12px; transition: all 0.2s;
    }}
    .leaderboard-row:hover {{
        border-color: {RED}44;
        background: linear-gradient(135deg, {NAVY_MID} 0%, {NAVY_LIGHT}44 100%);
    }}
    .leaderboard-row.top-1 {{ border-left: 3px solid {RED}; }}
    .leaderboard-row.top-2 {{ border-left: 3px solid {SILVER}; }}
    .leaderboard-row.top-3 {{ border-left: 3px solid {SILVER_DARK}; }}
    .lb-rank {{
        font-size: 1em; font-weight: 800; color: {SILVER};
        min-width: 24px; text-align: center;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .lb-rank.gold {{ color: {RED}; }}
    .lb-rank.silver {{ color: {WHITE}; }}
    .lb-rank.bronze {{ color: {SILVER}; }}
    .lb-iata {{
        font-size: 1.1em; font-weight: 900; color: {WHITE}; min-width: 40px;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .lb-name {{ font-size: 0.78em; color: {SILVER}; flex: 1; font-weight: 500; }}
    .lb-bar-bg {{
        flex: 2; height: 22px; background: rgba(255,255,255,0.04);
        border-radius: 4px; position: relative; overflow: hidden; min-width: 100px;
    }}
    .lb-bar {{
        height: 100%; border-radius: 4px;
        background: linear-gradient(90deg, {NAVY_LIGHT}, {SILVER_DARK});
        transition: width 0.5s ease;
    }}
    .lb-bar.hot {{ background: linear-gradient(90deg, {RED}, {RED_LIGHT}); }}
    .lb-bar.warm {{ background: linear-gradient(90deg, {NAVY_LIGHT}, {SILVER}); }}
    .lb-count {{
        font-size: 0.9em; font-weight: 800; color: {WHITE};
        min-width: 28px; text-align: right;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .lb-detail {{
        font-size: 0.6em; color: {SILVER_DARK}; min-width: 90px; text-align: right;
        font-family: 'JetBrains Mono', monospace !important;
    }}

    /* Live dot */
    .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
    .status-dot.live {{ background: #22c55e; animation: pulse 2s infinite; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}

    /* Section headers */
    .section-header {{
        color: {WHITE}; font-size: 1.1em; font-weight: 800;
        text-transform: uppercase; letter-spacing: 1px;
        padding-bottom: 8px; margin-top: 8px;
        border-bottom: 2px solid {RED};
        display: inline-block;
    }}

    /* Override Streamlit defaults for dark navy bg */
    .stCaption {{ color: {SILVER_DARK} !important; }}
    [data-testid="stExpander"] {{ border-color: rgba(255,255,255,0.06) !important; }}

    /* Mobile responsiveness */
    @media (max-width: 768px) {{
        /* Header */
        .sky-header {{ padding: 14px 0 10px 0; margin-bottom: 12px; }}
        .sky-title {{
            font-size: clamp(1.2rem, 5vw, 2.2rem);
            letter-spacing: 1px; gap: 8px;
            flex-wrap: wrap;
        }}
        .sky-title svg {{ width: 28px; height: 28px; }}
        .sky-title .delta-widget {{ font-size: 0.4em; padding: 3px 8px; }}
        .sky-subtitle {{ font-size: clamp(0.6rem, 2.5vw, 0.8rem); }}

        /* Metric cards - 3x2 grid instead of 6 across */
        div[data-testid="stHorizontalBlock"] {{ gap: 0.5rem !important; flex-wrap: wrap !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
            min-width: 30% !important;
            flex: 1 1 30% !important;
        }}
        .metric-card {{
            padding: 10px 6px;
            overflow-wrap: break-word;
            word-break: break-word;
        }}
        .metric-value {{ font-size: clamp(1.2rem, 5vw, 2em); }}
        .metric-label {{ font-size: clamp(0.45rem, 1.8vw, 0.65em); letter-spacing: 0.5px; }}
        .metric-sub {{ font-size: clamp(0.4rem, 1.5vw, 0.55em); line-height: 1.2; }}

        /* Leaderboard */
        .leaderboard-row {{ padding: 8px 8px; gap: 6px; }}
        .lb-rank {{ font-size: 0.85em; min-width: 20px; }}
        .lb-iata {{ font-size: 0.95em; min-width: 34px; }}
        .lb-name {{ display: none; }}
        .lb-bar-bg {{ min-width: 50px; flex: 1.5; height: 18px; }}
        .lb-count {{ font-size: 0.8em; min-width: 24px; }}
        .lb-detail {{ font-size: 0.45em; min-width: 50px; }}

        /* Section headers */
        .section-header {{ font-size: clamp(0.8rem, 2.5vw, 1.1em); }}

        /* Touch targets - minimum 44px for tappable elements */
        button, [role="button"],
        .stSelectbox > div > div,
        [data-testid="stSelectbox"] > div > div {{
            min-height: 44px !important;
        }}
        [data-testid="stExpander"] summary {{
            min-height: 44px !important;
            display: flex;
            align-items: center;
        }}
        /* Selectbox font readable on mobile */
        .stSelectbox label, [data-testid="stSelectbox"] label {{
            font-size: clamp(0.75rem, 2.5vw, 0.875rem) !important;
        }}

        /* AI summary card */
        div[style*="border-left:3px solid"] {{
            padding: 0.75rem 1rem !important;
        }}

        /* General overflow protection */
        .stApp div {{
            overflow-wrap: break-word;
        }}
    }}

    /* Extra small screens (phones in portrait) */
    @media (max-width: 480px) {{
        .sky-title {{ font-size: clamp(1rem, 5vw, 1.5rem); letter-spacing: 0.5px; }}
        .sky-title .delta-widget {{ font-size: 0.35em; }}
        .metric-value {{ font-size: clamp(1rem, 4.5vw, 1.5rem); }}
        .metric-label {{ font-size: clamp(0.4rem, 1.6vw, 0.55em); letter-spacing: 0; }}
        .metric-sub {{ display: none; }}
        .leaderboard-row {{ padding: 6px 6px; gap: 4px; }}
        .lb-detail {{ display: none; }}
        .lb-bar-bg {{ min-width: 40px; }}
    }}

    /* Plotly chart height cap on mobile - map and side-by-side charts */
    @media (max-width: 768px) {{
        [data-testid="stPlotlyChart"] > div {{
            max-height: 400px !important;
        }}
    }}

    /* Data dictionary table scroll on mobile */
    @media (max-width: 768px) {{
        [data-testid="stExpander"] table {{
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
    }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Header
_plane_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="38" height="38" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;transform:rotate(-45deg);"><path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.3c.4-.2.6-.7.5-1.1z"/></svg>'
st.markdown(
    f'<div class="sky-header">'
    f'<div class="sky-title">{_plane_svg} SKY STATUS <span class="delta-widget">LIVE</span></div>'
    f'<div class="sky-subtitle"><span class="status-dot live"></span>Real-time US airport congestion tracker</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# Fetch data - try MotherDuck first, fall back to live API
def _load_from_motherduck():
    """Load latest snapshot from MotherDuck."""
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        try:
            token = st.secrets["MOTHERDUCK_TOKEN"]
        except (KeyError, FileNotFoundError):
            return None
    if not token:
        return None
    try:
        import duckdb
        con = duckdb.connect(f"md:data_viz?motherduck_token={token}")
        # Get most recent snapshot
        meta = con.execute("""
            SELECT snapshot_time, total_us_aircraft
            FROM airport_congestion
            ORDER BY snapshot_time DESC LIMIT 1
        """).fetchone()
        if not meta:
            con.close()
            return None
        snap_time, total_aircraft = meta
        rows = con.execute("""
            SELECT icao, iata, airport_name, active, on_ground, airborne,
                   low_altitude, descending, climbing, total_nearby
            FROM airport_congestion
            WHERE snapshot_time = ?
            ORDER BY active DESC
        """, [snap_time]).fetchall()
        # Load airline breakdown with status for this snapshot
        try:
            airline_rows = con.execute("""
                SELECT icao, airline, count, on_ground, descending, climbing, low_alt
                FROM airport_airlines
                WHERE snapshot_time = ?
            """, [snap_time]).fetchall()
            _has_status = True
        except Exception:
            # Fallback if status columns don't exist yet
            airline_rows = con.execute("""
                SELECT icao, airline, count
                FROM airport_airlines
                WHERE snapshot_time = ?
            """, [snap_time]).fetchall()
            _has_status = False
        con.close()
        # Build airline lookup: icao -> {airline: count}
        airline_lookup = {}
        airline_status_lookup = {}
        for ar in airline_rows:
            airline_lookup.setdefault(ar[0], {})[ar[1]] = ar[2]
            if _has_status:
                airline_status_lookup.setdefault(ar[0], {})[ar[1]] = {
                    "on_ground": ar[3] or 0, "descending": ar[4] or 0,
                    "climbing": ar[5] or 0, "low_alt": ar[6] or 0,
                }
        airports = []
        for r in rows:
            airports.append({
                "icao": r[0], "iata": r[1], "name": r[2],
                "lat": next((a["lat"] for a in AIRPORTS if a["icao"] == r[0]), 0),
                "lon": next((a["lon"] for a in AIRPORTS if a["icao"] == r[0]), 0),
                "active": r[3], "on_ground": r[4], "airborne": r[5],
                "low_altitude": r[6], "descending": r[7], "climbing": r[8],
                "total_nearby": r[9], "aircraft": [],
                "airlines": airline_lookup.get(r[0], {}),
                "airline_status": airline_status_lookup.get(r[0], {}),
            })
        return {
            "timestamp": snap_time if isinstance(snap_time, str) else snap_time.isoformat(),
            "total_us_aircraft": total_aircraft,
            "airports": airports,
            "source": "MotherDuck",
        }
    except Exception as e:
        return None


@st.cache_data(ttl=120)
def load_snapshot():
    # Try MotherDuck first (fast, no external API timeout risk)
    md = _load_from_motherduck()
    if md:
        return md
    # Fall back to live API
    data = get_congestion_snapshot()
    data["source"] = "OpenSky Live"
    return data

from airports import AIRPORTS
from health_score import (
    score_snapshot, score_color_hex, compute_historical_baselines,
    airport_health_score, system_health_score, SCORE_COLORS,
    THRESHOLD_GREEN, THRESHOLD_YELLOW,
)

with st.spinner("Loading airport data..."):
    snapshot = load_snapshot()

ts = datetime.fromisoformat(snapshot["timestamp"])
ts_local = ts.astimezone(USER_TZ)
local_ts = ts_local.strftime(f"%b %d, %Y %I:%M %p {_tz_abbr}")

# Top metrics
active_airports = sum(1 for a in snapshot["airports"] if a["active"] > 0)
total_active = sum(a["active"] for a in snapshot["airports"])
busiest = snapshot["airports"][0] if snapshot["airports"] else None

total_ground = sum(a["on_ground"] for a in snapshot["airports"])
total_descending = sum(a["descending"] for a in snapshot["airports"])
total_climbing = sum(a["climbing"] for a in snapshot["airports"])
ground_pct = round(total_ground / total_active * 100) if total_active else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{snapshot["total_us_aircraft"]:,}</div><div class="metric-label">Aircraft Over US</div><div class="metric-sub">All ADS-B transponders in US airspace</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{active_airports}</div><div class="metric-label">Active Airports</div><div class="metric-sub">With at least 1 aircraft nearby</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_active}</div><div class="metric-label">Near Airports</div><div class="metric-sub">Within 20km and below 10,000ft</div></div>', unsafe_allow_html=True)
with c4:
    if busiest:
        busiest_gpct = round(busiest["on_ground"] / busiest["active"] * 100) if busiest["active"] else 0
        st.markdown(f'<div class="metric-card"><div class="metric-value">{busiest["iata"]}</div><div class="metric-label">Busiest Right Now</div><div class="metric-sub">{busiest["active"]} active, {busiest_gpct}% on ground</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{ground_pct}%</div><div class="metric-label">On Ground</div><div class="metric-sub">At gates, taxiways, or runways</div></div>', unsafe_allow_html=True)
with c6:
    total_airborne = sum(a["airborne"] for a in snapshot["airports"])
    arrival_pct = round(total_descending / total_airborne * 100) if total_airborne else 0
    arr_color = RED if arrival_pct >= 60 else RED_LIGHT if arrival_pct >= 40 else WHITE
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{arr_color}">{total_descending}</div><div class="metric-label">Inbound Now</div><div class="metric-sub">Descending within 20km right now</div></div>', unsafe_allow_html=True)

_src = snapshot.get("source", "OpenSky")
st.caption(f"Updated: {local_ts}  |  Source: {_src}  |  Refreshes every 2 min")


# ---------------------------------------------------------------------------
# AI Summary + FAA Advisories (functions + display)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _fetch_faa_status():
    """Fetch FAA airport status advisories from NASSTATUS XML API."""
    import requests
    import xml.etree.ElementTree as ET
    try:
        r = requests.get("https://nasstatus.faa.gov/api/airport-status-information", timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        advisories = []
        for delay_type in root.findall("Delay_type"):
            for gd in delay_type.findall(".//Ground_Delay"):
                arpt = gd.findtext("ARPT", "")
                reason = gd.findtext("Reason", "")
                avg = gd.findtext("Avg", "")
                mx = gd.findtext("Max", "")
                advisories.append(f"{arpt}: Ground Delay Program - {reason}, avg {avg}, max {mx}")
            for gs in delay_type.findall(".//Ground_Stop"):
                arpt = gs.findtext("ARPT", "")
                reason = gs.findtext("Reason", "")
                end = gs.findtext("End_Time", "")
                advisories.append(f"{arpt}: Ground Stop - {reason}, until {end}")
            for ad in delay_type.findall(".//Arrive_Depart_Delay"):
                arpt = ad.findtext("ARPT", "")
                reason = ad.findtext("Reason", "")
                mn = ad.findtext("Min", "")
                mx = ad.findtext("Max", "")
                trend = ad.findtext("Trend", "")
                advisories.append(f"{arpt}: Arrival/Departure Delay - {reason}, {mn}-{mx}, trend {trend}")
            for cl in delay_type.findall(".//Closure"):
                arpt = cl.findtext("ARPT", "")
                reason = cl.findtext("Reason", "")
                advisories.append(f"{arpt}: CLOSED - {reason}")
        return advisories
    except Exception:
        return []


def _build_sky_prompt(snapshot_data, ts_str):
    """Build a structured prompt with all current data for the AI summary."""
    top10 = snapshot_data["airports"][:10]
    total_ac = snapshot_data["total_us_aircraft"]
    _total_active = sum(a["active"] for a in snapshot_data["airports"])
    _total_ground = sum(a["on_ground"] for a in snapshot_data["airports"])
    _total_desc = sum(a["descending"] for a in snapshot_data["airports"])
    _total_climb = sum(a["climbing"] for a in snapshot_data["airports"])
    _ground_pct = round(_total_ground / _total_active * 100) if _total_active else 0

    airport_lines = "\n".join(
        f"  {a['iata']} ({a['name']}): {a['active']} active, "
        f"{a['on_ground']} ground ({round(a['on_ground']/a['active']*100) if a['active'] else 0}%), "
        f"{a['descending']} arriving, {a['climbing']} departing"
        for a in top10
    )

    high_ground = [a for a in top10 if a["active"] > 0 and a["on_ground"] / a["active"] > 0.7]
    arrival_heavy = [a for a in top10 if a["descending"] > a["climbing"] * 2 and a["descending"] >= 5]
    departure_heavy = [a for a in top10 if a["climbing"] > a["descending"] * 2 and a["climbing"] >= 5]

    _patterns = []
    if high_ground:
        _patterns.append(f"High ground congestion (>70%): {', '.join(a['iata'] for a in high_ground)}")
    if arrival_heavy:
        _patterns.append(f"Arrival-heavy airports: {', '.join(a['iata'] for a in arrival_heavy)}")
    if departure_heavy:
        _patterns.append(f"Departure-heavy airports: {', '.join(a['iata'] for a in departure_heavy)}")

    pattern_block = "\n".join(f"  - {p}" for p in _patterns) if _patterns else "  None detected"

    faa = _fetch_faa_status()
    faa_block = "\n".join(f"  - {a}" for a in faa) if faa else "  No active FAA advisories"

    return f"""CURRENT DATA ({ts_str}):
  Total aircraft over US: {total_ac:,}
  Total active near airports: {_total_active}
  Overall ground rate: {_ground_pct}% ({_total_ground} ground / {_total_active} active)
  Total arriving (descending): {_total_desc}
  Total departing (climbing): {_total_climb}

TOP 10 AIRPORTS:
{airport_lines}

NOTABLE PATTERNS:
{pattern_block}

FAA ADVISORIES (live):
{faa_block}

Write a 3-4 sentence briefing about the CURRENT DATA above. All times should be in {_tz_abbr}. Match the examples' tone and data density. If FAA advisories are active, weave them into the analysis naturally (don't just list them).

EXAMPLE OUTPUTS (match this tone and structure):
"ORD leads ground congestion at 71%, with 89 active aircraft on tarmac, pointing to taxi delays. ATL and DFW are arrival-heavy at 2:1 ratios. The system has 4,800 aircraft with a 48% ground rate, well above the typical mid-afternoon 35%."
"DEN is pushing departures hard with 45 climbing vs. 18 descending, likely a post-bank push from United's hub. LAX and SFO show the opposite pattern. Ground rates are moderate at 38% system-wide across 5,100 tracked aircraft.\""""


_AI_SYSTEM_PROMPT = f"""You are a concise aviation analyst writing snapshot briefings of US airspace.
Your audience is informed general readers, like a flight tracker blog or aviation Twitter account.
Rules:
- Exactly 3-4 sentences. No more.
- Lead with the most interesting finding, not a generic overview.
- Use specific numbers (airport codes, counts, percentages).
- If FAA advisories are active, reference them with context.
- All times in {_tz_abbr}.
- Present tense. No hedging. No em dashes. No filler.
- Sound like a sharp analyst, not a press release."""


@st.cache_data(ttl=300)
def _get_ai_summary(prompt):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            api_key = ""
    if not api_key:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=250,
        temperature=0.3,
        system=_AI_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# Display AI briefing + FAA advisories at top
if HAS_ANTHROPIC:
    _ai_prompt = _build_sky_prompt(snapshot, local_ts)
    _ai_summary = _get_ai_summary(_ai_prompt)
    if _ai_summary:
        st.markdown(
            f'<div style="background:linear-gradient(135deg, {NAVY_MID} 0%, {NAVY} 100%); '
            f'padding:1rem 1.5rem; border-radius:8px; border-left:3px solid {RED}; '
            f'margin:0.5rem 0 0.5rem 0; overflow-wrap:break-word; word-break:break-word;">'
            f'<span style="color:{WHITE}; font-size:clamp(0.8rem, 2.5vw, 0.92rem); line-height:1.7; font-family:Inter,sans-serif;">'
            f'{_ai_summary}</span></div>',
            unsafe_allow_html=True,
        )

_faa_advisories = _fetch_faa_status()
if _faa_advisories:
    _faa_items = "".join(
        f'<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.06);">'
        f'<span style="color:#ef4444;font-weight:700;font-family:JetBrains Mono,monospace;font-size:0.8em;">'
        f'{a.split(":")[0]}</span>'
        f'<span style="color:{SILVER};font-size:0.85em;margin-left:8px;">{":".join(a.split(":")[1:])}</span></div>'
        for a in _faa_advisories
    )
    st.markdown(
        f'<div style="background:linear-gradient(135deg, {NAVY_MID} 0%, {NAVY} 100%);'
        f'padding:0.75rem 1.25rem;border-radius:8px;border-left:3px solid #ef4444;'
        f'margin:0.25rem 0 1rem 0;">'
        f'<div style="font-size:0.7em;text-transform:uppercase;letter-spacing:1px;color:#ef4444;'
        f'font-weight:700;margin-bottom:6px;font-family:Inter,sans-serif;">'
        f'FAA Advisories</div>{_faa_items}</div>',
        unsafe_allow_html=True,
    )


def _score_color(score):
    if score >= THRESHOLD_GREEN:
        return SCORE_COLORS["green"]
    elif score >= THRESHOLD_YELLOW:
        return SCORE_COLORS["yellow"]
    return SCORE_COLORS["red"]


def _score_label(score):
    if score >= THRESHOLD_GREEN:
        return "Healthy"
    elif score >= THRESHOLD_YELLOW:
        return "Moderate"
    return "Congested"


def _get_md_token():
    """Get MotherDuck token from env or Streamlit secrets."""
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        try:
            token = st.secrets["MOTHERDUCK_TOKEN"]
        except (KeyError, FileNotFoundError):
            pass
    return token


@st.cache_data(ttl=300)
def _load_all_historical():
    """Single cached query for baselines, avg scores, and trend data.

    Returns (avg_today, avg_3d, n_snapshots, baselines, trend_data, airport_hist).
    """
    token = _get_md_token()
    if not token:
        return None, None, None, {}, None, {}
    try:
        import duckdb
        from datetime import timedelta
        from collections import defaultdict
        con = duckdb.connect(f"md:data_viz?motherduck_token={token}")

        snap_rows = con.execute("""
            SELECT snapshot_time, icao, active, on_ground, airborne,
                   low_altitude, descending, climbing, total_nearby
            FROM airport_congestion
            WHERE snapshot_time >= NOW() - INTERVAL 7 DAY
            ORDER BY snapshot_time
        """).fetchall()

        icao_sums = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        for r in snap_rows:
            icao = r[1]
            s = icao_sums[icao]
            s[0] += r[3] or 0
            s[1] += r[2] or 0
            s[2] += r[5] or 0
            s[3] += r[6] or 0
            s[4] += r[7] or 0
            s[5] += 1

        baseline_rows = []
        for icao, s in icao_sums.items():
            n = s[5]
            if n > 0:
                baseline_rows.append((icao, s[0]/n, s[1]/n, s[2]/n, s[3]/n, s[4]/n))
        baselines = compute_historical_baselines(baseline_rows)

        con.close()

        if not snap_rows:
            return None, None, None, baselines, None, {}

        snapshots = defaultdict(list)
        for r in snap_rows:
            snapshots[r[0]].append({
                "icao": r[1], "active": r[2], "on_ground": r[3],
                "airborne": r[4], "low_altitude": r[5],
                "descending": r[6], "climbing": r[7], "total_nearby": r[8],
            })

        now = datetime.now(timezone.utc)
        scores_today = []
        scores_3d = []
        trend = []
        apt_scores = defaultdict(lambda: {"1h": [], "3h": [], "today": [], "3d": []})

        for snap_time in sorted(snapshots.keys()):
            airports = snapshots[snap_time]
            scored_snap = score_snapshot(airports, baselines)
            sys_score = scored_snap["system"]["score"]

            ts = snap_time if hasattr(snap_time, 'date') else datetime.fromisoformat(str(snap_time))
            if hasattr(ts, 'tzinfo') and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = now - ts
            if age <= timedelta(days=3):
                scores_3d.append(sys_score)
            if age <= timedelta(days=1):
                scores_today.append(sys_score)

            for apt, sc in scored_snap["airports"]:
                icao = apt.get("icao", "")
                if age <= timedelta(hours=1):
                    apt_scores[icao]["1h"].append(sc["score"])
                if age <= timedelta(hours=3):
                    apt_scores[icao]["3h"].append(sc["score"])
                if age <= timedelta(days=1):
                    apt_scores[icao]["today"].append(sc["score"])
                if age <= timedelta(days=3):
                    apt_scores[icao]["3d"].append(sc["score"])

            trend.append({"time": snap_time, "score": sys_score,
                          "healthy": scored_snap["system"]["healthy"],
                          "congested": scored_snap["system"]["congested"]})

        avg_today = round(sum(scores_today) / len(scores_today), 1) if scores_today else None
        avg_3d = round(sum(scores_3d) / len(scores_3d), 1) if scores_3d else None
        n_snapshots = len(scores_3d) + len(scores_today)

        airport_hist = {}
        for icao, s in apt_scores.items():
            _avg = lambda lst: round(sum(lst) / len(lst), 1) if lst else None
            airport_hist[icao] = {
                "avg_1h": _avg(s["1h"]),
                "avg_3h": _avg(s["3h"]),
                "avg_today": _avg(s["today"]),
                "avg_3d": _avg(s["3d"]),
            }

        return avg_today, avg_3d, n_snapshots, baselines, trend, airport_hist
    except Exception:
        return None, None, None, {}, None, {}


def _make_gauge(score, title, subtitle=""):
    """Create a Plotly gauge chart for a health score."""
    color = _score_color(score)
    label = _score_label(score)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=36, family="JetBrains Mono", color=WHITE), suffix=""),
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:{SILVER}'>{subtitle}</span>", font=dict(size=13, color=WHITE, family="Inter")),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor="rgba(0,0,0,0)", tickfont=dict(size=1, color="rgba(0,0,0,0)")),
            bar=dict(color=color, thickness=0.75),
            bgcolor="rgba(255,255,255,0.04)",
            borderwidth=0,
            steps=[
                dict(range=[0, THRESHOLD_YELLOW], color="rgba(239,68,68,0.08)"),
                dict(range=[THRESHOLD_YELLOW, THRESHOLD_GREEN], color="rgba(234,179,8,0.06)"),
                dict(range=[THRESHOLD_GREEN, 100], color="rgba(34,197,94,0.06)"),
            ],
            threshold=dict(line=dict(color=WHITE, width=2), thickness=0.85, value=score),
        ),
    ))
    fig.add_annotation(
        x=0.5, y=-0.15, text=label, showarrow=False,
        font=dict(size=13, color=color, family="Inter", weight=700),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=250,
        margin=dict(t=50, b=25, l=20, r=20),
        font=dict(family="Inter, sans-serif"),
    )
    return fig


# Load historical baselines + scores (single cached query)
avg_today, avg_3d, n_hist, hist_baselines, trend_data, airport_hist = _load_all_historical()

# Score current snapshot using the DS model (with historical baselines if available)
scored = score_snapshot(snapshot["airports"], hist_baselines)
current_score = scored["system"]["score"]
sys_info = scored["system"]

st.markdown("---")
st.markdown(f'<div class="section-header" style="margin-bottom:0.75rem;">Traffic Health Score</div>', unsafe_allow_html=True)

g1, g2, g3 = st.columns(3, gap="large")
with g1:
    _sub = f'{sys_info["healthy"]} healthy, {sys_info["moderate"]} moderate, {sys_info["congested"]} congested'
    st.plotly_chart(_make_gauge(current_score, "NOW", _sub), use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
with g2:
    if avg_today is not None:
        st.plotly_chart(_make_gauge(avg_today, "TODAY", f"Last 24 hours"), use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
    else:
        st.markdown(f'<div style="text-align:center;padding:60px 0;color:{SILVER_DARK};font-size:0.85em;">Today average<br>needs more snapshots</div>', unsafe_allow_html=True)
with g3:
    if avg_3d is not None:
        st.plotly_chart(_make_gauge(avg_3d, "3-DAY AVG", f"{n_hist} snapshots"), use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
    else:
        st.markdown(f'<div style="text-align:center;padding:60px 0;color:{SILVER_DARK};font-size:0.85em;">3-day average<br>needs more snapshots</div>', unsafe_allow_html=True)

# Per-airport health score table (sortable)
display_apts = sorted(
    [(apt, sc) for apt, sc in scored["airports"] if apt.get("active", 0) > 0],
    key=lambda x: x[1]["score"], reverse=True,
)

def _bar_color(score):
    """Red -> orange -> yellow -> green gradient for score 0-100."""
    if score < 30:
        return "#ef4444"  # red
    elif score < 50:
        t = (score - 30) / 20
        r = int(239 + (245 - 239) * t)
        g = int(68 + (158 - 68) * t)
        b = int(68 + (11 - 68) * t)
        return f"rgb({r},{g},{b})"  # red -> orange
    elif score < 70:
        t = (score - 50) / 20
        r = int(245 + (234 - 245) * t)
        g = int(158 + (179 - 158) * t)
        b = int(11 + (8 - 11) * t)
        return f"rgb({r},{g},{b})"  # orange -> yellow
    else:
        t = min((score - 70) / 30, 1.0)
        r = int(234 + (34 - 234) * t)
        g = int(179 + (197 - 179) * t)
        b = int(8 + (94 - 8) * t)
        return f"rgb({r},{g},{b})"  # yellow -> green

def _score_bar_html(score):
    if score is None:
        return '<span style="color:#5C6F82;">-</span>'
    color = _bar_color(score)
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="flex:1;height:8px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden;">'
        f'<div style="width:{score}%;height:100%;background:{color};border-radius:4px;"></div></div>'
        f'<span style="min-width:24px;text-align:right;font-family:JetBrains Mono,monospace;font-size:0.8em;color:{color};">{score:.0f}</span></div>'
    )

if display_apts:
    _th_style = f'padding:6px 10px;text-align:left;color:{SILVER};font-size:0.65em;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid rgba(255,255,255,0.08);font-family:Inter,sans-serif;'
    _td_style = f'padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:JetBrains Mono,monospace;font-size:0.8em;color:{WHITE};'
    health_rows = ""
    for apt, sc in display_apts:
        icao = apt.get("icao", "")
        hist = airport_hist.get(icao, {})
        now_score = sc["score"]
        avg_today_apt = hist.get("avg_today")
        avg3 = hist.get("avg_3d")
        status_color = _score_color(now_score)
        health_rows += f'''<tr>
            <td style="{_td_style}font-weight:700;"><a href="?airport={apt["iata"]}" style="color:{WHITE};text-decoration:none;border-bottom:1px dotted {SILVER_DARK};">{apt["iata"]}</a></td>
            <td style="{_td_style}color:{SILVER};font-family:Inter,sans-serif;"><a href="?airport={apt["iata"]}" style="color:{SILVER};text-decoration:none;">{apt.get("name","")}</a></td>
            <td style="{_td_style}color:{status_color};font-weight:600;font-size:0.75em;">{sc["label"]}</td>
            <td style="{_td_style}min-width:120px;">{_score_bar_html(now_score)}</td>
            <td style="{_td_style}min-width:120px;">{_score_bar_html(avg_today_apt)}</td>
            <td style="{_td_style}min-width:120px;">{_score_bar_html(avg3)}</td>
            <td style="{_td_style}text-align:right;">{sc["components"]["ground_ratio"]["raw"]:.0%}</td>
            <td style="{_td_style}text-align:right;">{sc["components"]["flow_balance"]["raw"]:.0%}</td>
            <td style="{_td_style}text-align:right;">{sc["components"]["low_alt_density"]["raw"]:.0%}</td>
            <td style="{_td_style}text-align:right;">{apt.get("active",0)}</td>
        </tr>'''

    st.html(f'''
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
    .health-scroll-wrapper {{
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        max-height: 600px;
        overflow-y: auto;
    }}
    .health-scroll-wrapper table {{ min-width: 700px; }}
    </style>
    <div class="health-scroll-wrapper">
    <table style="width:100%;border-collapse:collapse;">
        <thead><tr>
            <th style="{_th_style}">Airport</th><th style="{_th_style}">Name</th>
            <th style="{_th_style}">Status</th><th style="{_th_style}min-width:120px;">Now</th>
            <th style="{_th_style}min-width:120px;">Today</th><th style="{_th_style}min-width:120px;">3-Day Avg</th>
            <th style="{_th_style}text-align:right;">Ground %</th><th style="{_th_style}text-align:right;">Flow Imbal</th>
            <th style="{_th_style}text-align:right;">Low Alt %</th><th style="{_th_style}text-align:right;">Active</th>
        </tr></thead>
        <tbody>{health_rows}</tbody>
    </table></div>
    ''')
    st.caption("Score = ground ratio (40%) + low-alt density (35%) + flow balance (25%).")

# Health Score trend line (from cached historical data)
if trend_data and len(trend_data) >= 3:
    fig_trend = go.Figure()
    times = [t["time"] for t in trend_data]
    scores = [t["score"] for t in trend_data]

    fig_trend.add_trace(go.Scatter(
        x=times, y=scores,
        mode="lines+markers",
        line=dict(color=SILVER, width=2),
        marker=dict(
            size=8,
            color=scores,
            colorscale=[
                [0, SCORE_COLORS["red"]], [0.4, "#eab308"],
                [0.7, SCORE_COLORS["green"]], [1, SCORE_COLORS["green"]]
            ],
            cmin=0, cmax=100,
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
        ),
        hovertemplate="<b>%{x|%b %d %I:%M %p}</b><br>Score: %{y}<extra></extra>",
        showlegend=False,
    ))

    fig_trend.add_hrect(y0=THRESHOLD_GREEN, y1=100, fillcolor="rgba(34,197,94,0.05)", line_width=0)
    fig_trend.add_hrect(y0=THRESHOLD_YELLOW, y1=THRESHOLD_GREEN, fillcolor="rgba(234,179,8,0.04)", line_width=0)
    fig_trend.add_hrect(y0=0, y1=THRESHOLD_YELLOW, fillcolor="rgba(239,68,68,0.04)", line_width=0)

    fig_trend.add_hline(y=THRESHOLD_GREEN, line=dict(color="rgba(34,197,94,0.3)", width=1, dash="dot"),
                        annotation_text="Healthy", annotation_position="right",
                        annotation_font=dict(size=9, color="rgba(34,197,94,0.5)"))
    fig_trend.add_hline(y=THRESHOLD_YELLOW, line=dict(color="rgba(234,179,8,0.3)", width=1, dash="dot"),
                        annotation_text="Moderate", annotation_position="right",
                        annotation_font=dict(size=9, color="rgba(234,179,8,0.5)"))

    fig_trend.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
        font=dict(family="JetBrains Mono, monospace", color="white"),
        margin=dict(l=40, r=60, t=10, b=30),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(title="Score", range=[0, 105], gridcolor="rgba(255,255,255,0.05)"),
    )
    st.markdown(f'<div style="margin-top:8px;"><span class="section-header" style="font-size:0.85em;">Health Score Over Time</span></div>', unsafe_allow_html=True)
    st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Airport detail dialog (baseball card popup)
filtered_airports = snapshot["airports"]

def _delta_html(val, net_val, suffix="", is_pct=False):
    """Render a delta vs network average."""
    if val is None or net_val is None or net_val == 0:
        return ""
    diff = val - net_val
    if is_pct:
        sign = "+" if diff > 0 else ""
        color = "#ef4444" if diff > 5 else "#22c55e" if diff < -5 else SILVER_DARK
        return f'<span style="font-size:0.55em;color:{color};margin-left:4px;">{sign}{diff:.0f}pp</span>'
    sign = "+" if diff > 0 else ""
    color = "#ef4444" if diff > 0.5 else "#22c55e" if diff < -0.5 else SILVER_DARK
    return f'<span style="font-size:0.55em;color:{color};margin-left:4px;">{sign}{diff:.1f}{suffix}</span>'


@st.dialog("Airport Detail", width="large")
def _show_airport_card(iata):
    apt = next((a for a in snapshot["airports"] if a["iata"] == iata), None)
    if not apt:
        st.error(f"Airport {iata} not found")
        return
    sc = next((s for a, s in scored["airports"] if a.get("iata") == iata), None)
    hist = airport_hist.get(apt.get("icao", ""), {})
    score = sc["score"] if sc else 0
    color = _score_color(score)
    label = _score_label(score)
    gpct = round(apt["on_ground"] / apt["active"] * 100) if apt["active"] else 0

    # Network averages for comparison
    _active_apts = [a for a in snapshot["airports"] if a["active"] > 0]
    _n = len(_active_apts) or 1
    net_ground_pct = round(sum(a["on_ground"] for a in _active_apts) / max(sum(a["active"] for a in _active_apts), 1) * 100)
    net_active = round(sum(a["active"] for a in _active_apts) / _n, 1)
    net_desc = round(sum(a["descending"] for a in _active_apts) / _n, 1)
    net_climb = round(sum(a["climbing"] for a in _active_apts) / _n, 1)

    # Header
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:8px;">'
        f'<span style="font-family:JetBrains Mono,monospace;font-size:2.2em;font-weight:900;color:{WHITE};">{iata}</span>'
        f'<div><div style="font-size:1em;font-weight:700;color:{WHITE};">{apt["name"]}</div>'
        f'<div style="font-size:0.7em;color:{SILVER};">{apt.get("icao","")} | {apt["active"]} active aircraft</div></div>'
        f'<div style="margin-left:auto;text-align:right;">'
        f'<span style="font-family:JetBrains Mono,monospace;font-size:1.8em;font-weight:900;color:{color};">{score:.0f}</span>'
        f'<div style="font-size:0.65em;color:{color};font-weight:600;">{label}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Row 1: Health score donuts (Now, 1h, 3h, Today)
    _score_items = [
        ("NOW", score),
        ("1-HR", hist.get("avg_1h")),
        ("3-HR", hist.get("avg_3h")),
        ("TODAY", hist.get("avg_today")),
    ]
    _gcols = st.columns(4)
    for _gc, (_slabel, _sval) in zip(_gcols, _score_items):
        with _gc:
            if _sval is not None:
                _sc = _bar_color(_sval)
                _fig_mini = go.Figure(go.Pie(
                    values=[_sval, 100 - _sval],
                    hole=0.7,
                    marker=dict(colors=[_sc, "rgba(255,255,255,0.04)"]),
                    textinfo="none", hoverinfo="none",
                    sort=False, direction="clockwise",
                ))
                _fig_mini.add_annotation(
                    text=f"<b>{_sval:.0f}</b>", x=0.5, y=0.55, font_size=22,
                    font=dict(color=_sc, family="JetBrains Mono"), showarrow=False,
                )
                _fig_mini.add_annotation(
                    text=_slabel, x=0.5, y=0.35, font_size=9,
                    font=dict(color=SILVER, family="Inter"), showarrow=False,
                )
                _fig_mini.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", height=140,
                    margin=dict(t=5, b=5, l=5, r=5), showlegend=False,
                )
                st.plotly_chart(_fig_mini, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
            else:
                st.markdown(
                    f'<div style="text-align:center;padding:30px 0;">'
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:1.2em;color:{SILVER_DARK};">--</div>'
                    f'<div style="font-size:0.55em;color:{SILVER};">{_slabel}</div></div>',
                    unsafe_allow_html=True,
                )

    # Row 2: Unified metrics box with deltas
    _gd = _delta_html(gpct, net_ground_pct, is_pct=True)
    _ad = _delta_html(apt["active"], net_active)
    _dd = _delta_html(apt["descending"], net_desc)
    _cd = _delta_html(apt["climbing"], net_climb)
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:12px;margin:4px 0;">'
        f'<div style="display:flex;gap:6px;text-align:center;">'
        f'<div style="flex:1;padding:6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:1.2em;font-weight:800;color:{WHITE};">{apt["on_ground"]}{_gd}</div>'
        f'<div style="font-size:0.55em;color:{SILVER};text-transform:uppercase;letter-spacing:0.5px;">Ground ({gpct}%)</div>'
        f'<div style="font-size:0.5em;color:{SILVER_DARK};">net avg: {net_ground_pct}%</div></div>'
        f'<div style="flex:1;padding:6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:1.2em;font-weight:800;color:{WHITE};">{apt["airborne"]}{_ad}</div>'
        f'<div style="font-size:0.55em;color:{SILVER};text-transform:uppercase;letter-spacing:0.5px;">Airborne</div>'
        f'<div style="font-size:0.5em;color:{SILVER_DARK};">{apt["low_altitude"]} below 10k ft</div></div>'
        f'<div style="flex:1;padding:6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:1.2em;font-weight:800;color:{WHITE};">{apt["descending"]}{_dd}</div>'
        f'<div style="font-size:0.55em;color:{SILVER};text-transform:uppercase;letter-spacing:0.5px;">Arriving</div>'
        f'<div style="font-size:0.5em;color:{SILVER_DARK};">net avg: {net_desc:.0f}</div></div>'
        f'<div style="flex:1;padding:6px;">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:1.2em;font-weight:800;color:{WHITE};">{apt["climbing"]}{_cd}</div>'
        f'<div style="font-size:0.55em;color:{SILVER};text-transform:uppercase;letter-spacing:0.5px;">Departing</div>'
        f'<div style="font-size:0.5em;color:{SILVER_DARK};">net avg: {net_climb:.0f}</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Row 3: Health components + Airline donut
    _cl, _cr = st.columns(2)
    with _cl:
        if sc:
            comps = sc["components"]
            _comp_html = '<div style="margin-top:8px;">'
            for cname, clbl, wt in [("ground_ratio", "Ground Ratio", "40%"), ("low_alt_density", "Low Alt Density", "35%"), ("flow_balance", "Flow Balance", "25%")]:
                c = comps[cname]
                cc = _bar_color(c["score"])
                _comp_html += (
                    f'<div style="display:flex;align-items:center;gap:6px;margin:5px 0;">'
                    f'<span style="min-width:95px;font-size:0.65em;color:{SILVER};">{clbl} <span style="color:{SILVER_DARK};">({wt})</span></span>'
                    f'<div style="flex:1;height:7px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden;">'
                    f'<div style="width:{c["score"]}%;height:100%;background:{cc};border-radius:4px;"></div></div>'
                    f'<span style="min-width:26px;text-align:right;font-family:JetBrains Mono,monospace;font-size:0.7em;color:{cc};">{c["score"]:.0f}</span></div>'
                )
            _comp_html += '</div>'
            st.markdown(_comp_html, unsafe_allow_html=True)

    with _cr:
        airlines = apt.get("airlines", {})
        if airlines:
            _sal = sorted(airlines.items(), key=lambda x: -x[1])
            _al_html = '<div style="margin-top:8px;">'
            for _aname, _acnt in _sal[:6]:
                _apct = round(_acnt / apt["active"] * 100) if apt["active"] else 0
                _AC = {"Delta": "#C8102E", "American": "#0078D2", "United": "#002244",
                       "Southwest": "#F9B612", "JetBlue": "#003DA5", "Spirit": "#FFD200",
                       "Frontier": "#006847", "Alaska": "#01426A", "SkyWest": "#8B9DAF",
                       "Republic": "#7A8B9C", "Private/GA": "#5C6F82"}
                _acolor = _AC.get(_aname, SILVER_DARK)
                _al_html += (
                    f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0;">'
                    f'<span style="min-width:70px;font-size:0.65em;color:{SILVER};overflow:hidden;text-overflow:ellipsis;">{_aname}</span>'
                    f'<div style="flex:1;height:7px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden;">'
                    f'<div style="width:{_apct}%;height:100%;background:{_acolor};border-radius:4px;min-width:2px;"></div></div>'
                    f'<span style="min-width:30px;text-align:right;font-family:JetBrains Mono,monospace;font-size:0.7em;color:{WHITE};">{_acnt}</span></div>'
                )
            if len(_sal) > 6:
                _rest = sum(c for _, c in _sal[6:])
                _al_html += f'<div style="font-size:0.6em;color:{SILVER_DARK};margin-top:4px;">+{len(_sal)-6} more ({_rest} aircraft)</div>'
            _al_html += '</div>'
            st.markdown(_al_html, unsafe_allow_html=True)

# Check query params and open dialog if airport is specified
_qp = st.query_params
_qp_airport = _qp.get("airport", "")
if _qp_airport:
    _show_airport_card(_qp_airport.upper())

# Congestion Leaderboard
st.markdown('<div class="section-header">Airport Congestion Leaderboard</div>', unsafe_allow_html=True)

_lb_airports = filtered_airports[:20]
max_active = max((a["active"] for a in _lb_airports), default=1) or 1

leaderboard_html = ""
for i, apt in enumerate(_lb_airports, 1):
    pct = (apt["active"] / max_active) * 100
    rank_class = "gold" if i == 1 else "silver" if i == 2 else "bronze" if i == 3 else ""
    row_class = f"top-{i}" if i <= 3 else ""
    detail = f'{apt["on_ground"]}g {apt["low_altitude"]}l {apt["descending"]}d {apt["climbing"]}c'
    # Smooth color blend: navy -> silver -> red based on pct
    t = pct / 100
    if t < 0.5:
        s = t / 0.5
        r = int(10 + (139 - 10) * s)
        g = int(74 + (157 - 74) * s)
        b = int(122 + (175 - 122) * s)
    else:
        s = (t - 0.5) / 0.5
        r = int(139 + (200 - 139) * s)
        g = int(157 + (16 - 157) * s)
        b = int(175 + (46 - 175) * s)
    bar_color = f"rgb({r},{g},{b})"

    leaderboard_html += f"""
    <a href="?airport={apt['iata']}" style="text-decoration:none;color:inherit;display:block;">
    <div class="leaderboard-row {row_class}" style="cursor:pointer;">
        <div class="lb-rank {rank_class}">{i}</div>
        <div class="lb-iata">{apt['iata']}</div>
        <div class="lb-name">{apt['name']}</div>
        <div class="lb-bar-bg"><div class="lb-bar" style="width:{max(pct, 2)}%;background:{bar_color};"></div></div>
        <div class="lb-count">{apt['active']}</div>
        <div class="lb-detail">{detail}</div>
    </div></a>"""

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
</style>
<div style="font-family:'Inter',sans-serif;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;margin-bottom:6px;font-size:0.55em;color:{SILVER_DARK};font-family:'JetBrains Mono',monospace;gap:4px;">
        <span style="overflow-wrap:break-word;">Ranked by active aircraft count (on ground + low altitude within 20km)</span>
        <span style="display:flex;gap:12px;flex-wrap:wrap;"><span>g = ground</span><span>l = low alt</span><span>d = descending</span><span>c = climbing</span></span>
    </div>
    {leaderboard_html}
</div>
""")

# Map + Ground Congestion side by side
st.markdown("---")
map_col, ground_col = st.columns([3, 2])

apt_data = [a for a in filtered_airports if a["active"] > 0]

with map_col:
    st.markdown(f'<div class="section-header">Live Airspace Map</div>', unsafe_allow_html=True)
    if apt_data:
        import math
        fig = go.Figure()

        # Aircraft with heading arrows (FR24-style)
        aircraft_lats = []
        aircraft_lons = []
        aircraft_headings = []
        aircraft_texts = []
        for apt in snapshot["airports"]:
            for ac in apt.get("aircraft", []):
                if not ac["on_ground"]:
                    aircraft_lats.append(ac["lat"])
                    aircraft_lons.append(ac["lon"])
                    aircraft_headings.append(ac.get("heading") or 0)
                    aircraft_texts.append(ac["callsign"] or ac["icao24"])

        if aircraft_lats:
            fig.add_trace(go.Scattermapbox(
                lat=aircraft_lats, lon=aircraft_lons,
                mode="markers",
                marker=dict(
                    size=7,
                    symbol="airport",
                    angle=aircraft_headings,
                    color="#F0B429",
                    opacity=0.7,
                ),
                text=aircraft_texts,
                hoverinfo="text",
                showlegend=False,
            ))

        # Airport markers
        max_act = max(a["active"] for a in apt_data) or 1
        ground_pcts = [round(a["on_ground"] / a["active"] * 100) if a["active"] else 0 for a in apt_data]
        fig.add_trace(go.Scattermapbox(
            lat=[a["lat"] for a in apt_data],
            lon=[a["lon"] for a in apt_data],
            mode="markers+text",
            marker=dict(
                size=[10 + 18 * math.log1p(a["active"]) / math.log1p(max_act) for a in apt_data],
                color=ground_pcts,
                colorscale=[[0, "#1565C0"], [0.4, "#42A5F5"], [0.7, "#FFB74D"], [1, "#E53935"]],
                cmin=0, cmax=100,
                opacity=0.85,
                colorbar=dict(
                    title=dict(text="Ground %", font=dict(color=SILVER, size=9)),
                    tickfont=dict(color=SILVER, size=8),
                    ticksuffix="%", len=0.4, thickness=8,
                    x=1.02,
                ),
            ),
            text=[a["iata"] for a in apt_data],
            textposition="top center",
            textfont=dict(size=9, color="white", family="JetBrains Mono"),
            hovertext=[f"<b>{a['iata']}</b> {a['name']}<br>Active: {a['active']}<br>Ground: {a['on_ground']}/{a['active']} = {g}%" for a, g in zip(apt_data, ground_pcts)],
            hoverinfo="text",
            showlegend=False,
        ))

        fig.update_layout(
            mapbox=dict(
                style="carto-darkmatter",
                center=dict(lat=38.5, lon=-96),
                zoom=3,
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=480,
            margin=dict(t=10, b=10, l=10, r=10),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

with ground_col:
    st.markdown(f'<div class="section-header">Ground Congestion</div>', unsafe_allow_html=True)
    ground_apts = [a for a in snapshot["airports"] if a["on_ground"] > 0 and a["active"] >= 3]
    if ground_apts:
        for a in ground_apts:
            a["_ground_pct"] = round(a["on_ground"] / a["active"] * 100) if a["active"] else 0
        ground_apts.sort(key=lambda a: a["_ground_pct"])
        ground_apts = ground_apts[-15:]

        bar_colors = []
        for a in ground_apts:
            pct = a["_ground_pct"]
            if pct >= 70:
                bar_colors.append(RED)
            elif pct >= 40:
                bar_colors.append(RED_LIGHT)
            else:
                bar_colors.append(SILVER)

        fig_ground = go.Figure()
        fig_ground.add_trace(go.Bar(
            y=[a["iata"] for a in ground_apts],
            x=[a["_ground_pct"] for a in ground_apts],
            orientation="h",
            marker_color=bar_colors,
            text=[f'{a["_ground_pct"]}% ({a["on_ground"]}/{a["active"]})' for a in ground_apts],
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="white", size=10, family="JetBrains Mono"),
            hovertext=[f"<b>{a['iata']}</b> {a['name']}<br>{a['on_ground']} on ground / {a['active']} active ({a['_ground_pct']}%)" for a in ground_apts],
            hoverinfo="text",
        ))
        fig_ground.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=480,
            font=dict(family="JetBrains Mono, monospace", color="white"),
            margin=dict(l=45, r=15, t=10, b=30),
            xaxis=dict(title="% on Ground", range=[0, 100], gridcolor="rgba(255,255,255,0.05)", showticklabels=False),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_ground, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Ground vs Air donut + Arrival/Departure flow side by side
st.markdown("---")
col_left, col_right = st.columns(2)

with col_left:
    st.markdown(f'<div class="section-header">Ground vs Airborne</div>', unsafe_allow_html=True)
    total_airborne = sum(a["airborne"] for a in snapshot["airports"])
    total_level = total_airborne - total_descending - total_climbing
    if total_level < 0:
        total_level = 0
    fig_donut = go.Figure(go.Pie(
        labels=["On Ground", "Arriving", "Departing", "In Pattern"],
        values=[total_ground, total_descending, total_climbing, total_level],
        hole=0.55,
        marker=dict(colors=[NAVY_LIGHT, RED, "#2E8B57", SILVER]),
        textinfo="label+value",
        textfont=dict(size=11, family="JetBrains Mono"),
        hoverinfo="label+value+percent",
    ))
    fig_donut.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(t=10, b=10, l=10, r=10),
        font=dict(family="Inter, sans-serif", color="white"),
        showlegend=False,
        annotations=[dict(
            text=f"<b>{total_active}</b><br><span style='font-size:10px'>active</span>",
            x=0.5, y=0.5, font_size=24, showarrow=False,
            font=dict(color="white", family="JetBrains Mono"),
        )],
    )
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

with col_right:
    st.markdown(f'<div class="section-header">Arrival vs Departure Flow</div>', unsafe_allow_html=True)
    flow_airports = [a for a in snapshot["airports"] if a["descending"] + a["climbing"] > 0][:12]
    if flow_airports:
        flow_airports.reverse()
        fig_flow = go.Figure()
        fig_flow.add_trace(go.Bar(
            y=[a["iata"] for a in flow_airports],
            x=[-a["descending"] for a in flow_airports],
            name="Arriving",
            orientation="h",
            marker_color=RED,
            text=[a["descending"] for a in flow_airports],
            textposition="inside",
            hoverinfo="none",
        ))
        fig_flow.add_trace(go.Bar(
            y=[a["iata"] for a in flow_airports],
            x=[a["climbing"] for a in flow_airports],
            name="Departing",
            orientation="h",
            marker_color="#2E8B57",
            text=[a["climbing"] for a in flow_airports],
            textposition="inside",
            hoverinfo="none",
        ))
        fig_flow.update_layout(
            barmode="relative",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=350,
            font=dict(family="JetBrains Mono, monospace", color="white", size=11),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
            margin=dict(l=40, r=20, t=40, b=20),
            xaxis=dict(zeroline=True, zerolinecolor=SILVER_DARK, zerolinewidth=1, title="Aircraft Count"),
        )
        st.plotly_chart(fig_flow, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Stacked bar
st.markdown("---")
st.markdown(f'<div class="section-header">Active Aircraft by Airport</div>', unsafe_allow_html=True)

top_airports = sorted(
    [a for a in snapshot["airports"] if a["active"] > 0],
    key=lambda a: a["on_ground"] + a["low_altitude"] + a["descending"] + a["climbing"],
)[-15:]
if top_airports:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["on_ground"] for a in top_airports],
        name="Ground", orientation="h",
        marker_color=NAVY_LIGHT,
        text=[a["on_ground"] for a in top_airports], textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["low_altitude"] for a in top_airports],
        name="Low Altitude (<10k ft)", orientation="h",
        marker_color=SILVER,
        text=[a["low_altitude"] for a in top_airports], textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["descending"] for a in top_airports],
        name="Descending", orientation="h",
        marker_color=RED,
        text=[a["descending"] for a in top_airports], textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["climbing"] for a in top_airports],
        name="Climbing", orientation="h",
        marker_color="#2E8B57",
        text=[a["climbing"] for a in top_airports], textposition="inside",
        hoverinfo="none",
    ))
    fig2.update_layout(
        barmode="stack",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(top_airports) * 35 + 80),
        font=dict(family="JetBrains Mono, monospace", color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
        margin=dict(l=50, r=20, t=40, b=20),
        xaxis_title="Aircraft Count",
    )
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Airline breakdown (stacked by status)
all_airline_status = {}
for apt in snapshot["airports"]:
    for airline, stats in apt.get("airline_status", {}).items():
        if airline not in all_airline_status:
            all_airline_status[airline] = {"on_ground": 0, "descending": 0, "climbing": 0, "low_alt": 0}
        for k in ("on_ground", "descending", "climbing", "low_alt"):
            all_airline_status[airline][k] += stats.get(k, 0)

# Fallback: if no airline_status data (MotherDuck cached), use simple counts
if not all_airline_status:
    all_airlines = {}
    for apt in snapshot["airports"]:
        for airline, count in apt.get("airlines", {}).items():
            all_airlines[airline] = all_airlines.get(airline, 0) + count
    for airline, count in all_airlines.items():
        all_airline_status[airline] = {"on_ground": count, "descending": 0, "climbing": 0, "low_alt": 0}

if all_airline_status:
    st.markdown("---")
    st.markdown(f'<div class="section-header">Airline Breakdown</div>', unsafe_allow_html=True)

    # Sort by total, take top 12
    _airline_totals = {a: sum(s.values()) for a, s in all_airline_status.items()}
    sorted_airlines = sorted(_airline_totals.items(), key=lambda x: -x[1])
    top_n = 12
    top_names = [name for name, _ in sorted_airlines[:top_n] if name != "Other"]

    # Merge everything else into Other
    other_status = {"on_ground": 0, "descending": 0, "climbing": 0, "low_alt": 0}
    for name, _ in sorted_airlines:
        if name not in top_names:
            for k in other_status:
                other_status[k] += all_airline_status[name].get(k, 0)
    if sum(other_status.values()) > 0:
        top_names.append("Other")
        all_airline_status["Other"] = other_status

    # Sort ascending for horizontal bar (bottom = biggest)
    top_names.sort(key=lambda n: sum(all_airline_status[n].values()))

    fig_airline = go.Figure()
    _status_config = [
        ("on_ground", "On Ground", NAVY_LIGHT),
        ("low_alt", "Low Altitude", SILVER),
        ("descending", "Arriving", RED),
        ("climbing", "Departing", "#2E8B57"),
    ]
    for _key, _label, _color in _status_config:
        _vals = [all_airline_status[n].get(_key, 0) for n in top_names]
        fig_airline.add_trace(go.Bar(
            y=top_names, x=_vals,
            name=_label, orientation="h",
            marker_color=_color,
            text=[v if v > 0 else "" for v in _vals],
            textposition="inside",
            textfont=dict(color="white", size=9, family="JetBrains Mono"),
            hoverinfo="none",
        ))
    fig_airline.update_layout(
        barmode="stack",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(top_names) * 32 + 80),
        font=dict(family="JetBrains Mono, monospace", color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
        margin=dict(l=80, r=20, t=40, b=30),
        xaxis=dict(title="Aircraft Near Airports", gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_airline, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Congestion heatmap (needs historical data from MotherDuck)
@st.cache_data(ttl=300)
def _load_heatmap_data():
    token = _get_md_token()
    if not token:
        return None
    try:
        import duckdb
        con = duckdb.connect(f"md:data_viz?motherduck_token={token}")
        n_snapshots = con.execute("SELECT COUNT(DISTINCT snapshot_time) FROM airport_congestion").fetchone()[0]
        if n_snapshots < 4:
            con.close()
            return None
        rows = con.execute("""
            SELECT iata, EXTRACT(HOUR FROM snapshot_time) as hour, AVG(active) as avg_active
            FROM airport_congestion
            WHERE iata IN (
                SELECT iata FROM airport_congestion
                GROUP BY iata ORDER BY AVG(active) DESC LIMIT 15
            )
            GROUP BY iata, hour
            ORDER BY iata, hour
        """).fetchall()
        con.close()
        return rows
    except Exception:
        return None

heatmap_data = _load_heatmap_data()
if heatmap_data:
    st.markdown("---")
    st.markdown(f'<div class="section-header">Congestion by Time of Day</div>', unsafe_allow_html=True)

    iatas = sorted(set(r[0] for r in heatmap_data))
    # Convert UTC hours to user's local timezone
    _utc_offset_h = int(datetime.now(timezone.utc).astimezone(USER_TZ).utcoffset().total_seconds() / 3600)
    utc_hours = sorted(set(int(r[1]) for r in heatmap_data))
    local_hours = sorted(set((h + _utc_offset_h) % 24 for h in utc_hours))
    # Build lookup with local hours
    lookup = {(r[0], (int(r[1]) + _utc_offset_h) % 24): r[2] for r in heatmap_data}
    z = [[lookup.get((iata, h), 0) for h in local_hours] for iata in iatas]

    fig_heat = go.Figure(go.Heatmap(
        z=z,
        x=[f"{h}:00" for h in local_hours],
        y=iatas,
        colorscale=[[0, NAVY_MID], [0.3, NAVY_LIGHT], [0.6, SILVER], [0.8, RED_LIGHT], [1, RED]],
        hovertemplate=f"<b>%{{y}}</b> at %{{x}} {_tz_abbr}<br>Avg active: %{{z:.1f}}<extra></extra>",
        colorbar=dict(title=dict(text="Avg Active", font=dict(color=SILVER, size=10)), tickfont=dict(color=SILVER, size=9)),
    ))
    fig_heat.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(iatas) * 28 + 80),
        font=dict(family="JetBrains Mono, monospace", color="white"),
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis=dict(title=f"Hour ({_tz_abbr})", dtick=1),
    )
    st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
    st.caption("Heatmap builds over time as more snapshots are collected every hour.")

# Data table
st.markdown("---")
with st.expander("Full Airport Data"):
    table = []
    for i, a in enumerate(snapshot["airports"], 1):
        if a["total_nearby"] == 0:
            continue
        table.append({
            "Rank": i, "IATA": a["iata"], "Airport": a["name"],
            "Active": a["active"], "Ground": a["on_ground"],
            "Low Alt": a["low_altitude"], "Descending": a["descending"],
            "Climbing": a["climbing"], "Total Nearby": a["total_nearby"],
        })
    if table:
        st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown("---")
with st.expander("Data Dictionary"):
    st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
</style>
<div style="font-family:'Inter',sans-serif; color:{SILVER}; font-size:clamp(0.75em, 2.5vw, 0.85em); line-height:1.7; overflow-wrap:break-word; overflow-x:auto; -webkit-overflow-scrolling:touch;">

<div style="color:{WHITE}; font-weight:700; font-size:1em; margin-bottom:8px; border-bottom:1px solid {SILVER_DARK}; padding-bottom:6px;">Metrics</div>
<table style="width:100%; border-collapse:collapse;">
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Active</td>
    <td style="padding:4px 0;">Aircraft on the ground + airborne below 10,000 ft within 20 km of the airport. Primary congestion score.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">On Ground</td>
    <td style="padding:4px 0;">Aircraft reporting ground contact (at gates, taxiways, or runways).</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Low Altitude</td>
    <td style="padding:4px 0;">Airborne aircraft below 10,000 ft (3,048 m). Includes arriving, departing, and holding traffic.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Arriving</td>
    <td style="padding:4px 0;">Airborne aircraft with vertical rate below -1 m/s (descending). Likely on approach.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Departing</td>
    <td style="padding:4px 0;">Airborne aircraft with vertical rate above +1 m/s (climbing). Likely just took off.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">In Pattern</td>
    <td style="padding:4px 0;">Airborne aircraft in level flight (vertical rate between -1 and +1 m/s). Could be holding, taxiing to runway, or transiting through.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Total Nearby</td>
    <td style="padding:4px 0;">All aircraft within 20 km regardless of altitude. Includes high-altitude overflights.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Ground %</td>
    <td style="padding:4px 0;">On Ground / Active. Higher values suggest surface congestion (taxi delays, gate holds).</td></tr>
</table>

<div style="color:{WHITE}; font-weight:700; font-size:1em; margin:16px 0 8px 0; border-bottom:1px solid {SILVER_DARK}; padding-bottom:6px;">Traffic Health Score</div>
<table style="width:100%; border-collapse:collapse;">
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Ground Ratio</td>
    <td style="padding:4px 0;">on_ground / active. Surface congestion. Weight: 40%. Healthy: &le;45%, Critical: &ge;85%.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Low Alt Density</td>
    <td style="padding:4px 0;">low_altitude / active. Airspace stacking (holding, sequencing). Weight: 35%. Healthy: &le;35%, Critical: &ge;75%.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Flow Balance</td>
    <td style="padding:4px 0;">|descending - climbing| / (desc + climb). Arrival/departure imbalance. Weight: 25%. Healthy: &le;15%, Critical: &ge;80%.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Drag Penalty</td>
    <td style="padding:4px 0;">If any sub-score drops below 30, overall score is dragged down by up to 20 points. Prevents one good metric from hiding a crisis.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Baselines</td>
    <td style="padding:4px 0;">When 7-day history is available, thresholds shift to each airport's normal behavior (ATL's 60% ground is its baseline, not penalized against 45%).</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">70-100</td>
    <td style="padding:4px 0;"><span style="color:#22c55e;font-weight:600;">Healthy</span> - free-flowing traffic, balanced arrivals/departures</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">40-69</td>
    <td style="padding:4px 0;"><span style="color:#eab308;font-weight:600;">Moderate</span> - some congestion, possible minor delays</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">0-39</td>
    <td style="padding:4px 0;"><span style="color:#ef4444;font-weight:600;">Congested</span> - significant delays likely, arrival waves or surface gridlock</td></tr>
</table>

<div style="color:{WHITE}; font-weight:700; font-size:1em; margin:16px 0 8px 0; border-bottom:1px solid {SILVER_DARK}; padding-bottom:6px;">Methodology</div>
<table style="width:100%; border-collapse:collapse;">
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Source</td>
    <td style="padding:4px 0;"><a href="https://opensky-network.org" style="color:{RED_LIGHT};">OpenSky Network</a> - free, crowdsourced ADS-B receiver network. No API key required.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Coverage</td>
    <td style="padding:4px 0;">Top 50 US airports by passenger volume. Bounding box: lat 24-50, lon -125 to -66.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Radius</td>
    <td style="padding:4px 0;">20 km (~10.8 nautical miles) from airport coordinates, calculated via haversine formula.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Low Alt Cutoff</td>
    <td style="padding:4px 0;">10,000 ft (3,048 m) barometric altitude. Standard transition altitude for approach/departure procedures.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Refresh</td>
    <td style="padding:4px 0;">Snapshots taken every 15 min (6 AM - 11 PM ET) and cached in MotherDuck. App cache TTL: 2 minutes.</td></tr>
</table>

<div style="color:{WHITE}; font-weight:700; font-size:1em; margin:16px 0 8px 0; border-bottom:1px solid {SILVER_DARK}; padding-bottom:6px;">Leaderboard Key</div>
<table style="width:100%; border-collapse:collapse;">
<tr><td style="padding:4px 12px 4px 0; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap; color:{SILVER_DARK};">g</td><td style="padding:4px 0;">Ground</td>
    <td style="padding:4px 12px 4px 16px; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap; color:{SILVER_DARK};">l</td><td style="padding:4px 0;">Low altitude</td></tr>
<tr><td style="padding:4px 12px 4px 0; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap; color:{SILVER_DARK};">d</td><td style="padding:4px 0;">Descending (arriving)</td>
    <td style="padding:4px 12px 4px 16px; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap; color:{SILVER_DARK};">c</td><td style="padding:4px 0;">Climbing (departing)</td></tr>
</table>

</div>
""")

st.caption("Data: OpenSky Network (free, no API key). Aircraft within 20km and below 10,000ft counted as active. Refreshes every 2 minutes.")
