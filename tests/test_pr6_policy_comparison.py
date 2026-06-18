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


def test_policy_comparison_shows_different_event_timing_counts_and_recommendations():
    client = client_with_sample_catalog()

    response = client.get(
        "/satellites/25544/ops-policy-comparison",
        params={"scenario": "thermal_drift", "seed": 42, "duration_minutes": 60, "step_seconds": 300},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_kind"] == "simulated_ops_policy_comparison"
    assert payload["scenario"] == "thermal_drift"
    assert payload["norad_cat_id"] == 25544
    assert set(payload["policies"].keys()) == {"conservative_ops", "balanced_ops", "relaxed_ops"}

    conservative = payload["policies"]["conservative_ops"]
    balanced = payload["policies"]["balanced_ops"]
    relaxed = payload["policies"]["relaxed_ops"]

    for policy_summary in [conservative, balanced, relaxed]:
        assert {"event_count", "first_warning_time", "first_critical_time", "top_affected_subsystem"}.issubset(
            policy_summary
        )
        assert policy_summary["recommended_operator_action"]
        assert policy_summary["policy_notes"]

    assert conservative["event_count"] >= balanced["event_count"] >= relaxed["event_count"]
    assert conservative["first_warning_time"] != relaxed["first_warning_time"]
    assert len({conservative["recommended_operator_action"], relaxed["recommended_operator_action"]}) > 1
    assert "not live spacecraft telemetry" in " ".join(payload["limitations"]).lower()


def test_policy_comparison_validates_scenario_and_missing_satellite():
    client = client_with_sample_catalog()

    unknown_scenario = client.get("/satellites/25544/ops-policy-comparison", params={"scenario": "solar_flare"})
    missing_satellite = client.get("/satellites/999999/ops-policy-comparison", params={"scenario": "thermal_drift"})

    assert unknown_scenario.status_code == 422
    assert missing_satellite.status_code == 404
