import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
import altair as alt

st.set_page_config(page_title="GDELT News Pulse", layout="wide")
st.title("GDELT News Pulse")
st.caption("Daily news tone and composition by country, from GDELT events matched to source-country domains.")

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials, project="open-intel-377412")

@st.cache_data(ttl="1d")
def load_data():
    query = """
        select *
        from `open-intel-377412.gdelt_dbt_dev.gold_news_by_country_date`
    """
    return client.query(query).to_dataframe()

df = load_data()

print(df["country"].isna().sum(), "rows with missing country name, out of", len(df))

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
    options=["avg_tone", "avg_goldstein", "events", "pct_material_conflict"],
    index=0,
)

filtered = df[df["country"].isin(selected_countries)]

chart = (
    alt.Chart(filtered)
    .mark_line()
    .encode(
        x=alt.X("event_date:T", title="Date"),
        y=alt.Y(f"{metric}:Q", title=metric),
        color=alt.Color("country:N", title="Country"),
        tooltip=["country", "event_date", metric],
    )
    .properties(height=450)
    .interactive()
)

st.altair_chart(chart, use_container_width=True)