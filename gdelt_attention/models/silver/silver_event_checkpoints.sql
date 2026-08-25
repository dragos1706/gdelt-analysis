{{ config(materialized='table') }}

WITH checkpoint_flags as (
  SELECT
    e.event_id,
    e.event_date,
    e.root_code,
    e.base_code,
    e.quad_class,
    e.goldstein_scale,
    e.avg_tone,
    max(coalesce(date_diff(m.mention_date, e.event_date, day), 0)) as days_survived,
    date_diff(current_date(), e.event_date, day) as event_age_days,
    max(if(date_diff(m.mention_date, e.event_date, day) = 1, 1, 0))  as hit_day1,
    max(if(date_diff(m.mention_date, e.event_date, day) = 7, 1, 0))  as hit_day7,
    max(if(date_diff(m.mention_date, e.event_date, day) = 30, 1, 0)) as hit_day30,
    max(if(date_diff(m.mention_date, e.event_date, day) >= 1, 1, 0))  as surv_day1,
    max(if(date_diff(m.mention_date, e.event_date, day) >= 7, 1, 0))  as surv_day7,
    max(if(date_diff(m.mention_date, e.event_date, day) >= 30, 1, 0)) as surv_day30,
  FROM {{ ref('bronze_events') }} e
  LEFT JOIN {{ ref('bronze_mentions') }} m 
  ON e.event_id = m.event_id
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)

SELECT
  *,
  event_age_days >= 1  as eligible_day1,
  event_age_days >= 7  as eligible_day7,
  event_age_days >= 30 as eligible_day30
FROM checkpoint_flags