import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas import DateOffset

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide", initial_sidebar_state="expanded")

# --- Template Generator ---
def create_template():
    data = {
        "Project": ["Example Project"],
        "Keyword": ["shoes for men"],
        "MSV": [12100],
        "Current Position": [8],
        "AI Overview": ["Yes"],
        "Featured Snippet": ["No"],
        "Current URL": ["https://example.com/shoes-for-men"]
    }
    return pd.DataFrame(data).to_csv(index=False).encode("utf-8")

# --- Session State Init ---
for key, default in [
    ("ctr_df", pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32, 25, 18, 12, 10, 8, 6, 4, 2, 1]})),
    ("seasonality_df", pd.DataFrame({
        "Month": [
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        ],
        "Adjustment (%)": [0, 0, 0, 0, 0, -20, 0, 0, 0, 0, 0, 0]
    })),
    ("paid_listings", {}),
    ("df", pd.DataFrame()),
    ("launch_month_df", pd.DataFrame(columns=["Project", "Launch Date"]))
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- Helpers ---
def get_movement(msv):
    try:
        m = float(msv)
    except:
        m = 0.0
    if m <= 500:
        return 1.5
    if m <= 2000:
        return 1.0
    if m <= 10000:
        return 0.75
    return 0.5

def get_ctr_for_position(pos):
    df = st.session_state.ctr_df
    return float(df.loc[df["Position"] == pos, "CTR"].iloc[0]) if pos in df["Position"].values else 0.0

# --- Sidebar ---
with st.sidebar:
    st.subheader("Download Template")
    st.download_button("Download Template", data=create_template(), file_name="forecast_template.csv")

    st.subheader("Upload Data")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if uploaded:
        # Read and initialize data
        st.session_state.uploaded_file = uploaded
        df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
        df["MSV"] = pd.to_numeric(df.get("MSV", 0), errors="coerce").fillna(0)
        df["Current Position"] = pd.to_numeric(df.get("Current Position", 0), errors="coerce").fillna(0)
        st.session_state.df = df.copy()
        projects = df["Project"].dropna().unique()
        st.session_state.launch_month_df = pd.DataFrame({
            "Project": projects,
            "Launch Date": [datetime.today().replace(day=1)] * len(projects)
        })
        st.session_state.paid_listings = {p: 2 for p in projects}

    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)", min_value=0, max_value=100)},
        hide_index=True, use_container_width=True
    )

    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100, max_value=100)},
        hide_index=True, use_container_width=True
    )

    fs_ctr = st.number_input("Featured Snippet CTR (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)", min_value=0.0, max_value=100.0, value=12.0)

    st.subheader("Avg. Paid Listings per Project")
    if not st.session_state.launch_month_df.empty:
        proj = st.selectbox("Project", st.session_state.launch_month_df["Project"])
        st.session_state.paid_listings[proj] = st.slider(f"{proj} Paid Listings", 0, 10, st.session_state.paid_listings.get(proj, 2))

    st.subheader("Ranking Speed")
    speed_factor = st.slider("Speed multiplier", min_value=0.1, max_value=5.0, value=1.0, step=0.1)

# --- Forecast Function ---
def forecast_data():
    df = st.session_state.df
    base = datetime.today().replace(day=1)
    # Convert launch dates to timestamps
    launch_map = {proj: pd.to_datetime(ld) for proj, ld in st.session_state.launch_month_df.values}
    records = []
    for scen, sm in [("High", 1.5), ("Medium", 1.0), ("Low", 0.5)]:
        for _, row in df.iterrows():
            proj = row["Project"]
            msv = row["MSV"]
            pos = row["Current Position"]
            has_fs = str(row.get("Featured Snippet", "")).lower() == "yes"
            has_aio = str(row.get("AI Overview", "")).lower() == "yes"
            launch_dt = launch_map.get(proj, base)
            cur_pos = pos
            for month_index in range(1, 25):
                date = base + DateOffset(months=month_index - 1)
                clicks = 0
                # compute movement and clicks only if after launch
                if date >= launch_dt:
                    if month_index == 1 and cur_pos > 15:
                        cur_pos = 15
                    elif month_index > 1:
                        phase = 3.0 if cur_pos > 15 else 1.0 if cur_pos > 6 else 0.5
                        cur_pos = max(1, cur_pos - get_movement(msv) * speed_factor * phase * sm)
                    # always define rank
                    rank = int(round(cur_pos))
                    if rank <= st.session_state.ctr_df["Position"].max():
                        ctr = get_ctr_for_position(rank)
                        if scen == "Medium":
                            ctr *= (1 - 0.05 * st.session_state.paid_listings.get(proj, 0))
                            if rank == 1 and has_aio:
                                ctr = aio_ctr
                            if rank == 1 and has_fs:
                                ctr = fs_ctr
                        elif scen == "Low":
                            ctr *= 0.8
                        season_adj = st.session_state.seasonality_df.loc[
                            st.session_state.seasonality_df["Month"] == date.strftime("%B"),
                            "Adjustment (%)"
                        ].iloc[0]
                        raw_clicks = (ctr / 100) * msv
                        clicks = raw_clicks * (1 + season_adj / 100)
                else:
                    # before launch, rank remains current pos
                    rank = int(round(cur_pos))
                records.append({
                    "Scenario": scen,
                    "Project": proj,
                    "Keyword": row["Keyword"],
                    "Date": date,
                    "Clicks": round(clicks),
                    "Position": rank
                })
    return pd.DataFrame(records)

