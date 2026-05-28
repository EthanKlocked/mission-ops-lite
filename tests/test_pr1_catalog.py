from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from mission_ops_lite.api import create_app
from mission_ops_lite.celestrak import CelesTrakClient
from mission_ops_lite.catalog import SatelliteCatalog
from mission_ops_lite.normalization import normalize_celestrak_record


class FakeCelesTrakClient:
    async def fetch_active_gp_records(self):
        return [SAMPLE_RECORD]


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


def test_normalizes_celestrak_record_and_preserves_traceability():
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)

    satellite = normalize_celestrak_record(SAMPLE_RECORD, ingested_at=ingested_at)

    assert satellite.object_name == "ISS (ZARYA)"
    assert satellite.object_id == "1998-067A"
    assert satellite.norad_cat_id == 25544
    assert satellite.epoch.isoformat() == "2026-05-28T02:50:05.123456+00:00"
    assert satellite.mean_motion == pytest.approx(15.49123456)
    assert satellite.inclination == pytest.approx(51.6421)
    assert satellite.eccentricity == pytest.approx(0.0006703)
    assert satellite.source.name == "CelesTrak GP active"
    assert satellite.source.url.startswith("https://celestrak.org/NORAD/elements/gp.php")
    assert satellite.raw_record == SAMPLE_RECORD
    assert satellite.ingested_at == ingested_at
    assert satellite.epoch_age_hours == pytest.approx(1.9986, rel=1e-3)
    assert satellite.freshness_status == "fresh"


def test_freshness_status_can_be_fresh_stale_or_unknown():
    now = datetime(2026, 5, 28, 12, tzinfo=timezone.utc)

    fresh = normalize_celestrak_record(
        {**SAMPLE_RECORD, "EPOCH": (now - timedelta(hours=12)).isoformat()}, ingested_at=now
    )
    stale = normalize_celestrak_record(
        {**SAMPLE_RECORD, "EPOCH": (now - timedelta(hours=80)).isoformat()}, ingested_at=now
    )
    unknown = normalize_celestrak_record({**SAMPLE_RECORD, "EPOCH": None}, ingested_at=now)

    assert fresh.freshness_status == "fresh"
    assert stale.freshness_status == "stale"
    assert unknown.epoch is None
    assert unknown.epoch_age_hours is None
    assert unknown.freshness_status == "unknown"


@pytest.mark.asyncio
async def test_celestrak_client_fetches_active_catalog_with_injected_transport():
    async def handler(request):
        import httpx

        assert str(request.url) == CelesTrakClient.ACTIVE_GP_JSON_URL
        return httpx.Response(200, json=[SAMPLE_RECORD])

    import httpx

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CelesTrakClient(http_client=http_client)
        records = await client.fetch_active_gp_records()

    assert records == [SAMPLE_RECORD]


def test_ingest_api_populates_satellite_catalog_from_injected_celestrak_client():
    app = create_app(celestrak_client=FakeCelesTrakClient())
    client = TestClient(app)

    ingest_response = client.post("/ingest/celestrak")
    assert ingest_response.status_code == 200
    ingest_payload = ingest_response.json()
    assert ingest_payload["count"] == 1
    assert ingest_payload["items"][0]["norad_cat_id"] == 25544
    assert "raw_record" not in ingest_payload["items"][0]

    list_response = client.get("/satellites")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    detail_response = client.get("/satellites/25544")
    assert detail_response.status_code == 200
    assert detail_response.json()["object_name"] == "ISS (ZARYA)"


def test_satellites_api_returns_bounded_normalized_records_without_unbounded_raw_payload():
    ingested_at = datetime(2026, 5, 28, 4, 50, tzinfo=timezone.utc)
    catalog = SatelliteCatalog.from_records([SAMPLE_RECORD], ingested_at=ingested_at)
    app = create_app(catalog=catalog)
    client = TestClient(app)

    list_response = client.get("/satellites")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["object_name"] == "ISS (ZARYA)"
    assert item["norad_cat_id"] == 25544
    assert item["source"]["type"] == "real_public_orbit_data"
    assert item["ingested_at"] == "2026-05-28T04:50:00Z"
    assert item["epoch_age_hours"] == pytest.approx(1.9986, rel=1e-3)
    assert item["freshness_status"] == "fresh"
    assert "raw_record" not in item
    assert item["raw_record_available"] is True

    detail_response = client.get("/satellites/25544")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["norad_cat_id"] == 25544
    assert detail["raw_record_available"] is True
    assert "raw_record" not in detail

    raw_detail_response = client.get("/satellites/25544?include_raw=true")
    assert raw_detail_response.status_code == 200
    assert raw_detail_response.json()["raw_record"]["OBJECT_NAME"] == "ISS (ZARYA)"

    missing_response = client.get("/satellites/999999")
    assert missing_response.status_code == 404
