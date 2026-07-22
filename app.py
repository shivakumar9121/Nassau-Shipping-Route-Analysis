import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="Nassau Candy - Shipping Route Efficiency",
    page_icon="🚚",
    layout="wide"
)

st.markdown("""
<style>

.main{
    background-color:#0E1117;
}

.block-container{
    padding-top:2rem;
    padding-bottom:2rem;
}

h1{
    color:#3FB6A8;
}

h2{
    color:#3FB6A8;
}

div[data-testid="stMetric"]{
    background:#1E2229;
    border-radius:15px;
    padding:18px;
    border:1px solid #3FB6A8;
    box-shadow:0px 0px 10px rgba(0,0,0,0.4);
}

div[data-testid="stMetricLabel"]{
    color:#FFB347;
    font-size:18px;
}

</style>
""", unsafe_allow_html=True)

# path to the dataset
DATA_PATH = "data/Nassau_Candy_Distributor.csv"

# colors reused across charts so things stay consistent
PRIMARY_COLOR = "#3FB6A8"
SECONDARY_COLOR = "#FFB347"
DANGER_COLOR = "#E4572E"

# -------------------------------------------------
# FACTORY REFERENCE DATA
# (this comes straight from the project brief - every product
# is manufactured at exactly one of these 5 factories)
# -------------------------------------------------
FACTORY_COORDS = {
    "Lot's O' Nuts":     {"lat": 32.881893, "lon": -111.768036},
    "Wicked Choccy's":   {"lat": 32.076176, "lon": -81.088371},
    "Sugar Shack":       {"lat": 48.119140, "lon": -96.181150},
    "Secret Factory":    {"lat": 41.446333, "lon": -90.565487},
    "The Other Factory": {"lat": 35.117500, "lon": -89.971107},
}

PRODUCT_FACTORY_MAP = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack",
    "SweeTARTS": "Sugar Shack",
    "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack",
    "Fizzy Lifting Drinks": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory",
    "Hair Toffee": "The Other Factory",
    "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
    "Kazookles": "The Other Factory",
}

# needed for the choropleth map, which only understands 2-letter
# USPS codes. Canadian provinces are kept out of the map itself but
# still show up everywhere else in the dashboard.
US_STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

# -------------------------------------------------
# TITLE
# -------------------------------------------------
st.title("🚚 Factory-to-Customer Shipping Route Efficiency Dashboard")
st.write("Route-level logistics intelligence for Nassau Candy Distributor")
st.caption("Built using Streamlit | Pandas | NumPy | Plotly")
st.divider()

