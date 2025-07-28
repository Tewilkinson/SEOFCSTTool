import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pandas import DateOffset
import re

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
if "ctr_df" not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({
        "Position": list(range(1,11)),
        "CTR":      [32,25,18,12,10,8,6,4,2,1]
    })
if "seasonality_df" not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        "Month": [
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        ],
        "Adjustment (%)": [0,0,0,0,0,-20,0,0,0,0,0,0]
    })
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project","Launch Date"])
if "rec_df" not in st.session_state:
    st.session_state.rec_df = pd.DataFrame()  # Initialize the rec_df for later use

# --- Helpers ---
def get_movement(msv):
    """Base movement per month based on MSV difficulty."""
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
    return 1.0

def get_ctr_for_position(pos):
    df = st.session_state.ctr_df
    max_pos = df["Position"].max()
    return float(df.loc[df["Position"] == pos, "CTR"].iloc[0]) if pos <= max_pos else 0.0

# --- Sidebar ---
with st.sidebar:
    st.subheader("Download Template")
    st.download_button("Download Template CSV", data=create_template(), file_name="forecast_template.csv")

    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)", min_value=0.0, max_value=100.0)},
        use_container_width=True, hide_index=True, key="ctr_editor"
    )

    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100.0, max_value=100.0)},
        use_container_width=True, hide_index=True, key="season_editor"
    )

    fs_ctr  = st.number_input("Featured Snippet CTR (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)",      min_value=0.0, max_value=100.0, value=12.0)

    st.subheader("Avg. Paid Listings per Project")
    if not st.session_state.launch_month_df.empty:
        proj = st.selectbox("Select Project for Paid Listings", st.session_state.launch_month_df["Project"].tolist(), key="paid_project_selector")
        st.session_state.paid_listings[proj] = st.slider(f"{proj} Paid Listings", 0, 10, st.session_state.paid_listings.get(proj,2), key=f"paid_{proj}")

    st.subheader("Ranking Speed")
    speed_factor = st.slider("Speed multiplier (×)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)

# --- Tab Navigation with st.radio (for compatibility) ---
tab_selection = st.radio("Select a Tab", ["Dashboard", "Keyword Rank Tables", "Project Summary"])

# --- Dashboard Tab ---
if tab_selection == "Dashboard":
    st.title("SEO Keyword FCSTin Tool")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if not uploaded:
        st.info("Please upload a CSV or Excel file to start forecasting.")
        st.stop()

    # Read & clean input
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    df["MSV"]              = pd.to_numeric(df.get("MSV",0), errors="coerce").fillna(0)
    df["Current Position"] = pd.to_numeric(df.get("Current Position",0), errors="coerce").fillna(0)
    st.session_state.df = df.copy()

    # Projects & launch dates
    projects = df["Project"].dropna().unique().tolist()
    if set(projects) != set(st.session_state.launch_month_df["Project"]):
        st.session_state.launch_month_df = pd.DataFrame({
            "Project": projects,
            "Launch Date": [datetime.today().replace(day=1)] * len(projects)
        })
        st.session_state.paid_listings = {p:2 for p in projects}

    selected = st.selectbox("Select Project", ["All"] + projects)
    filtered = df if selected=="All" else df[df["Project"]==selected]

    base       = datetime.today().replace(day=1)
    launch_map = st.session_state.launch_month_df.set_index("Project")["Launch Date"].to_dict()
    rec = []

    for scenario in ["High","Medium","Low"]:
        for _, r in filtered.iterrows():
            proj, msv, pos = r["Project"], r["MSV"], r["Current Position"]
            url = r.get("Current URL","") or ""
            kw = r["Keyword"]
            has_aio = str(r["AI Overview"]).lower()=="yes"
            has_fs  = str(r["Featured Snippet"]).lower()=="yes"
            launch  = launch_map.get(proj, base)
            cur_pos = pos

            for i in range(1,25):
                date = base + DateOffset(months=i-1)
                raw_clicks = adjusted_clicks = 0

                if date >= launch:
                    # Month 1 snap: >15→15
                    if i == 1 and cur_pos > 15:
                        cur_pos = 15
                    elif i > 1:
                        # determine phase multiplier
                        if   cur_pos > 15: phase_mul = 3.0   # fast
                        elif cur_pos >  6: phase_mul = 1.0   # medium
                        else:               phase_mul = 0.5  # hard
                        drift = get_movement(msv) * speed_factor * phase_mul
                        cur_pos = max(1, cur_pos - drift)

                    pi = int(round(cur_pos))
                    if pi <= st.session_state.ctr_df["Position"].max():
                        base_ctr = get_ctr_for_position(pi)
                        if scenario=="High":
                            ctr = base_ctr
                        elif scenario=="Medium":
                            ctr = base_ctr * (1 - 0.05*st.session_state.paid_listings.get(proj,0))
                            if pi==1 and has_aio: ctr = aio_ctr
                            if pi==1 and has_fs:  ctr = fs_ctr
                        else:
                            ctr = base_ctr * 0.8 * (1 - 0.05*st.session_state.paid_listings.get(proj,0))
                            if pi==1 and has_aio: ctr = aio_ctr*0.8
                            if pi==1 and has_fs:  ctr = fs_ctr*0.8

                        adj = st.session_state.seasonality_df.loc[
                            st.session_state.seasonality_df["Month"]==date.strftime("%B"),
                            "Adjustment (%)"
                        ].iloc[0]

                        raw_clicks      = (ctr/100) * msv
                        adjusted_clicks = raw_clicks * (1 + adj/100)

                rec.append({
                    "Scenario": scenario,
                    "Project":   proj,
                    "URL":       url,
                    "Keyword":   kw,
                    "Date":      date,
                    "Raw Clicks":      round(raw_clicks),
                    "Adjusted Clicks": round(adjusted_clicks),
                    "Position": cur_pos
                })

    rec_df  = pd.DataFrame(rec)
    st.session_state.rec_df = rec_df  # Store rec_df in session state for later use

    plot_df = (rec_df
               .groupby(["Scenario","Date"])["Adjusted Clicks"]
               .sum().reset_index().rename(columns={"Adjusted Clicks":"Clicks"}))

    # --- KPI Pickers & Charts ---
    st.subheader("Forecast KPIs")
    c1, c2 = st.columns(2)
    min_d, max_d = plot_df["Date"].min().date(), plot_df["Date"].max().date()
    with c1:
        start_date = st.date_input("Start Date", min_value=min_d, max_value=max_d, value=min_d)
    with c2:
        end_date   = st.date_input("End Date",   min_value=min_d, max_value=max_d, value=max_d)
    if end_date < start_date:
        st.error("End date must be on or after start date.")
    else:
        mask   = (plot_df["Date"].dt.date>=start_date)&(plot_df["Date"].dt.date<=end_date)
        totals = plot_df[mask].groupby("Scenario")["Clicks"].sum().to_dict()
        m1,m2,m3 = st.columns(3)
        m1.metric("High Forecast",   totals.get("High",0))
        m2.metric("Medium Forecast", totals.get("Medium",0))
        m3.metric("Low Forecast",    totals.get("Low",0))

        fig = px.line(plot_df[mask], x="Date", y="Clicks", color="Scenario", markers=True)
        fig.update_layout(title="Projected Traffic Scenarios Over Time")
        st.plotly_chart(fig, use_container_width=True)

        summ = plot_df[mask].copy()
        summ["Month"]   = summ["Date"].dt.strftime("%b %Y")
        summ["SortKey"] = summ["Date"]
        pivot = (summ.pivot_table(index=["Month","SortKey"], columns="Scenario", values="Clicks", aggfunc="sum")
                 .reset_index().sort_values("SortKey").drop(columns="SortKey"))
        pivot.columns.name = None
        st.subheader("Forecast Summary by Scenario")
        st.dataframe(pivot, use_container_width=True, hide_index=True)

# --- Keyword Rank Tables Tab ---
if tab_selection == "Keyword Rank Tables":
    st.title("Keyword Rank Tables")
    
    # Retrieve the stored rec_df from session state
    rec_df = st.session_state.rec_df

    # Show the positions over time for each keyword based on the forecast scenarios.
    rank_table = rec_df.pivot_table(index=["Project", "Keyword", "Scenario"], columns="Date", values="Position", aggfunc="mean")
    st.subheader("Keyword Rank Progression")
    st.dataframe(rank_table, use_container_width=True)

# --- Project Summary Tab ---
if tab_selection == "Project Summary":
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run forecast first.")
    else:
        st.data_editor(
            st.session_state.launch_month_df.reset_index(drop=True),
            column_config={"Launch Date": st.column_config.DateColumn("Launch Date")},
            use_container_width=True, hide_index=True, key="proj_summary"
        )
