# Data Platform Medallion/OLAP Implementation Plan

**Goal:** Add a local-first data engineering layer to Mission Ops Lite that demonstrates Spark/Databricks Medallion Architecture and Snowflake OLAP modeling over public CelesTrak orbit catalog data.

**Boundary:** This is hands-on project infrastructure, not a live Databricks/Snowflake deployment. No credentials, paid cloud setup, or production claims are included.

## Task 1: Capture PR10 acceptance tests

**Files:**

- `tests/test_pr10_data_platform_medallion.py`
- `tests/test_pr10_data_platform_artifacts.py`

**Expected coverage:**

- Bronze preserves source-shaped raw data, raw JSON, ingestion date, and source lineage.
- Silver casts analytical types, parses timestamps, deduplicates duplicate satellite/epoch rows, and labels freshness/quality.
- Gold aggregates OLAP-ready freshness metrics.
- Databricks notebook scripts import the shared transformation module and call `saveAsTable`.
- Snowflake SQL files define schema, stage/load contract, and analysis queries.

## Task 2: Implement shared PySpark Medallion transforms

**Files:**

- `src/mission_ops_lite/data_platform/__init__.py`
- `src/mission_ops_lite/data_platform/medallion.py`
- `src/mission_ops_lite/data_platform/run_local_medallion.py`

**Design:**

- Keep Spark transformation logic in importable functions so local PySpark tests and Databricks notebooks use the same business logic.
- Use local Parquet writes for credential-free development.
- Use Databricks `saveAsTable` only in notebook artifacts.

## Task 3: Add Databricks notebook artifacts

**Files:**

- `notebooks/databricks/01_bronze_ingest.py`
- `notebooks/databricks/02_silver_transform.py`
- `notebooks/databricks/03_gold_metrics.py`

**Design:**

- Notebook scripts assume workspace-provided `spark` and `display`.
- Bronze reads a JSON file from a workspace path/Volume.
- Silver and Gold read prior tables and materialize next-layer tables with `saveAsTable`.

## Task 4: Add Snowflake OLAP artifacts

**Files:**

- `sql/snowflake/01_create_olap_schema.sql`
- `sql/snowflake/02_create_gold_tables.sql`
- `sql/snowflake/03_load_gold_metrics.sql`
- `sql/snowflake/04_analysis_queries.sql`

**Design:**

- Define a small warehouse/database/schema contract.
- Define `GOLD_ORBIT_FRESHNESS_METRICS` as the analytical table.
- Use a Parquet file format and internal stage as a simple load contract.
- Include freshness/quality KPI queries that are explainable in interviews.

## Task 5: Update docs and evidence

**Files:**

- `README.md`
- `docs/DECISIONS.md`
- `docs/QA_REPORT.md`
- `.ouroboros/seeds/mission-ops-lite-data-platform-medallion-olap.yaml`

**Verification:**

```bash
uv run --extra dev --extra data python -m pytest tests/test_pr10_data_platform_medallion.py tests/test_pr10_data_platform_artifacts.py -q
uv run --extra data python -m mission_ops_lite.data_platform.run_local_medallion --input-json data/sample/celestrak_active_gp_sample.json --output-root data/medallion
uv run --extra dev python -m pytest -q
```
