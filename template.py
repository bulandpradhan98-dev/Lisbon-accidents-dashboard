import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium

st.set_page_config(page_title="Lisbon Road Accidents", layout="wide")

st.title("Lisbon Road Accidents – Interactive Dashboard")
st.markdown("Explore and analyze road accident data from Lisbon (2023).")

st.markdown(
    """
> ⚠️ **Important Notice**  
> This dataset contains real road accident records from Portugal in 2023, provided by **ANSR (National Road Safety Authority)**.  
> It is intended **exclusively for educational use within this course**. Redistribution or use for any other purpose is strictly prohibited.
"""
)

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df

df = load_data("Road_Accidents_Lisbon.csv")

# -----------------------------
# Feature engineering
# -----------------------------
inj_cols = ["fatalities_30d", "serious_injuries_30d", "minor_injuries_30d"]
for c in inj_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

df["severity"] = "No injury"
df.loc[df["minor_injuries_30d"] > 0, "severity"] = "Minor"
df.loc[df["serious_injuries_30d"] > 0, "severity"] = "Serious"
df.loc[df["fatalities_30d"] > 0, "severity"] = "Fatal"

# Month ordering (optional but nice)
month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
if "month" in df.columns:
    df["month"] = df["month"].astype(str)
    df["month"] = pd.Categorical(df["month"], categories=month_order, ordered=True)

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filter Options")

# Weekday
weekday_options = sorted(df["weekday"].dropna().unique().tolist())
selected_weekdays = st.sidebar.multiselect("Weekday", weekday_options, default=weekday_options)

# Hour
selected_hours = st.sidebar.slider("Hour of Day", 0, 23, (0, 23))

# Month
month_options = [m for m in month_order if m in set(df["month"].dropna().unique())] if "month" in df.columns else []
selected_months = st.sidebar.multiselect("Month", month_options, default=month_options if month_options else None)

# Municipality
muni_options = sorted(df["municipality"].dropna().unique().tolist()) if "municipality" in df.columns else []
selected_muni = st.sidebar.multiselect("Municipality", muni_options, default=muni_options if muni_options else None)

# Severity (derived)
severity_options = ["Fatal", "Serious", "Minor", "No injury"]
selected_severity = st.sidebar.multiselect("Severity", severity_options, default=severity_options)

# Map layers
st.sidebar.subheader("Map Layers")
use_marker_cluster = st.sidebar.checkbox("Marker clustering", value=True)
use_heatmap = st.sidebar.checkbox("Heatmap", value=False)

# -----------------------------
# Apply filters
# -----------------------------
df_filtered = df.copy()
df_filtered = df_filtered[df_filtered["weekday"].isin(selected_weekdays)]
df_filtered = df_filtered[df_filtered["hour"].between(selected_hours[0], selected_hours[1])]
df_filtered = df_filtered[df_filtered["severity"].isin(selected_severity)]

if selected_months:
    df_filtered = df_filtered[df_filtered["month"].isin(selected_months)]
if selected_muni:
    df_filtered = df_filtered[df_filtered["municipality"].isin(selected_muni)]

df_filtered = df_filtered.dropna(subset=["latitude", "longitude"])

if len(df_filtered) == 0:
    st.warning("No accidents match your current filters.")
    st.stop()

# -----------------------------
# KPIs
# -----------------------------
st.subheader("Overview")
c1, c2, c3, c4 = st.columns(4)

c1.metric("Accidents (filtered)", f"{len(df_filtered):,}")
c2.metric("Fatalities (30d)", f"{int(df_filtered['fatalities_30d'].sum()):,}")
c3.metric("Serious injuries (30d)", f"{int(df_filtered['serious_injuries_30d'].sum()):,}")
c4.metric("Minor injuries (30d)", f"{int(df_filtered['minor_injuries_30d'].sum()):,}")

# -----------------------------
# GeoDataFrame + layout
# -----------------------------
gdf = gpd.GeoDataFrame(
    df_filtered,
    geometry=[Point(xy) for xy in zip(df_filtered["longitude"], df_filtered["latitude"])],
    crs="EPSG:4326"
)

left, right = st.columns([1.35, 1])

# -----------------------------
# Map
# -----------------------------
with left:
    st.subheader("Accident Map")

    center = [gdf["latitude"].mean(), gdf["longitude"].mean()]
    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB Positron")

    # color per severity
    color_map = {
        "Fatal": "black",
        "Serious": "orange",
        "Minor": "blue",
        "No injury": "gray"
    }

    parent = m
    if use_marker_cluster:
        cluster = MarkerCluster(name="Markers (clustered)")
        cluster.add_to(m)
        parent = cluster

    for _, row in gdf.iterrows():
        sev = row["severity"]
        popup = (
            f"ID: {row['id']}<br>"
            f"Weekday: {row['weekday']}<br>"
            f"Hour: {int(row['hour']):02d}:00<br>"
            f"Severity: {sev}<br>"
            f"Fatalities: {row['fatalities_30d']}<br>"
            f"Serious injuries: {row['serious_injuries_30d']}<br>"
            f"Minor injuries: {row['minor_injuries_30d']}<br>"
            f"Municipality: {row.get('municipality','—')}"
        )

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5,
            color=color_map.get(sev, "red"),
            fill=True,
            fill_opacity=0.65,
            popup=popup
        ).add_to(parent)

    if use_heatmap:
        HeatMap(gdf[["latitude", "longitude"]].values.tolist(), name="Heatmap").add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width=900, height=620)

# -----------------------------
# Charts + Insights
# -----------------------------
with right:
    st.subheader("Visual Summaries")

    try:
        import plotly.express as px

        # By hour
        hour_counts = df_filtered["hour"].value_counts().sort_index().reset_index()
        hour_counts.columns = ["hour", "count"]
        fig_h = px.bar(hour_counts, x="hour", y="count", title="Accidents by Hour")
        st.plotly_chart(fig_h, use_container_width=True)

        # By weekday
        wd_counts = df_filtered["weekday"].value_counts().reset_index()
        wd_counts.columns = ["weekday", "count"]
        fig_wd = px.bar(wd_counts, x="weekday", y="count", title="Accidents by Weekday")
        st.plotly_chart(fig_wd, use_container_width=True)

        # By severity
        sev_counts = df_filtered["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        fig_s = px.bar(sev_counts, x="severity", y="count", title="Accidents by Severity")
        st.plotly_chart(fig_s, use_container_width=True)

        # Hour x weekday heatmap (nice “bonus-like” insight)
        pivot = df_filtered.pivot_table(index="weekday", columns="hour", values="id", aggfunc="count").fillna(0)
        fig_hw = px.imshow(pivot, title="Accidents Heatmap: Weekday × Hour", aspect="auto")
        st.plotly_chart(fig_hw, use_container_width=True)

    except Exception:
        st.info("Plotly not installed. Install with: pip install plotly")

    st.subheader("What this suggests (quick insights)")
    peak_hour = int(df_filtered["hour"].value_counts().idxmax())
    top_day = df_filtered["weekday"].value_counts().idxmax()
    top_sev = df_filtered["severity"].value_counts().idxmax()

    st.markdown(
        f"""
- Peak accident hour in the filtered data is **{peak_hour:02d}:00**.
- Accidents occur most often on **{top_day}**.
- Most common severity (derived) is **{top_sev}**.
- Severity rule used: Fatal if fatalities>0, else Serious if serious injuries>0, else Minor if minor injuries>0, else No injury.
"""
    )

st.caption("Use the sidebar to isolate patterns by time, severity, and municipality, then compare map hotspots with chart peaks.")