# -------------------------------------------------
# LOAD + PREP DATA
# -------------------------------------------------
@st.cache_data
def load_data():
    data = pd.read_csv(DATA_PATH)

    # dates in this export are day-first (dd-mm-yyyy)
    data["Order Date"] = pd.to_datetime(data["Order Date"], dayfirst=True, errors="coerce")
    data["Ship Date"] = pd.to_datetime(data["Ship Date"], dayfirst=True, errors="coerce")

    for col in ["Sales", "Units", "Gross Profit", "Cost"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # a record is only useful if we actually know when it was ordered,
    # when it shipped, and what it was worth
    data = data.dropna(subset=["Order Date", "Ship Date", "Sales", "Units", "Gross Profit"])

    # this is the core KPI the whole project is built around
    data["Lead Time"] = (data["Ship Date"] - data["Order Date"]).dt.days

    # negative lead time means the shipment left before it was ordered,
    # which isn't physically possible - drop those rows
    data = data[data["Lead Time"] >= 0]

    # attach factory + route info
    data["Factory"] = data["Product Name"].map(PRODUCT_FACTORY_MAP)
    data = data.dropna(subset=["Factory"])

    data["Route (State)"] = data["Factory"] + " -> " + data["State/Province"]
    data["Route (Region)"] = data["Factory"] + " -> " + data["Region"]

    data["Factory Lat"] = data["Factory"].map(lambda f: FACTORY_COORDS[f]["lat"])
    data["Factory Lon"] = data["Factory"].map(lambda f: FACTORY_COORDS[f]["lon"])

    data["State Abbr"] = data["State/Province"].map(US_STATE_ABBR)

    data["Order Month"] = data["Order Date"].dt.to_period("M").astype(str)

    return data


try:
    df = load_data()
except FileNotFoundError:
    st.error(f"Could not find the data file at '{DATA_PATH}'. Make sure it's inside the data folder.")
    st.stop()
except Exception as e:
    st.error(f"Something went wrong while loading the data: {e}")
    st.stop()

st.success("Shipment dataset loaded and cleaned successfully!")

with st.expander("📄 View Dataset Preview"):
    st.dataframe(df.head())

# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------
st.sidebar.header("🔎 Filters")

min_date = df["Order Date"].min().date()
max_date = df["Order Date"].max().date()

date_range = st.sidebar.date_input(
    "Order Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

region_filter = st.sidebar.multiselect(
    "Region",
    options=sorted(df["Region"].unique()),
    default=sorted(df["Region"].unique())
)

state_filter = st.sidebar.multiselect(
    "State / Province",
    options=sorted(df["State/Province"].unique()),
    default=sorted(df["State/Province"].unique())
)

ship_mode_filter = st.sidebar.multiselect(
    "Ship Mode",
    options=sorted(df["Ship Mode"].unique()),
    default=sorted(df["Ship Mode"].unique())
)

lead_time_threshold = st.sidebar.slider(
    "Delay Threshold (days)",
    min_value=int(df["Lead Time"].min()),
    max_value=int(df["Lead Time"].max()),
    value=int(df["Lead Time"].quantile(0.75)),
    help="Shipments with a lead time above this value are counted as 'delayed' for the KPIs below."
)

# -------------------------------------------------
# APPLY FILTERS
# -------------------------------------------------
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

filtered_df = df[
    (df["Order Date"].dt.date >= start_date) &
    (df["Order Date"].dt.date <= end_date) &
    (df["Region"].isin(region_filter)) &
    (df["State/Province"].isin(state_filter)) &
    (df["Ship Mode"].isin(ship_mode_filter))
]

if filtered_df.empty:
    st.warning("No shipments match the current filters. Try widening the date range or selections in the sidebar.")
    st.stop()

# -------------------------------------------------
# KPI CALCULATIONS
# -------------------------------------------------
total_shipments = len(filtered_df)
avg_lead_time = filtered_df["Lead Time"].mean()
median_lead_time = filtered_df["Lead Time"].median()
lead_time_std = filtered_df["Lead Time"].std()
delayed_shipments = (filtered_df["Lead Time"] > lead_time_threshold).sum()
delay_rate = (delayed_shipments / total_shipments) * 100
total_routes = filtered_df["Route (State)"].nunique()
total_factories = filtered_df["Factory"].nunique()

# -------------------------------------------------
# KPI CARDS
# -------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("📦 Total Shipments", f"{total_shipments:,}")

with c2:
    st.metric("⏱️ Average Lead Time", f"{avg_lead_time:,.1f} days")

with c3:
    st.metric("📐 Lead Time Variability", f"±{lead_time_std:,.1f} days")

with c4:
    st.metric("⚠️ Delay Frequency", f"{delay_rate:,.1f}%")

c5, c6 = st.columns(2)

with c5:
    st.metric("🛣️ Active Routes", f"{total_routes:,}")

with c6:
    st.metric("🏭 Factories in Use", f"{total_factories:,}")

st.divider()

# ==========================================================
# TABS
# ==========================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚚 Route Efficiency Overview",
    "🗺️ Geographic Shipping Map",
    "📦 Ship Mode Comparison",
    "🔍 Route Drill-Down",
    "🗂 Dataset Explorer",
    "ℹ️ About Project"
])

