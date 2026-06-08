from fastapi.testclient import TestClient

from mission_ops_lite.api import create_app
from mission_ops_lite.store import SQLiteCatalogStore

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


class FakeCelesTrakClient:
    async def fetch_active_gp_records(self):
        return [SAMPLE_RECORD]


def test_sqlite_store_persists_latest_catalog_across_app_instances(tmp_path):
    db_path = tmp_path / "mission_ops_lite.db"
    first_app = create_app(
        celestrak_client=FakeCelesTrakClient(),
        store=SQLiteCatalogStore(db_path),
    )
    first_client = TestClient(first_app)

    ingest_response = first_client.post("/ingest/celestrak?force=true")

    assert ingest_response.status_code == 200
    assert ingest_response.json()["count"] == 1

    second_app = create_app(store=SQLiteCatalogStore(db_path))
    second_client = TestClient(second_app)

    list_response = second_client.get("/satellites")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["object_name"] == "ISS (ZARYA)"
    assert payload["items"][0]["source"]["type"] == "real_public_orbit_data"


def test_ingest_uses_recent_sqlite_cache_without_refetching(tmp_path):
    class CountingCelesTrakClient:
        def __init__(self):
            self.calls = 0

        async def fetch_active_gp_records(self):
            self.calls += 1
            return [SAMPLE_RECORD]

    db_path = tmp_path / "mission_ops_lite.db"
    celestrak_client = CountingCelesTrakClient()
    app = create_app(
        celestrak_client=celestrak_client,
        store=SQLiteCatalogStore(db_path),
        cache_ttl_hours=2.0,
    )
    client = TestClient(app)

    first_response = client.post("/ingest/celestrak")
    second_response = client.post("/ingest/celestrak")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert celestrak_client.calls == 1
    assert second_response.json()["count"] == 1

    forced_response = client.post("/ingest/celestrak?force=true")
    assert forced_response.status_code == 200
    assert celestrak_client.calls == 2


def test_ingestion_runs_endpoint_reports_sqlite_ingestion_history(tmp_path):
    app = create_app(
        celestrak_client=FakeCelesTrakClient(),
        store=SQLiteCatalogStore(tmp_path / "mission_ops_lite.db"),
    )
    client = TestClient(app)

    client.post("/ingest/celestrak?force=true")
    runs_response = client.get("/ingestion-runs")

    assert runs_response.status_code == 200
    runs = runs_response.json()["items"]
    assert len(runs) == 1
    assert runs[0]["source_name"] == "CelesTrak GP active"
    assert runs[0]["status"] == "success"
    assert runs[0]["record_count"] == 1
