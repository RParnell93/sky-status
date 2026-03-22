import os
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone

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
SILVER_DARK = "#5C6F82"
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
        con.close()
        airports = []
        for r in rows:
            airports.append({
                "icao": r[0], "iata": r[1], "name": r[2],
                "lat": next((a["lat"] for a in AIRPORTS if a["icao"] == r[0]), 0),
                "lon": next((a["lon"] for a in AIRPORTS if a["icao"] == r[0]), 0),
                "active": r[3], "on_ground": r[4], "airborne": r[5],
                "low_altitude": r[6], "descending": r[7], "climbing": r[8],
                "total_nearby": r[9], "aircraft": [],
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
    st.markdown(f'<div class="metric-card"><div class="metric-value">{snapshot["total_us_aircraft"]:,}</div><div class="metric-label">Aircraft Over US</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{active_airports}</div><div class="metric-label">Active Airports</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_active}</div><div class="metric-label">Near Airports</div></div>', unsafe_allow_html=True)
with c4:
    if busiest:
        busiest_gpct = round(busiest["on_ground"] / busiest["active"] * 100) if busiest["active"] else 0
        st.markdown(f'<div class="metric-card"><div class="metric-value">{busiest["iata"]}</div><div class="metric-label">Busiest Right Now</div><div style="font-size:0.7em;color:{SILVER};margin-top:6px;font-family:JetBrains Mono,monospace;">{busiest["active"]} active - {busiest_gpct}% on ground</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{ground_pct}%</div><div class="metric-label">On Ground</div></div>', unsafe_allow_html=True)
with c6:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_descending}</div><div class="metric-label">Inbound Now</div></div>', unsafe_allow_html=True)

_src = snapshot.get("source", "OpenSky")
st.caption(f"Updated: {local_ts}  |  Source: {_src}  |  Refreshes every 2 min")

# Congestion Leaderboard
st.markdown('<div class="section-header">Airport Congestion Leaderboard</div>', unsafe_allow_html=True)

max_active = max((a["active"] for a in snapshot["airports"]), default=1) or 1

leaderboard_html = ""
for i, apt in enumerate(snapshot["airports"][:20], 1):
    pct = (apt["active"] / max_active) * 100
    rank_class = "gold" if i == 1 else "silver" if i == 2 else "bronze" if i == 3 else ""
    row_class = f"top-{i}" if i <= 3 else ""
    bar_class = "hot" if pct > 70 else "warm" if pct > 40 else ""
    detail = f'{apt["on_ground"]}g {apt["low_altitude"]}l {apt["descending"]}d {apt["climbing"]}c'

    leaderboard_html += f"""
    <div class="leaderboard-row {row_class}">
        <div class="lb-rank {rank_class}">{i}</div>
        <div class="lb-iata">{apt['iata']}</div>
        <div class="lb-name">{apt['name']}</div>
        <div class="lb-bar-bg"><div class="lb-bar {bar_class}" style="width:{max(pct, 2)}%;"></div></div>
        <div class="lb-count">{apt['active']}</div>
        <div class="lb-detail">{detail}</div>
    </div>"""

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
</style>
<div style="font-family:'Inter',sans-serif;">
    <div style="display:flex;justify-content:flex-end;gap:16px;margin-bottom:6px;font-size:0.55em;color:{SILVER_DARK};font-family:'JetBrains Mono',monospace;">
        <span>g = ground</span><span>l = low alt</span><span>d = descending</span><span>c = climbing</span>
    </div>
    {leaderboard_html}
</div>
""")

# Map + Ground Congestion side by side
st.markdown("---")
map_col, ground_col = st.columns([3, 2])

apt_data = [a for a in snapshot["airports"] if a["active"] > 0]

with map_col:
    st.markdown(f'<div class="section-header">Live Airspace Map</div>', unsafe_allow_html=True)
    if apt_data:
        fig = go.Figure()

        # Aircraft dots
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
                marker=dict(size=3, color=SILVER, opacity=0.3),
                text=aircraft_texts,
                hoverinfo="text",
                showlegend=False,
            ))

        import math
        max_act = max(a["active"] for a in apt_data) or 1
        ground_pcts = [round(a["on_ground"] / a["active"] * 100) if a["active"] else 0 for a in apt_data]
        fig.add_trace(go.Scattergeo(
            lat=[a["lat"] for a in apt_data],
            lon=[a["lon"] for a in apt_data],
            mode="markers+text",
            marker=dict(
                size=[8 + 20 * math.log1p(a["active"]) / math.log1p(max_act) for a in apt_data],
                color=ground_pcts,
                colorscale=[[0, "#2E8B57"], [0.4, SILVER], [0.7, RED_LIGHT], [1, RED]],
                cmin=0, cmax=100,
                opacity=0.75,
                line=dict(width=1, color="rgba(255,255,255,0.5)"),
                colorbar=dict(
                    title=dict(text="Ground %", font=dict(color=SILVER, size=9)),
                    tickfont=dict(color=SILVER, size=8),
                    ticksuffix="%", len=0.5, thickness=10,
                ),
            ),
            text=[f'{a["iata"]} {a["active"]}' for a in apt_data],
            textposition="top center",
            textfont=dict(size=8, color="white", family="JetBrains Mono"),
            hovertext=[f"<b>{a['iata']}</b> {a['name']}<br>Active: {a['active']} (size)<br>Ground: {a['on_ground']}/{a['active']} = {g}% (color)" for a, g in zip(apt_data, ground_pcts)],
            hoverinfo="text",
            showlegend=False,
        ))

        fig.update_geos(
            scope="usa",
            bgcolor="rgba(0,0,0,0)",
            landcolor=NAVY_MID,
            lakecolor=NAVY,
            showlakes=True,
            coastlinecolor=SILVER_DARK,
            countrycolor=SILVER_DARK,
            subunitcolor="rgba(92,111,130,0.27)",
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=550,
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

top_airports = [a for a in snapshot["airports"] if a["active"] > 0][:15]
if top_airports:
    top_airports.reverse()
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

# Congestion heatmap (needs historical data from MotherDuck)
def _load_heatmap_data():
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
    st.caption("Heatmap builds over time as more snapshots are collected every 2 hours.")

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
    <td style="padding:4px 0;">Snapshots taken every 2 hours (6 AM - 10 PM ET) and cached in MotherDuck. App cache TTL: 2 minutes.</td></tr>
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
