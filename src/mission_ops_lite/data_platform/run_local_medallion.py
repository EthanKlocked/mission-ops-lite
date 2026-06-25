from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mission_ops_lite.data_platform.medallion import (
    build_bronze_orbit_records,
    build_gold_freshness_metrics,
    build_silver_orbit_snapshots,
    create_local_spark,
    write_medallion_layers,
)


def run(input_json: Path, output_root: Path) -> dict[str, Path]:
    spark = create_local_spark("mission-ops-lite-local-medallion")
    try:
        raw_records = json.loads(input_json.read_text())
        bronze = build_bronze_orbit_records(
            spark,
            raw_records,
            ingested_at=datetime.now(timezone.utc),
        )
        silver = build_silver_orbit_snapshots(bronze)
        gold = build_gold_freshness_metrics(silver)
        return write_medallion_layers(
            bronze=bronze,
            silver=silver,
            gold=gold,
            output_root=output_root,
            mode="overwrite",
        )
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local PySpark medallion pipeline.")
    parser.add_argument(
        "--input-json",
        type=Path,
        default=Path("data/sample/celestrak_active_gp_sample.json"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/medallion"),
    )
    args = parser.parse_args()

    outputs = run(args.input_json, args.output_root)
    for layer, path in outputs.items():
        print(f"{layer}: {path}")


if __name__ == "__main__":
    main()
