{{ config(materialized='table') }}

WITH base as (
  SELECT * 
  FROM {{ ref('silver_event_checkpoints') }}
),

day1 as (
  SELECT quad_class, count(*) as n_events, sum(hit_day1) as n_hit
  FROM base
  WHERE eligible_day1
  GROUP BY quad_class
),

day7 as (
  SELECT quad_class, count(*) as n_events, sum(hit_day7) as n_hit
  FROM base
  WHERE eligible_day7
  GROUP BY quad_class
),

day30 as (
  SELECT quad_class, count(*) as n_events, sum(hit_day30) as n_hit
  FROM base
  WHERE eligible_day30
  GROUP BY quad_class
),

combined as (
  SELECT quad_class, 1  as checkpoint_day, n_events, n_hit 
  FROM day1
  UNION ALL
  SELECT quad_class, 7  as checkpoint_day, n_events, n_hit 
  FROM day7
  UNION ALL
  SELECT quad_class, 30 as checkpoint_day, n_events, n_hit 
  FROM day30
)

SELECT
  quad_class,
  CASE quad_class
    WHEN 2 THEN 'Material cooperation'
    WHEN 1 THEN 'Verbal cooperation'
    WHEN 3 THEN 'Verbal conflict'
    WHEN 4 THEN 'Material conflict'
  END as quad_class_label,
  checkpoint_day,
  n_events,
  round(safe_divide(n_hit, n_events) * 100, 2) as pct_covered
FROM combined
ORDER BY quad_class, checkpoint_day