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
        "Month": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "Adjustment (%)": [0, 0, 0, 0, 0, -20, 0, 0, 0, 0, 0, 0]
    })
if "launch_month_df" not in st.session_state:
    st.session_state.launch_month_df = pd.DataFrame(columns=["Project", "Launch Date"])
if "paid_listings" not in st.session_state:
    st.session_state.paid_listings = {}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "forecast_df" not in st.session_state:
    st.session_state.forecast_df = pd.DataFrame()

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

    # Template Download
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
    uploaded = st.file_uploader("Upload CSV or Excel Template", type=["csv", "xlsx"])
    if uploaded:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
        st.session_state.df = df.copy()

        # Initialize launch dates for new projects
        projects = df['Project'].dropna().unique().tolist()
        if st.session_state.launch_month_df.empty:
            st.session_state.launch_month_df = pd.DataFrame({
                "Project": projects,
                "Launch Date": [datetime.today().replace(day=1)] * len(projects)
            })

        selected_project = st.selectbox("Select a Project to View Forecast", ["All"] + projects)
        filtered_df = df if selected_project == "All" else df[df['Project'] == selected_project]

        st.markdown(f"### Keyword Inputs for Project: {selected_project}")
        st.dataframe(filtered_df, use_container_width=True)

        # --- Forecast Calculation ---
        forecast_results = []
        base_date = datetime.today().replace(day=1)
        launch_dict = st.session_state.launch_month_df.set_index("Project")['Launch Date'].to_dict()

        for _, row in filtered_df.iterrows():
            project = row['Project']
            msv = row['MSV']
            pos = row['Current Position']
            has_aio = str(row['AI Overview']).strip().lower() == 'yes'
            has_fs = str(row['Featured Snippet']).strip().lower() == 'yes'
            launch_date = launch_dict.get(project, base_date)

            for month in range(1, 25):
                current_month = base_date + DateOffset(months=month - 1)
                forecast_month = current_month.strftime("%b %Y")

                if current_month < launch_date:
                    adjusted_clicks = 0
                    ctr = 0
                    position_val = pos
                else:
                    movement = get_movement(msv)
                    if month > 1:
                        pos = max(1, pos - movement)
                    pos_int = int(round(pos))

                    if pos_int == 1 and has_aio:
                        ctr = aio_ctr
                    elif pos_int == 1 and has_fs:
                        ctr = fs_ctr
                    else:
                        ctr = get_ctr_for_position(pos_int)

                    avg_paid = st.session_state.paid_listings.get(project, 0)
                    ctr = max(0, ctr * (1 - 0.05 * avg_paid))

                    seasonal_adj = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == current_month.strftime("%B"),
                        'Adjustment (%)'
                    ].values[0]
                    adjusted_clicks = (ctr / 100) * msv * (1 + seasonal_adj / 100)
                    position_val = pos

                forecast_results.append({
                    "Project": project,
                    "Keyword": row['Keyword'],
                    "Month": forecast_month,
                    "Position": round(position_val, 2),
                    "CTR": round(ctr, 2),
                    "Forecast Clicks": round(adjusted_clicks),
                    "Current URL": row['Current URL']
                })

        forecast_df = pd.DataFrame(forecast_results)
        st.session_state.forecast_df = forecast_df

        # --- Line Chart ---
        summary_df = forecast_df.groupby("Month", sort=False)["Forecast Clicks"].sum().reset_index()
        summary_df["Month_dt"] = pd.to_datetime(summary_df["Month"], format="%b %Y")
        summary_df = summary_df.sort_values("Month_dt")

        chart = px.line(
            summary_df,
            x="Month_dt",
            y="Forecast Clicks",
            title="Projected Total Traffic Over Time",
            markers=True
        )
        chart.update_xaxes(tickformat="%b %Y")
        st.plotly_chart(chart, use_container_width=True)

        st.subheader("Forecast Table")
        st.dataframe(forecast_df, use_container_width=True)

        csv = forecast_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Forecast CSV", data=csv, file_name="traffic_forecast.csv")

# --- Project Launch & Summary Tab ---
with tabs[1]:
    st.header("Project Launch & Forecast Summary")
    if st.session_state.df.empty:
        st.info("Run a forecast first by uploading the keyword template.")
    else:
        st.write("### Forecast at Key Milestones (3, 6, 9, 12 months)")
        month_names = st.session_state.seasonality_df['Month'].tolist()
        options = [f"{month} {year}" for year in range(2023, 2031) for month in month_names]

        rows = []
        for project in st.session_state.df['Project'].dropna().unique():
            # Launch date selector
            current_launch = st.session_state.launch_month_df.set_index('Project').loc[project, 'Launch Date']
            default_idx = options.index(current_launch.strftime("%B %Y")) if current_launch.strftime("%B %Y") in options else 0
            selected = st.selectbox(f"Launch Date for {project}", options=options, index=default_idx, key=f"launch2_{project}")
            launch_dt = datetime.strptime(selected, "%B %Y")
            st.session_state.launch_month_df.loc[
                st.session_state.launch_month_df['Project'] == project, 'Launch Date'
            ] = launch_dt

            # Calculate milestone clicks
            total_clicks = {}
            project_df = st.session_state.df[st.session_state.df['Project'] == project]
            for months in [3, 6, 9, 12]:
                sum_clicks = 0
                for _, row in project_df.iterrows():
                    msv = row['MSV']
                    pos = row['Current Position']
                    has_aio = str(row['AI Overview']).strip().lower() == 'yes'
                    has_fs = str(row['Featured Snippet']).strip().lower() == 'yes'

                    # simulate movement
                    pos_i = pos
                    for i in range(1, months + 1):
                        if i > 1:
                            pos_i = max(1, pos_i - get_movement(msv))
                    pos_int = int(round(pos_i))

                    # CTR determination
                    if pos_int == 1 and has_aio:
                        ctr_val = aio_ctr
                    elif pos_int == 1 and has_fs:
                        ctr_val = fs_ctr
                    else:
                        ctr_val = get_ctr_for_position(pos_int)
                    avg_paid = st.session_state.paid_listings.get(project, 0)
                    ctr_val = max(0, ctr_val * (1 - 0.05 * avg_paid))

                    # seasonality
                    month_name = (launch_dt + DateOffset(months=months - 1)).strftime("%B")
                    seasonal = st.session_state.seasonality_df.loc[
                        st.session_state.seasonality_df['Month'] == month_name,
                        'Adjustment (%)'
                    ].values[0]

                    sum_clicks += (ctr_val / 100) * msv * (1 + seasonal / 100)
                total_clicks[months] = round(sum_clicks)

            rows.append({
                "Project": project,
                "Launch Date": selected,
                "3-Month Clicks": total_clicks[3],
                "6-Month Clicks": total_clicks[6],
                "9-Month Clicks": total_clicks[9],
                "12-Month Clicks": total_clicks[12]
            })

        summary_df2 = pd.DataFrame(rows)
        st.dataframe(summary_df2, use_container_width=True)
