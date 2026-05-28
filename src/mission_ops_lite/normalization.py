from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from .celestrak import CelesTrakClient
from .models import SatelliteOrbitRecord

FRESHNESS_STALE_AFTER_HOURS = 72.0


def parse_celestrak_epoch(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _float_or_none(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_raise(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} is required and must be an integer") from exc


def calculate_epoch_age_hours(epoch: Optional[datetime], ingested_at: datetime) -> Optional[float]:
    if epoch is None:
        return None
    return max(0.0, (ingested_at - epoch).total_seconds() / 3600.0)


def classify_freshness(epoch_age_hours: Optional[float]) -> str:
    if epoch_age_hours is None:
        return "unknown"
    if epoch_age_hours <= FRESHNESS_STALE_AFTER_HOURS:
        return "fresh"
    return "stale"


def normalize_celestrak_record(
    record: Mapping[str, Any], *, ingested_at: Optional[datetime] = None
) -> SatelliteOrbitRecord:
    """Normalize one CelesTrak GP JSON record while preserving raw traceability."""

    ingestion_time = ingested_at or datetime.now(timezone.utc)
    if ingestion_time.tzinfo is None:
        ingestion_time = ingestion_time.replace(tzinfo=timezone.utc)
    else:
        ingestion_time = ingestion_time.astimezone(timezone.utc)

    epoch = parse_celestrak_epoch(record.get("EPOCH"))
    age_hours = calculate_epoch_age_hours(epoch, ingestion_time)

    return SatelliteOrbitRecord(
        object_name=str(record.get("OBJECT_NAME") or "UNKNOWN"),
        object_id=record.get("OBJECT_ID"),
        norad_cat_id=_int_or_raise(record.get("NORAD_CAT_ID"), "NORAD_CAT_ID"),
        epoch=epoch,
        mean_motion=_float_or_none(record.get("MEAN_MOTION")),
        inclination=_float_or_none(record.get("INCLINATION")),
        eccentricity=_float_or_none(record.get("ECCENTRICITY")),
        source=CelesTrakClient.source(),
        raw_record=dict(record),
        ingested_at=ingestion_time,
        epoch_age_hours=age_hours,
        freshness_status=classify_freshness(age_hours),
    )
