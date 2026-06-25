-- Load curated Gold freshness metrics from a Snowflake internal stage.
-- Example workflow:
-- 1. Export Databricks/Spark gold output as Parquet.
-- 2. PUT files into @MISSION_OPS_GOLD_STAGE using SnowSQL or a managed integration.
-- 3. Run this COPY statement.
-- The transformed SELECT maps lower-case Parquet field names produced by the Spark Gold dataframe.
-- Use explicit transformed field projection because this load reads nested Parquet values.

USE DATABASE MISSION_OPS_LITE;
USE SCHEMA OLAP;

COPY INTO GOLD_ORBIT_FRESHNESS_METRICS (
  METRIC_DATE,
  SOURCE_NAME,
  FRESHNESS_STATUS,
  QUALITY_STATUS,
  SATELLITE_COUNT,
  AVG_EPOCH_AGE_HOURS,
  MIN_EPOCH_AGE_HOURS,
  MAX_EPOCH_AGE_HOURS
)
FROM (
  SELECT
    $1:metric_date::DATE,
    $1:source_name::VARCHAR,
    $1:freshness_status::VARCHAR,
    $1:quality_status::VARCHAR,
    $1:satellite_count::NUMBER,
    $1:avg_epoch_age_hours::FLOAT,
    $1:min_epoch_age_hours::FLOAT,
    $1:max_epoch_age_hours::FLOAT
  FROM @MISSION_OPS_GOLD_STAGE/gold_orbit_freshness_metrics/
)
FILE_FORMAT = (FORMAT_NAME = MISSION_OPS_PARQUET_FORMAT);
