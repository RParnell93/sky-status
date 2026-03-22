import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone
import time

from fetch import get_congestion_snapshot
from airports import AIRPORTS

st.set_page_config(page_title="Sky Status", page_icon="*", layout="wide")

CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"], .stApp { font-family: 'JetBrains Mono', monospace !important; }
    h1, h2, h3 { font-family: 'JetBrains Mono', monospace !important; letter-spacing: -0.5px; }
    .metric-card {
        background: linear-gradient(135deg, #0a0e1a 0%, #111827 100%);
        border-radius: 12px; padding: 16px; text-align: center;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }
    .metric-value { font-size: 2em; font-weight: 800; color: #38bdf8; }
    .metric-label { font-size: 0.7em; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
    .leaderboard-row {
        display: flex; align-items: center; padding: 10px 14px; margin: 4px 0;
        background: linear-gradient(135deg, #0a0e1a 0%, #111827 100%);
        border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.08);
        gap: 12px;
    }
    .leaderboard-row:hover { border-color: rgba(56, 189, 248, 0.3); }
    .lb-rank {
        font-size: 1.1em; font-weight: 800; color: #38bdf8;
        min-width: 28px; text-align: center;
    }
    .lb-rank.gold { color: #fbbf24; }
    .lb-rank.silver { color: #cbd5e1; }
    .lb-rank.bronze { color: #d97706; }
    .lb-iata { font-size: 1.2em; font-weight: 800; color: white; min-width: 40px; }
    .lb-name { font-size: 0.8em; color: #94a3b8; flex: 1; }
    .lb-bar-bg {
        flex: 2; height: 24px; background: rgba(56, 189, 248, 0.08);
        border-radius: 6px; position: relative; overflow: hidden; min-width: 100px;
    }
    .lb-bar {
        height: 100%; border-radius: 6px;
        background: linear-gradient(90deg, #0ea5e9, #38bdf8);
        transition: width 0.5s ease;
    }
    .lb-bar.hot {
        background: linear-gradient(90deg, #ef4444, #f97316);
    }
    .lb-bar.warm {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }
    .lb-count {
        font-size: 0.9em; font-weight: 700; color: white;
        min-width: 30px; text-align: right;
    }
    .lb-detail { font-size: 0.65em; color: #64748b; min-width: 100px; text-align: right; }
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
    .status-dot.live { background: #22c55e; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Header
st.markdown(
    '<h1 style="margin-bottom:0;color:white;">SKY STATUS</h1>'
    '<p style="color:#64748b;font-size:0.8em;margin-top:0;">'
    '<span class="status-dot live"></span>Live US Airport Congestion</p>',
    unsafe_allow_html=True,
)

# Fetch data
@st.cache_data(ttl=120)
def load_snapshot():
    return get_congestion_snapshot()

with st.spinner("Fetching live aircraft data..."):
    snapshot = load_snapshot()

ts = datetime.fromisoformat(snapshot["timestamp"])
local_ts = ts.strftime("%b %d, %Y %I:%M %p UTC")

# Top metrics
active_airports = sum(1 for a in snapshot["airports"] if a["active"] > 0)
total_active = sum(a["active"] for a in snapshot["airports"])
busiest = snapshot["airports"][0] if snapshot["airports"] else None

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{snapshot["total_us_aircraft"]:,}</div><div class="metric-label">Aircraft Over US</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{active_airports}</div><div class="metric-label">Active Airports</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_active}</div><div class="metric-label">Near Airports</div></div>', unsafe_allow_html=True)
with c4:
    if busiest:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{busiest["iata"]}</div><div class="metric-label">Busiest Right Now</div></div>', unsafe_allow_html=True)

st.caption(f"Updated: {local_ts} | Data: OpenSky Network")

# Congestion Leaderboard
st.markdown("## Airport Congestion Leaderboard")

max_active = max((a["active"] for a in snapshot["airports"]), default=1) or 1

leaderboard_html = ""
for i, apt in enumerate(snapshot["airports"][:20], 1):
    pct = (apt["active"] / max_active) * 100
    rank_class = "gold" if i == 1 else "silver" if i == 2 else "bronze" if i == 3 else ""
    bar_class = "hot" if pct > 70 else "warm" if pct > 40 else ""
    detail = f'{apt["on_ground"]}g {apt["low_altitude"]}l {apt["descending"]}d {apt["climbing"]}c'

    leaderboard_html += f"""
    <div class="leaderboard-row">
        <div class="lb-rank {rank_class}">{i}</div>
        <div class="lb-iata">{apt['iata']}</div>
        <div class="lb-name">{apt['name']}</div>
        <div class="lb-bar-bg"><div class="lb-bar {bar_class}" style="width:{pct}%;"></div></div>
        <div class="lb-count">{apt['active']}</div>
        <div class="lb-detail">{detail}</div>
    </div>"""

st.html(f"""
<style>@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');</style>
<div style="font-family:'JetBrains Mono',monospace;">
    <div style="display:flex;justify-content:flex-end;gap:16px;margin-bottom:8px;font-size:0.6em;color:#64748b;">
        <span>g=ground</span><span>l=low alt</span><span>d=descending</span><span>c=climbing</span>
    </div>
    {leaderboard_html}
</div>
""")

# Map
st.markdown("---")
st.markdown("## Live Airspace Map")

# Airport bubbles sized by congestion
apt_data = [a for a in snapshot["airports"] if a["active"] > 0]
if apt_data:
    fig = go.Figure()

    # All aircraft as tiny dots
    aircraft_lats = []
    aircraft_lons = []
    aircraft_texts = []
    for apt in snapshot["airports"]:
        for ac in apt.get("aircraft", []):
            if not ac["on_ground"]:
                aircraft_lats.append(ac["lat"])
                aircraft_lons.append(ac["lon"])
                aircraft_texts.append(ac["callsign"] or ac["icao24"])

    if aircraft_lats:
        fig.add_trace(go.Scattergeo(
            lat=aircraft_lats, lon=aircraft_lons,
            mode="markers",
            marker=dict(size=3, color="#38bdf8", opacity=0.4),
            text=aircraft_texts,
            hoverinfo="text",
            name="Aircraft",
            showlegend=False,
        ))

    # Airport bubbles
    fig.add_trace(go.Scattergeo(
        lat=[a["lat"] for a in apt_data],
        lon=[a["lon"] for a in apt_data],
        mode="markers+text",
        marker=dict(
            size=[max(a["active"] * 4, 8) for a in apt_data],
            color=[a["active"] for a in apt_data],
            colorscale=[[0, "#0ea5e9"], [0.5, "#fbbf24"], [1, "#ef4444"]],
            opacity=0.7,
            line=dict(width=1, color="white"),
        ),
        text=[a["iata"] for a in apt_data],
        textposition="top center",
        textfont=dict(size=9, color="white", family="JetBrains Mono"),
        hovertext=[f"{a['iata']} {a['name']}<br>Active: {a['active']}<br>Ground: {a['on_ground']}<br>Low Alt: {a['low_altitude']}" for a in apt_data],
        hoverinfo="text",
        name="Airports",
        showlegend=False,
    ))

    fig.update_geos(
        scope="usa",
        bgcolor="rgba(0,0,0,0)",
        landcolor="#111827",
        lakecolor="#0a0e1a",
        showlakes=True,
        coastlinecolor="#1e293b",
        countrycolor="#1e293b",
        subunitcolor="#1e293b",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(t=10, b=10, l=10, r=10),
        font=dict(family="JetBrains Mono, monospace"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

# Horizontal bar chart for quick comparison
st.markdown("---")
st.markdown("## Active Aircraft by Airport")

top_airports = [a for a in snapshot["airports"] if a["active"] > 0][:15]
if top_airports:
    top_airports.reverse()  # bottom to top for horizontal bar
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["on_ground"] for a in top_airports],
        name="Ground",
        orientation="h",
        marker_color="#334155",
        text=[a["on_ground"] for a in top_airports],
        textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["low_altitude"] for a in top_airports],
        name="Low Altitude (<10k ft)",
        orientation="h",
        marker_color="#0ea5e9",
        text=[a["low_altitude"] for a in top_airports],
        textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["descending"] for a in top_airports],
        name="Descending",
        orientation="h",
        marker_color="#f59e0b",
        text=[a["descending"] for a in top_airports],
        textposition="inside",
        hoverinfo="none",
    ))
    fig2.add_trace(go.Bar(
        y=[a["iata"] for a in top_airports],
        x=[a["climbing"] for a in top_airports],
        name="Climbing",
        orientation="h",
        marker_color="#22c55e",
        text=[a["climbing"] for a in top_airports],
        textposition="inside",
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

# Data table
st.markdown("---")
with st.expander("Full Airport Data"):
    table = []
    for i, a in enumerate(snapshot["airports"], 1):
        if a["total_nearby"] == 0:
            continue
        table.append({
            "Rank": i,
            "IATA": a["iata"],
            "Airport": a["name"],
            "Active": a["active"],
            "Ground": a["on_ground"],
            "Low Alt": a["low_altitude"],
            "Descending": a["descending"],
            "Climbing": a["climbing"],
            "Total Nearby": a["total_nearby"],
        })
    if table:
        st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Data: OpenSky Network (free, no API key). Aircraft within 20km and below 10,000ft of each airport are counted as 'active'. Refreshes every 2 minutes.")
