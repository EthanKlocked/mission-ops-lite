-- Example OLAP queries over curated Gold metrics.

USE DATABASE MISSION_OPS_LITE;
USE SCHEMA OLAP;

-- Freshness distribution by ingestion date.
SELECT
  metric_date,
  freshness_status,
  SUM(satellite_count) AS satellite_count
FROM GOLD_ORBIT_FRESHNESS_METRICS
GROUP BY metric_date, freshness_status
ORDER BY metric_date, freshness_status;

-- Data quality distribution for source records.
SELECT
  metric_date,
  quality_status,
  SUM(satellite_count) AS satellite_count,
  ROUND(AVG(avg_epoch_age_hours), 2) AS avg_epoch_age_hours
FROM GOLD_ORBIT_FRESHNESS_METRICS
GROUP BY metric_date, quality_status
ORDER BY metric_date, quality_status;

-- Executive-style freshness KPI.
SELECT
  metric_date,
  SUM(CASE WHEN freshness_status = 'fresh' THEN satellite_count ELSE 0 END) AS fresh_satellites,
  SUM(CASE WHEN freshness_status = 'stale' THEN satellite_count ELSE 0 END) AS stale_satellites,
  SUM(CASE WHEN freshness_status = 'unknown' THEN satellite_count ELSE 0 END) AS unknown_satellites,
  SUM(satellite_count) AS total_satellites
FROM GOLD_ORBIT_FRESHNESS_METRICS
GROUP BY metric_date
ORDER BY metric_date DESC;
