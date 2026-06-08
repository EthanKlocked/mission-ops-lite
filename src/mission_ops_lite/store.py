from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .catalog import SatelliteCatalog
from .celestrak import CelesTrakClient
from .models import SatelliteOrbitRecord


class SQLiteCatalogStore:
    """Small SQLite-backed cache for CelesTrak catalog snapshots."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS satellites (
                    norad_cat_id INTEGER PRIMARY KEY,
                    object_name TEXT NOT NULL,
                    object_id TEXT,
                    source_name TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orbit_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingestion_run_id INTEGER NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
                    norad_cat_id INTEGER NOT NULL REFERENCES satellites(norad_cat_id),
                    object_name TEXT NOT NULL,
                    object_id TEXT,
                    epoch TEXT,
                    mean_motion REAL,
                    inclination REAL,
                    eccentricity REAL,
                    source_json TEXT NOT NULL,
                    raw_record_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    epoch_age_hours REAL,
                    freshness_status TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_orbit_snapshots_run
                    ON orbit_snapshots(ingestion_run_id);
                CREATE INDEX IF NOT EXISTS idx_orbit_snapshots_norad
                    ON orbit_snapshots(norad_cat_id);
                """
            )

    def save_successful_ingestion(self, catalog: SatelliteCatalog) -> int:
        source = CelesTrakClient.source()
        now = datetime.now(timezone.utc)
        records = catalog.list_satellites()
        now_text = _format_datetime(now)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs (
                    source_name, source_url, started_at, completed_at, status, record_count
                ) VALUES (?, ?, ?, ?, 'success', ?)
                """,
                (source.name, source.url, now_text, now_text, len(records)),
            )
            assert cursor.lastrowid is not None
            run_id = int(cursor.lastrowid)
            for record in records:
                self._upsert_satellite(connection, record)
                connection.execute(
                    """
                    INSERT INTO orbit_snapshots (
                        ingestion_run_id, norad_cat_id, object_name, object_id, epoch,
                        mean_motion, inclination, eccentricity, source_json, raw_record_json,
                        ingested_at, epoch_age_hours, freshness_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        record.norad_cat_id,
                        record.object_name,
                        record.object_id,
                        _format_datetime(record.epoch),
                        record.mean_motion,
                        record.inclination,
                        record.eccentricity,
                        record.source.model_dump_json(),
                        json.dumps(record.raw_record, sort_keys=True),
                        _format_datetime(record.ingested_at),
                        record.epoch_age_hours,
                        record.freshness_status,
                    ),
                )
            return run_id

    def save_failed_ingestion(self, error_message: str, http_status: Optional[int] = None) -> int:
        source = CelesTrakClient.source()
        now_text = _format_datetime(datetime.now(timezone.utc))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs (
                    source_name, source_url, started_at, completed_at, status,
                    http_status, record_count, error_message
                ) VALUES (?, ?, ?, ?, 'error', ?, 0, ?)
                """,
                (source.name, source.url, now_text, now_text, http_status, error_message),
            )
            assert cursor.lastrowid is not None
            return int(cursor.lastrowid)

    def latest_catalog(self) -> SatelliteCatalog:
        run = self.latest_successful_run()
        if run is None:
            return SatelliteCatalog.empty()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM orbit_snapshots
                WHERE ingestion_run_id = ?
                ORDER BY object_name, norad_cat_id
                """,
                (run["id"],),
            ).fetchall()
        return SatelliteCatalog([_record_from_row(row) for row in rows])

    def latest_successful_run(self) -> Optional[dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM ingestion_runs
                WHERE status = 'success'
                ORDER BY completed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row is not None else None

    def has_recent_successful_ingestion(self, ttl_hours: float) -> bool:
        run = self.latest_successful_run()
        if run is None or run.get("completed_at") is None:
            return False
        completed_at = _parse_datetime(run["completed_at"])
        return datetime.now(timezone.utc) - completed_at <= timedelta(hours=ttl_hours)

    def list_ingestion_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ingestion_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _upsert_satellite(self, connection: sqlite3.Connection, record: SatelliteOrbitRecord) -> None:
        existing = connection.execute(
            "SELECT first_seen_at FROM satellites WHERE norad_cat_id = ?",
            (record.norad_cat_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO satellites (
                    norad_cat_id, object_name, object_id, source_name, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.norad_cat_id,
                    record.object_name,
                    record.object_id,
                    record.source.name,
                    _format_datetime(record.ingested_at),
                    _format_datetime(record.ingested_at),
                ),
            )
            return
        connection.execute(
            """
            UPDATE satellites
            SET object_name = ?, object_id = ?, source_name = ?, last_seen_at = ?
            WHERE norad_cat_id = ?
            """,
            (
                record.object_name,
                record.object_id,
                record.source.name,
                _format_datetime(record.ingested_at),
                record.norad_cat_id,
            ),
        )


def _format_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_from_row(row: sqlite3.Row) -> SatelliteOrbitRecord:
    return SatelliteOrbitRecord(
        object_name=row["object_name"],
        object_id=row["object_id"],
        norad_cat_id=row["norad_cat_id"],
        epoch=_parse_datetime(row["epoch"]) if row["epoch"] else None,
        mean_motion=row["mean_motion"],
        inclination=row["inclination"],
        eccentricity=row["eccentricity"],
        source=json.loads(row["source_json"]),
        raw_record=json.loads(row["raw_record_json"]),
        ingested_at=_parse_datetime(row["ingested_at"]),
        epoch_age_hours=row["epoch_age_hours"],
        freshness_status=row["freshness_status"],
    )
