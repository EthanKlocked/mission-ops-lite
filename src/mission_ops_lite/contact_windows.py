from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, radians, sin, sqrt

from .models import SatelliteOrbitRecord
from .propagation import PropagationInputError, PropagationRuntimeError, parse_requested_at, propagate_sgp4_position

_EARTH_EQUATORIAL_RADIUS_KM = 6378.137
_EARTH_FLATTENING = 1 / 298.257223563
_EARTH_ECCENTRICITY_SQUARED = _EARTH_FLATTENING * (2 - _EARTH_FLATTENING)


class ContactWindowInputError(ValueError):
    """Raised when contact-window request parameters are invalid."""


@dataclass(frozen=True)
class GroundStation:
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float


@dataclass(frozen=True)
class ContactWindow:
    start: datetime
    end: datetime
    peak_at: datetime
    duration_seconds: float
    max_elevation_deg: float


@dataclass(frozen=True)
class ContactWindowEstimate:
    object_name: str
    norad_cat_id: int
    source_epoch: datetime
    start: datetime
    end: datetime
    ground_station: GroundStation
    min_elevation_deg: float
    step_seconds: int
    windows: list[ContactWindow]
    freshness_status: str
    epoch_age_hours: float | None


def parse_contact_window_bounds(start: str, end: str) -> tuple[datetime, datetime]:
    parsed_start = parse_requested_at(start)
    parsed_end = parse_requested_at(end)
    if parsed_end <= parsed_start:
        raise ContactWindowInputError("end must be after start")
    return parsed_start, parsed_end


def estimate_contact_windows(
    record: SatelliteOrbitRecord,
    *,
    ground_station: GroundStation,
    start: datetime,
    end: datetime,
    step_seconds: int,
    min_elevation_deg: float,
) -> ContactWindowEstimate:
    """Estimate approximate ground-station visibility windows from public orbit elements."""

    if step_seconds <= 0:
        raise ContactWindowInputError("step_seconds must be positive")
    if end <= start:
        raise ContactWindowInputError("end must be after start")

    start = _to_utc(start)
    end = _to_utc(end)
    station_ecef = _ground_station_ecef_km(ground_station)

    visible_samples: list[tuple[datetime, float]] = []
    windows: list[ContactWindow] = []
    current = start
    step = timedelta(seconds=step_seconds)
    last_estimate = None

    while current <= end:
        estimate = propagate_sgp4_position(record, requested_at=current)
        last_estimate = estimate
        position = estimate.approximate_geodetic
        satellite_ecef = _geodetic_to_ecef_km(
            position["latitude_deg"], position["longitude_deg"], position["altitude_km"]
        )
        elevation = _elevation_deg(station_ecef, satellite_ecef, ground_station)
        if elevation >= min_elevation_deg:
            visible_samples.append((current, elevation))
        elif visible_samples:
            windows.append(_samples_to_window(visible_samples))
            visible_samples = []
        current += step

    if visible_samples:
        windows.append(_samples_to_window(visible_samples))

    if last_estimate is None:
        raise PropagationRuntimeError("contact-window range did not include any samples")

    return ContactWindowEstimate(
        object_name=last_estimate.object_name,
        norad_cat_id=last_estimate.norad_cat_id,
        source_epoch=last_estimate.source_epoch,
        start=start,
        end=end,
        ground_station=ground_station,
        min_elevation_deg=min_elevation_deg,
        step_seconds=step_seconds,
        windows=windows,
        freshness_status=last_estimate.freshness_status,
        epoch_age_hours=last_estimate.epoch_age_hours,
    )


def _samples_to_window(samples: list[tuple[datetime, float]]) -> ContactWindow:
    peak_at, max_elevation = max(samples, key=lambda sample: sample[1])
    start = samples[0][0]
    end = samples[-1][0]
    return ContactWindow(
        start=start,
        end=end,
        peak_at=peak_at,
        duration_seconds=(end - start).total_seconds(),
        max_elevation_deg=max_elevation,
    )


def _ground_station_ecef_km(station: GroundStation) -> tuple[float, float, float]:
    return _geodetic_to_ecef_km(station.latitude_deg, station.longitude_deg, station.altitude_m / 1000.0)


def _geodetic_to_ecef_km(latitude_deg: float, longitude_deg: float, altitude_km: float) -> tuple[float, float, float]:
    lat = radians(latitude_deg)
    lon = radians(longitude_deg)
    sin_lat = sin(lat)
    cos_lat = cos(lat)
    prime_vertical_radius = _EARTH_EQUATORIAL_RADIUS_KM / sqrt(1 - _EARTH_ECCENTRICITY_SQUARED * sin_lat * sin_lat)
    x = (prime_vertical_radius + altitude_km) * cos_lat * cos(lon)
    y = (prime_vertical_radius + altitude_km) * cos_lat * sin(lon)
    z = (prime_vertical_radius * (1 - _EARTH_ECCENTRICITY_SQUARED) + altitude_km) * sin_lat
    return x, y, z


def _elevation_deg(
    station_ecef: tuple[float, float, float],
    satellite_ecef: tuple[float, float, float],
    station: GroundStation,
) -> float:
    dx = satellite_ecef[0] - station_ecef[0]
    dy = satellite_ecef[1] - station_ecef[1]
    dz = satellite_ecef[2] - station_ecef[2]
    lat = radians(station.latitude_deg)
    lon = radians(station.longitude_deg)
    east = -sin(lon) * dx + cos(lon) * dy
    north = -sin(lat) * cos(lon) * dx - sin(lat) * sin(lon) * dy + cos(lat) * dz
    up = cos(lat) * cos(lon) * dx + cos(lat) * sin(lon) * dy + sin(lat) * dz
    return degrees(atan2(up, sqrt(east * east + north * north)))


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
