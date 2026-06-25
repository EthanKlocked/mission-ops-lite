# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze ingest — public CelesTrak orbit records
# MAGIC Lands source-shaped records with raw JSON and ingestion lineage.

# COMMAND ----------

from datetime import datetime, timezone
import json

from mission_ops_lite.data_platform.medallion import build_bronze_orbit_records

# In a Databricks workspace, `spark` is provided by the runtime.
# Upload or mount a JSON file containing CelesTrak active GP records, then set RAW_JSON_PATH.
RAW_JSON_PATH = "/Volumes/mission_ops/raw/celestrak/active_gp_sample.json"
BRONZE_TABLE = "mission_ops.bronze.orbit_records"

with open(RAW_JSON_PATH, "r", encoding="utf-8") as handle:
    raw_records = json.load(handle)

bronze_df = build_bronze_orbit_records(
    spark,
    raw_records,
    ingested_at=datetime.now(timezone.utc),
)

bronze_df.write.mode("overwrite").saveAsTable(BRONZE_TABLE)
display(bronze_df.limit(20))
