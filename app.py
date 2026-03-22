import os
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from fetch import get_congestion_snapshot

st.set_page_config(page_title="Sky Status", page_icon="favicon.svg", layout="wide")

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
        .sky-title {{ font-size: clamp(1.3rem, 4vw, 2.2rem); letter-spacing: 1px; }}
        .sky-subtitle {{ font-size: 0.7em; }}
        .metric-card {{ padding: 12px 8px; }}
        .metric-value {{ font-size: clamp(1.3rem, 5vw, 2em); }}
        .metric-label {{ font-size: 0.55em; letter-spacing: 1px; }}
        .metric-sub {{ font-size: 0.5em; }}
        .leaderboard-row {{ padding: 8px 10px; gap: 8px; }}
        .lb-name {{ display: none; }}
        .lb-detail {{ font-size: 0.5em; min-width: 60px; }}
        .lb-bar-bg {{ min-width: 60px; }}
        .section-header {{ font-size: 0.9em; }}
        div[data-testid="stHorizontalBlock"] {{ gap: 0.5rem !important; }}
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
        # Load airline breakdown for this snapshot
        airline_rows = con.execute("""
            SELECT icao, airline, count
            FROM airport_airlines
            WHERE snapshot_time = ?
        """, [snap_time]).fetchall()
        con.close()
        # Build airline lookup: icao -> {airline: count}
        airline_lookup = {}
        for ar in airline_rows:
            airline_lookup.setdefault(ar[0], {})[ar[1]] = ar[2]
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
local_ts = ts.strftime("%b %d, %Y %I:%M %p UTC")

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

# Load historical baselines + scores (single cached query)
avg_3d, avg_7d, n_hist, hist_baselines, trend_data, airport_hist = _load_all_historical()

# Score current snapshot using the DS model (with historical baselines if available)
scored = score_snapshot(snapshot["airports"], hist_baselines)
current_score = scored["system"]["score"]
sys_info = scored["system"]

st.markdown("---")
st.markdown(f'<div class="section-header">Traffic Health Score</div>', unsafe_allow_html=True)

g1, g2, g3 = st.columns(3)
with g1:
    _sub = f'{sys_info["healthy"]} healthy, {sys_info["moderate"]} moderate, {sys_info["congested"]} congested'
    st.plotly_chart(_make_gauge(current_score, "NOW", _sub), use_container_width=True, config={"displayModeBar": False})
