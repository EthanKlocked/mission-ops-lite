# Mission Ops Lite

Mission Ops Lite is a private-first portfolio project for mission-data / operations-policy simulation.

The current backend ingests public CelesTrak active GP orbit metadata, normalizes records, preserves raw traceability internally, stores the latest catalog in SQLite, and exposes bounded catalog/detail APIs.

## What this is

- A mission-data modeling backend.
- A public satellite/orbit catalog ingestion service using CelesTrak GP JSON.
- A timestamp-lineage demonstration that separates source event time from ingestion time.
- A foundation for later simulated telemetry and operations-policy comparison.

## What this is not

- No live spacecraft connection.
- No RF/downlink processing.
- No telecommand capability.
- Not flight software.
- No mission-grade validation claim.
- Simulated telemetry, when added in later PRs, is not real spacecraft telemetry.
- This is not a fake satellite control console.

## Data lineage labels

PR 1 uses only `real_public_orbit_data` from CelesTrak.

Timestamp fields:

- `epoch`: source event time from the CelesTrak `EPOCH` field.
- `ingested_at`: local time when the source record was normalized into the catalog.
- `generated_at`: reserved for future simulated/derived data; not emitted in PR 1.

Raw CelesTrak records are preserved on internal normalized records for traceability. API responses intentionally do not include `raw_record` unless the caller explicitly requests it on the detail endpoint with `?include_raw=true`.

## Storage and cache

The default local server uses SQLite at:

```text
data/mission_ops_lite.db
```

The database file is intentionally ignored by git. It stores:

- ingestion run history
- stable satellite identifiers
- orbit data snapshots for the latest and prior successful ingestions

`POST /ingest/celestrak` uses a 2-hour cache window by default. If a successful ingestion happened recently, the API returns the cached latest catalog instead of downloading the same CelesTrak snapshot again. Use `?force=true` to force a fresh upstream fetch.

## API

### `POST /ingest/celestrak`

Fetches live active GP JSON records from:

```text
https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json
```

The response returns normalized records after ingestion. If the SQLite cache is still fresh, this returns the latest cached catalog without re-fetching. Add `?force=true` to bypass the cache.

CelesTrak may return `403 Forbidden` when the same dataset has already been downloaded recently from the same network before the next data update window. The API translates upstream HTTP/network failures into `502` responses instead of treating them as successful ingestions.

### `GET /satellites`

Returns normalized catalog records without unbounded raw source payloads.

Minimum normalized fields:

- `object_name`
- `object_id`
- `norad_cat_id`
- `epoch`
- `mean_motion`
- `inclination`
- `eccentricity`
- `source`
- `ingested_at`
- `epoch_age_hours`
- `freshness_status`
- `raw_record_available`

### `GET /satellites/{norad_cat_id}`

Returns one normalized satellite record. Add `?include_raw=true` to include the retained raw source record for explicit trace inspection.

### `GET /ingestion-runs`

Returns recent ingestion attempts from SQLite, including source URL, status, record count, and error details when available.

## Freshness model

Freshness is calculated from source `EPOCH` relative to `ingested_at`:

- `fresh`: epoch age is less than or equal to 72 hours.
- `stale`: epoch age is greater than 72 hours.
- `unknown`: `EPOCH` is missing or cannot be parsed.

## Local setup

Requirements:

- Python 3.9+
- `uv`

Install/test:

```bash
uv run --extra dev pytest
```

Run the backend:

```bash
uv run uvicorn mission_ops_lite.api:app --reload
```

Ingest live public CelesTrak data:

```bash
curl -X POST http://127.0.0.1:8000/ingest/celestrak
curl -X POST 'http://127.0.0.1:8000/ingest/celestrak?force=true'
```

Query the catalog:

```bash
curl http://127.0.0.1:8000/satellites
curl http://127.0.0.1:8000/satellites/25544
curl 'http://127.0.0.1:8000/satellites/25544?include_raw=true'
```

## Test strategy

The tests mock the CelesTrak HTTP response through `httpx.MockTransport`, so they can run without network access. They cover:

- CelesTrak client parsing.
- Normalized satellite/orbit record fields.
- Raw record preservation for traceability.
- EPOCH age and `fresh` / `stale` / `unknown` statuses.
- API response bounds so raw records are not exposed by default.
