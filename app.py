import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas import DateOffset

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")


# --- Initialize session state ---
if "ctr_df" not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32,25,18,12,10,8,6,4,2,1]})
if "seasonality_df" not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        "Month": ["January","February","March","April","May","June","July","August","September","October","November","December"],
        "Adjustment (%)": [0,0,0,0,0,-20,0,0,0,0,0,0]
    })
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project","Launch Date"])

# --- Helper functions ---
def get_movement(msv):
    if msv <= 500: return 1.5
    if msv <= 2000: return 1.0
    if msv <= 10000: return 0.5
    return 0.25

def get_ctr_for_position(pos):
    ctrs = st.session_state.ctr_df
    return float(ctrs.loc[ctrs['Position']==pos,'CTR'].iloc[0]) if pos in ctrs['Position'].tolist() else float(ctrs['CTR'].iloc[-1])

# --- Sidebar Controls (Sticky) ---
with st.sidebar:
    st.header("CTR Controls")
    st.subheader("CTR by Position")
    st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)", min_value=0, max_value=100)},
        use_container_width=True,
        key="ctr_editor"
    )
    st.subheader("Seasonality by Month")
    st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100, max_value=100)},
        use_container_width=True,
        key="season_editor"
    )
    fs_ctr = st.number_input("Featured Snippet CTR (%)", 0.0, 100.0, value=18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)", 0.0, 100.0, value=12.0)
    st.subheader("Avg. Paid Listings per Project")
    for p in (st.session_state.launch_month_df['Project'] if not st.session_state.launch_month_df.empty else []):
        st.session_state.paid_listings[p] = st.slider(
            f"{p} Paid Listings", 0, 10, st.session_state.paid_listings.get(p,2), key=f"paid_{p}"
        )

# --- Tabs Layout ---
tabs = st.tabs(["Upload & Forecast", "Project Summary"])

# --- Upload & Forecast Tab ---
with tabs[0]:
    st.title("Upload & Forecast")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
        st.session_state.df = df.copy()
        projs = df['Project'].dropna().unique().tolist()
        if set(projs) != set(st.session_state.launch_month_df['Project']):
            st.session_state.launch_month_df = pd.DataFrame({
                "Project": projs,
                "Launch Date": [datetime.today().replace(day=1)] * len(projs)
            })
            st.session_state.paid_listings = {p:2 for p in projs}
        sel = st.selectbox("Select Project", ["All"] + projs)
        filtered = df if sel == "All" else df[df['Project']==sel]

        # Scenario plotting
        base = datetime.today().replace(day=1)
        launch_map = {k: pd.to_datetime(v) for k,v in st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict().items()}
        rec = []
        for scenario in ["High","Medium","Low"]:
            for _,r in filtered.iterrows():
                project,msv,pos = r['Project'],r['MSV'],r['Current Position']
                has_aio = str(r['AI Overview']).lower() == 'yes'
                has_fs = str(r['Featured Snippet']).lower() == 'yes'
                launch = launch_map.get(project, base)
                cur_pos = pos
                for m in range(1,25):
                    date = base + DateOffset(months=m-1)
                    clicks = 0
                    if date >= launch:
                        if m>1:
                            cur_pos = max(1, cur_pos - get_movement(msv))
                        pi = int(round(cur_pos))
                        base_ctr = get_ctr_for_position(pi)
                        if scenario == "High":
                            ctr = base_ctr
                        elif scenario == "Medium":
                            ctr = base_ctr * (1-0.05*st.session_state.paid_listings.get(project,0))
                            if pi==1 and has_aio: ctr = aio_ctr
                            if pi==1 and has_fs: ctr = fs_ctr
                        else:
                            ctr = base_ctr * 0.8 * (1-0.05*st.session_state.paid_listings.get(project,0))
                            if pi==1 and has_aio: ctr = aio_ctr*0.8
                            if pi==1 and has_fs: ctr = fs_ctr*0.8
                        adj = st.session_state.seasonality_df.loc[
                            st.session_state.seasonality_df['Month']==date.strftime('%B'),'Adjustment (%)'
                        ].iloc[0]
                        clicks = (ctr/100) * msv * (1+adj/100)
                    rec.append({"Scenario":scenario,"Date":date,"Clicks":round(clicks)})
        # Fixed syntax: removed extra parenthesis
        plot_df = pd.DataFrame(rec).groupby(["Scenario","Date"])['Clicks'].sum().reset_index()

        st.subheader("Projected Traffic Scenarios")
        fig = px.line(plot_df, x='Date', y='Clicks', color='Scenario', markers=True)
        fig.update_xaxes(tickformat='%b %Y')
        st.plotly_chart(fig, use_container_width=True)

        med = plot_df[plot_df['Scenario']=='Medium'].groupby('Date')['Clicks'].sum().reset_index()
        med['Month'] = med['Date'].dt.strftime('%b %Y')
        st.subheader("Forecast Summary (Medium)")
        st.dataframe(med[['Month','Clicks']], use_container_width=True)

        st.subheader("Keyword Inputs")
        st.dataframe(filtered, use_container_width=True)
    else:
        st.info("Upload a file to begin.")

# --- Project Summary Tab ---
with tabs[1]:
    st.header("Project Launch & Summary")
    if st.session_state.df.empty:
        st.info("Upload and run forecast first.")
    else:
        st.session_state.launch_month_df['Launch Date'] = pd.to_datetime(st.session_state.launch_month_df['Launch Date'])
        rows=[]
        for project,launch_dt in st.session_state.launch_month_df.set_index('Project')['Launch Date'].items():
            row = {"Project":project,"Launch Date":launch_dt}
            subset = st.session_state.df[st.session_state.df['Project']==project]
            for m in [3,6,9,12]:
                tot=0
                for _,r in subset.iterrows():
                    pos,msv = r['Current Position'],r['MSV']
                    has_aio = str(r['AI Overview']).lower()=='yes'
                    has_fs = str(r['Featured Snippet']).lower()=='yes'
                    cur=pos
                    for i in range(1,m+1):
                        if i>1: cur = max(1, cur - get_movement(msv))
                    pi=int(round(cur))
                    base_ctr=get_ctr_for_position(pi)
                    ctr = base_ctr * (1-0.05*st.session_state.paid_listings.get(project,0))
                    if pi==1 and has_aio: ctr=aio_ctr
                    if pi==1 and has_fs: ctr=fs_ctr
                    adj_month=(launch_dt + DateOffset(months=m-1)).strftime('%B')
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==adj_month,'Adjustment (%)'
                    ].iloc[0]
                    tot += (ctr/100)*msv*(1+adj/100)
                row[f"{m}-Month Clicks"] = round(tot)
            rows.append(row)
        summary_df = pd.DataFrame(rows)
        edited = st.data_editor(
            summary_df,
            column_config={ 'Launch Date': st.column_config.DateColumn('Launch Date') },
            use_container_width=True,
            key='final_summary'
        )
        st.session_state.launch_month_df = edited[['Project','Launch Date']].copy()
