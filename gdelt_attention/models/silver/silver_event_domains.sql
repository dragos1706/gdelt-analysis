{{ config(materialized='table') }}

WITH domains AS (
    SELECT 
        event_id,
        NET.REG_DOMAIN(source_url) AS matched_domain
    FROM {{ ref('bronze_events') }}
    WHERE source_url IS NOT NULL
)

SELECT 
    d.event_id,
    d.matched_domain,
    c.CountryHumanName AS country
FROM domains d
INNER JOIN {{source('gdelt', 'domainsbycountry_alllangs_april2015')}} c
ON LOWER(d.matched_domain) = LOWER(c.Domain)