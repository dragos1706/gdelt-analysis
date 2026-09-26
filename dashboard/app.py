import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
import altair as alt

METRIC_LABELS = {
    "avg_tone": "Average tone (−100 to 100)",
    "avg_goldstein": "Average Goldstein scale (−10 to 10)",
    "events": "Events",
    "pct_material_conflict": "Material conflict (% of events)",
}

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
    return get_client().query(query).to_dataframe()

df = load_data()

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

if not selected_countries:
    st.info("Select at least one country to see the chart.")
    st.stop()

filtered = df[df["country"].isin(selected_countries)]

chart = (
    alt.Chart(filtered)
    .mark_line()
    .encode(
        x=alt.X("event_date:T", title="Date"),
        y=alt.Y(f"{metric}:Q", title=METRIC_LABELS[metric]),
        color=alt.Color("country:N", title="Country"),
        tooltip=["country", "event_date", metric],
    )
    .properties(height=450)
    .interactive()
)

st.altair_chart(chart)
