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

QUAD_CLASS_LABELS = {
    "pct_verbal_cooperation": "Verbal cooperation",
    "pct_material_cooperation": "Material cooperation",
    "pct_verbal_conflict": "Verbal conflict",
    "pct_material_conflict": "Material conflict",
}


def weighted_mean(frame, col):
    return (frame[col] * frame["events"]).sum() / frame["events"].sum()


def combine_countries(frame):
    """One row per date across all countries in `frame`: summed events, event-weighted metrics."""
    return frame.groupby("event_date").apply(
        lambda day: pd.Series(
            {"events": day["events"].sum(), **{col: weighted_mean(day, col) for col in WEIGHTED_METRICS}}
        )
    )


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

with st.expander("About the data"):
    st.markdown(
        """
- **Source**: [GDELT](https://www.gdeltproject.org/) event records, refreshed weekly via dbt on BigQuery.
- **Country** means the country a news source's coverage *focuses on*, from GDELT's 2015 domains-by-country
  crosswalk, not where the publisher is based or where the event happened.
- The crosswalk is skewed: about 38% of its sources are US-focused, so treat cross-country comparisons of
  volume with care. About 83% of events match a known domain; the rest are excluded.
- **Tone** ranges from −100 (very negative) to 100 (very positive); in practice most values sit just below zero.
- **Goldstein scale** ranges from −10 (most destabilising) to 10 (most cooperative) — the theoretical impact of
  the event type, not of the specific article.
- **Quad class** buckets events into verbal/material cooperation and verbal/material conflict.
"""
    )

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
    key="countries",
    bind="query-params",
)

metric = st.selectbox(
    "Metric",
    options=list(METRIC_LABELS),
    format_func=METRIC_LABELS.get,
    index=0,
    key="metric",
    bind="query-params",
)

smooth = st.toggle(
    "7-day rolling average",
    help="Smooths day-to-day noise; averages are weighted by event count.",
    key="smooth",
    bind="query-params",
)

if not selected_countries:
    st.info("Select at least one country to see the chart.")
    st.stop()

selected = df[df["country"].isin(selected_countries)]

# KPI row: last 7 days vs the 7 before, all selected countries combined
daily = combine_countries(selected)
last_date = daily.index.max()
last_week = daily[daily.index > last_date - pd.Timedelta(days=7)]
prev_week = daily[
    (daily.index > last_date - pd.Timedelta(days=14)) & (daily.index <= last_date - pd.Timedelta(days=7))
]
sparkline = daily[daily.index > last_date - pd.Timedelta(days=56)]

st.subheader("Last 7 days, selected countries")
with st.container(horizontal=True):
    events_now, events_prev = last_week["events"].sum(), prev_week["events"].sum()
    st.metric(
        "Events",
        f"{events_now:,.0f}",
        f"{(events_now / events_prev - 1) * 100:+.1f}% vs prior week",
        border=True,
        chart_data=sparkline["events"],
    )
    for col, fmt, delta_color in [
        ("avg_tone", "{:.2f}", "normal"),
        ("avg_goldstein", "{:.2f}", "normal"),
        ("pct_material_conflict", "{:.1f}%", "inverse"),
    ]:
        now, prev = weighted_mean(last_week, col), weighted_mean(prev_week, col)
        st.metric(
            METRIC_LABELS[col],
            fmt.format(now),
            f"{now - prev:+.2f} vs prior week",
            delta_color=delta_color,
            border=True,
            chart_data=sparkline[col],
        )

chart_df = selected
if smooth:
    chart_df = (
        selected.groupby("country")[["event_date", "events", *WEIGHTED_METRICS]]
        .apply(rolling_7d)
        .reset_index(level="country")
        .dropna(subset=["events"])
    )
smooth_suffix = " · 7-day avg" if smooth else ""

with st.container(border=True):
    st.subheader("Trend by country")
    chart = (
        alt.Chart(chart_df)
        .mark_line()
        .encode(
            x=alt.X("event_date:T", title="Date"),
            y=alt.Y(f"{metric}:Q", title=METRIC_LABELS[metric] + smooth_suffix),
            color=alt.Color("country:N", title="Country"),
            tooltip=["country", "event_date", alt.Tooltip(f"{metric}:Q", format=".2f")],
        )
        .properties(height=450)
        .interactive()
    )
    st.altair_chart(chart)

with st.container(border=True):
    st.subheader("Event mix by quad class")
    composition_country = st.selectbox(
        "Country", options=selected_countries, key="mix_country", bind="query-params"
    )
    composition = (
        chart_df[chart_df["country"] == composition_country]
        .melt(
            id_vars="event_date",
            value_vars=list(QUAD_CLASS_LABELS),
            var_name="quad_class",
            value_name="pct",
        )
        .assign(quad_class=lambda d: d["quad_class"].map(QUAD_CLASS_LABELS))
    )
    area = (
        alt.Chart(composition)
        .mark_area()
        .encode(
            x=alt.X("event_date:T", title="Date"),
            y=alt.Y("pct:Q", stack=True, title="% of events" + smooth_suffix, scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "quad_class:N",
                title="Quad class",
                sort=list(QUAD_CLASS_LABELS.values()),
                scale=alt.Scale(domain=list(QUAD_CLASS_LABELS.values()), range=["#4c9be8", "#1f5fa8", "#f0a35e", "#c8382c"]),
            ),
            order=alt.Order("quad_class_order:Q"),
            tooltip=["event_date:T", "quad_class:N", alt.Tooltip("pct:Q", format=".1f")],
        )
        .transform_calculate(
            quad_class_order=f"indexof({list(QUAD_CLASS_LABELS.values())}, datum.quad_class)"
        )
        .properties(height=350)
    )
    st.altair_chart(area)
