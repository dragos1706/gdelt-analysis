# Exploring the GDELT Dataset and Documentation

My initial intention is to analyse the news as I start this project. I've been meaning to do it for a while, ever since I learned about GDELT a few years ago. 

Assessing news longevity (which types of events are more likely to be mentioned) seems like a sensible place to start. News events are categorised in different ways, such as whether they involve cooperation or conflict, or how positively or negatively a given event is reported by the media. Seeing how these factors influence how long a news event is mentioned is a great way to understand news behaviour and explore the GDELT data.

But these news categories, together with additional factors such as how many times or how many different sources have mentioned a given event, can yield further insights. Its public availability in BigQuery makes it even more enticing. 


All the info and documentation about the GDELT project can be found on [their website](https://www.gdeltproject.org/).  This is the context in which I start exploring the data.

## Getting to know the data
There are two main tables I am interested in - the events table and the mentions table. The events table contains summarised information about news events it has identified. The mentions table contains detailed information on how often events were mentioned across publications on different dates. 

I’m starting this analysis by making sure I understand the data well enough before proceeding. This involves reading through the documentation and querying the data in BQ. Worth noting that both tables are also available as [partitioned tables](https://docs.cloud.google.com/bigquery/docs/partitioned-tables). Both tables are partitioned on a field named _PARTITIONTIME. To keep my query costs low, I will work with them instead of the unpartitioned versions.

I’ll start with the events table. 

### The Events table
The GDELT events table has many fields. To minimise BQ usage and costs, I reviewed the documentation to identify fields that could be useful for this analysis, as follows:

- DATEADDED (the date the event was added to the master database in YYYYMMDDHHMMSS format in the UTC timezone),
- Day,
- GlobalEventID, 
- Actor1Code,
- Actor1_Name,
- Actor2Code,
- Actor2_Name,
- EventCode (raw CAMEO action code), 
- EventBaseCode,
- EventRootCode,
- QuadClass (1=Verbal Cooperation, 2=Material Cooperation, 3=Verbal Conflict, 4=Material Conflict),
- GoldsteinScale (theoretical potential impact that type of event will have on the stability of a country, ranging from -10 to 10; based on the type of event, not the specifics of the actual event),
- NumMentions (total number of mentions of this event across all source
documents during the 15-minute update in which it was first seen. Multiple references to an event within a single document also contribute to this count. Can be used as a proxy for importance)
- NumSources (This is the total number of information sources containing one or more
mentions of this event during the 15-minute update in which it was first seen. ),
- NumArticles (This is the total number of source documents containing one or more
mentions of this event during the 15-minute update in which it was first seen. )
- AvgTone (average “tone” of all documents containing one or more mentions of this event during the 15-minute update in which it was first seen; from -100 to 100).

#### data checks
I ran this query to check whether GLOBALEVENTID appears more than once in the events table.

```
WITH tbl1 AS(
        SELECT GlobalEventID,
        	DATEADDED,
        FROM `gdelt-bq.gdeltv2.events_partitioned` 
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND 			TIMESTAMP("2026-06-06")
	)
SELECT COUNT(*), COUNT(DISTINCT GlobalEventID)
FROM tbl1
```

It doesn't seem to. I got 1010317 counts for both. 

Through some follow-up queries, I realised that the partitioning is based on SQLDATE rather than DATEADDED. The SQLDATE is the date on which the event actually took place, as per GDELT documentation. This was most clearly evidenced by the following query:
```
SELECT
  DATE(_PARTITIONTIME) AS part_date,
  COUNT(*) AS n,
  ROUND(COUNTIF(PARSE_DATE('%Y%m%d', CAST(SQLDATE AS STRING))
                = DATE(_PARTITIONTIME)) / COUNT(*), 4) AS pct_matches_sqldate,
  ROUND(COUNTIF(DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING)))
                = DATE(_PARTITIONTIME)) / COUNT(*), 4) AS pct_matches_dateadded
FROM `gdelt-bq.gdeltv2.events_partitioned`
WHERE _PARTITIONTIME BETWEEN TIMESTAMP('2026-06-01') AND TIMESTAMP('2026-06-03')
GROUP BY 1
ORDER BY 1

```
Which rendered the following results:
| Row | part_date | n | pct_matches_sqldate | pct_matches_dateadded |
| --- | --- | --- | --- | --- |
|1	|2026-06-01|	164925	|1.0|	0.9881|
|2	|2026-06-02|	184547	|1.0|	0.9895|
|3	|2026-06-03|	186754	|1.0|	0.9882	|

Next, I asked myself how the DATEADDED and SQLDATE differ in aggregate. They were supposed to be added on the same day in most instances.

So I ran the query below (with a couple of different dates for _PARTITIONTIME). ALL differences were either 1, 7, 30 or 365 days later. At no point was there a negative difference between DATEADDED and _PARTITIONTIME. 

```
SELECT
  DATE(_PARTITIONTIME) AS part_date,
  DATE_DIFF(DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING))), DATE(_PARTITIONTIME), DAY) diff_dateadded,
  COUNT(DATE_DIFF(DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING))), DATE(_PARTITIONTIME), DAY)) cnt
FROM `gdelt-bq.gdeltv2.events_partitioned`
WHERE _PARTITIONTIME BETWEEN TIMESTAMP('2023-06-01') AND TIMESTAMP('2023-06-10')
AND DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING))) != DATE(_PARTITIONTIME)
GROUP BY DATE(_PARTITIONTIME), diff_dateadded
ORDER BY 1
```

The table below illustrates one such extract:

| Row | part_date  | diff_dateadded | cnt  |   |
|-----|------------|----------------|------|---|
| 1   | 2023-06-01 | 7              | 1393 |   |
| 2   | 2023-06-01 | 1              | 866  |   |
| 3   | 2023-06-01 | 365            | 1480 |   |
| 4   | 2023-06-01 | 30             | 352  |   |
| 5   | 2023-06-02 | 1              | 485  |   |

This seems to be part of how data is processed (the mechanics), and there's no clear documentation about it, as far as I could see. The best I can come up with is that some events are reordered or added at a later stage as part of the data-processing flows. 

I ran one last query just to check how these mismatches are spread:
```
WITH parsed AS (
  SELECT
    DATE(_PARTITIONTIME) AS part_date,
    DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING))) AS added_date
  FROM `gdelt-bq.gdeltv2.events_partitioned`
  WHERE _PARTITIONTIME BETWEEN TIMESTAMP('2023-06-01') AND TIMESTAMP('2023-06-10')
)
SELECT
  DATE_DIFF(added_date, part_date, DAY) AS lag_days,
  COUNT(*) AS n,
  ROUND(COUNT(*) / SUM(COUNT(*)) OVER (), 5) AS share_of_all
FROM parsed
GROUP BY lag_days
ORDER BY n DESC
```
And got the following result:

| Row | lag_days | n       | share_of_all |
|-----|----------|---------|--------------|
| 1   | 0        | 2041070 | 0.98008      |
| 2   | 7        | 12299   | 0.00591      |
| 3   | 365      | 11911   | 0.00572      |
| 4   | 30       | 9841    | 0.00473      |
| 5   | 1        | 7423    | 0.00356      |

This is the best I can guess so far, though I'm unsure whether it will impact my analysis. 

### The Mentions table
This is the big one. It contains every individual mention identified for a given GlobalEventId.So an event that's been mentioned in 100 articles will appear 100 times in this table. As per documentation, mentions "are recorded irrespective of the date of the original event, meaning that a mention today of an event from a year ago will still be recorded, making it possible to trace discussion of “anniversary events” or historical events being recontextualized into present actions. If a news report mentions multiple events, each
mention is recorded separately in this table". 

As before, I'll first go through the documentation so select the fields I think would be of interest: 

- GlobalEventID,
- EventTimeDate (This is the 15-minute timestamp (YYYYMMDDHHMMSS) when the event being mentioned was first recorded by GDELT (the DATEADDED field of the original event record). Unsure how useful it is given that I'm more interested in the date the event was first mentioned, rather than when it was first captured by GDELT, but I'm adding it here),
- MentionTimeDate (This is the 15-minute timestamp (YYYYMMDDHHMMSS) of the *current update*)
- Confidence (Per cent confidence in extracting an event from an article. The language used in news articles is often ambiguous, making it difficult to link an article to a specific event. It could be useful to filter out event mentions with low confidence.)
- MentionDocTone (The same contents as the AvgTone field in the Events table, but
computed for this particular article)

#### data checks
This table is also partitioned on _PARTITIONTIME, similar to the event table. So again, the question of which field the data is partitioned on comes to mind. I am presuming EventTimeDate. I ran the query below, and indeed I got a ratio of 1.0 across the board. So I'm assuming that the partition is based on EventTimeDate. For the EventMentionDate, I got matches above 99%, which is high, but never a 1. 

```
 SELECT DATE(_PARTITIONTIME) AS part_date,
         COUNT(*) AS n,
         ROUND(COUNTIF(DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(EventTimeDate AS STRING)))
                = DATE(_PARTITIONTIME)) / COUNT(*), 4) AS pct_matches_event_time_date,

        ROUND(COUNTIF(DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(MentionTimeDate AS STRING)))
                = DATE(_PARTITIONTIME)) / COUNT(*), 4) AS pct_matches_mention_time_date

  FROM `gdelt-bq.gdeltv2.eventmentions_partitioned` 
  WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND 			TIMESTAMP("2026-06-06")
  GROUP BY DATE(_PARTITIONTIME)
  ORDER BY DATE(_PARTITIONTIME)
```

The next question that comes to mind is how the quantity of unique events identified in the events and the evenementions tables differs. Since the event table was partitioned on SQLDATE and the eventmentions table on DATEADDED/EventTimeDate, I expect there'll be some mismatch. SQLDATE identifies the date the event occurred, while DATEADDED/EventTimeDate is the date the event was first registered by GDELT. 
Running:
```
WITH tbl1 AS(
        SELECT GlobalEventID,
        FROM `gdelt-bq.gdeltv2.eventmentions_partitioned` 
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND TIMESTAMP("2026-06-06")
	)
SELECT COUNT(*) event_mentions, 
       COUNT(DISTINCT GlobalEventID) unique_events,
       COUNT(*)/COUNT(DISTINCT GlobalEventID) ratio
FROM tbl1
```

Gave:

| Row | event_mentions | unique_events | ratio              |
|-----|----------------|---------------|--------------------|
| 1   | 2435707        | 1016776       | 2.3955197604978875 |
|     |                |               |                    |

Over the same _PARTITIONTIME, the events table has 1010317 unique events, whereas the eventmentions table has 1016776, or 6459 more. Since the data is updated every 15 minutes, the mismatch shouldn't be large, and indeed it isn't. However, it's worth noting that some events might be reported at specific times of the day (e.g., due to their "breaking news" effect), and in that sense, the mismatch isn't random. I'll leave this as a limitation.

### Joining and examining the two tables together

Some notes on what I'd like to check and my current thinking:
- There should be no EventTimeDate (eventmentions table) before a SQLDATE (events table) for a given event ID. This is because SQLDATE is the date the event was first reported, while EventTimeDate is the date the event (mention) was captured. 
- Over the same _PARTITIONTIME, what percentage of unique EventID's match across the two tables? 
- I can use the events table _PARTITIONTIME to generate the window of new events I'd like to observe, and the eventmentions table _PARTITIONTIME to generate the period over which I'd like to observe those new events, provided that the earliest date used in both tables is the same. 

To check how many of the eventIDs matched between the two tables, I ran:

```
WITH tbl1 AS(
        SELECT DISTINCT GlobalEventID eventID,
        FROM `gdelt-bq.gdeltv2.events_partitioned` 
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND TIMESTAMP("2026-06-06")
	),

  tbl2 AS (
        SELECT DISTINCT GlobalEventID mentionID,
        FROM `gdelt-bq.gdeltv2.eventmentions_partitioned` 
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND TIMESTAMP("2026-06-06")
  )
  SELECT COUNT(eventID),
         COUNT(mentionID),
         COUNTIF (eventID = mentionID) matching,
         ROUND(COUNTIF (eventID = mentionID)/COUNT(eventID), 4) pct_matching_events,
         ROUND(COUNTIF (eventID = mentionID)/COUNT(mentionID), 4) pct_matching_mentions
  FROM tbl1
  FULL JOIN tbl2 ON tbl1.eventID = tbl2.mentionID
```
With the following results:

| Row | f0_     | f1_     | matching | pct_matching_events | pct_matching_mentions |
|-----|---------|---------|----------|---------------------|-----------------------|
| 1   | 1010317 | 1016776 | 1002433  | 0.9922              | 0.9859                |


Next, I want to test my "no mentions of an event before its SQLDATE (i.e. date of first occurrence)" hypothesis. I ran this query (and a few others, for sanity's sake):

```
WITH tbl1 AS(
        SELECT GlobalEventID eventID,
               DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING))) date_added,
               PARSE_DATE('%Y%m%d', CAST(SQLDATE AS STRING)) sql_date,
               AvgTone avg_tone,
               GoldsteinScale goldstein_scale,
               EventRootCode root_code,
               EventBaseCode base_code,
               QuadClass quad_class
        FROM `gdelt-bq.gdeltv2.events_partitioned` 
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND TIMESTAMP("2026-06-02")
	),

  tbl2 AS (
        SELECT GlobalEventID mentionID,
               DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(EventTimeDate AS STRING))) date_added,
               DATE(PARSE_DATETIME('%Y%m%d%H%M%S', CAST(MentionTimeDate AS STRING))) date_mentioned,
               Confidence confidence
        FROM `gdelt-bq.gdeltv2.eventmentions_partitioned`
        WHERE TIMESTAMP_TRUNC(_PARTITIONTIME, DAY) BETWEEN TIMESTAMP("2026-06-01") AND TIMESTAMP("2026-06-02")
  )

  SELECT tbl1.sql_date,
       tbl2.date_mentioned,
         DATE_DIFF(tbl2.date_mentioned, tbl1.sql_date, DAY) date_diff,
         COUNT(DATE_DIFF(tbl2.date_mentioned, tbl1.sql_date, DAY)) num_obs,


  FROM tbl1
  JOIN tbl2 ON tbl1.eventID = tbl2.mentionID
  GROUP BY tbl1.sql_date, tbl2.date_mentioned
```
To get the following results:
| Row | sql_date   | date_mentioned | date_diff | num_obs |
|-----|------------|----------------|-----------|---------|
| 1   | 2026-06-01 | 2026-06-02     | 1         | 1136    |
| 2   | 2026-06-01 | 2026-06-01     | 0         | 382569  |
| 3   | 2026-06-01 | 2026-06-08     | 7         | 476     |
| 4   | 2026-06-01 | 2026-07-01     | 30        | 268     |
| 5   | 2026-06-02 | 2026-06-09     | 7         | 725     |
| 6   | 2026-06-02 | 2026-06-02     | 0         | 456722  |
| 7   | 2026-06-02 | 2026-07-02     | 30        | 438     |
| 8   | 2026-06-02 | 2026-06-03     | 1         | 379     |

At this point, I am thoroughly confused. I was expecting the dates for the event mentions to be much more evenly spaced. Instead, for each SQLDATE (which represents the date on which an event actually took place), the mention dates are truncated around 0, 1, 7, and 30 days. I ran a similar query comparing the DATEADDED field in the events table with the date mentioned, and the same pattern emerges. Also when I compared EventTimeDate and MentionTimeDate.

I can only assume this is due to computational limitations and that the event mentions are binned accurately and accordingly. 

I conclude my exploration here, noting that I will left join with the events table on the left.

## PS: Domains by Country Table
There's one more dataset worth mentioning - the Domains by Country one - which aims to estimate the country of origin of various online news outlets. This estimation isn't based on the domain. Instead, GDELT estimates a country's status based on news coverage. If CNN.com mostly covers news about the US, for example, it gets labelled as a US publication. 

This method has its limitations. The GDELT authors do mention that "who.int" was assigned to Guinea, for example, because WHO has focused a large volume of its news coverage thus far this year on the Ebola outbreak in Guinea. The documentation is available [here](https://blog.gdeltproject.org/announcing-new-source-country-crossreferencing-dataset/).

As of the end of August 2026, the dataset identifies 32790 sources. It identifies sources across 216 countries. However, the sources are skewed, with the US accounting for 12331 (38%), followed by Italy (4.6%), the UK (4.5%), China (3.1%), Canada (2.5%), France (2.2%), and Russia (2.1%). 18 countries have a single source.

### Joining it with the events table
The two tables can be joined based on the domain. The events table has the SOURCEURL field, which contains the domain. I wrote a regex query to extract the domain and the subdomain when included. But I couldn't find a way to extract the domain when subdomains were involved. For example, I cannot extract yahoo.com for an article published on the finance.yahoo.com subdomain.

Since the Domains by Country tables were last updated in 2015, I will use a short Python script to extract the registrable domains, upload them, and treat them as static. More on this later though, as I haven't decided to implement it yet. 

# Queries and pipeline
As mentioned above, I want to analyse news longevity. That is, what types of events are likely to be mentioned more often. I'll use the `events` table to filter out a window over which events are observed and obtain their characteristics, such as whether a reported event involved cooperation or conflict. I'll use the `mentions` table to figure out the frequency of mentions. 

In this section I describe the pipeline setup and queries used. 

## Pipeline setup

I used dbt to create a "bronze", "silver", and "gold" layer of the GDELT data. In the first layer, I select the relevant subset of data (fields and period observed). In the silver layer, I join the tables with the necessary pre-calculations. In the gold layer, I create light summary tables that can serve as a source for continuous analysis. 

Note that I haven't yet decided how or how often I'll refresh (which data), so I might need to modify some of the layers below as I go. 

And, since the queries used for the dbt pipeline are visible in the code, I won't add them all in here. Instead, I describe each of them briefly. As the project progresses, I'll adjust the documentation to keep it up to date. 

### Bronze layer
This layer is the simplest. I add the data from the `events` and `mentions` tables as two separate tables. Both are filtered to include only data from 01 June 2026 onwards. I include several columns that I think might be useful now or in the future. A largely speculative decision on my part. 

### Silver layer
This is where I left-join the `events` and `mentions` tables into a single table and model. What's noteworthy:

Since I plan to analyse news events' "longevity", I need to consider how fresh the event is. If an event occurred a week ago, for example, it would be incorrect to count it as an event that didn't survive past a week - we don't know that yet. As such, I create the following event indicators that tell something about how long an event has been around, as illustrated:

```
date_diff(current_date(), e.event_date, day) as event_age_days,
max(if(date_diff(m.mention_date, e.event_date, day) = 7, 1, 0))  as hit_day7,
max(if(date_diff(m.mention_date, e.event_date, day) >= 7, 1, 0))  as surv_day7
```

`event_age_days` simply computes how old an event is compared to the date the data was refreshed. I use this field to filter out ineligible events.

Before I explain the next two, keep in mind that GDELT bins mentions of an event into 1-, 7-, or 30-day buckets. That is, if an event was mentioned 3 days after it first appeared, the mention date would be captured as 7 days after. If it was mentioned 12 days after, the mention date would be allocated to the 30-day bin.

`hit_day_7` captures whether an event was mentioned exactly 7 days after it appeared (0 or 1). I also created similar indicators for the 1- and 30-day bins (i.e. `hit_day_1` and `hit_day_30`).

`surv_day7` captures whether an event was mentioned 7 days *or earlier* after it first appeared (0 or 1). Here, I also created indicators for the 1- and 30-day bins (i.e. `surv_day_1` and `surv_day_30`).

Altogether, I'll use these "special" fields further down the flow to filter and count relevant data points, as follows. 

### Gold layer
I'm starting this analysis with a single table in the golden layer. 

The table calculates the percentage of *eligible* news events that were mentioned within 1, 7, or 30 days of their first appearance, grouped by Quad Class. It illustrates the relationship between an event's Quad Class and the likelihood that it'll be mentioned at some point in the future. 

An event is eligible for analysis if it was mentioned at least x days after it first appeared. So an event that was mentioned again at least once 7 or more days after it first appeared is eligible to be counted when calculating the percentage of events mentioned at least 7 days after they took place. 

The calculation thus becomes:
$$
percentageOfEventsOnDayX =
countOfEventsMentionedAfterExactlyXDays/countOfEventsMentionedOnDayXOrAfter
$$

So, the question it answers is: of all the news events mentioned at least once in the observed window, what percentage was mentioned within X days? And, to complicate things a bit further, the "within X days" part needs to be interpreted as within X days, but after the previous bucket. This is because GDELT places mentions of events that occurred within 1 day, between 2 and 7 days, and between 8 and 30 days (or more) into separate buckets. See my notes on the mentions table and on the silver layer above for further details.








