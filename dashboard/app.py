import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
import altair as alt
import pandas as pd

METRIC_LABELS = {
    "avg_tone": "Average tone (−100 to 100)",
    "avg_goldstein": "Average Goldstein scale (−10 to 10)",
    "events": "Events",
    "pct_material_conflict": "Material conflict (% of events)",
}

# Per-event averages/shares: combining several days must weight each day by its event count.
WEIGHTED_METRICS = [
    "avg_tone",
    "avg_goldstein",
    "pct_verbal_cooperation",
    "pct_material_cooperation",
    "pct_verbal_conflict",
    "pct_material_conflict",
]


def rolling_7d(country_df):
    """7-day rolling values for one country: events as a daily average, other metrics event-weighted."""
    daily = country_df.set_index("event_date").sort_index().asfreq("D")
    events = daily["events"].fillna(0)  # a missing day means zero matched events
    events_7d = events.rolling(7, min_periods=7).sum()

    out = pd.DataFrame({"events": events_7d / 7}, index=daily.index)
    for col in WEIGHTED_METRICS:
        weighted_sum = (daily[col] * events).fillna(0).rolling(7, min_periods=7).sum()
        out[col] = weighted_sum / events_7d
    return out.reset_index()


st.set_page_config(page_title="GDELT news pulse", layout="wide")
st.title("GDELT news pulse")
st.caption("Daily news tone and composition by country, from GDELT events matched to source-country domains.")


@st.cache_resource
def get_client():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    return bigquery.Client(credentials=credentials, project="open-intel-377412")


@st.cache_data(ttl="7d")
def load_data():
    query = """
        select *
        from `open-intel-377412.gdelt_dbt_dev.gold_news_by_country_date`
    """
    df = get_client().query(query).to_dataframe()
    df["event_date"] = pd.to_datetime(df["event_date"])
    return df

df = load_data()

st.caption(f"Data through {df['event_date'].max():%Y-%m-%d} · refreshed weekly")

top_countries = (
    df.groupby("country")["events"].sum()
    .sort_values(ascending=False)
    .head(8)
    .index.tolist()
)

selected_countries = st.multiselect(
    "Countries",
    options=sorted(df["country"].dropna().unique()),
    default=top_countries,
)

metric = st.selectbox(
    "Metric",
    options=list(METRIC_LABELS),
    format_func=METRIC_LABELS.get,
    index=0,
)

smooth = st.toggle("7-day rolling average", help="Smooths day-to-day noise; averages are weighted by event count.")

if not selected_countries:
    st.info("Select at least one country to see the chart.")
    st.stop()

filtered = df[df["country"].isin(selected_countries)]
if smooth:
    filtered = (
        filtered.groupby("country")[["event_date", "events", *WEIGHTED_METRICS]]
        .apply(rolling_7d)
        .reset_index(level="country")
        .dropna(subset=["events"])
    )

y_title = METRIC_LABELS[metric] + (" · 7-day avg" if smooth else "")

chart = (
    alt.Chart(filtered)
    .mark_line()
    .encode(
        x=alt.X("event_date:T", title="Date"),
        y=alt.Y(f"{metric}:Q", title=y_title),
        color=alt.Color("country:N", title="Country"),
        tooltip=["country", "event_date", metric],
    )
    .properties(height=450)
    .interactive()
)

st.altair_chart(chart)