with g2:
    if avg_3d is not None:
        st.plotly_chart(_make_gauge(avg_3d, "3-DAY AVG", f"{n_hist} snapshots"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(f'<div style="text-align:center;padding:60px 0;color:{SILVER_DARK};font-size:0.85em;">3-day average<br>needs more snapshots</div>', unsafe_allow_html=True)
with g3:
    if avg_7d is not None:
        st.plotly_chart(_make_gauge(avg_7d, "7-DAY AVG", f"{n_hist} snapshots"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(f'<div style="text-align:center;padding:60px 0;color:{SILVER_DARK};font-size:0.85em;">7-day average<br>needs more snapshots</div>', unsafe_allow_html=True)

# Per-airport health score table (sortable)
display_apts = [(apt, sc) for apt, sc in scored["airports"] if apt.get("active", 0) > 0]

if display_apts:
    import pandas as pd
    table_rows = []
    for apt, sc in display_apts:
        icao = apt.get("icao", "")
        hist = airport_hist.get(icao, {})
        table_rows.append({
            "Airport": f'{apt["iata"]}',
            "Name": apt.get("name", ""),
            "Now": sc["score"],
            "Status": sc["label"],
            "3-Day": hist.get("avg_3d") if hist.get("avg_3d") is not None else None,
            "7-Day": hist.get("avg_7d") if hist.get("avg_7d") is not None else None,
            "Ground %": sc["components"]["ground_ratio"]["raw"],
            "Flow Imbal": sc["components"]["flow_balance"]["raw"],
            "Low Alt %": sc["components"]["low_alt_density"]["raw"],
            "Active": apt.get("active", 0),
        })
    df_health = pd.DataFrame(table_rows)

    # Color-code scores
    def _color_score(val):
        if pd.isna(val):
            return ""
        if val >= THRESHOLD_GREEN:
            return f"background-color: rgba(34,197,94,0.2); color: {SCORE_COLORS['green']}"
        elif val >= THRESHOLD_YELLOW:
            return f"background-color: rgba(234,179,8,0.15); color: #eab308"
        return f"background-color: rgba(239,68,68,0.15); color: {SCORE_COLORS['red']}"

    styled = df_health.style.applymap(
        _color_score, subset=["Now", "3-Day", "7-Day"]
    ).format({
        "Ground %": "{:.0%}",
        "Flow Imbal": "{:.0%}",
        "Low Alt %": "{:.0%}",
        "3-Day": lambda x: f"{x:.0f}" if pd.notna(x) else "-",
        "7-Day": lambda x: f"{x:.0f}" if pd.notna(x) else "-",
    })

    st.dataframe(
        df_health,
        use_container_width=True,
        hide_index=True,
        height=min(600, len(table_rows) * 35 + 40),
        column_config={
            "Airport": st.column_config.TextColumn("Airport", width="small"),
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Now": st.column_config.ProgressColumn("Now", min_value=0, max_value=100, format="%d"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "3-Day": st.column_config.ProgressColumn("3-Day Avg", min_value=0, max_value=100, format="%d"),
            "7-Day": st.column_config.ProgressColumn("7-Day Avg", min_value=0, max_value=100, format="%d"),
            "Ground %": st.column_config.NumberColumn("Ground %", format="%.0f%%"),
            "Flow Imbal": st.column_config.NumberColumn("Flow Imbal", format="%.0f%%"),
            "Low Alt %": st.column_config.NumberColumn("Low Alt %", format="%.0f%%"),
            "Active": st.column_config.NumberColumn("Active", format="%d"),
        },
    )
    st.caption("Click any column header to sort. Score = ground ratio (40%) + low-alt density (35%) + flow balance (25%).")

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

# AI Briefing (auto-triggered)
if HAS_ANTHROPIC:
    prompt = _build_sky_prompt(snapshot, local_ts)
    summary = _get_ai_summary(prompt)
    if summary:
        st.markdown(
            f'<div style="background:linear-gradient(135deg, {NAVY_MID} 0%, {NAVY} 100%); '
            f'padding:1rem 1.5rem; border-radius:8px; border-left:3px solid {RED}; '
            f'margin:0.5rem 0 1rem 0;">'
            f'<span style="color:{WHITE}; font-size:0.92rem; line-height:1.7; font-family:Inter,sans-serif;">'
            f'{summary}</span></div>',
            unsafe_allow_html=True,
        )

# Airline filter
st.markdown("---")
all_airlines_set = set()
for apt in snapshot["airports"]:
    for airline in apt.get("airlines", {}):
        if airline != "Other":
            all_airlines_set.add(airline)
airline_options = ["All Airlines"] + sorted(all_airlines_set)
selected_airline = st.selectbox("Filter by airline", airline_options, index=0, label_visibility="collapsed")

# Filter airports if an airline is selected
if selected_airline != "All Airlines":
    filtered_airports = []
    for apt in snapshot["airports"]:
        airline_count = apt.get("airlines", {}).get(selected_airline, 0)
        if airline_count > 0:
            filtered_airports.append({**apt, "_airline_count": airline_count})
    filtered_airports.sort(key=lambda x: x["_airline_count"], reverse=True)
else:
    filtered_airports = snapshot["airports"]

# Congestion Leaderboard
st.markdown('<div class="section-header">Airport Congestion Leaderboard</div>', unsafe_allow_html=True)

_lb_airports = filtered_airports[:20]
_lb_key = "_airline_count" if selected_airline != "All Airlines" else "active"
max_active = max((a[_lb_key] for a in _lb_airports), default=1) or 1

leaderboard_html = ""
for i, apt in enumerate(_lb_airports, 1):
    pct = (apt[_lb_key] / max_active) * 100
    rank_class = "gold" if i == 1 else "silver" if i == 2 else "bronze" if i == 3 else ""
    row_class = f"top-{i}" if i <= 3 else ""
    if selected_airline != "All Airlines":
        detail = f'{apt.get("_airline_count", 0)} {selected_airline} / {apt["active"]} total'
    else:
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
    <div class="leaderboard-row {row_class}">
        <div class="lb-rank {rank_class}">{i}</div>
        <div class="lb-iata">{apt['iata']}</div>
        <div class="lb-name">{apt['name']}</div>
        <div class="lb-bar-bg"><div class="lb-bar" style="width:{max(pct, 2)}%;background:{bar_color};"></div></div>
        <div class="lb-count">{apt.get('_airline_count', apt['active']) if selected_airline != 'All Airlines' else apt['active']}</div>
        <div class="lb-detail">{detail}</div>
    </div>"""

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
</style>
<div style="font-family:'Inter',sans-serif;">
    <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:0.55em;color:{SILVER_DARK};font-family:'JetBrains Mono',monospace;">
        <span>Ranked by active aircraft count (on ground + low altitude within 20km)</span>
        <span style="display:flex;gap:12px;"><span>g = ground</span><span>l = low alt</span><span>d = descending</span><span>c = climbing</span></span>
    </div>
    {leaderboard_html}
</div>
""")

# ---------------------------------------------------------------------------
# AI Summary
# ---------------------------------------------------------------------------

def _build_sky_prompt(snapshot, ts_str):
    """Build a structured prompt with all current data for the AI summary."""
    top10 = snapshot["airports"][:10]
    total_ac = snapshot["total_us_aircraft"]
    total_active = sum(a["active"] for a in snapshot["airports"])
    total_ground = sum(a["on_ground"] for a in snapshot["airports"])
    total_desc = sum(a["descending"] for a in snapshot["airports"])
    total_climb = sum(a["climbing"] for a in snapshot["airports"])
    ground_pct = round(total_ground / total_active * 100) if total_active else 0

    airport_lines = "\n".join(
        f"  {a['iata']} ({a['name']}): {a['active']} active, "
        f"{a['on_ground']} ground ({round(a['on_ground']/a['active']*100) if a['active'] else 0}%), "
        f"{a['descending']} arriving, {a['climbing']} departing"
        for a in top10
    )

    # Find notable patterns
    high_ground = [a for a in top10 if a["active"] > 0 and a["on_ground"] / a["active"] > 0.7]
    arrival_heavy = [a for a in top10 if a["descending"] > a["climbing"] * 2 and a["descending"] >= 5]
    departure_heavy = [a for a in top10 if a["climbing"] > a["descending"] * 2 and a["climbing"] >= 5]

    patterns = []
    if high_ground:
        patterns.append(f"High ground congestion (>70%): {', '.join(a['iata'] for a in high_ground)}")
    if arrival_heavy:
        patterns.append(f"Arrival-heavy airports: {', '.join(a['iata'] for a in arrival_heavy)}")
    if departure_heavy:
        patterns.append(f"Departure-heavy airports: {', '.join(a['iata'] for a in departure_heavy)}")

    pattern_block = "\n".join(f"  - {p}" for p in patterns) if patterns else "  None detected"

    return f"""CURRENT DATA ({ts_str}):
  Total aircraft over US: {total_ac:,}
  Total active near airports: {total_active}
  Overall ground rate: {ground_pct}% ({total_ground} ground / {total_active} active)
  Total arriving (descending): {total_desc}
  Total departing (climbing): {total_climb}

TOP 10 AIRPORTS:
{airport_lines}

NOTABLE PATTERNS:
{pattern_block}

EXAMPLE OUTPUTS (match this tone and structure):

Example 1 (high ground congestion):
"ORD leads ground congestion at 71%, with 89 of 125 active aircraft sitting on tarmac, pointing to taxi delays and likely gate holds. ATL and DFW are both running arrival-heavy at 2:1 ratios, pulling in 40+ descending aircraft each while departures lag behind. The system has 4,800 aircraft over US airspace with a 48% overall ground rate, well above the typical mid-afternoon 35%."

Example 2 (balanced, quiet system):
"US airspace is carrying 3,200 aircraft this Sunday evening, about 20% below weekday averages. ATL tops the board at 95 active but only 33% on the ground, a clean flow with 22 arrivals matching 24 departures. No airport in the top 10 exceeds 40% ground rate, so taxi queues are short across the board."

Example 3 (departure surge):
"DEN is pushing departures hard with 45 climbing vs. 18 descending, likely a post-bank push from United's hub operation. LAX and SFO show the opposite pattern, each pulling in 30+ arrivals with fewer than 15 departures, consistent with West Coast evening arrival waves. Ground rates are moderate at 38% system-wide across 5,100 tracked aircraft."

Write a 3-4 sentence briefing about the CURRENT DATA above. Match the examples' tone and data density."""


_AI_SYSTEM_PROMPT = """You are a concise aviation analyst writing snapshot briefings of US airspace.
Your audience is informed general readers, like a flight tracker blog or aviation Twitter account.
Rules:
- Exactly 3-4 sentences. No more.
- Lead with the most interesting finding, not a generic overview.
- Use specific numbers (airport codes, counts, percentages).
- Compare airports to each other when relevant.
- If ground rates are high, note traveler impact (delays, taxi queues).
- If arrival/departure imbalance exists, note it.
- Present tense. No hedging. State what the data shows.
- No em dashes. No inflated language. No filler phrases.
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

    Returns (avg_3d, avg_7d, n_snapshots, baselines, trend_data, airport_hist).
    Merges what used to be 3 separate MotherDuck connections into 1.
    """
    token = _get_md_token()
    if not token:
        return None, None, None, {}, None, {}
    try:
        import duckdb
        from datetime import timedelta
        from collections import defaultdict
        con = duckdb.connect(f"md:data_viz?motherduck_token={token}")

        # Single query: all 7-day airport data (used for baselines, scoring, and trend)
        snap_rows = con.execute("""
            SELECT snapshot_time, icao, active, on_ground, airborne,
                   low_altitude, descending, climbing, total_nearby
            FROM airport_congestion
            WHERE snapshot_time >= NOW() - INTERVAL 7 DAY
            ORDER BY snapshot_time
        """).fetchall()

        # Baselines from aggregates (computed in Python to avoid a second query)
        # Accumulate sums per icao for baseline calculation
        icao_sums = defaultdict(lambda: [0, 0, 0, 0, 0, 0])  # ground, active, low_alt, desc, climb, count
        for r in snap_rows:
            icao = r[1]
            s = icao_sums[icao]
            s[0] += r[3] or 0   # on_ground
            s[1] += r[2] or 0   # active
            s[2] += r[5] or 0   # low_altitude
            s[3] += r[6] or 0   # descending
            s[4] += r[7] or 0   # climbing
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

        # Group by snapshot_time
        snapshots = defaultdict(list)
        for r in snap_rows:
            snapshots[r[0]].append({
                "icao": r[1], "active": r[2], "on_ground": r[3],
                "airborne": r[4], "low_altitude": r[5],
                "descending": r[6], "climbing": r[7], "total_nearby": r[8],
            })

        now = datetime.now(timezone.utc)
        scores_3d = []
        scores_7d = []
        trend = []
        # Per-airport score accumulation: icao -> {"3d": [...], "7d": [...]}
        apt_scores = defaultdict(lambda: {"3d": [], "7d": []})

        for snap_time in sorted(snapshots.keys()):
            airports = snapshots[snap_time]
            scored_snap = score_snapshot(airports, baselines)
            sys_score = scored_snap["system"]["score"]

            ts = snap_time if hasattr(snap_time, 'date') else datetime.fromisoformat(str(snap_time))
            if hasattr(ts, 'tzinfo') and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = now - ts
            scores_7d.append(sys_score)
            if age <= timedelta(days=3):
                scores_3d.append(sys_score)

            # Track per-airport scores
            for apt, sc in scored_snap["airports"]:
                icao = apt.get("icao", "")
                apt_scores[icao]["7d"].append(sc["score"])
                if age <= timedelta(days=3):
                    apt_scores[icao]["3d"].append(sc["score"])

            trend.append({"time": snap_time, "score": sys_score,
                          "healthy": scored_snap["system"]["healthy"],
                          "congested": scored_snap["system"]["congested"]})

        avg_3d = round(sum(scores_3d) / len(scores_3d), 1) if scores_3d else None
        avg_7d = round(sum(scores_7d) / len(scores_7d), 1) if scores_7d else None
        n_snapshots = len(scores_7d)

        # Compute per-airport averages
        airport_hist = {}
        for icao, s in apt_scores.items():
            airport_hist[icao] = {
                "avg_3d": round(sum(s["3d"]) / len(s["3d"]), 1) if s["3d"] else None,
                "avg_7d": round(sum(s["7d"]) / len(s["7d"]), 1) if s["7d"] else None,
            }

        return avg_3d, avg_7d, n_snapshots, baselines, trend, airport_hist
    except Exception:
        return None, None, None, {}, None, {}


def _make_gauge(score, title, subtitle=""):
    """Create a Plotly gauge chart for a health score."""
    color = _score_color(score)
    label = _score_label(score)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=42, family="JetBrains Mono", color=WHITE), suffix=""),
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:{SILVER}'>{subtitle}</span>", font=dict(size=14, color=WHITE, family="Inter")),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor="rgba(0,0,0,0)", tickfont=dict(size=1, color="rgba(0,0,0,0)")),
            bar=dict(color=color, thickness=0.85),
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
        x=0.5, y=-0.05, text=label, showarrow=False,
        font=dict(size=13, color=color, family="Inter", weight=700),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        margin=dict(t=50, b=10, l=20, r=20),
        font=dict(family="Inter, sans-serif"),
    )
    return fig


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
            height=550,
            margin=dict(t=10, b=10, l=10, r=10),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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
            height=550,
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