# ==========================================================
# TAB 1 - ROUTE EFFICIENCY OVERVIEW
# ==========================================================
with tab1:

    st.subheader("🏆 Route Performance Leaderboard")

    route_stats = (
        filtered_df.groupby("Route (State)")
        .agg(
            Shipments=("Order ID", "count"),
            Avg_Lead_Time=("Lead Time", "mean"),
            Lead_Time_Std=("Lead Time", "std"),
        )
        .reset_index()
    )
    route_stats["Lead_Time_Std"] = route_stats["Lead_Time_Std"].fillna(0)

    # delay % per route, computed against the same threshold used for the KPI cards
    delay_per_route = (
        filtered_df.assign(Delayed=filtered_df["Lead Time"] > lead_time_threshold)
        .groupby("Route (State)")["Delayed"]
        .mean()
        .mul(100)
        .rename("Delay_Rate")
        .reset_index()
    )
    route_stats = route_stats.merge(delay_per_route, on="Route (State)")

    # Route Efficiency Score: normalized 0-100, faster + more consistent routes score higher.
    # Lower average lead time and lower variability both push the score up.
    min_lt, max_lt = route_stats["Avg_Lead_Time"].min(), route_stats["Avg_Lead_Time"].max()
    if max_lt > min_lt:
        route_stats["Efficiency Score"] = 100 * (1 - (route_stats["Avg_Lead_Time"] - min_lt) / (max_lt - min_lt))
    else:
        route_stats["Efficiency Score"] = 100.0

    route_stats = route_stats.sort_values("Avg_Lead_Time")

    left, right = st.columns(2)

    with left:
        st.markdown("**🟢 Top 10 Most Efficient Routes**")
        top10 = route_stats.head(10)
        fig_top = px.bar(
            top10,
            x="Avg_Lead_Time",
            y="Route (State)",
            orientation="h",
            color_discrete_sequence=[PRIMARY_COLOR],
            title="Fastest Routes (lowest avg lead time)"
        )
        fig_top.update_layout(
            template="plotly_dark", height=420,
            yaxis=dict(autorange="reversed"),
            margin=dict(l=10, r=10, t=60, b=40)
        )
        st.plotly_chart(fig_top, use_container_width=True)

    with right:
        st.markdown("**🔴 Bottom 10 Least Efficient Routes**")
        bottom10 = route_stats.tail(10).sort_values("Avg_Lead_Time", ascending=False)
        fig_bottom = px.bar(
            bottom10,
            x="Avg_Lead_Time",
            y="Route (State)",
            orientation="h",
            color_discrete_sequence=[DANGER_COLOR],
            title="Slowest Routes (highest avg lead time)"
        )
        fig_bottom.update_layout(
            template="plotly_dark", height=420,
            yaxis=dict(autorange="reversed"),
            margin=dict(l=10, r=10, t=60, b=40)
        )
        st.plotly_chart(fig_bottom, use_container_width=True)

    st.divider()
    st.subheader("📋 Full Route Leaderboard")
    st.dataframe(
        route_stats.rename(columns={
            "Avg_Lead_Time": "Avg Lead Time (days)",
            "Lead_Time_Std": "Lead Time Std Dev",
            "Delay_Rate": "Delay Rate (%)"
        }).style.format({
            "Avg Lead Time (days)": "{:.1f}",
            "Lead Time Std Dev": "{:.1f}",
            "Delay Rate (%)": "{:.1f}%",
            "Efficiency Score": "{:.1f}"
        }),
        use_container_width=True,
        height=400
    )

    st.divider()
    st.subheader("📊 Route Volume vs Lead Time")
    fig_vol = px.scatter(
        route_stats,
        x="Shipments",
        y="Avg_Lead_Time",
        size="Shipments",
        color="Efficiency Score",
        color_continuous_scale="RdYlGn",
        hover_name="Route (State)",
        title="Route volume against average lead time (bubble = shipment count)"
    )
    fig_vol.update_layout(
        template="plotly_dark", height=500,
        xaxis_title="Total Shipments on Route",
        yaxis_title="Average Lead Time (days)",
        margin=dict(l=40, r=40, t=60, b=40)
    )
    st.plotly_chart(fig_vol, use_container_width=True)

