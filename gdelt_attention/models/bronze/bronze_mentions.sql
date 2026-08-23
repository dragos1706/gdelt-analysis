{{ config(materialized='table') }}

SELECT
  GlobalEventID AS event_id,
  DATE(parse_datetime('%Y%m%d%H%M%S', CAST(MentionTimeDate AS string))) AS mention_date,
  MentionSourceName AS source_name,
  MentionDocTone AS doc_tone,
  Confidence AS confidence

FROM {{ source('gdelt', 'eventmentions_partitioned') }}
WHERE _PARTITIONTIME >= timestamp('2026-06-01')