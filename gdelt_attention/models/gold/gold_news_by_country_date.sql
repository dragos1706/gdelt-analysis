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
-- exclude the latest event_date in bronze: it's the load day (weekly CI runs Mon 06:00 UTC),
-- so only a partial day of events exists for it. Derived from the data, not CURRENT_DATE(),
-- so it stays correct when gold is rebuilt on a later day than bronze.
WHERE e.event_date < (SELECT MAX(event_date) FROM {{ ref('bronze_events') }})
GROUP BY d.country, e.event_date
ORDER BY d.country, e.event_date