# Airline breakdown
all_airlines = {}
for apt in snapshot["airports"]:
    for airline, count in apt.get("airlines", {}).items():
        all_airlines[airline] = all_airlines.get(airline, 0) + count

if all_airlines:
    st.markdown("---")
    st.markdown(f'<div class="section-header">Airline Breakdown</div>', unsafe_allow_html=True)

    # Sort and take top 12, group the rest as "Other"
    sorted_airlines = sorted(all_airlines.items(), key=lambda x: -x[1])
    top_n = 12
    top_airlines = sorted_airlines[:top_n]
    other_count = sum(c for _, c in sorted_airlines[top_n:])
    existing_other = next((c for name, c in top_airlines if name == "Other"), 0)
    top_airlines = [(name, c) for name, c in top_airlines if name != "Other"]
    if other_count + existing_other > 0:
        top_airlines.append(("Other", other_count + existing_other))
    top_airlines.sort(key=lambda x: x[1])

    # Assign colors - major carriers get brand colors
    AIRLINE_COLORS = {
        "Delta": "#C8102E", "American": "#0078D2", "United": "#002244",
        "Southwest": "#F9B612", "JetBlue": "#003DA5", "Spirit": "#FFD200",
        "Frontier": "#006847", "Alaska": "#01426A", "Hawaiian": "#2D1E5B",
        "SkyWest": "#8B9DAF", "FedEx": "#660099", "UPS": "#351C15",
    }
    bar_colors = [AIRLINE_COLORS.get(name, SILVER_DARK) for name, _ in top_airlines]

    fig_airline = go.Figure(go.Bar(
        y=[name for name, _ in top_airlines],
        x=[count for _, count in top_airlines],
        orientation="h",
        marker_color=bar_colors,
        text=[count for _, count in top_airlines],
        textposition="outside",
        textfont=dict(color="white", size=10, family="JetBrains Mono"),
        hoverinfo="none",
    ))
    fig_airline.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(280, len(top_airlines) * 30 + 60),
        font=dict(family="JetBrains Mono, monospace", color="white"),
        margin=dict(l=80, r=40, t=10, b=30),
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
    hours = sorted(set(int(r[1]) for r in heatmap_data))
    lookup = {(r[0], int(r[1])): r[2] for r in heatmap_data}
    z = [[lookup.get((iata, h), 0) for h in hours] for iata in iatas]

    fig_heat = go.Figure(go.Heatmap(
        z=z,
        x=[f"{h}:00" for h in hours],
        y=iatas,
        colorscale=[[0, NAVY_MID], [0.3, NAVY_LIGHT], [0.6, SILVER], [0.8, RED_LIGHT], [1, RED]],
        hovertemplate="<b>%{y}</b> at %{x} UTC<br>Avg active: %{z:.1f}<extra></extra>",
        colorbar=dict(title=dict(text="Avg Active", font=dict(color=SILVER, size=10)), tickfont=dict(color=SILVER, size=9)),
    ))
    fig_heat.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(iatas) * 28 + 80),
        font=dict(family="JetBrains Mono, monospace", color="white"),
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis=dict(title="Hour (UTC)", dtick=1),
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
<div style="font-family:'Inter',sans-serif; color:{SILVER}; font-size:0.85em; line-height:1.7;">

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
    <td style="padding:4px 0;">Top 30 US airports by passenger volume. Bounding box: lat 24-50, lon -125 to -66.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Radius</td>
    <td style="padding:4px 0;">20 km (~10.8 nautical miles) from airport coordinates, calculated via haversine formula.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Low Alt Cutoff</td>
    <td style="padding:4px 0;">10,000 ft (3,048 m) barometric altitude. Standard transition altitude for approach/departure procedures.</td></tr>
<tr><td style="padding:4px 12px 4px 0; color:{WHITE}; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">Refresh</td>
    <td style="padding:4px 0;">Snapshots taken every hour (6 AM - 11 PM ET) and cached in MotherDuck. App cache TTL: 2 minutes.</td></tr>
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
