from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from mission_ops_lite.celestrak import CelesTrakClient


def _require_pyspark():
    try:
        from pyspark.sql import SparkSession, functions as F, types as T
    except ImportError as exc:  # pragma: no cover - exercised by optional dependency boundary
        raise RuntimeError(
            "PySpark is required for the data-platform pipeline. "
            "Install with `uv sync --extra data` or run `uv run --extra data ...`."
        ) from exc
    return SparkSession, F, T


def create_local_spark(app_name: str = "mission-ops-lite-data-platform"):
    """Create a local SparkSession for deterministic development and tests.

    Databricks notebooks/jobs should use the workspace-provided `spark` session instead of this
    helper. Keeping the transformation functions separate lets the same logic run in local PySpark
    and Databricks.
    """

    SparkSession, _, _ = _require_pyspark()
    session = (
        SparkSession.builder.master("local[2]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    session.conf.set("spark.sql.session.timeZone", "UTC")
    return session


def _utc_timestamp_string(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def build_bronze_orbit_records(
    spark,
    raw_records: Iterable[Mapping[str, Any]],
    *,
    ingested_at: datetime | None = None,
):
    """Build the Bronze layer from raw CelesTrak GP records.

    Bronze intentionally preserves the source-shaped fields and the full raw JSON payload while
    adding ingestion/source lineage. This mirrors a Databricks Medallion first hop: land the data
    with enough traceability to replay downstream transforms.
    """

    _, F, T = _require_pyspark()
    source = CelesTrakClient.source()
    ingestion_time = ingested_at or datetime.now(timezone.utc)
    ingestion_time_text = _utc_timestamp_string(ingestion_time)

    rows = []
    for record in raw_records:
        rows.append(
            {
                "object_name": None if record.get("OBJECT_NAME") is None else str(record.get("OBJECT_NAME")),
                "object_id": None if record.get("OBJECT_ID") is None else str(record.get("OBJECT_ID")),
                "norad_cat_id": None
                if record.get("NORAD_CAT_ID") is None
                else str(record.get("NORAD_CAT_ID")),
                "epoch_raw": None if record.get("EPOCH") is None else str(record.get("EPOCH")),
                "mean_motion_raw": None
                if record.get("MEAN_MOTION") in (None, "")
                else str(record.get("MEAN_MOTION")),
                "inclination_raw": None
                if record.get("INCLINATION") in (None, "")
                else str(record.get("INCLINATION")),
                "eccentricity_raw": None
                if record.get("ECCENTRICITY") in (None, "")
                else str(record.get("ECCENTRICITY")),
                "raw_record_json": json.dumps(dict(record), sort_keys=True),
                "source_name": source.name,
                "source_url": source.url,
                "source_type": source.type,
                "ingested_at_raw": ingestion_time_text,
            }
        )

    schema = T.StructType(
        [
            T.StructField("object_name", T.StringType(), True),
            T.StructField("object_id", T.StringType(), True),
            T.StructField("norad_cat_id", T.StringType(), True),
            T.StructField("epoch_raw", T.StringType(), True),
            T.StructField("mean_motion_raw", T.StringType(), True),
            T.StructField("inclination_raw", T.StringType(), True),
            T.StructField("eccentricity_raw", T.StringType(), True),
            T.StructField("raw_record_json", T.StringType(), False),
            T.StructField("source_name", T.StringType(), False),
            T.StructField("source_url", T.StringType(), False),
            T.StructField("source_type", T.StringType(), False),
            T.StructField("ingested_at_raw", T.StringType(), False),
        ]
    )

    return (
        spark.createDataFrame(rows, schema=schema)
        .withColumn("ingested_at", F.to_timestamp("ingested_at_raw"))
        .withColumn("ingestion_date", F.to_date("ingested_at"))
        .drop("ingested_at_raw")
    )


def build_silver_orbit_snapshots(bronze_df):
    """Normalize Bronze records into a Silver orbit-snapshot table.

    Silver casts business columns into analytical types, removes duplicate satellite/epoch rows,
    computes freshness, and marks records with missing required analytical fields.
    """

    _, F, _ = _require_pyspark()
    bronze_df.sparkSession.conf.set("spark.sql.session.timeZone", "UTC")

    normalized = (
        bronze_df.withColumn("norad_cat_id", F.col("norad_cat_id").cast("long"))
        .withColumn("epoch", F.to_timestamp("epoch_raw"))
        .withColumn("mean_motion", F.col("mean_motion_raw").cast("double"))
        .withColumn("inclination", F.col("inclination_raw").cast("double"))
        .withColumn("eccentricity", F.col("eccentricity_raw").cast("double"))
        .withColumn(
            "epoch_age_hours",
            F.when(F.col("epoch").isNull(), F.lit(None).cast("double")).otherwise(
                (F.unix_timestamp("ingested_at") - F.unix_timestamp("epoch")) / F.lit(3600.0)
            ),
        )
        .withColumn(
            "freshness_status",
            F.when(F.col("epoch").isNull(), F.lit("unknown"))
            .when(F.col("epoch_age_hours") <= F.lit(72.0), F.lit("fresh"))
            .otherwise(F.lit("stale")),
        )
        .withColumn(
            "quality_status",
            F.when(F.col("epoch").isNull(), F.lit("invalid_missing_epoch"))
            .when(F.col("norad_cat_id").isNull(), F.lit("invalid_missing_norad_cat_id"))
            .otherwise(F.lit("valid")),
        )
    )

    return normalized.dropDuplicates(["norad_cat_id", "epoch_raw"]).select(
        "object_name",
        "object_id",
        "norad_cat_id",
        "epoch",
        "mean_motion",
        "inclination",
        "eccentricity",
        "source_name",
        "source_url",
        "source_type",
        "ingested_at",
        "ingestion_date",
        "epoch_age_hours",
        "freshness_status",
        "quality_status",
        "raw_record_json",
    )


def build_gold_freshness_metrics(silver_df):
    """Build an OLAP-ready Gold metric table for freshness and quality reporting."""

    _, F, _ = _require_pyspark()

    return (
        silver_df.withColumn("metric_date", F.col("ingestion_date"))
        .groupBy("metric_date", "source_name", "freshness_status", "quality_status")
        .agg(
            F.count("*").alias("satellite_count"),
            F.avg("epoch_age_hours").alias("avg_epoch_age_hours"),
            F.min("epoch_age_hours").alias("min_epoch_age_hours"),
            F.max("epoch_age_hours").alias("max_epoch_age_hours"),
        )
        .orderBy("metric_date", "source_name", "freshness_status", "quality_status")
    )


def write_medallion_layers(*, bronze, silver, gold, output_root: str | Path, mode: str = "overwrite"):
    """Write local Parquet outputs that mirror Databricks table materialization.

    Databricks notebooks use `saveAsTable`; local development uses Parquet paths so the pipeline can
    be verified without cloud credentials.
    """

    root = Path(output_root)
    outputs = {
        "bronze": root / "bronze_orbit_records",
        "silver": root / "silver_orbit_snapshots",
        "gold": root / "gold_orbit_freshness_metrics",
    }
    bronze.write.mode(mode).parquet(str(outputs["bronze"]))
    silver.write.mode(mode).parquet(str(outputs["silver"]))
    gold.write.mode(mode).parquet(str(outputs["gold"]))
    return outputs
