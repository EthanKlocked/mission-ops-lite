from datetime import datetime, timezone

from fastapi.testclient import TestClient

from mission_ops_lite.api import create_app
from mission_ops_lite.catalog import SatelliteCatalog


SGP4_READY_RECORD = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "NORAD_CAT_ID": 25544,
    "EPOCH": "2026-05-28T02:50:05.123456",
    "MEAN_MOTION": 15.49123456,
    "INCLINATION": 51.6421,
    "ECCENTRICITY": 0.0006703,
    "RA_OF_ASC_NODE": 11.22,
    "ARG_OF_PERICENTER": 87.12,
    "MEAN_ANOMALY": 43.55,
    "BSTAR": 0.0002731,
    "MEAN_MOTION_DOT": 0.00016717,
    "MEAN_MOTION_DDOT": 0.0,
}


def _client() -> TestClient:
    catalog = SatelliteCatalog.from_records(
        [SGP4_READY_RECORD], ingested_at=datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    )
    return TestClient(create_app(catalog=catalog))


def test_orbit_track_endpoint_returns_approximate_sgp4_track_points_with_lineage():
    client = _client()

    response = client.get(
        "/satellites/25544/orbit-track"
        "?start=2026-05-28T03:00:00Z&end=2026-05-28T03:10:00Z&step_seconds=300"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object_name"] == "ISS (ZARYA)"
    assert payload["norad_cat_id"] == 25544
    assert payload["source"]["type"] == "real_public_orbit_data"
    assert payload["source_epoch"] == "2026-05-28T02:50:05.123456Z"
    assert payload["start"] == "2026-05-28T03:00:00Z"
    assert payload["end"] == "2026-05-28T03:10:00Z"
    assert payload["step_seconds"] == 300
    assert payload["sample_count"] == 3
    assert payload["propagator"] == "SGP4"
    assert payload["coordinate_frame"] == "TEME"
    assert payload["is_approximate"] is True
    assert payload["visualization_mode"] == "approximate_3d_orbit_playback"
    assert payload["limitations"] == [
        "SGP4-derived approximate orbit playback from public orbit elements.",
        "Not live spacecraft tracking",
        "Not mission-grade flight dynamics validation",
        "No Cesium, Cesium Ion token, or external map service required",
    ]

    points = payload["points"]
    assert [point["sequence"] for point in points] == [0, 1, 2]
    assert [point["timestamp"] for point in points] == [
        "2026-05-28T03:00:00Z",
        "2026-05-28T03:05:00Z",
        "2026-05-28T03:10:00Z",
    ]
    first = points[0]
    assert set(first["position_km"]) == {"x", "y", "z"}
    assert set(first["velocity_km_s"]) == {"x", "y", "z"}
    assert -90 <= first["approximate_geodetic"]["latitude_deg"] <= 90
    assert -180 <= first["approximate_geodetic"]["longitude_deg"] <= 180
    assert first["approximate_geodetic"]["altitude_km"] > 100


def test_orbit_track_endpoint_returns_404_for_unknown_satellite():
    client = TestClient(create_app(catalog=SatelliteCatalog.empty()))

    response = client.get(
        "/satellites/999999/orbit-track"
        "?start=2026-05-28T03:00:00Z&end=2026-05-28T03:10:00Z&step_seconds=300"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Satellite not found"


def test_orbit_track_endpoint_rejects_invalid_time_range():
    client = _client()

    response = client.get(
        "/satellites/25544/orbit-track"
        "?start=2026-05-28T03:10:00Z&end=2026-05-28T03:00:00Z&step_seconds=300"
    )

    assert response.status_code == 422
    assert "end must be after start" in response.json()["detail"]


def test_orbit_track_endpoint_rejects_too_many_samples():
    client = _client()

    response = client.get(
        "/satellites/25544/orbit-track"
        "?start=2026-05-28T03:00:00Z&end=2026-05-30T03:00:00Z&step_seconds=10"
    )

    assert response.status_code == 422
    assert "sample count" in response.json()["detail"]