# ==========================================================
# TAB 2 - GEOGRAPHIC SHIPPING MAP
# ==========================================================
with tab2:

    st.subheader("🗺️ US Shipping Efficiency Heatmap")

    us_df = filtered_df[filtered_df["Country/Region"] == "United States"].copy()

    if us_df.empty:
        st.info("No United States shipments in the current filter selection to plot on the map.")
    else:
        state_geo = (
            us_df.groupby(["State/Province", "State Abbr"])
            .agg(
                Shipments=("Order ID", "count"),
                Avg_Lead_Time=("Lead Time", "mean")
            )
            .reset_index()
        )

        fig_map = go.Figure()

        fig_map.add_trace(go.Choropleth(
            locations=state_geo["State Abbr"],
            z=state_geo["Avg_Lead_Time"],
            locationmode="USA-states",
            colorscale="RdYlGn_r",
            colorbar_title="Avg Lead Time (days)",
            marker_line_color="white",
            marker_line_width=0.5,
            text=state_geo["State/Province"]
        ))

        factory_points = (
            us_df.groupby("Factory")
            .agg(Shipments=("Order ID", "count"))
            .reset_index()
        )
        factory_points["lat"] = factory_points["Factory"].map(lambda f: FACTORY_COORDS[f]["lat"])
        factory_points["lon"] = factory_points["Factory"].map(lambda f: FACTORY_COORDS[f]["lon"])

        fig_map.add_trace(go.Scattergeo(
            lon=factory_points["lon"],
            lat=factory_points["lat"],
            text=factory_points["Factory"] + " (" + factory_points["Shipments"].astype(str) + " shipments)",
            mode="markers+text",
            textposition="top center",
            marker=dict(size=12, color=SECONDARY_COLOR, symbol="star", line=dict(width=1, color="black")),
            name="Factories"
        ))

        fig_map.update_layout(
            template="plotly_dark",
            geo=dict(scope="usa", bgcolor="rgba(0,0,0,0)", lakecolor="#0E1117"),
            height=600,
            margin=dict(l=10, r=10, t=30, b=10)
        )

        st.plotly_chart(fig_map, use_container_width=True)

        st.caption("Darker red = slower average lead time. Stars mark the 5 Nassau Candy factories.")

        st.divider()
        st.subheader("🚧 Geographic Bottleneck Analysis")

        avg_shipments = state_geo["Shipments"].mean()
        avg_state_lead_time = state_geo["Avg_Lead_Time"].mean()

        bottlenecks = state_geo[
            (state_geo["Avg_Lead_Time"] > avg_state_lead_time) &
            (state_geo["Shipments"] > avg_shipments)
        ].sort_values("Avg_Lead_Time", ascending=False)

        if bottlenecks.empty:
            st.info("No states currently combine above-average shipment volume with above-average lead time.")
        else:
            st.write(
                f"States below ship **above-average volume** ({avg_shipments:.0f}+ shipments) "
                f"**and** have **above-average lead time** ({avg_state_lead_time:.0f}+ days) — "
                "these are the routes worth investigating first."
            )
            st.dataframe(
                bottlenecks[["State/Province", "Shipments", "Avg_Lead_Time"]].rename(
                    columns={"Avg_Lead_Time": "Avg Lead Time (days)"}
                ).style.format({"Avg Lead Time (days)": "{:.1f}"}),
                use_container_width=True
            )

    non_us_df = filtered_df[filtered_df["Country/Region"] != "United States"]
    if not non_us_df.empty:
        st.divider()
        st.subheader("🇨🇦 Cross-Border Shipments (not shown on map)")
        non_us_stats = (
            non_us_df.groupby("State/Province")
            .agg(Shipments=("Order ID", "count"), Avg_Lead_Time=("Lead Time", "mean"))
            .reset_index()
            .sort_values("Shipments", ascending=False)
        )
        st.dataframe(
            non_us_stats.rename(columns={"Avg_Lead_Time": "Avg Lead Time (days)"}).style.format(
                {"Avg Lead Time (days)": "{:.1f}"}
            ),
            use_container_width=True
        )

