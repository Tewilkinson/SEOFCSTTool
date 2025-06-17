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
tabs = st.tabs(["Upload & Forecast", "CTR Controls", "Project Launch Dates"])

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

    st.markdown("---")
    st.subheader("Average Paid Listings by Project")
    if st.session_state.launch_month_df is not None and not st.session_state.launch_month_df.empty:
        for project in st.session_state.launch_month_df['Project'].unique():
            st.session_state.paid_listings[project] = st.slider(
                f"{project} – Avg. Paid Listings on SERP", min_value=0, max_value=10, value=2, key=f"paid_{project}"
            )

with tabs[2]:
    st.header("Project Launch Dates")

    if st.session_state.launch_month_df.empty:
        st.info("No launch months found. If you've uploaded keyword data, click below to initialize.")
        if st.button("Initialize Launch Table with Example Project"):
            st.session_state.launch_month_df = pd.DataFrame({"Project": ["Example Project"], "Launch Month": ["January"]})
            st.experimental_rerun()
    else:
        month_options = list(st.session_state.seasonality_df["Month"])
        st.session_state.launch_month_df["Launch Month"] = st.session_state.launch_month_df["Launch Month"].apply(
            lambda x: x if x in month_options else "January"
        )
        st.session_state.launch_month_df = st.data_editor(
            st.session_state.launch_month_df,
            column_config={
                "Launch Month": st.column_config.SelectboxColumn("Launch Month", options=month_options)
            },
            num_rows="dynamic",
            use_container_width=True,
            key="launch_month_editor"
        )

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
        df_template = pd.DataFrame(data)
        return df_template.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Template CSV",
        data=create_template(),
        file_name="forecast_template.csv",
        mime="text/csv"
    )

    st.subheader("Upload Keyword Template")
    template_file = st.file_uploader("Upload CSV or Excel Template", type=["csv", "xlsx"])

    if template_file:
        if template_file.name.endswith(".csv"):
            df = pd.read_csv(template_file)
        else:
            df = pd.read_excel(template_file)

        projects = df['Project'].dropna().unique().tolist()
        if st.session_state.launch_month_df.empty:
            st.session_state.launch_month_df = pd.DataFrame({"Project": projects, "Launch Month": ["January"] * len(projects)})

        selected_project = st.selectbox("Select a Project to View Forecast", ["All"] + projects)

        filtered_df = df if selected_project == "All" else df[df['Project'] == selected_project]

        st.markdown("### Keyword Inputs for Project: " + selected_project)
        st.dataframe(filtered_df, use_container_width=True)

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

        forecast_results = []
        base_date = datetime.today().replace(day=1)

        project_launch_month = st.session_state.launch_month_df.set_index("Project").to_dict().get("Launch Month", {})
        launch_month_index = datetime.strptime(project_launch_month.get(selected_project, "January"), "%B").month
        avg_paid_listings = st.session_state.paid_listings.get(selected_project, 0)

        for _, row in filtered_df.iterrows():
            keyword = row['Keyword']
            msv = row['MSV']
            position = row['Current Position']
            has_aio = str(row['AI Overview']).strip().lower() == 'yes'
            has_fs = str(row['Featured Snippet']).strip().lower() == 'yes'

            monthly_gain = get_movement(msv)
            month = 1
            pos = position

            while month <= 24:
                current_month = base_date + pd.DateOffset(months=month - 1)
                forecast_month = current_month.strftime("%b %Y")

                # Only skip months before launch month in the first launch year
                skip = current_month.year == base_date.year and current_month.month < launch_month_index

                if skip:
                    adjusted_clicks = 0
                    position_val = pos
                    ctr = 0
                else:
                    pos = max(1, pos - monthly_gain)
                    pos_int = int(round(pos))

                    if pos_int == 1 and has_aio:
                        ctr = aio_ctr
                    elif pos_int == 1 and has_fs:
                        ctr = fs_ctr
                    else:
                        ctr = get_ctr_for_position(pos_int)

                    ctr = ctr * (1 - 0.05 * avg_paid_listings)
                    ctr = max(0, ctr)

                    seasonal_adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == current_month.strftime("%B"),
                        'Adjustment (%)'
                    ].values[0]
                    adjusted_clicks = (ctr / 100) * msv * (1 + seasonal_adj / 100)
                    position_val = pos

                forecast_results.append({
                    "Project": row['Project'],
                    "Keyword": keyword,
                    "Month": forecast_month,
                    "Position": round(position_val, 2),
                    "CTR": round(ctr, 2),
                    "Forecast Clicks": round(adjusted_clicks),
                    "Current URL": row['Current URL']
                })
                month += 1

        forecast_df = pd.DataFrame(forecast_results)

        st.subheader("Traffic Forecast")

        summary_df = forecast_df.groupby("Month", sort=False)["Forecast Clicks"].sum().reset_index()

        chart = px.line(
            summary_df,
            x="Month",
            y="Forecast Clicks",
            title="Projected Total Traffic Over Time",
            markers=True
        )
        st.plotly_chart(chart, use_container_width=True)

        st.subheader("Forecast Table")
        st.dataframe(forecast_df, use_container_width=True)

        csv = forecast_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Forecast CSV", data=csv, file_name="traffic_forecast.csv")
