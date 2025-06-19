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
    return pd.DataFrame(data).to_csv(index=False).encode('utf-8')

# --- Slugify Function ---
def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", '-', text)
    return text.strip('-')

# --- Session State Init ---
if 'ctr_df' not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({'Position': list(range(1,11)), 'CTR': [32,25,18,12,10,8,6,4,2,1]})
if 'seasonality_df' not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        'Month': ['January','February','March','April','May','June','July','August','September','October','November','December'],
        'Adjustment (%)': [0,0,0,0,0,-20,0,0,0,0,0,0]
    })
if 'paid_listings' not in st.session_state:
    st.session_state.paid_listings = {}
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'launch_month_df' not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=['Project','Launch Date'])

# --- Helpers ---
def get_movement(msv):
    if msv <= 500: return 1.5
    if msv <= 2000: return 1.0
    if msv <= 10000: return 0.5
    return 0.25

def get_ctr_for_position(pos):
    df = st.session_state.ctr_df
    if pos in df['Position'].tolist():
        return float(df.loc[df['Position']==pos,'CTR'].iloc[0])
    return float(df['CTR'].iloc[-1])

# --- Sidebar ---
with st.sidebar:
    st.subheader('Download Template')
    st.download_button('Download Template CSV', data=create_template(), file_name='forecast_template.csv')
    st.subheader('CTR by Position')
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={'CTR': st.column_config.NumberColumn('CTR (%)', min_value=0.0, max_value=100.0)},
        use_container_width=True,
        hide_index=True,
        key='ctr_editor'
    )
    st.subheader('Seasonality by Month')
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={'Adjustment (%)': st.column_config.NumberColumn('Adjustment (%)', min_value=-100.0, max_value=100.0)},
        use_container_width=True,
        hide_index=True,
        key='season_editor'
    )
    fs_ctr = st.number_input('Featured Snippet CTR (%)', min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input('AI Overview CTR (%)', min_value=0.0, max_value=100.0, value=12.0)
    st.subheader('Avg. Paid Listings per Project')
    if not st.session_state.launch_month_df.empty:
        for p in st.session_state.launch_month_df['Project']:
            st.session_state.paid_listings[p] = st.slider(
                f'{p} Paid Listings',
                min_value=0,
                max_value=10,
                value=st.session_state.paid_listings.get(p, 2),
                key=f'paid_{p}'
            )

# --- Tabs ---
tabs = st.tabs(['Upload & Forecast','Project Summary'])

# --- Upload & Forecast Tab ---
with tabs[0]:
    st.title('Upload & Forecast')
    uploaded = st.file_uploader('Upload CSV or Excel', type=['csv','xlsx'])
    if not uploaded:
        st.info('Please upload a CSV or Excel file to start forecasting.')
        st.stop()
    df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
    st.session_state.df = df.copy()

    projects = df['Project'].dropna().unique().tolist()
    if set(projects) != set(st.session_state.launch_month_df['Project']):
        st.session_state.launch_month_df = pd.DataFrame({'Project': projects, 'Launch Date': [datetime.today().replace(day=1)]*len(projects)})
        st.session_state.paid_listings = {p:2 for p in projects}

    selected = st.selectbox('Select Project', ['All'] + projects)
    filtered = df if selected=='All' else df[df['Project']==selected]

    # Build rec_df with raw and adjusted clicks
    base = datetime.today().replace(day=1)
    launch_map = st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict()
    rec = []
    for scenario in ['High','Medium','Low']:
        for _, r in filtered.iterrows():
            proj, msv, pos = r['Project'], r['MSV'], r['Current Position']
            url = r.get('Current URL','') or ''
            kw = r['Keyword']
            has_aio = str(r['AI Overview']).lower()=='yes'
            has_fs = str(r['Featured Snippet']).lower()=='yes'
            launch = launch_map.get(proj, base)
            cur_pos = pos
            for i in range(1,25):
                date = base + DateOffset(months=i-1)
                raw_clicks = 0
                adjusted_clicks = 0
                if date >= launch:
                    if i>1: cur_pos = max(1, cur_pos-get_movement(msv))
                    pi = int(round(cur_pos))
                    base_ctr = get_ctr_for_position(pi)
                    # scenario CTR
                    if scenario=='High': ctr = base_ctr
                    elif scenario=='Medium':
                        ctr = base_ctr*(1-0.05*st.session_state.paid_listings.get(proj,0))
                        if pi==1 and has_aio: ctr = aio_ctr
                        if pi==1 and has_fs: ctr = fs_ctr
                    else:
                        ctr = base_ctr*0.8*(1-0.05*st.session_state.paid_listings.get(proj,0))
                        if pi==1 and has_aio: ctr = aio_ctr*0.8
                        if pi==1 and has_fs: ctr = fs_ctr*0.8
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==date.strftime('%B'),'Adjustment (%)'
                    ].iloc[0]
                    raw_clicks = (ctr/100)*msv
                    adjusted_clicks = raw_clicks * (1+adj/100)
                rec.append({'Scenario':scenario,'Project':proj,'URL':url,'Keyword':kw,'Date':date,'Raw Clicks':round(raw_clicks),'Adjusted Clicks':round(adjusted_clicks)})
    rec_df = pd.DataFrame(rec)
    plot_df = rec_df.groupby(['Scenario','Date'])['Adjusted Clicks'].sum().reset_index().rename(columns={'Adjusted Clicks':'Clicks'})

    # KPI pickers
    st.subheader('Forecast KPIs')
    c1,c2 = st.columns(2)
    min_d,max_d = plot_df['Date'].min().date(), plot_df['Date'].max().date()
    with c1: start_date = st.date_input('Start Date', min_value=min_d, max_value=max_d, value=min_d)
    with c2: end_date = st.date_input('End Date', min_value=min_d, max_value=max_d, value=max_d)
    if end_date < start_date: st.error('End date must be on or after start date.')
    else:
        mask = (plot_df['Date'].dt.date>=start_date)&(plot_df['Date'].dt.date<=end_date)
        totals = plot_df[mask].groupby('Scenario')['Clicks'].sum().to_dict()
        m1,m2,m3 = st.columns(3)
        m1.metric('High Forecast',totals.get('High',0)); m2.metric('Medium Forecast',totals.get('Medium',0)); m3.metric('Low Forecast',totals.get('Low',0))

        # Line chart
        fig = px.line(plot_df[mask], x='Date', y='Clicks', color='Scenario', markers=True)
        fig.update_layout(title='Projected Traffic Scenarios Over Time')
        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        summ = plot_df[mask].copy(); summ['Month']=summ['Date'].dt.strftime('%b %Y'); summ['SortKey']=summ['Date']
        pivot = summ.pivot_table(index=['Month','SortKey'], columns='Scenario', values='Clicks', aggfunc='sum').reset_index()
        pivot = pivot.sort_values('SortKey').drop(columns='SortKey'); pivot.columns.name=None
        st.subheader('Forecast Summary by Scenario'); st.dataframe(pivot, use_container_width=True, hide_index=True)

        # Combo chart
        rec_mask = (rec_df['Scenario']=='Medium') & (rec_df['Date'].dt.date>=start_date) & (rec_df['Date'].dt.date<=end_date)
        med = rec_df[rec_mask].groupby('Project')['Raw Clicks'].sum().reset_index()
        kc = filtered.groupby('Project')['Keyword'].count().reset_index(name='Keyword Count')
        combo = kc.merge(med, on='Project', how='left').fillna(0)
        fig2 = go.Figure()
        if not combo.empty:
            fig2.add_bar(x=combo['Project'], y=combo['Raw Clicks'], name='Medium Clicks')
            fig2.add_scatter(x=combo['Project'], y=combo['Keyword Count'], mode='lines+markers', name='Keyword Count', yaxis='y2')
            fig2.update_layout(title='Medium Clicks vs Keyword Count by Project', yaxis=dict(title='Medium Clicks'), yaxis2=dict(overlaying='y', side='right', title='Keyword Count'), legend=dict(x=0.7, y=1.1))
        st.plotly_chart(fig2, use_container_width=True)

        # Actions Summary
        m3 = base + DateOffset(months=2)
        m6 = base + DateOffset(months=5)
        records = []
        # Unique projects
        for proj in filtered['Project'].unique():
            # Existing URL actions
            existing_urls = filtered[filtered['Project']==proj]['Current URL'].dropna().unique()
            for url in existing_urls:
                # 3-month and 6-month clicks
                clicks3 = rec_df[(rec_df['Scenario']=='Medium') & (rec_df['Project']==proj) & (rec_df['URL']==url) & (rec_df['Date']<=m3)]['Raw Clicks'].sum()
                clicks6 = rec_df[(rec_df['Scenario']=='Medium') & (rec_df['Project']==proj) & (rec_df['URL']==url) & (rec_df['Date']<=m6)]['Raw Clicks'].sum()
                # Weighted avg rank
                wr = filtered[(filtered['Project']==proj) & (filtered['Current URL']==url)]
                weighted = (wr['Current Position'] * wr['MSV']).sum() / wr['MSV'].sum() if not wr.empty else None
                records.append({'Project':proj,'Action':'Optimisation','URL':url,'Weighted Avg Rank':int(round(weighted)) if weighted else None,'3-Month Clicks':int(clicks3),'6-Month Clicks':int(clicks6)})
            # New page actions per keyword without URL
            blank_rows = filtered[(filtered['Project']==proj) & (filtered['Current URL'].isna()| (filtered['Current URL']==''))]
            for _, br in blank_rows.iterrows():
                kw = br['Keyword']
                clicks3 = rec_df[(rec_df['Scenario']=='Medium') & (rec_df['Project']==proj) & (rec_df['URL']=='') & (rec_df['Keyword']==kw) & (rec_df['Date']<=m3)]['Raw Clicks'].sum()
                clicks6 = rec_df[(rec_df['Scenario']=='Medium') & (rec_df['Project']==proj) & (rec_df['URL']=='') & (rec_df['Keyword']==kw) & (rec_df['Date']<=m6)]['Raw Clicks'].sum()
                records.append({'Project':proj,'Action':'Create New Page','URL':'','Weighted Avg Rank':None,'3-Month Clicks':int(clicks3),'6-Month Clicks':int(clicks6)})
        actions_df = pd.DataFrame(records)
        st.subheader('Optimisation Actions Summary')
        st.dataframe(actions_df[['Project','Action','URL','Weighted Avg Rank','3-Month Clicks','6-Month Clicks']], use_container_width=True, hide_index=True)

# --- Project Summary Tab ---
with tabs[1]:
    st.header('Project Launch & Forecast Summary')
    if st.session_state.df.empty:
        st.info('Run forecast first.')
    else:
        st.data_editor(
            st.session_state.launch_month_df,
            column_config={'Launch Date':st.column_config.DateColumn('Launch Date')},
            use_container_width=True,
            hide_index=True,
            key='proj_summary'
        )