# --- Tabs Layout ---
tabs = st.tabs(["Dashboard", "Keyword Rank Tables", "Project Summary"])

# --- Dashboard Tab ---
with tabs[0]:
    st.title("SEO Forecast Dashboard")
    if st.session_state.df.empty:
        st.info("Upload data in the sidebar to begin.")
    else:
        rec_df = forecast_data()
        plot_df = rec_df.groupby(["Scenario", "Date"])["Clicks"].sum().reset_index()
        dmin = plot_df["Date"].min().date()
        dmax = plot_df["Date"].max().date()
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start Date", dmin, min_value=dmin, max_value=dmax)
        end_date = c2.date_input("End Date", dmax, min_value=dmin, max_value=dmax)
        st.session_state.endpoints = {"start": start_date, "end": end_date}
        mask = (
            (plot_df["Date"].dt.date >= start_date)
            & (plot_df["Date"].dt.date <= end_date)
        )
        totals = plot_df[mask].groupby("Scenario")["Clicks"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("High Forecast", totals.get("High", 0))
        m2.metric("Medium Forecast", totals.get("Medium", 0))
        m3.metric("Low Forecast", totals.get("Low", 0))
        fig = px.line(plot_df[mask], x="Date", y="Clicks", color="Scenario", markers=True)
        fig.update_layout(title="Projected Traffic Scenarios Over Time", yaxis_title="Clicks")
        st.plotly_chart(fig, use_container_width=True)
        summary_df = plot_df[mask].copy()
        summary_df["Month"] = summary_df["Date"].dt.strftime('%b %Y')
        summary_df["SortKey"] = summary_df["Date"]
        pivot = summary_df.pivot_table(
            index=["Month", "SortKey"],
            columns="Scenario",
            values="Clicks",
            aggfunc="sum"
        ).reset_index().sort_values("SortKey").drop(columns=["SortKey"])
        pivot.columns.name = None
        st.subheader("Forecast Summary by Scenario")
        st.dataframe(pivot, use_container_width=True)

# --- Keyword Rank Tables Tab ---
with tabs[1]:
    st.title("Keyword Rank Tables")
    if st.session_state.df.empty:
        st.info("Upload data in the sidebar to begin.")
    else:
        rec_df = forecast_data()
        rec_df['Month'] = rec_df['Date'].dt.to_period('M').dt.to_timestamp()
        scenario_selected = st.selectbox("Scenario", rec_df['Scenario'].unique())
        filtered = rec_df[rec_df['Scenario'] == scenario_selected]
        rank_table = filtered.pivot_table(
            index=["Project", "Keyword"],
            columns="Month",
            values="Position",
            aggfunc=lambda x: int(round(x))
        )
        rank_table = rank_table.sort_index(axis=1)
        rank_table.columns = [dt.strftime('%b %Y') for dt in rank_table.columns]
        st.subheader("Keyword Rank Progression")
        st.dataframe(rank_table, use_container_width=True)

# --- Project Summary Tab ---
with tabs[2]:
    st.title("Project Launch & Forecast Summary")
    # require data and dashboard end date
    if st.session_state.df.empty or 'end' not in st.session_state.endpoints:
        st.info("Upload data and select an End Date in the Dashboard to begin.")
    else:
        # calculate medium scenario clicks per project between launch and end_date
        rec_df = forecast_data()
        end_dt = pd.to_datetime(st.session_state.endpoints['end'])
        # map launch dates
        launch_series = pd.to_datetime(
            st.session_state.launch_month_df.set_index('Project')['Launch Date']
        )
        med = rec_df[rec_df['Scenario'] == 'Medium'].copy()
        med['Launch'] = med['Project'].map(launch_series)
        med = med[(med['Date'] >= med['Launch']) & (med['Date'] <= end_dt)]
        clicks_sum = med.groupby('Project')['Clicks'].sum().rename('Total Clicks')

        # build summary dataframe
        summary_df = st.session_state.launch_month_df.copy()
        summary_df['Total Clicks'] = summary_df['Project'].map(clicks_sum).fillna(0).astype(int)
        # ensure datetime dtype for calendar picker
        summary_df['Launch Date'] = pd.to_datetime(summary_df['Launch Date'])

        st.subheader("Launch Dates & Forecasted Clicks")
        # editable launch date (calendar), read-only clicks
        col_cfg = {
            'Launch Date': st.column_config.DateColumn(
                'Launch Date', format="YYYY-MM-DD"
            ),
            'Total Clicks': st.column_config.NumberColumn('Total Clicks', disabled=True)
        }
        edited = st.data_editor(
            summary_df,
            column_config=col_cfg,
            hide_index=True,
            use_container_width=True,
            key='proj_summary'
        )
        # save updated launches
        st.session_state.launch_month_df['Launch Date'] = edited['Launch Date']
