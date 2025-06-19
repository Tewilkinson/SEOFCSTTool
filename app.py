import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
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

# --- Sidebar Controls ---
with st.sidebar:
    st.subheader("Download Template")
    st.download_button("Download Template CSV", data=create_template(), file_name="forecast_template.csv")
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
            st.session_state.paid_listings[p] = st.slider(
                f"{p} Paid Listings", 0, 10, st.session_state.paid_listings.get(p,2), key=f"paid_{p}"
            )

# --- Tabs ---
tabs = st.tabs(["Upload & Forecast","Project Summary"])

# --- Upload & Forecast Tab ---
with tabs[0]:
    st.title("Upload & Forecast")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if not uploaded:
        st.info("Upload a file to begin.")
        st.stop()
    df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
    st.session_state.df = df.copy()
    projs = df['Project'].dropna().unique().tolist()
    if set(projs) != set(st.session_state.launch_month_df['Project']):
        st.session_state.launch_month_df = pd.DataFrame({"Project": projs, "Launch Date": [datetime.today().replace(day=1)] * len(projs)})
        st.session_state.paid_listings = {p:2 for p in projs}
    sel = st.selectbox("Select Project", ["All"] + projs)
    filtered = df if sel=="All" else df[df['Project']==sel]

    # Build scenario records
    base = datetime.today().replace(day=1)
    launch_map = {k: pd.to_datetime(v) for k,v in st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict().items()}
    rec = []
    for scenario in ["High","Medium","Low"]:
        for _, r in filtered.iterrows():
            project,msv,pos,url = r['Project'], r['MSV'], r['Current Position'], r['Current URL']
            has_aio = str(r['AI Overview']).lower()=='yes'
            has_fs = str(r['Featured Snippet']).lower()=='yes'
            launch = launch_map.get(project,base)
            cur_pos = pos
            for m in range(1,25):
                date = base + DateOffset(months=m-1)
                clicks = 0
                if date >= launch:
                    if m>1:
                        cur_pos = max(1, cur_pos - get_movement(msv))
                    pi = int(round(cur_pos))
                    base_ctr = get_ctr_for_position(pi)
                    if scenario=="High": ctr = base_ctr
                    elif scenario=="Medium":
                        ctr = base_ctr*(1-0.05*st.session_state.paid_listings.get(project,0))
                        if pi==1 and has_aio: ctr = aio_ctr
                        if pi==1 and has_fs: ctr = fs_ctr
                    else:
                        ctr = base_ctr*0.8*(1-0.05*st.session_state.paid_listings.get(project,0))
                        if pi==1 and has_aio: ctr = aio_ctr*0.8
                        if pi==1 and has_fs: ctr = fs_ctr*0.8
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==date.strftime('%B'),'Adjustment (%)'
                    ].iloc[0]
                    clicks = (ctr/100)*msv*(1+adj/100)
                rec.append({"Scenario":scenario,"Project":project,"URL":url,"Date":date,"Clicks":round(clicks)})
    rec_df = pd.DataFrame(rec)
    plot_df = rec_df.groupby(["Scenario","Date"])['Clicks'].sum().reset_index()

    # KPI Date Pickers
    st.subheader("Forecast KPIs")
    c_start, c_end = st.columns(2)
    min_date = plot_df['Date'].min().date()
    max_date = plot_df['Date'].max().date()
    with c_start:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with c_end:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    if end_date < start_date:
        st.error("End date must be on or after start date.")
    else:
        mask = (plot_df['Date'].dt.date >= start_date) & (plot_df['Date'].dt.date <= end_date)
        kpi_vals = plot_df[mask].groupby('Scenario')['Clicks'].sum().to_dict()
        k1,k2,k3 = st.columns(3)
        k1.metric("High Forecast", kpi_vals.get("High",0))
        k2.metric("Medium Forecast", kpi_vals.get("Medium",0))
        k3.metric("Low Forecast", kpi_vals.get("Low",0))

        # Line chart with title
        st.plotly_chart(
            px.line(plot_df[mask], x='Date', y='Clicks', color='Scenario', markers=True)
            .update_layout(title="Projected Traffic Scenarios Over Time"),
            use_container_width=True
        )

        # Summary table pivoted
        summary = plot_df[mask].copy()
        summary['Month'] = summary['Date'].dt.strftime('%b %Y')
        summary['SortKey'] = summary['Date']
        pivot = summary.pivot_table(index=['Month','SortKey'], columns='Scenario', values='Clicks', aggfunc='sum').reset_index()
        pivot = pivot.sort_values('SortKey').drop(columns='SortKey')
        pivot.columns.name = None
        st.subheader("Forecast Summary by Scenario")
        st.dataframe(pivot, use_container_width=True)

        # Combo chart: Medium clicks vs keyword count
        medium = rec_df[(rec_df['Scenario']=='Medium') & mask].groupby('Project')['Clicks'].sum().reset_index()
        keyword_counts = filtered.groupby('Project')['Keyword'].count().reset_index(name='Keyword Count')
        combo = medium.merge(keyword_counts, on='Project', how='left').fillna(0)
        fig2 = go.Figure()
        fig2.add_bar(x=combo['Project'], y=combo['Clicks'], name='Medium Clicks')
        fig2.add_scatter(x=combo['Project'], y=combo['Keyword Count'], mode='lines+markers', name='Keyword Count', yaxis='y2')
        fig2.update_layout(
            title="Medium Clicks vs Keyword Count by Project",
            yaxis=dict(title='Medium Clicks'),
            yaxis2=dict(overlaying='y', side='right', title='Keyword Count'),
            legend=dict(x=0.7, y=1.1)
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Optimisation actions summary with action type and weighted average rank
        month3_date = base + DateOffset(months=2)
        month6_date = base + DateOffset(months=5)
        actions = rec_df[rec_df['Scenario']=='Medium']
        # 3-month and 6-month clicks
        actions3 = actions[actions['Date']==month3_date].groupby(['Project','URL'])['Clicks']
            .sum().reset_index(name='3-Month Clicks')
        actions6 = actions[actions['Date']==month6_date].groupby(['Project','URL'])['Clicks']
            .sum().reset_index(name='6-Month Clicks')
        actions_summary = pd.merge(actions3, actions6, on=['Project','URL'], how='outer').fillna(0)
        # Weighted average current rank per URL
        rank_df = filtered.groupby(['Project','Current URL']).apply(
            lambda d: (d['Current Position'] * d['MSV']).sum() / d['MSV'].sum()
        ).reset_index(name='Weighted Avg Rank')
        actions_summary = actions_summary.merge(
            rank_df, left_on=['Project','URL'], right_on=['Project','Current URL'], how='left'
        ).drop(columns='Current URL')
        # Action type: optimisation if URL exists, else net new page
        actions_summary['Action'] = actions_summary['URL'].apply(
            lambda u: 'Optimisation' if pd.notna(u) and u != '' else 'Net New Page'
        )
        # Reorder and display
        cols = ['Project','Action','URL','Weighted Avg Rank','3-Month Clicks','6-Month Clicks']
        st.subheader("Optimisation Actions Summary")
        st.dataframe(actions_summary[cols], use_container_width=True)

# --- Project Summary Tab ---
with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Upload and forecast first.")
    else:
        st.session_state.launch_month_df['Launch Date'] = pd.to_datetime(st.session_state.launch_month_df['Launch Date'])
        rows = []
        for proj,ldt in st.session_state.launch_month_df.set_index('Project')['Launch Date'].items():
            row = {'Project':proj,'Launch Date':ldt}
            subset = st.session_state.df[st.session_state.df['Project']==proj]
            for m in [3,6,9,12]:
                tot = 0
                for _, r in subset.iterrows():
                    # same calc as above
                    pass
                row[f"{m}-Month Clicks"] = tot
            rows.append(row)
        st.data_editor(pd.DataFrame(rows), column_config={'Launch Date':st.column_config.DateColumn('Launch Date')}, use_container_width=True, key='proj_summary')
