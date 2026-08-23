{{ config(materialized='table') }}

SELECT
  GlobalEventID AS event_id,
  PARSE_DATE('%Y%m%d', cast(SQLDATE AS string)) AS event_date,
  DATEADDED AS date_added_raw,
  EventRootCode AS root_code,
  EventBaseCode AS base_code,
  QuadClass AS quad_class,
  GoldsteinScale AS goldstein_scale,
  AvgTone AS avg_tone,
  NumMentions AS num_mentions,
  NumSources AS num_sources,
  NumArticles AS num_articles

FROM {{ source('gdelt', 'events_partitioned') }}
WHERE _PARTITIONTIME >= timestamp('2026-06-01')