# Databricks notebook source
# MAGIC %md
# MAGIC # Silver transform — normalized orbit snapshots
# MAGIC Casts analytical types, removes duplicate satellite/epoch rows, and labels freshness/quality.

# COMMAND ----------

from mission_ops_lite.data_platform.medallion import build_silver_orbit_snapshots

BRONZE_TABLE = "mission_ops.bronze.orbit_records"
SILVER_TABLE = "mission_ops.silver.orbit_snapshots"

bronze_df = spark.read.table(BRONZE_TABLE)
silver_df = build_silver_orbit_snapshots(bronze_df)

silver_df.write.mode("overwrite").saveAsTable(SILVER_TABLE)
display(silver_df.limit(20))
