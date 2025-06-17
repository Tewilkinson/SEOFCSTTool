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

# --- Tabs Layout ---
tabs = st.tabs(["Upload & Forecast", "CTR Controls", "Project Launch Dates"])

with tabs[2]:
    st.header("Project Launch Dates")
    edit_mode_launch = st.checkbox("Enable Edit Mode", key="launch_edit")

    if edit_mode_launch:
        edited_launch = st.data_editor(
            st.session_state.launch_month_df.copy(),
            num_rows="dynamic",
            use_container_width=True,
            key="edit_launch_month"
        )
        if st.button("Save Launch Dates"):
            st.session_state.launch_month_df = edited_launch.copy()
            st.success("Launch months updated.")
    el# Removed editable launch month table from CTR Controls,
            num_rows="dynamic",
            use_container_width=True,
            key="edit_ctr_table"
        )

        edited_seasonality = st.data_editor(
            st.session_state.seasonality_df.copy(),
            num_rows="fixed",
            use_container_width=True,
            key="edit_seasonality"
        )

        if not st.session_state.launch_month_df.empty:
            edited_launch = st.data_editor(
                st.session_state.launch_month_df.copy(),
                num_rows="dynamic",
                use_container_width=True,
                key="edit_launch_month"
            )
        else:
            edited_launch = pd.DataFrame(columns=["Project", "Launch Month"])

        if st.button("Save Changes"):
            st.session_state.ctr_df = edited_ctr.copy()
            st.session_state.seasonality_df = edited_seasonality.copy()
            st.session_state.launch_month_df = edited_launch.copy()
            st.success("Changes saved and applied to forecast.")
    else:
        st.dataframe(st.session_state.ctr_df, use_container_width=True)
        st.dataframe(st.session_state.seasonality_df, use_container_width=True)
        # Removed read-only launch month table from CTR Controls

    fs_ctr = st.number_input("CTR for Featured Snippet (%)", min_value=0.0, max_value=100.0, value=18.0)
    aio_ctr = st.number_input("CTR for AI Overview (%)", min_value=0.0, max_value=100.0, value=12.0)

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

        selected_project = st.selectbox("Select a Project to View Forecast", projects)

        filtered_df = df[df['Project'] == selected_project]

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
                current_month = (base_date + pd.DateOffset(months=month - 1))
                forecast_month = current_month.strftime("%B")

                if current_month.month < launch_month_index:
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

                    seasonal_adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == forecast_month,
                        'Adjustment (%)'
                    ].values[0]
                    adjusted_clicks = (ctr / 100) * msv * (1 + seasonal_adj / 100)
                    position_val = pos

                forecast_results.append({
                    "Project": row['Project'],
                    "Keyword": keyword,
                    "Month": forecast_month,
                    "Position": round(position_val, 2),
                    "CTR": ctr,
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

        st.dataframe(forecast_df, use_container_width=True)

        csv = forecast_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Forecast CSV", data=csv, file_name="traffic_forecast.csv")
