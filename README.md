# Mission Ops Lite

Mission Ops Lite is a public portfolio project for mission-data / operations-policy simulation.

The current backend ingests public CelesTrak active GP orbit metadata, normalizes records, preserves raw traceability internally, stores the latest catalog in SQLite, and exposes bounded catalog/detail APIs. It can also derive approximate satellite positions and ground-station contact windows for requested timestamps using SGP4 and public orbit elements.

## What this is

- A mission-data modeling backend.
- A public satellite/orbit catalog ingestion service using CelesTrak GP JSON.
- A timestamp-lineage demonstration that separates source event time from ingestion time.
- An SGP4-derived approximate position API from public orbit elements.
- A ground-station visibility/contact-window planning API derived from approximate positions.
- A foundation for later simulated telemetry and operations-policy comparison.

## What this is not

- No live spacecraft connection.
- No RF/downlink processing.
- No RF link-budget, antenna scheduling, terrain masking, or weather modeling.
- No telecommand capability.
- Not flight software.
- No mission-grade validation claim.
- Not live spacecraft telemetry or real-time spacecraft tracking.
- Simulated telemetry, when added in later PRs, is not real spacecraft telemetry.
- This is not a fake satellite control console.

## Data lineage labels

The catalog uses `real_public_orbit_data` from CelesTrak. Position and contact-window outputs are derived from those public orbit elements, not directly measured live position or spacecraft telemetry.

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

### `GET /satellites/{norad_cat_id}/position?at=...`

Returns an SGP4-derived approximate position from public CelesTrak GP orbit elements.

Important framing:

- CelesTrak GP/TLE-style data provides orbit elements at a source `EPOCH`; it does not directly provide latest latitude/longitude/altitude.
- SGP4 uses those orbit elements plus the requested `at` timestamp to propagate an approximate state.
- `position_km` and `velocity_km_s` are returned in the TEME coordinate frame.
- `approximate_geodetic` is included as an approximate latitude/longitude/altitude convenience field.
- This endpoint is not live spacecraft telemetry, real-time spacecraft tracking, or mission-grade flight dynamics validation.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/position?at=2026-05-28T03:00:00Z'
```

### `GET /satellites/{norad_cat_id}/contact-windows?...`

Returns approximate ground-station visibility/contact windows over a requested planning range.

Required query parameters:

- `latitude_deg`: ground-station latitude, from `-90` to `90`.
- `longitude_deg`: ground-station longitude, from `-180` to `180`.
- `start`: ISO-8601 start timestamp.
- `end`: ISO-8601 end timestamp.

Optional query parameters:

- `ground_station_name`: display name, default `Ground station`.
- `altitude_m`: ground-station altitude in meters, default `0`.
- `step_seconds`: sampling interval from `10` to `600`, default `60`.
- `min_elevation_deg`: minimum visibility elevation from `0` to `90`, default `10`.

Important framing:

- This is a planning aid derived from public orbit elements and approximate SGP4 positions.
- The endpoint reads the currently loaded latest catalog record for the requested NORAD ID. On the default server, that latest catalog is restored from SQLite at startup and refreshed by `POST /ingest/celestrak` subject to the 2-hour cache policy.
- Contact windows are sampled estimates; finer `step_seconds` values can improve timing granularity at higher compute cost.
- The response does not model RF link budget, antenna masks, terrain, weather, scheduling conflicts, or operational validation.
- Requests are read-only and do not store derived contact-window outputs in SQLite.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/contact-windows?ground_station_name=Pacific%20demo%20station&latitude_deg=8.45&longitude_deg=-106.20&altitude_m=0&start=2026-05-28T02:45:00Z&end=2026-05-28T03:20:00Z&step_seconds=30&min_elevation_deg=10'
```

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
uv run --extra dev python -m pytest
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
curl 'http://127.0.0.1:8000/satellites/25544/position?at=2026-05-28T03:00:00Z'
curl 'http://127.0.0.1:8000/satellites/25544/contact-windows?latitude_deg=8.45&longitude_deg=-106.20&start=2026-05-28T02:45:00Z&end=2026-05-28T03:20:00Z'
```

## Test strategy

The tests mock the CelesTrak HTTP response through `httpx.MockTransport`, so they can run without network access. They cover:

- CelesTrak client parsing.
- Normalized satellite/orbit record fields.
- Raw record preservation for traceability.
- EPOCH age and `fresh` / `stale` / `unknown` statuses.
- API response bounds so raw records are not exposed by default.
- SGP4-derived approximate position metadata, missing-satellite handling, and insufficient-orbit-element handling.
- Ground-station contact-window responses, empty-window handling, invalid time ranges, and missing-satellite handling.
