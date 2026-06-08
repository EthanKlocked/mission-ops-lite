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


def _client_with_catalog() -> TestClient:
    catalog = SatelliteCatalog.from_records(
        [SGP4_READY_RECORD], ingested_at=datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    )
    return TestClient(create_app(catalog=catalog))


def test_contact_windows_endpoint_returns_approximate_visibility_windows():
    client = _client_with_catalog()

    response = client.get(
        "/satellites/25544/contact-windows",
        params={
            "ground_station_name": "Pacific demo station",
            "latitude_deg": 8.45,
            "longitude_deg": -106.20,
            "altitude_m": 0,
            "start": "2026-05-28T02:45:00Z",
            "end": "2026-05-28T03:20:00Z",
            "step_seconds": 30,
            "min_elevation_deg": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["norad_cat_id"] == 25544
    assert payload["object_name"] == "ISS (ZARYA)"
    assert payload["ground_station"]["name"] == "Pacific demo station"
    assert payload["ground_station"]["latitude_deg"] == 8.45
    assert payload["ground_station"]["longitude_deg"] == -106.2
    assert payload["start"] == "2026-05-28T02:45:00Z"
    assert payload["end"] == "2026-05-28T03:20:00Z"
    assert payload["step_seconds"] == 30
    assert payload["min_elevation_deg"] == 10
    assert payload["propagator"] == "SGP4"
    assert payload["is_approximate"] is True
    assert payload["count"] >= 1
    first_window = payload["windows"][0]
    assert first_window["start"] <= first_window["end"]
    assert first_window["duration_seconds"] >= 0
    assert first_window["max_elevation_deg"] >= 10
    assert first_window["peak_at"] is not None
    assert "SGP4-derived approximate visibility" in payload["limitations"][0]
    assert "Not live spacecraft telemetry" in payload["limitations"]
    assert "Not mission-grade contact validation" in payload["limitations"]


def test_contact_windows_endpoint_can_return_empty_windows_for_no_visibility():
    client = _client_with_catalog()

    response = client.get(
        "/satellites/25544/contact-windows",
        params={
            "latitude_deg": 80.0,
            "longitude_deg": 0.0,
            "start": "2026-05-28T02:45:00Z",
            "end": "2026-05-28T03:20:00Z",
            "step_seconds": 60,
            "min_elevation_deg": 80,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 0
    assert payload["windows"] == []


def test_contact_windows_endpoint_rejects_invalid_time_ranges():
    client = _client_with_catalog()

    response = client.get(
        "/satellites/25544/contact-windows",
        params={
            "latitude_deg": 8.45,
            "longitude_deg": -106.20,
            "start": "2026-05-28T03:20:00Z",
            "end": "2026-05-28T02:45:00Z",
        },
    )

    assert response.status_code == 422
    assert "end must be after start" in response.json()["detail"]


def test_contact_windows_endpoint_returns_404_for_unknown_satellite():
    app = create_app(catalog=SatelliteCatalog.empty())
    client = TestClient(app)

    response = client.get(
        "/satellites/999999/contact-windows",
        params={
            "latitude_deg": 8.45,
            "longitude_deg": -106.20,
            "start": "2026-05-28T02:45:00Z",
            "end": "2026-05-28T03:20:00Z",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Satellite not found"
