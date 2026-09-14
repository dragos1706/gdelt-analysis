{{ config(materialized='table') }}

SELECT
    d.country,
    e.event_date,
    COUNT(*) AS events,
    ROUND(AVG(e.avg_tone), 3) AS avg_tone,
    ROUND(STDDEV(e.avg_tone), 3) AS stddev_tone,
    ROUND(AVG(e.goldstein_scale), 3) AS avg_goldstein,
    ROUND(STDDEV(e.goldstein_scale), 3) AS stddev_goldstein,

    ROUND(SAFE_DIVIDE(COUNTIF(e.quad_class = 1), COUNT(*)) * 100, 2) as pct_verbal_cooperation,
    ROUND(SAFE_DIVIDE(COUNTIF(e.quad_class = 2), COUNT(*)) * 100, 2) as pct_material_cooperation,
    ROUND(SAFE_DIVIDE(COUNTIF(e.quad_class = 3), COUNT(*)) * 100, 2) as pct_verbal_conflict,
    ROUND(SAFE_DIVIDE(COUNTIF(e.quad_class = 4), COUNT(*)) * 100, 2) as pct_material_conflict

FROM {{ ref('bronze_events') }} e
INNER JOIN {{ ref('silver_event_domains') }} d 
ON e.event_id = d.event_id
GROUP BY d.country, e.event_date
ORDER BY d.country, e.event_date