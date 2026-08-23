{{ config(materialized='table') }}

WITH base as (
  SELECT * 
  FROM {{ ref('silver_event_checkpoints') }}
),

day1 as (
  SELECT quad_class, count(*) as n_events_1, 
  sum(hit_day1) as n_hit_1
  FROM base
  WHERE eligible_day1
  GROUP BY quad_class
),

day7 as (
  SELECT quad_class, count(*) as n_events_7, 
  sum(hit_day7) as n_hit_7
  FROM base
  WHERE eligible_day7
  GROUP BY quad_class
),

day30 as (
  SELECT quad_class, count(*) as n_events_30, 
  sum(hit_day30) as n_hit_30
  FROM base
  WHERE eligible_day30
  GROUP BY quad_class
)

SELECT
  d1.quad_class,
  d1.n_events_1,
  round(safe_divide(d1.n_hit_1, d1.n_events_1) * 100, 2) as pct_day1,
  d7.n_events_7,
  round(safe_divide(d7.n_hit_7, d7.n_events_7) * 100, 2) as pct_day7,
  d30.n_events_30,
  round(safe_divide(d30.n_hit_30, d30.n_events_30) * 100, 2) as pct_day30
FROM day1 d1
LEFT JOIN day7 d7 
USING (quad_class)
LEFT JOIN day30 d30 
USING (quad_class)
ORDER BY d1.quad_class