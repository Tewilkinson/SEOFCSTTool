import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
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

# --- Slugify for recommended URLs ---
def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", '-', text)
    return text.strip('-')

# --- Session State Init ---
if "ctr_df" not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({"Position": list(range(1,11)), "CTR": [32,25,18,12,10,8,6,4,2,1]})
if "seasonality_df" not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        "Month": ["January","February","March","April","May","June","July","August","September","October","November","December"],
        "Adjustment (%)": [0]*5 + [-20] + [0]*6
    })
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project","Launch Date"])

# --- Helpers ---
def get_movement(msv):
    if msv <= 500: return 1.5
    if msv <= 2000: return 1.0
    if msv <= 10000: return 0.5
    return 0.25

def get_ctr_for_position(pos):
    df = st.session_state.ctr_df
    return float(df.loc[df['Position']==pos, 'CTR'].iloc[0]) if pos in df['Position'].tolist() else float(df['CTR'].iloc[-1])

# --- Sidebar ---
with st.sidebar:
    st.subheader("Download Template")
    st.download_button("Download Template CSV", data=create_template(), file_name="forecast_template.csv")
    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)",0,100)},
        use_container_width=True,
        key="ctr_editor"
    )
    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", -100,100)},
        use_container_width=True,
        key="season_editor"
    )
    fs_ctr = st.number_input("Featured Snippet CTR (%)", 0.0,100.0,18.0)
    aio_ctr = st.number_input("AI Overview CTR (%)", 0.0,100.0,12.0)
    st.subheader("Avg. Paid Listings by Project")
    for p in st.session_state.launch_month_df['Project'] if not st.session_state.launch_month_df.empty else []:
        st.session_state.paid_listings[p] = st.slider(
            f"{p} Paid Listings", 0,10,st.session_state.paid_listings.get(p,2), key=f"paid_{p}"
        )

# --- Tabs ---
tabs = st.tabs(["Upload & Forecast", "Project Summary"])

