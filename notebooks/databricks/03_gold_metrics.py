# Databricks notebook source
# MAGIC %md
# MAGIC # Gold metrics — OLAP-ready freshness metrics
# MAGIC Produces a compact aggregate table that can be loaded into Snowflake for KPI/OLAP analysis.

# COMMAND ----------

from mission_ops_lite.data_platform.medallion import build_gold_freshness_metrics

SILVER_TABLE = "mission_ops.silver.orbit_snapshots"
GOLD_TABLE = "mission_ops.gold.orbit_freshness_metrics"

silver_df = spark.read.table(SILVER_TABLE)
gold_df = build_gold_freshness_metrics(silver_df)

gold_df.write.mode("overwrite").saveAsTable(GOLD_TABLE)
display(gold_df)
