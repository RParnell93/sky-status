# Sky Status

Real-time US airport congestion tracker. Live at **[sky-status.streamlit.app](https://sky-status.streamlit.app/)**.

## What it does

Tracks aircraft activity at the 30 busiest US airports using live ADS-B data from the OpenSky Network. Shows congestion levels, ground delays, arrival/departure flow, and how each airport compares in real time.

## Dashboard

- **Congestion Leaderboard** - top 20 airports ranked by active aircraft, with smooth color gradient
- **Live Airspace Map** - bubble map sized by traffic volume, colored by ground congestion %
- **Ground Congestion** - which airports have the most planes stuck on the ground
- **Ground vs Airborne** - donut breakdown of arriving, departing, in-pattern, and ground traffic
- **Arrival vs Departure Flow** - diverging bar showing traffic direction imbalance per airport
- **Active Aircraft Breakdown** - stacked bar with ground, low altitude, descending, and climbing counts
- **Congestion by Time of Day** - heatmap that builds over time (activates with 4+ snapshots)

## Data

- **Source**: [OpenSky Network](https://opensky-network.org/) (free, crowdsourced ADS-B)
- **Coverage**: 30 US airports, aircraft within 20km radius and below 10,000ft
- **Storage**: MotherDuck (cloud DuckDB)
- **Refresh**: Every 2 hours via GitHub Actions (6am-10pm ET)
- **Additional pipelines**: Daily earthquake (USGS), wildfire (NASA FIRMS), air quality (Open-Meteo), and campaign finance (FEC) snapshots

## Stack

- Python, Streamlit, Plotly
- DuckDB / MotherDuck
- OpenSky Network API
- GitHub Actions for scheduled snapshots

## Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires `MOTHERDUCK_TOKEN` in `.env` or Streamlit secrets for cloud data access. Falls back to live OpenSky API if unavailable.