# ==========================================================
# TAB 3 - SHIP MODE COMPARISON
# ==========================================================
with tab3:

    st.subheader("📦 Lead Time by Ship Mode")

    fig_box = px.box(
        filtered_df,
        x="Ship Mode",
        y="Lead Time",
        color="Ship Mode",
        color_discrete_sequence=px.colors.qualitative.Set2,
        title="Distribution of shipping lead time per ship mode"
    )
    fig_box.update_layout(template="plotly_dark", height=480, showlegend=False,
                           margin=dict(l=40, r=40, t=60, b=40))
    st.plotly_chart(fig_box, use_container_width=True)

    st.divider()

    mode_stats = (
        filtered_df.assign(Delayed=filtered_df["Lead Time"] > lead_time_threshold)
        .groupby("Ship Mode")
        .agg(
            Shipments=("Order ID", "count"),
            Avg_Lead_Time=("Lead Time", "mean"),
            Avg_Sales=("Sales", "mean"),
            Avg_Cost=("Cost", "mean"),
            Delay_Rate=("Delayed", "mean")
        )
        .reset_index()
    )
    mode_stats["Delay_Rate"] = mode_stats["Delay_Rate"] * 100
    mode_stats = mode_stats.sort_values("Avg_Lead_Time")

    left, right = st.columns(2)

    with left:
        fig_mode_bar = px.bar(
            mode_stats,
            x="Ship Mode",
            y="Avg_Lead_Time",
            color="Ship Mode",
            text_auto=".1f",
            color_discrete_sequence=px.colors.qualitative.Set2,
            title="Average Lead Time by Ship Mode"
        )
        fig_mode_bar.update_traces(textposition="outside")
        fig_mode_bar.update_layout(template="plotly_dark", height=420, showlegend=False,
                                    margin=dict(l=40, r=40, t=60, b=40))
        st.plotly_chart(fig_mode_bar, use_container_width=True)

    with right:
        fig_delay_bar = px.bar(
            mode_stats,
            x="Ship Mode",
            y="Delay_Rate",
            color="Ship Mode",
            text_auto=".1f",
            color_discrete_sequence=px.colors.qualitative.Set2,
            title="Delay Frequency (%) by Ship Mode"
        )
        fig_delay_bar.update_traces(textposition="outside")
        fig_delay_bar.update_layout(template="plotly_dark", height=420, showlegend=False,
                                     margin=dict(l=40, r=40, t=60, b=40))
        st.plotly_chart(fig_delay_bar, use_container_width=True)

    st.divider()
    st.subheader("💰 Cost vs Time Tradeoff (descriptive)")
    st.caption("This just lays the numbers side by side — it doesn't say one mode is 'better', since that depends on business priorities.")
    st.dataframe(
        mode_stats.rename(columns={
            "Avg_Lead_Time": "Avg Lead Time (days)",
            "Avg_Sales": "Avg Sales ($)",
            "Avg_Cost": "Avg Cost ($)",
            "Delay_Rate": "Delay Rate (%)"
        }).style.format({
            "Avg Lead Time (days)": "{:.1f}",
            "Avg Sales ($)": "${:,.2f}",
            "Avg Cost ($)": "${:,.2f}",
            "Delay Rate (%)": "{:.1f}%"
        }),
        use_container_width=True
    )

# ==========================================================
# TAB 4 - ROUTE DRILL-DOWN
# ==========================================================
with tab4:

    st.subheader("🔍 Inspect a Single Route")

    route_options = sorted(filtered_df["Route (State)"].unique())
    selected_route = st.selectbox("Choose a Factory → State route", options=route_options)

    route_df = filtered_df[filtered_df["Route (State)"] == selected_route].sort_values("Order Date")

    r1, r2, r3, r4 = st.columns(4)

    with r1:
        st.metric("Shipments", f"{len(route_df):,}")
    with r2:
        st.metric("Avg Lead Time", f"{route_df['Lead Time'].mean():.1f} days")
    with r3:
        st.metric("Fastest Shipment", f"{route_df['Lead Time'].min():.0f} days")
    with r4:
        st.metric("Slowest Shipment", f"{route_df['Lead Time'].max():.0f} days")

    st.divider()
    st.subheader("📈 Order-Level Shipment Timeline")

    fig_timeline = px.scatter(
        route_df,
        x="Order Date",
        y="Lead Time",
        color="Ship Mode",
        hover_data=["Order ID", "Product Name", "Sales"],
        color_discrete_sequence=px.colors.qualitative.Set2,
        title=f"Lead time over time for {selected_route}"
    )
    fig_timeline.add_hline(
        y=lead_time_threshold, line_dash="dash", line_color=DANGER_COLOR,
        annotation_text="Delay threshold", annotation_position="top left"
    )
    fig_timeline.update_layout(template="plotly_dark", height=450,
                               margin=dict(l=40, r=40, t=60, b=40))
    st.plotly_chart(fig_timeline, use_container_width=True)

    st.divider()
    st.subheader("📋 Order-Level Records for this Route")
    st.dataframe(
        route_df[[
            "Order ID", "Order Date", "Ship Date", "Ship Mode",
            "Product Name", "Sales", "Units", "Lead Time"
        ]].reset_index(drop=True),
        use_container_width=True
    )