# --- Upload & Forecast ---
with tabs[0]:
    st.title("Upload & Forecast")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if not uploaded:
        st.info("Please upload a file to start forecasting.")
        st.stop()
    df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
    st.session_state.df = df.copy()
    projects = df['Project'].dropna().unique().tolist()
    if set(projects) != set(st.session_state.launch_month_df['Project']):
        st.session_state.launch_month_df = pd.DataFrame({
            "Project": projects,
            "Launch Date": [datetime.today().replace(day=1)]*len(projects)
        })
        st.session_state.paid_listings = {p:2 for p in projects}
    selected = st.selectbox("Select Project", ["All"]+projects)
    filtered = df if selected=="All" else df[df['Project']==selected]

    # Build rec_df with project, URL, keyword, date, clicks
    base = datetime.today().replace(day=1)
    launch_map = st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict()
    rec = []
    for scenario in ["High","Medium","Low"]:
        for _, row in filtered.iterrows():
            proj = row['Project']; msv=row['MSV']; pos=row['Current Position']; url=row.get('Current URL',''); kw=row['Keyword']
            has_aio = str(row['AI Overview']).lower()=='yes'
            has_fs = str(row['Featured Snippet']).lower()=='yes'
            launch = pd.to_datetime(launch_map.get(proj, base))
            cur = pos
            for m in range(1,25):
                date = base + DateOffset(months=m-1)
                clicks = 0
                if date >= launch:
                    if m>1: cur = max(1, cur-get_movement(msv))
                    pi = int(round(cur)); base_ctr = get_ctr_for_position(pi)
                    if scenario=="High": ctr=base_ctr
                    elif scenario=="Medium":
                        ctr = base_ctr * (1-0.05*st.session_state.paid_listings.get(proj,0))
                        if pi==1 and has_aio: ctr=aio_ctr
                        if pi==1 and has_fs: ctr=fs_ctr
                    else:
                        ctr = base_ctr * 0.8 * (1-0.05*st.session_state.paid_listings.get(proj,0))
                        if pi==1 and has_aio: ctr=aio_ctr*0.8
                        if pi==1 and has_fs: ctr=fs_ctr*0.8
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==date.strftime('%B'), 'Adjustment (%)'
                    ].iloc[0]
                    clicks = (ctr/100)*msv*(1+adj/100)
                rec.append({
                    "Scenario":scenario,
                    "Project":proj,
                    "URL":url,
                    "Keyword":kw,
                    "Date":date,
                    "Clicks":round(clicks)
                })
    rec_df = pd.DataFrame(rec)
    plot_df = rec_df.groupby(["Scenario","Date"])['Clicks'].sum().reset_index()

    # KPI pickers
    st.subheader("Forecast KPIs")
    col1, col2 = st.columns(2)
    min_d = plot_df['Date'].min().date(); max_d = plot_df['Date'].max().date()
    with col1:
        start_date = st.date_input("Start Date", value=min_d, min_value=min_d, max_value=max_d)
    with col2:
        end_date = st.date_input("End Date", value=max_d, min_value=min_d, max_value=max_d)
    if end_date < start_date:
        st.error("End date must be on or after start date.")
    else:
        mask = (plot_df['Date'].dt.date>=start_date)&(plot_df['Date'].dt.date<=end_date)
        totals = plot_df[mask].groupby('Scenario')['Clicks'].sum().to_dict()
        m1,m2,m3 = st.columns(3)
        m1.metric("High Forecast", totals.get("High",0))
        m2.metric("Medium Forecast", totals.get("Medium",0))
        m3.metric("Low Forecast", totals.get("Low",0))

        # Line chart
        fig = px.line(plot_df[mask], x='Date', y='Clicks', color='Scenario', markers=True)
        fig.update_layout(title="Projected Traffic Scenarios Over Time")
        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        summ = plot_df[mask].copy()
        summ['Month'] = summ['Date'].dt.strftime('%b %Y')
        summ['SortKey'] = summ['Date']
        pivot = summ.pivot_table(index=['Month','SortKey'], columns='Scenario', values='Clicks', aggfunc='sum').reset_index()
        pivot = pivot.sort_values('SortKey').drop(columns='SortKey')
        pivot.columns.name = None
        st.subheader("Forecast Summary by Scenario")
        st.dataframe(pivot, use_container_width=True)

        # Combo chart
        med = rec_df[mask & (rec_df['Scenario']=='Medium')].groupby('Project')['Clicks'].sum().reset_index()
        kc = filtered.groupby('Project')['Keyword'].count().reset_index(name='Keyword Count')
        combo = med.merge(kc, on='Project', how='left').fillna(0)
        fig2 = go.Figure()
        fig2.add_bar(x=combo['Project'], y=combo['Clicks'], name='Medium Clicks')
        fig2.add_trace(go.Scatter(x=combo['Project'], y=combo['Keyword Count'], mode='lines+markers', name='Keyword Count', yaxis='y2'))
        fig2.update_layout(
            title="Medium Clicks vs Keyword Count by Project",
            yaxis=dict(title='Medium Clicks'),
            yaxis2=dict(overlaying='y', side='right', title='Keyword Count'),
            legend=dict(x=0.7, y=1.1)
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Optimisation Actions Summary
        m3 = base + DateOffset(months=2)
        m6 = base + DateOffset(months=5)
        action_df = rec_df[rec_df['Scenario']=='Medium']
        a3 = action_df[action_df['Date']==m3].groupby(['Project','URL'])['Clicks'].sum().reset_index(name='3-Month Clicks')
        a6 = action_df[action_df['Date']==m6].groupby(['Project','URL'])['Clicks'].sum().reset_index(name='6-Month Clicks')
        actions = a3.merge(a6, on=['Project','URL'], how='outer').fillna(0)
        # Weighted avg rank
        rank_df = filtered.groupby(['Project','Current URL']).apply(
            lambda d: (d['Current Position']*d['MSV']).sum()/d['MSV'].sum()
        ).reset_index(name='Weighted Avg Rank')
        actions = actions.merge(rank_df, left_on=['Project','URL'], right_on=['Project','Current URL'], how='left').drop(columns='Current URL')
        # Determine action type
        actions['Action'] = actions.apply(
            lambda r: 'Net New Page' if (r['Weighted Avg Rank']>100 or not r['URL']) else 'Optimisation',
            axis=1
        )
        # Recommended URL
        actions['Recommended URL'] = actions.apply(
            lambda r: f"https://example.com/{slugify(r['Project'])}/{slugify(r['URL'] or r['Project'] + ' ' + r['Action'])}" if r['Action']=='Net New Page' else r['URL'],
            axis=1
        )
        st.subheader("Optimisation Actions Summary")
        st.dataframe(
            actions[['Project','Action','URL','Recommended URL','Weighted Avg Rank','3-Month Clicks','6-Month Clicks']],
            use_container_width=True
        )

# --- Project Summary ---
with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run forecast first.")
    else:
        st.data_editor(
            st.session_state.launch_month_df,
            column_config={ 'Launch Date': st.column_config.DateColumn('Launch Date') },
            use_container_width=True,
            key='proj_summary'
        )
