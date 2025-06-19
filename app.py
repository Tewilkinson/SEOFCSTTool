import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas import DateOffset

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")

# --- Initialize session state ---
if "ctr_df" not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32, 25, 18, 12, 10, 8, 6, 4, 2, 1]})
if "seasonality_df" not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        "Month": ["January","February","March","April","May","June","July","August","September","October","November","December"],
        "Adjustment (%)": [0,0,0,0,0,-20,0,0,0,0,0,0]
    })
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project", "Launch Date"])
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()

# --- Helper functions ---
def get_movement(msv):
    if msv <= 500:
        return 1.5
    elif msv <= 2000:
        return 1.0
    elif msv <= 10000:
        return 0.5
    else:
        return 0.25


def get_ctr_for_position(pos):
    try:
        return st.session_state.ctr_df.loc[st.session_state.ctr_df['Position'] == pos, 'CTR'].values[0]
    except IndexError:
        return st.session_state.ctr_df['CTR'].iloc[-1]

# --- Sidebar Controls ---
with st.sidebar:
    st.header("CTR Controls")
    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={"CTR": st.column_config.NumberColumn("CTR (%)", min_value=0.0, max_value=100.0, format="%.1f")},
        num_rows="dynamic",
        use_container_width=True,
        key="ctr_editor"
    )
    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={"Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100, max_value=100, format="%.0f")},
        num_rows="fixed",
        use_container_width=True,
        key="season_editor"
    )
    fs_ctr = st.number_input("CTR for Featured Snippet (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("CTR for AI Overview (%)", min_value=0.0, max_value=100.0, value=12.0)

    st.subheader("Avg. Paid Listings by Project")
    if not st.session_state.launch_month_df.empty:
        for project in st.session_state.launch_month_df['Project'].unique():
            st.session_state.paid_listings[project] = st.slider(
                f"{project} Paid Listings", min_value=0, max_value=10, value=2, key=f"paid_{project}"
            )

# --- Tabs ---
tabs = st.tabs(["Upload & Forecast", "Project Launch & Summary"])

# --- Upload & Forecast Tab ---
with tabs[0]:
    st.title("SEO Forecast Tool")
    st.subheader("Download Forecast Template")
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
    st.download_button("Download Template CSV", data=create_template(), file_name="forecast_template.csv")

    st.subheader("Upload Keyword Template")
    uploaded = st.file_uploader("Upload CSV or Excel Template", type=["csv","xlsx"] )
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.session_state.df = df.copy()

        projects = df['Project'].dropna().unique().tolist()
        st.session_state.launch_month_df = pd.DataFrame({
            "Project": projects,
            "Launch Date": [datetime.today().replace(day=1)]*len(projects)
        })
        selected_project = st.selectbox("Select Project", ["All"]+projects)
        filtered = df if selected_project=="All" else df[df['Project']==selected_project]
        st.dataframe(filtered, use_container_width=True)

        records=[]
        base = datetime.today().replace(day=1)
        launch_map = st.session_state.launch_month_df.set_index("Project")['Launch Date'].to_dict()
        for _,r in filtered.iterrows():
            msv,pos = r['MSV'],r['Current Position']
            aio= str(r['AI Overview']).lower()=='yes'
            fs = str(r['Featured Snippet']).lower()=='yes'
            launch= launch_map.get(r['Project'],base)
            cur_pos = pos
            for m in range(1,25):
                date = base+DateOffset(months=m-1)
                month_str = date.strftime("%b %Y")
                if date<launch:
                    clicks=0
                else:
                    if m>1: cur_pos=max(1,cur_pos-get_movement(msv))
                    pi=int(round(cur_pos))
                    if pi==1 and aio: ctr=aio_ctr
                    elif pi==1 and fs: ctr=fs_ctr
                    else: ctr=get_ctr_for_position(pi)
                    avgp = st.session_state.paid_listings.get(r['Project'],0)
                    ctr = max(0, ctr*(1-0.05*avgp))
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==date.strftime("%B"),'Adjustment (%)'
                    ].iat[0]
                    clicks= (ctr/100)*msv*(1+adj/100)
                records.append({"Month":month_str,"Forecast Clicks":round(clicks)})
        sum_df=pd.DataFrame(records).groupby('Month',sort=False).sum().reset_index()
        sum_df['Month_dt']=pd.to_datetime(sum_df['Month'],format="%b %Y")
        fig=px.line(sum_df.sort_values('Month_dt'), x='Month_dt', y='Forecast Clicks', markers=True)
        fig.update_xaxes(tickformat="%b %Y")
        st.plotly_chart(fig, use_container_width=True)

# --- Project Launch & Summary Tab ---
with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Upload and run forecast to populate summary.")
    else:
        # editable launch dates inline
        lm = st.session_state.launch_month_df.copy()
        lm = st.data_editor(
            lm,
            column_config={
                'Launch Date': st.column_config.DateColumn('Launch Date')
            },
            use_container_width=True,
            key='launch_editor'
        )
        st.session_state.launch_month_df = lm
        # build summary with launch date column
        rows=[]
        for p in st.session_state.df['Project'].dropna().unique():
            launch_dt = pd.to_datetime(lm.set_index('Project').loc[p,'Launch Date'])
            row_dict = {"Project": p, "Launch Date": launch_dt.strftime("%b %Y")}
            for m in [3,6,9,12]:
                total=0
                subset = st.session_state.df[st.session_state.df['Project']==p]
                for _,r in subset.iterrows():
                    pos,msv = r['Current Position'],r['MSV']
                    aio = str(r['AI Overview']).lower()=='yes'
                    fs = str(r['Featured Snippet']).lower()=='yes'
                    curp=pos
                    for i in range(1,m+1):
                        if i>1: curp = max(1,curp-get_movement(msv))
                    pi=int(round(curp))
                    if pi==1 and aio: ctr=aio_ctr
                    elif pi==1 and fs: ctr=fs_ctr
                    else: ctr=get_ctr_for_position(pi)
                    ctr = max(0, ctr*(1-0.05*st.session_state.paid_listings.get(p,0)))
                    mon = (launch_dt+DateOffset(months=m-1)).strftime("%B")
                    adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month']==mon,'Adjustment (%)'
                    ].iat[0]
                    total += (ctr/100)*msv*(1+adj/100)
                row_dict[f"{m}-Month Clicks"] = round(total)
            rows.append(row_dict)
        summary_table = pd.DataFrame(rows)
        st.dataframe(summary_table, use_container_width=True)
