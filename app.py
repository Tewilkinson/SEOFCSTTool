import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas import DateOffset

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")

# --- Initialize session state ---
for key, df in {
    "ctr_df": pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32,25,18,12,10,8,6,4,2,1]}),
    "seasonality_df": pd.DataFrame({
        "Month": ["January","February","March","April","May","June","July","August","September","October","November","December"],
        "Adjustment (%)": [0,0,0,0,0,-20,0,0,0,0,0,0]
    }),
}.items():
    if key not in st.session_state:
        st.session_state[key] = df.copy()
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project","Launch Date"])
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()

# --- Helper functions ---
def get_movement(msv):
    if msv <= 500: return 1.5
    if msv <= 2000: return 1.0
    if msv <= 10000: return 0.5
    return 0.25

def get_ctr_for_position(pos):
    ctrs = st.session_state.ctr_df
    return float(ctrs.loc[ctrs['Position']==pos,'CTR'].iloc[0]) if pos in ctrs['Position'].tolist() else float(ctrs['CTR'].iloc[-1])

# --- Sidebar Controls ---
with st.sidebar:
    st.header("CTR Controls")
    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)", min_value=0, max_value=100)},
        use_container_width=True,
        key="ctr_editor"
    )
    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100, max_value=100)},
        use_container_width=True,
        key="season_editor"
    )
    fs_ctr = st.number_input("Featured Snippet CTR (%)", 0.0, 100.0, value=18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)", 0.0, 100.0, value=12.0)
    st.subheader("Avg. Paid Listings per Project")
    if not st.session_state.launch_month_df.empty:
        for p in st.session_state.launch_month_df['Project']:
            st.session_state.paid_listings[p] = st.slider(f"{p} Paid Listings", 0, 10, 2, key=f"paid_{p}")

# --- Tabs Layout ---
tabs = st.tabs(["Upload & Forecast", "Project Summary"])

# --- Upload & Forecast Tab ---
with tabs[0]:
    st.title("SEO Forecast Tool")
    # Download template
    st.download_button(
        "Download Template CSV",
        data=pd.DataFrame({
            "Project":["Example"],
            "Keyword":["shoes for men"],
            "MSV":[12100],
            "Current Position":[8],
            "AI Overview":["Yes"],
            "Featured Snippet":["No"],
            "Current URL":["https://example.com"]
        }).to_csv(index=False).encode('utf-8'),
        file_name="template.csv"
    )

    # Upload and display input
    uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
        st.session_state.df = df.copy()
        projs = df['Project'].dropna().unique().tolist()
        # initialize launch dates if projects changed
        if set(projs) != set(st.session_state.launch_month_df['Project']):
            st.session_state.launch_month_df = pd.DataFrame({
                "Project": projs,
                "Launch Date": [datetime.today().replace(day=1)]*len(projs)
            })
        selected = st.selectbox("Select Project", ["All"]+projs)
        filtered = df if selected == "All" else df[df['Project']==selected]
        st.subheader("Keyword Inputs")
        st.dataframe(filtered, use_container_width=True)

        # compute and display chart
        rec = []
        base = datetime.today().replace(day=1)
        launch_map = st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict()
        for _, r in filtered.iterrows():
            project = r['Project']
            msv = r['MSV']
            cur_pos = r['Current Position']
            has_aio = str(r['AI Overview']).strip().lower() == 'yes'
            has_fs = str(r['Featured Snippet']).strip().lower() == 'yes'
            launch = launch_map.get(project, base)
            pos = cur_pos
            for m in range(1, 25):
                date = base + DateOffset(months=m-1)
                label = date.strftime('%b %Y')
                if date < launch:
                    clicks = 0
                else:
                    if m > 1:
                        pos = max(1, pos - get_movement(msv))
                    pi = int(round(pos))
                    if pi == 1 and has_aio:
                        ctr = aio_ctr
                    elif pi == 1 and has_fs:
                        ctr = fs_ctr
                    else:
                        ctr = get_ctr_for_position(pi)
                    avg_paid = st.session_state.paid_listings.get(project, 0)
                    ctr = max(0, ctr * (1 - 0.05 * avg_paid))
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == date.strftime('%B'),
                        'Adjustment (%)'
                    ].iloc[0]
                    clicks = (ctr/100) * msv * (1 + adj/100)
                rec.append({"Month": label, "Clicks": round(clicks)})
        summary = pd.DataFrame(rec).groupby('Month', sort=False).sum().reset_index()
        summary['Date'] = pd.to_datetime(summary['Month'], format='%b %Y')

        st.subheader("Projected Traffic Over Time")
        fig = px.line(summary.sort_values('Date'), x='Date', y='Clicks', markers=True)
        fig.update_xaxes(tickformat='%b %Y')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Forecast Summary Table")
        st.dataframe(summary[['Month','Clicks']], use_container_width=True)

# --- Project Summary Tab ---
with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run forecast first in the Upload & Forecast tab.")
    else:
        # build summary rows
        rows = []
        launch_map = st.session_state.launch_month_df.set_index('Project')['Launch Date']
        for project, launch_dt in launch_map.iteritems():
            launch_date = pd.to_datetime(launch_dt)
            row = {"Project": project, "Launch Date": launch_date.strftime('%b %Y')}
            subset = st.session_state.df[st.session_state.df['Project']==project]
            for m in [3,6,9,12]:
                total_clicks = 0
                for _, r in subset.iterrows():
                    pos = r['Current Position']
                    msv = r['MSV']
                    has_aio = str(r['AI Overview']).strip().lower() == 'yes'
                    has_fs = str(r['Featured Snippet']).strip().lower() == 'yes'
                    p = pos
                    for _ in range(1, m+1):
                        if _ > 1:
                            p = max(1, p - get_movement(msv))
                    pi = int(round(p))
                    if pi == 1 and has_aio:
                        ctr = aio_ctr
                    elif pi == 1 and has_fs:
                        ctr = fs_ctr
                    else:
                        ctr = get_ctr_for_position(pi)
                    avg_paid = st.session_state.paid_listings.get(project, 0)
                    ctr = max(0, ctr * (1 - 0.05 * avg_paid))
                    adj_month = (launch_date + DateOffset(months=m-1)).strftime('%B')
                    seasonal_adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == adj_month,
                        'Adjustment (%)'
                    ].iloc[0]
                    total_clicks += (ctr/100) * msv * (1 + seasonal_adj/100)
                row[f"{m}-Month Clicks"] = round(total_clicks)
            rows.append(row)
        summary_df = pd.DataFrame(rows)
        st.data_editor(
            summary_df,
            column_config={'Launch Date': st.column_config.DateColumn('Launch Date')},
            use_container_width=True,
            key='final_summary'
        )
