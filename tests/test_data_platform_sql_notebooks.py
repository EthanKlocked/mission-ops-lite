from pathlib import Path


def test_snowflake_sql_artifacts_define_olap_schema_and_queries():
    base = Path("sql/snowflake")
    expected_files = [
        "01_create_olap_schema.sql",
        "02_create_gold_tables.sql",
        "03_load_gold_metrics.sql",
        "04_analysis_queries.sql",
    ]

    for file_name in expected_files:
        assert (base / file_name).exists(), f"missing {file_name}"

    create_tables = (base / "02_create_gold_tables.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS GOLD_ORBIT_FRESHNESS_METRICS" in create_tables
    assert "SATELLITE_COUNT NUMBER" in create_tables
    assert "QUALITY_STATUS VARCHAR" in create_tables

    load_sql = (base / "03_load_gold_metrics.sql").read_text()
    assert "COPY INTO GOLD_ORBIT_FRESHNESS_METRICS" in load_sql
    assert "@MISSION_OPS_GOLD_STAGE" in load_sql
    assert "MATCH_BY_COLUMN_NAME" not in load_sql

    query_sql = (base / "04_analysis_queries.sql").read_text()
    assert "freshness_status" in query_sql.lower()
    assert "GROUP BY" in query_sql
    assert "ORDER BY" in query_sql


def test_databricks_notebooks_reuse_shared_medallion_module():
    notebook_dir = Path("notebooks/databricks")
    notebooks = [
        notebook_dir / "01_bronze_ingest.py",
        notebook_dir / "02_silver_transform.py",
        notebook_dir / "03_gold_metrics.py",
    ]

    for notebook in notebooks:
        assert notebook.exists(), f"missing {notebook}"
        text = notebook.read_text()
        assert "mission_ops_lite.data_platform.medallion" in text
        assert "saveAsTable" in text
        assert "Bronze" in text or "Silver" in text or "Gold" in text
