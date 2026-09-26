# GDELT Analysis

dbt pipelines that turn GDELT's global news event data (in BigQuery) into analysis-ready tables about how news events spread and where they come from, plus a public Streamlit dashboard on top of them.

**Live dashboard:** https://news-pulse.streamlit.app/

## Overview

This is a solo analytics-engineering project built on [GDELT](https://www.gdeltproject.org/) (the Global Database of Events, Language, and Tone), which continuously monitors news media worldwide and codes reported events into a structured dataset. The project asks two questions of that data:

1. **News longevity** — which kinds of events (cooperative vs. conflictual) keep getting mentioned in the days and weeks after they happen, and which fade quickly?
2. **Country-level news pulse** — by mapping each event's source article back to a country, what does the daily volume, tone, and composition of news coverage look like per country? This is the question the [dashboard](#dashboard) answers.

Both analyses run on the same [bronze/silver/gold](#architecture) dbt pipeline against BigQuery, refreshed automatically every week via GitHub Actions; the dashboard reads the refreshed gold tables directly.

## Architecture

The pipeline follows a bronze/silver/gold layering:

```
bronze_events ─┬─→ silver_event_checkpoints ──→ gold_checkpoint_coverage_by_quadclass
               ├─→ silver_event_domains ────────→ gold_news_by_country_date ──→ Streamlit dashboard
bronze_mentions┘
```

- **Bronze** — thin selects/renames off the raw GDELT BigQuery tables, filtered on a fixed start date (`_PARTITIONTIME >= '2026-06-01'`), so the window grows with each weekly refresh. No business logic, just a stable, minimal interface onto the source data.
- **Silver** — two independent enrichment tracks built on top of bronze:
  - `silver_event_checkpoints` joins events to their mentions and computes news-longevity indicators.
  - `silver_event_domains` maps each event's source URL to a country.
- **Gold** — one analysis-ready summary table per feature arc, aggregated and ready to query directly.

All models are explicitly materialized as `table` (the project default in `dbt_project.yml` is `view`, overridden per-model via `config()`).

## Data Sources

All source data comes from GDELT's public BigQuery dataset `gdelt-bq.gdeltv2` (declared in `gdelt_attention/models/staging/sources.yml` — a leftover folder name; there are no staging models, the project uses bronze/silver/gold throughout):

| Table | Contents |
|---|---|
| `events_partitioned` | One row per coded news event — actors, event type, tone, and impact scores. |
| `eventmentions_partitioned` | One row per mention of an event in a specific article, across the days/weeks after the event was first recorded. |
| `domainsbycountry_alllangs_april2015` | A static crosswalk mapping news-source domains to the country their coverage is estimated to focus on. |

For deeper reference, see:
- `GDELT documentation with my notes/GDELT-Event_Codebook-V2.0.pdf` — official GDELT field documentation.
- `GDELT documentation with my notes/CAMEO.Manual.1.1b3.pdf` — official CAMEO event-coding manual.
- `GDELT documentation with my notes/Project Notes & Decisions (detailed).md` — this project's own research log: exploratory queries, data-quality findings, and the reasoning behind design decisions.

## Model Reference

**Bronze**
- `bronze_events` — key event fields from `events_partitioned`: event id/date, event/root/base codes, quad class, Goldstein scale, average tone, mention/source/article counts, and the source article URL.
- `bronze_mentions` — key mention fields from `eventmentions_partitioned`: event id, mention date, source name, mention-level tone, and confidence.

**Silver**
- `silver_event_checkpoints` — joins events to their mentions and computes, at 1/7/30-day checkpoints: `days_survived`, `event_age_days`, exact-hit flags (`hit_day1/7/30`), cumulative-survival flags (`surv_day1/7/30`), and eligibility flags (`eligible_day1/7/30`, whether an event is old enough to be validly evaluated at that checkpoint yet). These specific buckets aren't arbitrary — GDELT's DATEADDED-to-partition lag clusters almost exclusively at 0/1/7/30/365 days, so those are the points where mention data is at its most complete.
- `silver_event_domains` — extracts the registrable domain from each event's source URL with BigQuery's `NET.REG_DOMAIN()`, then joins it to the domains-by-country crosswalk to attach a country to each event (~83% match rate).

**Gold**
- `gold_checkpoint_coverage_by_quadclass` — for each quad class × checkpoint (1/7/30 days), the share of eligible events that were still being mentioned at exactly that checkpoint (`pct_covered = count mentioned at exactly X days / count mentioned on day X or after`). Output is tidy/long (one row per quad_class × checkpoint_day).
- `gold_news_by_country_date` — daily, per-country rollup: event volume, average/stddev tone, average/stddev Goldstein scale, and the percentage composition of each quad class. This is the "country-level news pulse" table.

## Dashboard

[GDELT News Pulse](https://news-pulse.streamlit.app/) (`dashboard/app.py`) is a Streamlit app that reads `gold_news_by_country_date` straight from BigQuery and plots it as an interactive Altair line chart over time:

- **Countries** — multiselect, defaulting to the 8 countries with the most events.
- **Metric** — `avg_tone`, `avg_goldstein`, `events`, or `pct_material_conflict`.

Query results are cached for 7 days (`st.cache_data(ttl="7d")`), matching the weekly dbt refresh, so the app doesn't re-query BigQuery on every page load. It's hosted on Streamlit Community Cloud, which redeploys automatically on every push to `main`; BigQuery credentials come from a `gcp_service_account` entry in the app's Streamlit secrets.

## Data Quality Notes & Caveats

The highlights below are the ones that actually shaped the model design; the full derivation, exploratory queries, and additional findings live in `GDELT documentation with my notes/Project Notes & Decisions (detailed).md`.

- `events_partitioned` is partitioned on `SQLDATE` (the event's occurrence date), not `DATEADDED` — this is why the bronze filter targets a recent event-date window rather than a load-date window.
- The lag between `DATEADDED` and its partition clusters almost exclusively at 0, 1, 7, 30, or 365 days — GDELT effectively bins mention data into those buckets, which is the direct motivation for the 1/7/30-day checkpoints used in `silver_event_checkpoints`.
- ~99.2% of event IDs present in the events table also appear in the mentions table over the same window, so join coverage between the two isn't a major concern.
- The domain-to-country mapping is based on what country a source's *news coverage focuses on*, not where the domain is registered (e.g., `who.int` is mapped to Guinea because of its Ebola-outbreak coverage, not because WHO is Guinean). The crosswalk is static, last updated in 2015, and covers 32,790 sources across 216 countries — but is heavily skewed toward the US (~38% of sources). Treat country-level results as reflecting this bias, not a balanced global sample.
- `GoldsteinScale` ranges from -10 to 10 (theoretical impact of an event); `AvgTone` ranges from -100 to 100.

## Setup & Running Locally

Requires a BigQuery project you have access to. The dbt project and the dashboard use **separate** virtual environments and dependency lists — don't mix them. Both use [uv](https://docs.astral.sh/uv/).

**dbt pipeline**

```bash
cd gdelt_attention
uv venv --python 3.12
source .venv/bin/activate
uv pip install dbt-bigquery

# configure ~/.dbt/profiles.yml for the `gdelt_attention` profile,
# targeting your own BigQuery project/dataset (oauth or service-account auth)

dbt build   # or: dbt run / dbt test
```

**Dashboard**

```bash
cd dashboard
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

# put a service-account key under [gcp_service_account] in
# dashboard/.streamlit/secrets.toml (gitignored — never commit it)

streamlit run app.py
```

## CI/CD

`.github/workflows/dbt_weekly.yml` runs `dbt build` every Monday at 06:00 UTC (and on manual `workflow_dispatch`). It authenticates to BigQuery as a dedicated `dbt-ci` service account (`bigquery.dataEditor` + `bigquery.jobUser`, key stored as the `GCP_SA_KEY` repo secret) and writes to the `gdelt_dbt_dev` dataset. The refreshed gold tables are what the dashboard reads.

## Repo Structure

```
gdelt-analysis/
├── gdelt_attention/              # the dbt project
│   ├── models/{bronze,silver,gold}/
│   └── dbt_project.yml
├── dashboard/                    # Streamlit app (own venv)
│   ├── app.py
│   └── requirements.txt          # only what Streamlit Cloud needs to run app.py
├── GDELT documentation with my notes/   # official GDELT reference PDFs + this project's research log
└── .github/workflows/            # weekly CI refresh
```
