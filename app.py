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
    ("launch_month_df", pd.DataFrame(columns=["Project","Launch Date"])),
    ("rec_df", pd.DataFrame()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- Helpers ---
def get_movement(msv):
    try:
        m = float(msv)
    except:
        m = 0.0
    # higher MSV harder to move (lower movement)
    if m <= 500:
        return 1.5
    if m <= 2000:
        return 1.0
    if m <= 10000:
        return 0.75
    return 0.5  # hardest for msv > 10000


def get_ctr_for_position(pos):
    df = st.session_state.ctr_df
    max_pos = df["Position"].max()
    return float(df.loc[df["Position"] == pos, "CTR"].iloc[0]) if pos <= max_pos else 0.0

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

# --- Tab Navigation ---
tab_selection = st.radio("Select a Tab", ["Dashboard", "Keyword Rank Tables", "Project Summary"])

# --- Dashboard Tab ---
if tab_selection == "Dashboard":
    st.title("SEO Keyword Forecast Tool")
    if "uploaded_file" not in st.session_state:
        st.info("Please upload a CSV or Excel file to start forecasting.")
        st.stop()

    # cache read
    if st.session_state.df.empty:
        file = st.session_state.uploaded_file
        df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
        df["MSV"] = pd.to_numeric(df.get("MSV",0), errors="coerce").fillna(0)
        df["Current Position"] = pd.to_numeric(df.get("Current Position",0), errors="coerce").fillna(0)
        st.session_state.df = df.copy()

    df = st.session_state.df
    projects = df["Project"].dropna().unique().tolist()
    if set(projects) != set(st.session_state.launch_month_df["Project"]):
        st.session_state.launch_month_df = pd.DataFrame({
            "Project": projects,
            "Launch Date": [datetime.today().replace(day=1)] * len(projects)
        })
        st.session_state.paid_listings = {p:2 for p in projects}

    selected = st.selectbox("Select Project", ["All"] + projects)
    filtered = df if selected=="All" else df[df["Project"]==selected]

    base = datetime.today().replace(day=1)
    launch_map = st.session_state.launch_month_df.set_index("Project")["Launch Date"].to_dict()
    scenario_speed_map = {"High":1.5, "Medium":1.0, "Low":0.5}

    # forecast once
    if st.session_state.rec_df.empty:
        rec = []
        for scenario in ["High","Medium","Low"]:
            scen_mul = scenario_speed_map[scenario]
            for _, r in filtered.iterrows():
                proj, msv, pos = r["Project"], r["MSV"], r["Current Position"]
                url = r.get("Current URL", "")
                has_aio = str(r["AI Overview"]).lower()=="yes"
                has_fs  = str(r["Featured Snippet"]).lower()=="yes"
                launch  = launch_map.get(proj, base)
                cur_pos = pos
                for i in range(1,25):
                    date = base + DateOffset(months=i-1)
                    raw_clicks = adjusted_clicks = 0
                    if date >= launch:
                        if i == 1 and cur_pos > 15:
                            cur_pos = 15
                        elif i > 1:
                            if cur_pos > 15: phase_mul=3.0
                            elif cur_pos > 6: phase_mul=1.0
                            else: phase_mul=0.5
                            drift = get_movement(msv)*speed_factor*phase_mul*scen_mul
                            cur_pos = max(1, cur_pos-drift)
                        pi = int(round(cur_pos))
                        if pi <= st.session_state.ctr_df["Position"].max():
                            base_ctr = get_ctr_for_position(pi)
                            if scenario=="High": ctr=base_ctr
                            elif scenario=="Medium":
                                ctr = base_ctr*(1-0.05*st.session_state.paid_listings.get(proj,0))
                                if pi==1 and has_aio: ctr=aio_ctr
                                if pi==1 and has_fs: ctr=fs_ctr
                            else:
                                ctr = base_ctr*0.8*(1-0.05*st.session_state.paid_listings.get(proj,0))
                                if pi==1 and has_aio: ctr=aio_ctr*0.8
                                if pi==1 and has_fs: ctr=fs_ctr*0.8
                            adj = st.session_state.seasonality_df.loc[
                                st.session_state.seasonality_df["Month"]==date.strftime("%B"),
                                "Adjustment (%)"
                            ].iloc[0]
                            raw_clicks=(ctr/100)*msv
                            adjusted_clicks=raw_clicks*(1+adj/100)
                    rec.append({
                        "Scenario":scenario,
                        "Project":proj,
                        "Date":date,
                        "Adjusted Clicks":adjusted_clicks
                    })
        # keep only for summary, store all separately
        st.session_state.rec_df = pd.DataFrame(rec)

    # plot unchanged
    rec_df = st.session_state.rec_df
    plot_df = rec_df.groupby(["Scenario","Date"])['Adjusted Clicks'].sum().reset_index()
    # ... existing KPI & chart code ...  (unchanged for brevity)

# --- Keyword Rank Tables Tab ---
if tab_selection == "Keyword Rank Tables":
    st.title("Keyword Rank Tables")
    full = st.session_state.rec_df.copy()
    full['Period'] = full['Date'].dt.to_period('M')
    full['Month'] = full['Period'].dt.to_timestamp()
    scenario_selected = st.selectbox("Select Scenario", full['Scenario'].unique(), key="kw_scenario")
    filtered = full[full['Scenario']==scenario_selected]
    rank_tbl = filtered.pivot_table(index=["Project","Keyword"], columns="Month", values="Position", aggfunc=lambda x: int(round(x)))
    rank_tbl = rank_tbl.sort_index(axis=1)
    rank_tbl.columns = [dt.strftime('%b %Y') for dt in rank_tbl.columns]
    st.subheader("Keyword Rank Progression")
    st.dataframe(rank_tbl, use_container_width=True)

# --- Project Summary Tab ---
if tab_selection == "Project Summary":
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run forecast first.")
    else:
        # editable launch dates
        edited = st.data_editor(
            st.session_state.launch_month_df.reset_index(drop=True),
            column_config={"Launch Date": st.column_config.DateColumn("Launch Date")},
            use_container_width=True, hide_index=True, key="proj_summary_edit"
        )
        # calculate click growth for medium scenario
        med = st.session_state.rec_df[st.session_state.rec_df['Scenario']=='Medium']
        # month index relative to first date per project
        med['MonthIndex'] = ((med['Date'].dt.year - med['Date'].dt.year.min())*12 + med['Date'].dt.month - med['Date'].dt.month.min()) + 1
        sums = med.groupby(['Project','MonthIndex'])['Adjusted Clicks'].sum().unstack(fill_value=0)
        # growth = clicks at index X minus index 1
        growth_3 = (sums.get(3,0) - sums.get(1,0)).rename('3mo Growth')
        growth_6 = (sums.get(6,0) - sums.get(1,0)).rename('6mo Growth')
        growth_9 = (sums.get(9,0) - sums.get(1,0)).rename('9mo Growth')
        summary = edited.set_index('Project').join(pd.concat([growth_3, growth_6, growth_9], axis=1)).reset_index()
        st.subheader("Click Growth (Medium Scenario)")
        st.dataframe(summary, use_container_width=True)
