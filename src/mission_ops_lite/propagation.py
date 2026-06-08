from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, degrees, pi, radians, sin, sqrt
from typing import Any

from sgp4.api import SGP4_ERRORS, Satrec, WGS72, jday

from .models import SatelliteOrbitRecord
from .normalization import parse_celestrak_epoch

_JD_1949_DEC_31_UTC = 2433281.5
_EARTH_EQUATORIAL_RADIUS_KM = 6378.137
_EARTH_FLATTENING = 1 / 298.257223563


class PropagationInputError(ValueError):
    """Raised when a catalog record does not contain enough public orbit elements."""


class PropagationRuntimeError(RuntimeError):
    """Raised when SGP4 cannot propagate the supplied orbit elements to a timestamp."""


@dataclass(frozen=True)
class SGP4PositionEstimate:
    object_name: str
    norad_cat_id: int
    source_epoch: datetime
    requested_at: datetime
    time_delta_minutes_from_epoch: float
    position_km: dict[str, float]
    velocity_km_s: dict[str, float]
    approximate_geodetic: dict[str, float]
    freshness_status: str
    epoch_age_hours: float | None


def parse_requested_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = parse_celestrak_epoch(value)
    if parsed is None:
        raise PropagationInputError("at must be an ISO-8601 timestamp")
    return parsed


def propagate_sgp4_position(
    record: SatelliteOrbitRecord, *, requested_at: datetime
) -> SGP4PositionEstimate:
    """Derive an approximate satellite position from public CelesTrak GP orbit elements."""

    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)
    else:
        requested_at = requested_at.astimezone(timezone.utc)

    if record.epoch is None:
        raise PropagationInputError("source EPOCH is required for SGP4 propagation")

    elements = _extract_required_elements(record)
    satellite = _build_satrec(record, elements)
    jd, fr = jday(
        requested_at.year,
        requested_at.month,
        requested_at.day,
        requested_at.hour,
        requested_at.minute,
        requested_at.second + requested_at.microsecond / 1_000_000,
    )
    error_code, position, velocity = satellite.sgp4(jd, fr)
    if error_code != 0:
        message = SGP4_ERRORS.get(error_code, "SGP4 propagation failed")
        raise PropagationRuntimeError(message)

    position_km = _axis_dict(position)
    velocity_km_s = _axis_dict(velocity)
    approximate_geodetic = _teme_to_approximate_geodetic(position, requested_at)
    source_epoch = record.epoch.astimezone(timezone.utc)

    return SGP4PositionEstimate(
        object_name=record.object_name,
        norad_cat_id=record.norad_cat_id,
        source_epoch=source_epoch,
        requested_at=requested_at,
        time_delta_minutes_from_epoch=(requested_at - source_epoch).total_seconds() / 60.0,
        position_km=position_km,
        velocity_km_s=velocity_km_s,
        approximate_geodetic=approximate_geodetic,
        freshness_status=record.freshness_status,
        epoch_age_hours=record.epoch_age_hours,
    )


def _extract_required_elements(record: SatelliteOrbitRecord) -> dict[str, float]:
    raw = record.raw_record
    required = {
        "mean_motion": record.mean_motion,
        "inclination": record.inclination,
        "eccentricity": record.eccentricity,
        "ra_of_asc_node": _float_or_none(raw.get("RA_OF_ASC_NODE")),
        "arg_of_pericenter": _float_or_none(raw.get("ARG_OF_PERICENTER")),
        "mean_anomaly": _float_or_none(raw.get("MEAN_ANOMALY")),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        joined = ", ".join(missing)
        raise PropagationInputError(f"record is missing required orbit elements: {joined}")

    elements = {name: float(value) for name, value in required.items() if value is not None}
    elements["bstar"] = _float_or_none(raw.get("BSTAR")) or 0.0
    elements["mean_motion_dot"] = _float_or_none(raw.get("MEAN_MOTION_DOT")) or 0.0
    elements["mean_motion_ddot"] = _float_or_none(raw.get("MEAN_MOTION_DDOT")) or 0.0
    return elements


def _build_satrec(record: SatelliteOrbitRecord, elements: dict[str, float]) -> Satrec:
    if record.epoch is None:
        raise PropagationInputError("source EPOCH is required for SGP4 propagation")

    epoch = record.epoch.astimezone(timezone.utc)
    epoch_jd, epoch_fr = jday(
        epoch.year,
        epoch.month,
        epoch.day,
        epoch.hour,
        epoch.minute,
        epoch.second + epoch.microsecond / 1_000_000,
    )
    epoch_days = epoch_jd + epoch_fr - _JD_1949_DEC_31_UTC

    satellite = Satrec()
    satellite.sgp4init(
        WGS72,
        "i",
        record.norad_cat_id,
        epoch_days,
        elements["bstar"],
        elements["mean_motion_dot"] * 2 * pi / (1440.0**2),
        elements["mean_motion_ddot"] * 2 * pi / (1440.0**3),
        elements["eccentricity"],
        radians(elements["arg_of_pericenter"]),
        radians(elements["inclination"]),
        radians(elements["mean_anomaly"]),
        elements["mean_motion"] * 2 * pi / 1440.0,
        radians(elements["ra_of_asc_node"]),
    )
    return satellite


def _teme_to_approximate_geodetic(position_km: tuple[float, float, float], at: datetime) -> dict[str, float]:
    """Approximate TEME-to-geodetic conversion suitable for product context, not flight dynamics."""

    theta = _gmst_radians(at)
    x_teme, y_teme, z_km = position_km
    x_km = cos(theta) * x_teme + sin(theta) * y_teme
    y_km = -sin(theta) * x_teme + cos(theta) * y_teme
    lon = atan2(y_km, x_km)

    semi_major = _EARTH_EQUATORIAL_RADIUS_KM
    flattening = _EARTH_FLATTENING
    semi_minor = semi_major * (1 - flattening)
    eccentricity_squared = 1 - (semi_minor * semi_minor) / (semi_major * semi_major)

    p = sqrt(x_km * x_km + y_km * y_km)
    lat = atan2(z_km, p * (1 - eccentricity_squared))
    altitude = 0.0
    for _ in range(5):
        sin_lat = sin(lat)
        prime_vertical_radius = semi_major / sqrt(1 - eccentricity_squared * sin_lat * sin_lat)
        altitude = p / cos(lat) - prime_vertical_radius
        lat = atan2(z_km, p * (1 - eccentricity_squared * prime_vertical_radius / (prime_vertical_radius + altitude)))

    longitude_deg = ((degrees(lon) + 180) % 360) - 180
    return {
        "latitude_deg": degrees(lat),
        "longitude_deg": longitude_deg,
        "altitude_km": altitude,
    }


def _gmst_radians(at: datetime) -> float:
    jd, fr = jday(
        at.year,
        at.month,
        at.day,
        at.hour,
        at.minute,
        at.second + at.microsecond / 1_000_000,
    )
    julian_date = jd + fr
    centuries = (julian_date - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (julian_date - 2451545.0)
        + 0.000387933 * centuries * centuries
        - centuries * centuries * centuries / 38710000.0
    )
    return radians(gmst_deg % 360.0)


def _axis_dict(values: tuple[float, float, float]) -> dict[str, float]:
    return {"x": values[0], "y": values[1], "z": values[2]}


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not _is_finite(parsed):
        return None
    return parsed


def _is_finite(value: float) -> bool:
    return not (value != value or value in (float("inf"), float("-inf")))