# ==========================================================
# TAB 5 - DATASET EXPLORER
# ==========================================================
with tab5:

    st.subheader("📄 Filtered Dataset")
    st.dataframe(filtered_df, use_container_width=True)

    st.divider()
    st.subheader("🧾 Dataset Summary")

    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.metric("Rows", f"{filtered_df.shape[0]:,}")
    with d2:
        st.metric("Columns", f"{filtered_df.shape[1]:,}")
    with d3:
        st.metric("Missing Values", f"{int(filtered_df.isnull().sum().sum()):,}")
    with d4:
        st.metric("Duplicate Rows", f"{int(filtered_df.duplicated().sum()):,}")

    st.divider()
    st.subheader("⬇ Download Filtered Dataset")

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="Filtered_Nassau_Candy_Shipments.csv",
        mime="text/csv"
    )

    st.divider()
    st.subheader("📊 Quick Stats")
    st.write(
        f"Order date range: {filtered_df['Order Date'].min().date()} "
        f"to {filtered_df['Order Date'].max().date()}"
    )
    st.dataframe(filtered_df.describe(include=[np.number]), use_container_width=True)

# ==========================================================
# TAB 6 - ABOUT PROJECT
# ==========================================================
with tab6:

    st.subheader("ℹ️ About this Project")

    st.markdown("""
#### Project Title
**Factory-to-Customer Shipping Route Efficiency Analysis for Nassau Candy Distributor**

#### Background
Nassau Candy Distributor ships products from 5 factories to customers across the US and Canada.
Before this dashboard, logistics decisions were made without any route-level visibility — nobody
could easily say which factory-to-customer lanes were reliable and which ones were quietly costing
the business time and money.

#### Objective
To turn raw order and shipment records into route-level operational intelligence: which routes are
fast, which are slow, how performance differs by ship mode, and where the geographic bottlenecks are.

#### Technologies Used
- Python
- Streamlit
- Pandas
- NumPy
- Plotly

#### Dataset
Nassau Candy Distributor order and shipment dataset (10,000+ line items), enriched with a
product → factory lookup table and factory GPS coordinates.

#### Factories
""")

    factory_table = pd.DataFrame([
        {"Factory": name, "Latitude": coords["lat"], "Longitude": coords["lon"]}
        for name, coords in FACTORY_COORDS.items()
    ])
    st.dataframe(factory_table, use_container_width=True, hide_index=True)

    st.markdown("""
#### Dashboard Modules
- Route Efficiency Overview — leaderboard, top/bottom 10 routes, efficiency score
- Geographic Shipping Map — US heatmap of lead time, factory locations, bottleneck states
- Ship Mode Comparison — lead time and delay rate by shipping method
- Route Drill-Down — order-level timeline for any single route
- Dataset Explorer — raw data, quality checks, CSV export

#### Key Performance Indicators
- **Shipping Lead Time** = Ship Date − Order Date
- **Average Lead Time** = mean lead time per route
- **Route Volume** = number of shipments per route
- **Delay Frequency** = % of shipments exceeding the chosen threshold
- **Route Efficiency Score** = normalized lead-time performance (0–100, higher is better)

#### Author
**Pathlavath Shiva Kumar**
""")

    st.divider()
with st.container():
    st.markdown(
        """
        <div style="text-align: center; line-height: 1.6;">
            <div style="font-size: 1.3rem; font-weight: bold; margin-bottom: 4px;">
                🚚 Factory-to-Customer Shipping Route Efficiency Dashboard
            </div>
            <div style="font-size: 0.95rem; opacity: 0.9;">
                Developed by <b>Pathlavath Shiva Kumar</b> |Data analytic Intern
            </div>
            <div style="font-size: 0.85rem; opacity: 0.75;">
                Built using <b>Python • Streamlit • Pandas • NumPy • Plotly</b>
            </div>
            <div style="font-size: 0.8rem; opacity: 0.6; margin-top: 10px;">
                © 2026 | Data Analytics & Logistics Analytics & Business Intelligence 
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
