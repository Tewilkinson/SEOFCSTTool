# seo_forecast_tool.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px
from datetime import datetime, timedelta

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")

# --- Initialize session state for editable tables ---
if "ctr_df" not in st.session_state:
    st.session_state.ctr_df = pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32, 25, 18, 12, 10, 8, 6, 4, 2, 1]})

if "seasonality_df" not in st.session_state:
    st.session_state.seasonality_df = pd.DataFrame({
        "Month": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "Adjustment (%)": [0, 0, 0, 0, 0, -20, 0, 0, 0, 0, 0, 0]
    })

if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project", "Launch Month"])

if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}

# --- Tabs Layout ---
tabs = st.tabs(["Upload & Forecast", "Project Launch Dates"])

with st.sidebar:
    st.header("CTR Controls")

    st.subheader("CTR by Position")
    st.session_state.ctr_df = st.data_editor(
        st.session_state.ctr_df,
        column_config={
            "CTR": st.column_config.NumberColumn("CTR (%)", min_value=0.0, max_value=100.0, format="%.1f")
        },
        num_rows="dynamic",
        use_container_width=True,
        key="edit_ctr_table"
    )

    st.subheader("Seasonality by Month")
    st.session_state.seasonality_df = st.data_editor(
        st.session_state.seasonality_df,
        column_config={
            "Adjustment (%)": st.column_config.NumberColumn("Adjustment (%)", min_value=-100, max_value=100, format="%.0f")
        },
        num_rows="fixed",
        use_container_width=True,
        key="edit_seasonality"
    )

    fs_ctr = st.number_input("CTR for Featured Snippet (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("CTR for AI Overview (%)", min_value=0.0, max_value=100.0, value=12.0)

    st.subheader("Avg. Paid Listings by Project")
    if st.session_state.launch_month_df is not None and not st.session_state.launch_month_df.empty:
        for project in st.session_state.launch_month_df['Project'].unique():
            st.session_state.paid_listings[project] = st.slider(
                f"{project} Paid Listings", min_value=0, max_value=10, value=2, key=f"paid_{project}"
            )

    

with tabs[1]:
    st.header("Project Launch Dates")

    # Aggregate forecast clicks if available
    forecast_summary = pd.DataFrame()
    if "forecast_df" in locals():
        forecast_summary = forecast_df.copy()
        forecast_summary["Month_Idx"] = forecast_summary["Month"].apply(lambda m: datetime.strptime(m, "%b %Y"))

        grouped = forecast_summary.groupby("Project")
        project_metrics = []
        for project, group in grouped:
            group = group.sort_values("Month_Idx")
            sum_3mo = group.head(3)["Forecast Clicks"].sum()
            sum_6mo = group.head(6)["Forecast Clicks"].sum()
            sum_12mo = group.head(12)["Forecast Clicks"].sum()
            actions = group["Keyword"].nunique()
            project_metrics.append({
                "Project": project,
                "# Keywords": actions,
                "Clicks (3mo)": sum_3mo,
                "Clicks (6mo)": sum_6mo,
                "Clicks (12mo)": sum_12mo
            })
        project_metrics_df = pd.DataFrame(project_metrics)
        st.session_state.launch_month_df = pd.merge(
            st.session_state.launch_month_df,
            project_metrics_df,
            on="Project",
            how="left"
        )

    month_options = list(st.session_state.seasonality_df["Month"])
    st.session_state.launch_month_df["Launch Month"] = st.session_state.launch_month_df["Launch Month"].apply(
        lambda x: x if x in month_options else "January"
    )
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

    gb = GridOptionsBuilder.from_dataframe(st.session_state.launch_month_df)
    gb.configure_column("Project", editable=False)
    gb.configure_column(
        "Launch Month",
        editable=True,
        cellEditor='agSelectCellEditor',
        cellEditorParams={"values": month_options}
    )
    grid_options = gb.build()

    ag_result = AgGrid(
        st.session_state.launch_month_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=300,
        key="launch_month_aggrid"
    )
    st.session_state.launch_month_df = ag_result["data"]
