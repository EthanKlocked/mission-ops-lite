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


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class ApproximateGeodeticPosition(BaseModel):
    latitude_deg: float
    longitude_deg: float
    altitude_km: float


class SatellitePositionResponse(BaseModel):
    object_name: str
    norad_cat_id: int
    source: DataSource
    source_epoch: datetime
    requested_at: datetime
    time_delta_minutes_from_epoch: float
    propagator: str = "SGP4"
    coordinate_frame: str = "TEME"
    position_km: Vector3
    velocity_km_s: Vector3
    approximate_geodetic: ApproximateGeodeticPosition
    freshness_status: FreshnessStatus
    epoch_age_hours: Optional[float]
    is_approximate: bool = True
    limitations: list[str]


class GroundStationResponse(BaseModel):
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float


class ContactWindowResponse(BaseModel):
    start: datetime
    end: datetime
    peak_at: datetime
    duration_seconds: float
    max_elevation_deg: float


class ContactWindowListResponse(BaseModel):
    object_name: str
    norad_cat_id: int
    source: DataSource
    source_epoch: datetime
    start: datetime
    end: datetime
    ground_station: GroundStationResponse
    min_elevation_deg: float
    step_seconds: int
    propagator: str = "SGP4"
    is_approximate: bool = True
    freshness_status: FreshnessStatus
    epoch_age_hours: Optional[float]
    count: int
    windows: list[ContactWindowResponse]
    limitations: list[str]
