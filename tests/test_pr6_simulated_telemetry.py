from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from mission_ops_lite.api import create_app
from mission_ops_lite.catalog import SatelliteCatalog


SAMPLE_RECORD = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "NORAD_CAT_ID": 25544,
    "EPOCH": "2026-05-28T02:50:05.123456",
    "MEAN_MOTION": 15.49123456,
    "INCLINATION": 51.6421,
    "ECCENTRICITY": 0.0006703,
    "RA_OF_ASC_NODE": 11.22,
}


def client_with_sample_catalog() -> TestClient:
    catalog = SatelliteCatalog.from_records(
        [SAMPLE_RECORD], ingested_at=datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    )
    return TestClient(create_app(catalog=catalog))


def test_simulated_telemetry_is_labeled_and_deterministic_for_fixed_seed():
    client = client_with_sample_catalog()

    first = client.get(
        "/satellites/25544/telemetry/simulated",
        params={"scenario": "thermal_drift", "seed": 42, "duration_minutes": 15, "step_seconds": 300},
    )
    second = client.get(
        "/satellites/25544/telemetry/simulated",
        params={"scenario": "thermal_drift", "seed": 42, "duration_minutes": 15, "step_seconds": 300},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload == second_payload
    assert first_payload["data_kind"] == "simulated_telemetry"
    assert first_payload["scenario"] == "thermal_drift"
    assert first_payload["simulation_version"]
    assert first_payload["norad_cat_id"] == 25544
    assert first_payload["object_name"] == "ISS (ZARYA)"
    assert any("not real spacecraft telemetry" in item.lower() for item in first_payload["limitations"])
    assert {"power", "thermal", "communications", "payload", "attitude_mode"}.issubset(
        {sample["subsystem"] for sample in first_payload["samples"]}
    )
    first_sample = first_payload["samples"][0]
    assert first_sample["source_event_time"]
    assert first_sample["generated_at"]
    assert first_sample["sequence_count"] == 0
    assert {"measurement_name", "measurement_value", "unit", "status", "quality_flag"}.issubset(first_sample)


def test_all_required_scenarios_are_supported_and_unknown_scenario_returns_422():
    client = client_with_sample_catalog()

    for scenario in ["nominal", "thermal_drift", "power_drop", "comms_degradation"]:
        response = client.get(
            "/satellites/25544/telemetry/simulated",
            params={"scenario": scenario, "seed": 7, "duration_minutes": 5, "step_seconds": 300},
        )
        assert response.status_code == 200
        assert response.json()["scenario"] == scenario

    unknown = client.get("/satellites/25544/telemetry/simulated", params={"scenario": "solar_flare"})
    assert unknown.status_code == 422


def test_missing_satellite_for_simulated_telemetry_returns_404():
    client = client_with_sample_catalog()

    response = client.get("/satellites/999999/telemetry/simulated", params={"scenario": "nominal"})

    assert response.status_code == 404
