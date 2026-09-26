# GDELT Analysis

A dbt + BigQuery data platform built on GDELT (global news event) data, with a public Streamlit dashboard. Started as a single analysis, now an evolving platform — no fixed roadmap; data sources and dashboard views are added incrementally.

## Structure

- `gdelt_attention/` — dbt project. BigQuery project `open-intel-377412`, dev dataset `gdelt_dbt_dev`.
- `dashboard/` — Streamlit app reading from BigQuery gold tables, deployed on Streamlit Community Cloud. Own venv, own `requirements.txt` — never share dependencies with the dbt project.
- `.github/workflows/` — weekly scheduled `dbt build` via a dedicated `dbt-ci` service account.

## Conventions

- **Layers**: `bronze` (raw, filtered from GDELT's public tables, always partition-filtered) → `silver` (joined/cleaned) → `gold` (aggregated, dashboard-ready).
- **Materialization**: anything read more than once (silver, gold) should be `materialized='table'`. Views re-run their full query, including joins, on every read.
- **Joins**: always explicit — `inner join` / `left join`, never bare `join`.
- **Time-dependent metrics**: anything measuring "did X happen within N days of an event" needs an eligibility/censoring check — don't compute it over events too recent to have had the chance yet. See existing checkpoint-survival models for the pattern.
- **Gold model shape**: prefer long/tidy format (one row per dimension × metric) over wide columns — charts and dashboards want this shape.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`), small and frequent.
- **Credentials**: never committed. Service account keys go straight into a secrets manager (`gh secret set`, Streamlit Cloud's secrets UI) and get deleted locally right after.

## Current state

Bronze/silver/gold pipeline live, weekly CI/CD refresh working, country-domain mapping and a country-level "news pulse" gold table built, Streamlit dashboard deployed. No published write-up yet.

- **Commits**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs`), imperative mood, small and frequent. Do not add "Generated with Claude Code," "Co-Authored-By," or any session-link trailer to commit messages — clean commits only.