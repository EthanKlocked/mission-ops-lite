from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from .models import SatelliteOrbitRecord
from .normalization import normalize_celestrak_record


class SatelliteCatalog:
    def __init__(self, records: Iterable[SatelliteOrbitRecord]):
        self._records = list(records)
        self._by_norad_id = {record.norad_cat_id: record for record in self._records}

    @classmethod
    def empty(cls) -> "SatelliteCatalog":
        return cls([])

    @classmethod
    def from_records(
        cls, raw_records: Iterable[dict], *, ingested_at: Optional[datetime] = None
    ) -> "SatelliteCatalog":
        ingestion_time = ingested_at or datetime.now(timezone.utc)
        normalized = [
            normalize_celestrak_record(record, ingested_at=ingestion_time) for record in raw_records
        ]
        return cls(normalized)

    def list_satellites(self) -> list[SatelliteOrbitRecord]:
        return list(self._records)

    def get_satellite(self, norad_cat_id: int) -> Optional[SatelliteOrbitRecord]:
        return self._by_norad_id.get(norad_cat_id)
