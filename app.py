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
    ("ctr_df", pd.DataFrame({"Position": list(range(1,11)), "CTR": [32,25,18,12,10,8,6,4,2,1]})),
    ("seasonality_df", pd.DataFrame({
        "Month": ["January","February","March","April","May","June","July","August","September","October","November","December"],
        "Adjustment (%)": [0,0,0,0,0,-20,0,0,0,0,0,0]
    })),
    ("paid_listings", {}),
    ("df", pd.DataFrame()),
    ("launch_month_df", pd.DataFrame(columns=["Project","Launch Date"]))
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
    st.download_button("Download Template CSV", data=create_template(), file_name="forecast_template.csv")

    st.subheader("Upload Data")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"], key="file_uploader")
    if uploaded:
        st.session_state.uploaded_file = uploaded

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

    fs_ctr  = st.number_input("Featured Snippet CTR (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)",      min_value=0.0, max_value=100.0, value=12.0)

    st.subheader("Avg. Paid Listings per Project")
    if not st.session_state.launch_month_df.empty:
        proj = st.selectbox("Project for Paid Listings", st.session_state.launch_month_df["Project"], key="paid_sel")
        st.session_state.paid_listings[proj] = st.slider(f"{proj} Paid Listings", 0, 10, st.session_state.paid_listings.get(proj,2))

    st.subheader("Ranking Speed")
    speed_factor = st.slider("Speed multiplier", min_value=0.1, max_value=5.0, value=1.0, step=0.1)

# --- Forecast Function ---
def forecast_data():
    df = st.session_state.df
    base = datetime.today().replace(day=1)
    launch_map = st.session_state.launch_month_df.set_index("Project")["Launch Date"].to_dict()
    scen_map = {"High":1.5, "Medium":1.0, "Low":0.5}
    rec = []
    for scen in ["High","Medium","Low"]:
        sm = scen_map[scen]
        for _, r in df.iterrows():
            proj, msv, pos = r["Project"], r["MSV"], r["Current Position"]
            fs = (r.get("Featured Snippet","") == "Yes")
            aio = (r.get("AI Overview","") == "Yes")
            launch = launch_map.get(proj, base)
            cp = pos
            for m in range(1, 25):
                date = base + DateOffset(months=m-1)
                raw, adj = 0, 0
                if date >= launch:
                    if m == 1 and cp > 15:
                        cp = 15
                    elif m > 1:
                        phase = 3 if cp > 15 else 1 if cp > 6 else 0.5
                        cp = max(1, cp - get_movement(msv) * speed_factor * phase * sm)
                    pi = int(round(cp))
                    if pi <= st.session_state.ctr_df["Position"].max():
                        ctr = get_ctr_for_position(pi)
                        if scen == "Medium":
                            ctr *= (1 - 0.05 * st.session_state.paid_listings.get(proj, 0))
                            if pi == 1 and aio: ctr = aio_ctr
                            if pi == 1 and fs: ctr = fs_ctr
                        elif scen == "Low":
                            ctr *= 0.8
                        adj_pct = st.session_state.seasonality_df.loc[
                            st.session_state.seasonality_df["Month"] == date.strftime("%B"),
                            "Adjustment (%)"
                        ].iloc[0]
                        raw = (ctr / 100) * msv
                        adj = raw * (1 + adj_pct / 100)
                rec.append({
                    "Scenario": scen,
                    "Project": proj,
                    "Keyword": r["Keyword"],
                    "Date": date,
                    "Raw": round(raw),
                    "Clicks": round(adj),
                    "Position": cp
                })
    return pd.DataFrame(rec)

# --- Tabs Layout ---
tabs = st.tabs(["Dashboard", "Keyword Rank Tables", "Project Summary"])

# --- Dashboard Tab ---
with tabs[0]:
    st.title("SEO Forecast Dashboard")
    if "uploaded_file" not in st.session_state:
        st.info("Upload file in sidebar to begin.")
    else:
        if st.session_state.df.empty:
            f = st.session_state.uploaded_file
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            df["MSV"] = pd.to_numeric(df["MSV"], errors='coerce').fillna(0)
            df["Current Position"] = pd.to_numeric(df["Current Position"], errors='coerce').fillna(0)
            st.session_state.df = df
            projects = df["Project"].unique()
            st.session_state.launch_month_df = pd.DataFrame({
                "Project": projects,
                "Launch Date": [datetime.today().replace(day=1)] * len(projects)
            })
        rec_df = forecast_data()
        plot_df = rec_df.groupby(["Scenario", "Date"])["Clicks"].sum().reset_index()
        dmin, dmax = plot_df["Date"].min().date(), plot_df["Date"].max().date()
        c1, c2 = st.columns(2)
        start = c1.date_input("Start Date", dmin, min_value=dmin, max_value=dmax)
        end = c2.date_input("End Date", dmax, min_value=dmin, max_value=dmax)
        mask = (plot_df["Date"].dt.date >= start) & (plot_df["Date"].dt.date <= end)
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
    rec_df = forecast_data()
    rec_df['MonthPeriod'] = rec_df['Date'].dt.to_period('M')
    rec_df['Month'] = rec_df['MonthPeriod'].dt.to_timestamp()
    scen_sel = st.selectbox("Select Scenario", rec_df['Scenario'].unique())
    filtered = rec_df[rec_df['Scenario'] == scen_sel]
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
    edited = st.data_editor(
        st.session_state.launch_month_df,
        column_config={"Launch Date": st.column_config.DateColumn()},
        hide_index=True,
        use_container_width=True
    )
    st.session_state.launch_month_df = edited
    rec_df = forecast_data()
    med = rec_df[rec_df['Scenario'] == 'Medium'].copy()
    med = med.sort_values(['Project', 'Date'])
    med['MonthIndex'] = med.groupby('Project').cumcount() + 1
    proj_sums = med.groupby(['Project', 'MonthIndex'])['Clicks'].sum().unstack(fill_value=0)
    cum3 = proj_sums.loc[:, proj_sums.columns <= 3].sum(axis=1).rename('3mo Clicks')
    cum6 = proj_sums.loc[:, proj_sums.columns <= 6].sum(axis=1).rename('6mo Clicks')
    cum9 = proj_sums.loc[:, proj_sums.columns <= 9].sum(axis=1).rename('9mo Clicks')
    summary = edited.set_index('Project').join(pd.concat([cum3, cum6, cum9], axis=1)).reset_index()
    summary['Launch Date'] = pd.to_datetime(summary['Launch Date']).dt.date
    st.dataframe(summary, use_container_width=True)
