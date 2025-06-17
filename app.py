# seo_forecast_tool.py
import streamlit as st
import pandas as pd
import numpy as np
import io

# --- App Config ---
st.set_page_config(page_title="SEO Forecast Tool", layout="wide")

# --- Tabs Layout ---
tabs = st.tabs(["Upload & Forecast", "CTR Controls"])

with tabs[1]:
    st.header("CTR Controls")

    def default_ctr_table():
        return pd.DataFrame({"Position": list(range(1, 11)), "CTR": [32, 25, 18, 12, 10, 8, 6, 4, 2, 1]})

    ctr_df = st.data_editor(
        default_ctr_table(),
        num_rows="dynamic",
        use_container_width=True,
        key="ctr_table"
    )

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
                return ctr_df.loc[ctr_df['Position'] == pos, 'CTR'].values[0]
            except IndexError:
                return ctr_df['CTR'].iloc[-1]

        forecast_results = []

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
                pos = max(1, pos - monthly_gain)
                pos_int = int(round(pos))

                if has_aio:
                    ctr = aio_ctr
                elif has_fs:
                    ctr = fs_ctr
                else:
                    ctr = get_ctr_for_position(pos_int)

                clicks = (ctr / 100) * msv

                forecast_results.append({
                    "Project": row['Project'],
                    "Keyword": keyword,
                    "Month": month,
                    "Position": round(pos, 2),
                    "CTR": ctr,
                    "Forecast Clicks": round(clicks),
                    "Current URL": row['Current URL']
                })
                month += 1

        forecast_df = pd.DataFrame(forecast_results)

        st.subheader("Traffic Forecast")
        st.dataframe(forecast_df, use_container_width=True)

        csv = forecast_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Forecast CSV", data=csv, file_name="traffic_forecast.csv")
