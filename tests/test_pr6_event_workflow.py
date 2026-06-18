from datetime import datetime, timezone

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


def test_nominal_scenario_generates_no_warning_or_critical_events_under_balanced_policy():
    client = client_with_sample_catalog()

    response = client.get(
        "/satellites/25544/events/simulated",
        params={"scenario": "nominal", "policy": "balanced_ops", "seed": 42},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_kind"] == "simulated_event_workflow"
    assert payload["scenario"] == "nominal"
    assert payload["policy"] == "balanced_ops"
    assert payload["event_count"] == 0
    assert all(event["severity"] not in {"warning", "critical"} for event in payload["events"])
    assert "simulated spacecraft telemetry" in payload["runbook_summary"].lower()


def test_thermal_drift_generates_warning_or_critical_events_with_runbook_fields():
    client = client_with_sample_catalog()

    response = client.get(
        "/satellites/25544/events/simulated",
        params={"scenario": "thermal_drift", "policy": "balanced_ops", "seed": 42},
    )

    assert response.status_code == 200
    payload = response.json()
    severities = {event["severity"] for event in payload["events"]}
    assert severities & {"warning", "critical"}
    event = payload["events"][0]
    assert event["event_id"].startswith("SIM-25544-thermal_drift-balanced_ops-")
    assert event["event_time"]
    assert event["subsystem"] == "thermal"
    assert event["scenario"] == "thermal_drift"
    assert event["policy"] == "balanced_ops"
    assert event["triggered_by"] == "battery_temperature_c"
    assert isinstance(event["measurement_value"], (int, float))
    assert isinstance(event["threshold"], (int, float))
    assert event["summary"]
    assert event["recommended_operator_check"]
    assert event["is_simulated"] is True
    assert "thermal" in payload["runbook_summary"].lower()


def test_policy_validation_for_event_workflow():
    client = client_with_sample_catalog()

    unknown_policy = client.get(
        "/satellites/25544/events/simulated",
        params={"scenario": "thermal_drift", "policy": "hair_trigger_ops", "seed": 42},
    )
    missing_satellite = client.get(
        "/satellites/999999/events/simulated",
        params={"scenario": "thermal_drift", "policy": "balanced_ops", "seed": 42},
    )

    assert unknown_policy.status_code == 422
    assert missing_satellite.status_code == 404
