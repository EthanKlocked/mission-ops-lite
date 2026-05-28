from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FreshnessStatus = Literal["fresh", "stale", "unknown"]
DataLineageType = Literal["real_public_orbit_data"]


class DataSource(BaseModel):
    name: str
    url: str
    type: DataLineageType = "real_public_orbit_data"


class SatelliteOrbitRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_name: str
    object_id: Optional[str]
    norad_cat_id: int
    epoch: Optional[datetime]
    mean_motion: Optional[float]
    inclination: Optional[float]
    eccentricity: Optional[float]
    source: DataSource
    raw_record: Dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime
    epoch_age_hours: Optional[float]
    freshness_status: FreshnessStatus


class SatelliteResponse(BaseModel):
    object_name: str
    object_id: Optional[str]
    norad_cat_id: int
    epoch: Optional[datetime]
    mean_motion: Optional[float]
    inclination: Optional[float]
    eccentricity: Optional[float]
    source: DataSource
    ingested_at: datetime
    epoch_age_hours: Optional[float]
    freshness_status: FreshnessStatus
    raw_record_available: bool
    raw_record: Optional[Dict[str, Any]] = None


class SatelliteListResponse(BaseModel):
    count: int
    items: list[SatelliteResponse]
