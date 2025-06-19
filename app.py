import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas import DateOffset

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")
# Fix sidebar width to prevent main view cutoff
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        width: 300px;
    }
    [data-testid="stSidebar"][aria-expanded="true"] {
        width: 300px;
    }
    [data-testid="stAppViewContainer"] {
        margin-left: 300px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
    return float(ctrs.loc[ctrs['Position']==pos,'CTR'].iloc[0]) if pos in list(ctrs['Position']) else float(ctrs['CTR'].iloc[-1])

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

# --- Tabs ---
tabs = st.tabs(["Upload & Forecast","Project Summary"])

with tabs[0]:
    st.title("SEO Forecast Tool")
    st.download_button("Download Template CSV", data=pd.DataFrame({
        "Project":["Example"],"Keyword":["shoes for men"],"MSV":[12100],"Current Position":[8],
        "AI Overview":["Yes"],"Featured Snippet":["No"],"Current URL":["https://example.com"]
    }).to_csv(index=False).encode(), file_name="template.csv")

    uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx"])
    if uploaded:
        st.session_state.df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
        projs = st.session_state.df['Project'].dropna().unique().tolist()
        # sync launch dates
        if set(projs) != set(st.session_state.launch_month_df['Project']):
            st.session_state.launch_month_df = pd.DataFrame({"Project":projs,
                "Launch Date":[datetime.today().replace(day=1)]*len(projs)
            })
        sel = st.selectbox("Project", ["All"]+projs)
        filt = st.session_state.df if sel=="All" else st.session_state.df[st.session_state.df['Project']==sel]
        st.dataframe(filt, use_container_width=True)
        # generate chart
        rec=[]; base=datetime.today().replace(day=1)
        lm=st.session_state.launch_month_df.set_index('Project')['Launch Date'].to_dict()
        for _,r in filt.iterrows():
            for m in range(1,25):
                dt=base+DateOffset(months=m-1); lbl=dt.strftime('%b %Y')
                if dt<lm.get(r['Project'],base): c=0
                else:
                    if m>1: rpos=max(1,r['Current Position']-get_movement(r['MSV']))
                    p=int(round(rpos));
                    ctr = aio_ctr if p==1 and str(r['AI Overview']).lower()=='yes' else fs_ctr if p==1 and str(r['Featured Snippet']).lower()=='yes' else get_ctr_for_position(p)
                    ctr*=1-0.05*st.session_state.paid_listings.get(r['Project'],0)
                    adj=st.session_state.seasonality_df.loc[st.session_state.seasonality_df['Month']==dt.strftime('%B'),'Adjustment (%)'].iloc[0]
                    c=(ctr/100)*r['MSV']*(1+adj/100)
                rec.append({'Month':lbl,'Clicks':round(c)})
        sdf=pd.DataFrame(rec).groupby('Month',sort=False).sum().reset_index()
        sdf['Date']=pd.to_datetime(sdf['Month'],format='%b %Y')
        fig=px.line(sdf.sort_values('Date'), x='Date', y='Clicks', markers=True)
        fig.update_xaxes(tickformat='%b %Y')
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run forecast first in tab 1.")
    else:
        rows=[]
        lm=st.session_state.launch_month_df.set_index('Project')['Launch Date']
        for p in lm.index:
            ld=pd.to_datetime(lm.loc[p])
            d={'Project':p,'Launch Date':ld.strftime('%b %Y')}
            sub=st.session_state.df[st.session_state.df['Project']==p]
            for m in [3,6,9,12]:
                tot=0
                for _,r in sub.iterrows():
                    pos=r['Current Position']; msv=r['MSV']; aio=str(r['AI Overview']).lower()=='yes'; fs=str(r['Featured Snippet']).lower()=='yes'
                    for i in range(1,m+1): pos=max(1,pos-get_movement(msv)) if i>1 else pos
                    pi=int(round(pos))
                    ctr = aio_ctr if pi==1 and aio else fs_ctr if pi==1 and fs else get_ctr_for_position(pi)
                    ctr*=1-0.05*st.session_state.paid_listings.get(p,0)
                    adj=st.session_state.seasonality_df.loc[st.session_state.seasonality_df['Month']==(ld+DateOffset(months=m-1)).strftime('%B'),'Adjustment (%)'].iloc[0]
                    tot+=(ctr/100)*msv*(1+adj/100)
                d[f"{m}-Month Clicks"]=round(tot)
            rows.append(d)
        summary=pd.DataFrame(rows)
        st.data_editor(summary, use_container_width=True, key='final_summary')
