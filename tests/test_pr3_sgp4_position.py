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


def test_position_endpoint_returns_sgp4_derived_approximate_position_metadata():
    catalog = SatelliteCatalog.from_records(
        [SGP4_READY_RECORD], ingested_at=datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    )
    app = create_app(catalog=catalog)
    client = TestClient(app)

    response = client.get("/satellites/25544/position?at=2026-05-28T03:00:00Z")

    assert response.status_code == 200
    payload = response.json()
    assert payload["norad_cat_id"] == 25544
    assert payload["object_name"] == "ISS (ZARYA)"
    assert payload["source"]["name"] == "CelesTrak GP active"
    assert payload["source_epoch"] == "2026-05-28T02:50:05.123456Z"
    assert payload["requested_at"] == "2026-05-28T03:00:00Z"
    assert payload["propagator"] == "SGP4"
    assert payload["coordinate_frame"] == "TEME"
    assert payload["is_approximate"] is True
    assert payload["time_delta_minutes_from_epoch"] > 0
    assert set(payload["position_km"]) == {"x", "y", "z"}
    assert set(payload["velocity_km_s"]) == {"x", "y", "z"}
    assert -90 <= payload["approximate_geodetic"]["latitude_deg"] <= 90
    assert -180 <= payload["approximate_geodetic"]["longitude_deg"] <= 180
    assert payload["approximate_geodetic"]["altitude_km"] > 100
    assert payload["freshness_status"] == "fresh"
    assert "SGP4-derived approximate position" in payload["limitations"][0]
    assert "Not live spacecraft telemetry" in payload["limitations"]


def test_position_endpoint_returns_404_for_unknown_satellite():
    app = create_app(catalog=SatelliteCatalog.empty())
    client = TestClient(app)

    response = client.get("/satellites/999999/position?at=2026-05-28T03:00:00Z")

    assert response.status_code == 404
    assert response.json()["detail"] == "Satellite not found"


def test_position_endpoint_rejects_records_without_required_orbit_elements():
    incomplete_record = {**SGP4_READY_RECORD, "ARG_OF_PERICENTER": None}
    catalog = SatelliteCatalog.from_records(
        [incomplete_record], ingested_at=datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    )
    app = create_app(catalog=catalog)
    client = TestClient(app)

    response = client.get("/satellites/25544/position?at=2026-05-28T03:00:00Z")

    assert response.status_code == 422
    assert "required orbit elements" in response.json()["detail"]
