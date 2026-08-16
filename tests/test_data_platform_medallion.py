from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

pyspark = pytest.importorskip("pyspark")

from mission_ops_lite.data_platform.medallion import (  # noqa: E402
    build_bronze_orbit_records,
    build_gold_freshness_metrics,
    build_silver_orbit_snapshots,
    create_local_spark,
    write_medallion_layers,
)


SAMPLE_RAW_RECORDS = [
    {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2026-05-28T02:50:05.123456",
        "MEAN_MOTION": 15.49123456,
        "INCLINATION": 51.6421,
        "ECCENTRICITY": 0.0006703,
    },
    {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2026-05-28T02:50:05.123456",
        "MEAN_MOTION": 15.49123456,
        "INCLINATION": 51.6421,
        "ECCENTRICITY": 0.0006703,
    },
    {
        "OBJECT_NAME": "NOAA 19",
        "OBJECT_ID": "2009-005A",
        "NORAD_CAT_ID": 33591,
        "EPOCH": "2026-05-24T00:00:00",
        "MEAN_MOTION": 14.1245,
        "INCLINATION": 99.194,
        "ECCENTRICITY": 0.0015,
    },
    {
        "OBJECT_NAME": "MISSING EPOCH SAT",
        "OBJECT_ID": "2026-001A",
        "NORAD_CAT_ID": 99901,
        "EPOCH": None,
        "MEAN_MOTION": "",
        "INCLINATION": "",
        "ECCENTRICITY": "",
    },
]


@pytest.fixture(scope="module")
def spark():
    session = create_local_spark("mission-ops-lite-medallion-tests")
    yield session
    session.stop()


def test_bronze_layer_preserves_raw_lineage_and_source_context(spark):
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)

    bronze = build_bronze_orbit_records(spark, SAMPLE_RAW_RECORDS, ingested_at=ingested_at)
    row = bronze.where("norad_cat_id = 25544").first()

    assert bronze.count() == 4
    assert row.object_name == "ISS (ZARYA)"
    assert row.source_name == "CelesTrak GP active"
    assert row.source_type == "real_public_orbit_data"
    assert row.raw_record_json is not None
    assert '"NORAD_CAT_ID": 25544' in row.raw_record_json
    assert row.ingestion_date.isoformat() == "2026-05-28"


def test_silver_layer_deduplicates_and_normalizes_orbit_snapshots(spark):
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    bronze = build_bronze_orbit_records(spark, SAMPLE_RAW_RECORDS, ingested_at=ingested_at)

    silver = build_silver_orbit_snapshots(bronze)
    rows = {row.norad_cat_id: row for row in silver.collect()}

    assert silver.count() == 3
    epoch_rendered = silver.where("norad_cat_id = 25544").selectExpr(
        "date_format(epoch, 'yyyy-MM-dd HH:mm:ss') AS epoch_text"
    ).first().epoch_text
    assert epoch_rendered == "2026-05-28 02:50:05"
    assert rows[25544].mean_motion == pytest.approx(15.49123456)
    assert rows[25544].freshness_status == "fresh"
    assert rows[25544].quality_status == "valid"
    assert rows[33591].freshness_status == "stale"
    assert rows[99901].freshness_status == "unknown"
    assert rows[99901].quality_status == "invalid_missing_epoch"


def test_gold_layer_builds_olap_ready_freshness_metrics(spark):
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    bronze = build_bronze_orbit_records(spark, SAMPLE_RAW_RECORDS, ingested_at=ingested_at)
    silver = build_silver_orbit_snapshots(bronze)

    gold = build_gold_freshness_metrics(silver)
    metrics = {row.freshness_status: row.satellite_count for row in gold.collect()}

    assert metrics == {"fresh": 1, "stale": 1, "unknown": 1}
    assert set(gold.columns) >= {
        "metric_date",
        "source_name",
        "freshness_status",
        "quality_status",
        "satellite_count",
        "avg_epoch_age_hours",
    }


def test_medallion_layers_can_be_written_as_local_parquet_outputs(spark, tmp_path: Path):
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    bronze = build_bronze_orbit_records(spark, SAMPLE_RAW_RECORDS, ingested_at=ingested_at)
    silver = build_silver_orbit_snapshots(bronze)
    gold = build_gold_freshness_metrics(silver)

    outputs = write_medallion_layers(
        bronze=bronze,
        silver=silver,
        gold=gold,
        output_root=tmp_path,
        mode="overwrite",
    )

    assert outputs["bronze"].name == "bronze_orbit_records"
    assert outputs["silver"].name == "silver_orbit_snapshots"
    assert outputs["gold"].name == "gold_orbit_freshness_metrics"
    assert any(outputs["gold"].glob("*.parquet"))
