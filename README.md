# Mission Ops Lite

Mission Ops Lite is a lightweight backend and local dashboard for public satellite orbit data ingestion, derived position estimates, and operations-planning workflows.

The current system ingests public CelesTrak active GP orbit metadata, normalizes records, preserves raw traceability internally, stores the latest catalog in SQLite, exposes bounded catalog/detail APIs, and provides a local operator-facing dashboard. It can also derive approximate satellite positions, 3D orbit-playback tracks, and ground-station contact windows for requested timestamps using SGP4 and public orbit elements.

## What this is

- A mission-data modeling backend.
- A public satellite/orbit catalog ingestion service using CelesTrak GP JSON.
- Timestamp-lineage handling that separates source event time from ingestion time.
- An SGP4-derived approximate position API from public orbit elements.
- An approximate 3D orbit-playback track API for local dashboard visualization.
- A ground-station visibility/contact-window planning API derived from approximate positions.
- A local operator dashboard for reviewing source lineage, freshness, approximate position, 3D orbit playback, and contact-window estimates.
- A simulation-backed subsystem-health workflow with deterministic telemetry scenarios, warning/critical events, operations-policy comparison, and runbook-style summaries.

## What this is not

- No live spacecraft connection.
- No RF/downlink processing.
- No RF link-budget, antenna scheduling, terrain masking, or weather modeling.
- No telecommand capability.
- Not flight software.
- No mission-grade validation claim.
- Not live spacecraft telemetry or real-time spacecraft tracking.
- No Cesium, Cesium Ion token, or external map service dependency for the 3D globe.
- Simulated telemetry in this project is generated locally and is not real spacecraft telemetry.
- This is not a fake satellite control console.

## Data lineage labels

The catalog uses `real_public_orbit_data` from CelesTrak. Position and contact-window outputs are derived from those public orbit elements, not directly measured live position or spacecraft telemetry.

Timestamp fields:

- `epoch`: source event time from the CelesTrak `EPOCH` field.
- `ingested_at`: local time when the source record was normalized into the catalog.
- `generated_at`: timestamp for derived/simulated outputs generated locally by the API.

## Simulated telemetry and event workflow

The telemetry and event workflow in this project is simulation-backed. It is layered on top of public CelesTrak orbit context to implement operational data modeling patterns: subsystem health, timestamp lineage, warning/critical thresholds, event timelines, policy-driven alerting, and runbook-style operator summaries. It does not ingest live spacecraft telemetry and is not suitable for mission operations.

Implemented scenarios:

- `nominal`
- `thermal_drift`
- `power_drop`
- `comms_degradation`

Implemented operations policy profiles:

- `conservative_ops`: lower warning/critical thresholds and faster escalation.
- `balanced_ops`: short persistence before escalation to balance sensitivity and alert fatigue.
- `relaxed_ops`: higher thresholds and longer persistence for fewer, later alerts.

Simulation outputs are deterministic when the same satellite, scenario, seed, duration, and step are requested.

Raw CelesTrak records are preserved on internal normalized records for traceability. API responses intentionally do not include `raw_record` unless the caller explicitly requests it on the detail endpoint with `?include_raw=true`.

## Walkthrough and visual overview

See [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) for a local review path and repo-owned screenshots of the catalog, source lineage, derived orbit/contact views, simulation-backed operations workflow, and data-platform flow.

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

### `GET /satellites/{norad_cat_id}/orbit-track?start=...&end=...&step_seconds=...`

Returns a bounded sequence of SGP4-derived approximate track points for local 3D orbit playback.

Required query parameters:

- `start`: ISO-8601 start timestamp.
- `end`: ISO-8601 end timestamp.

Optional query parameters:

- `step_seconds`: sampling interval from `10` to `3600`, default `120`.

Important framing:

- The response samples public orbit elements through the same approximate SGP4 propagation used by the position endpoint.
- Each point includes timestamp, sequence, TEME `position_km`, TEME `velocity_km_s`, and approximate geodetic latitude/longitude/altitude.
- The endpoint is read-only and does not store derived track outputs in SQLite.
- The dashboard renders the track with local Three.js/React Three Fiber primitives and does not require Cesium, Cesium Ion tokens, or external map services.
- This endpoint is not live spacecraft tracking or mission-grade flight dynamics validation.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/orbit-track?start=2026-05-28T03:00:00Z&end=2026-05-28T04:30:00Z&step_seconds=180'
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
curl 'http://127.0.0.1:8000/satellites/25544/contact-windows?ground_station_name=Pacific%20ground%20station&latitude_deg=8.45&longitude_deg=-106.20&altitude_m=0&start=2026-05-28T02:45:00Z&end=2026-05-28T03:20:00Z&step_seconds=30&min_elevation_deg=10'
```

### `GET /satellites/{norad_cat_id}/telemetry/simulated?...`

Returns deterministic simulated spacecraft telemetry for a selected satellite. Query parameters:

- `scenario`: one of `nominal`, `thermal_drift`, `power_drop`, `comms_degradation`.
- `seed`: optional deterministic seed.
- `duration_minutes`: simulation duration, default `60`.
- `step_seconds`: sample interval, default `60`.

Each response includes `data_kind: simulated_telemetry`, `simulation_version`, `generated_at`, satellite identity, limitations, and samples with source event time, generated time, sequence count, subsystem, measurement, unit, status, and quality flag.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/telemetry/simulated?scenario=thermal_drift&seed=42&duration_minutes=60&step_seconds=300'
```

### `GET /satellites/{norad_cat_id}/events/simulated?...`

Generates warning/critical events from the simulated telemetry stream under an operations policy profile. Query parameters include `scenario`, `policy`, `seed`, `duration_minutes`, and `step_seconds`.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/events/simulated?scenario=thermal_drift&policy=balanced_ops&seed=42'
```

### `GET /satellites/{norad_cat_id}/ops-policy-comparison?...`

Runs the same simulated telemetry stream through `conservative_ops`, `balanced_ops`, and `relaxed_ops`, returning event counts, first warning/critical timing, top affected subsystem, recommended operator action, and policy notes.

Example:

```bash
curl 'http://127.0.0.1:8000/satellites/25544/ops-policy-comparison?scenario=thermal_drift&seed=42'
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
PYTHONPATH=src uv run python -m uvicorn mission_ops_lite.api:app --reload
```

Run the dashboard in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

The dashboard expects the backend at `http://127.0.0.1:8000` by default. Override with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Build the dashboard:

```bash
cd frontend
npm run build
```

The dashboard uses manual and preset ground-station inputs. It does not request browser geolocation by default.

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
curl 'http://127.0.0.1:8000/satellites/25544/telemetry/simulated?scenario=thermal_drift&seed=42&duration_minutes=60&step_seconds=300'
curl 'http://127.0.0.1:8000/satellites/25544/events/simulated?scenario=thermal_drift&policy=balanced_ops&seed=42'
curl 'http://127.0.0.1:8000/satellites/25544/ops-policy-comparison?scenario=thermal_drift&seed=42'
```

## Data platform extension: PySpark Medallion and Snowflake OLAP contracts

This repository also includes a local-first data engineering layer that processes the same public orbit catalog through PySpark Bronze/Silver/Gold transforms and prepares SQL contracts for OLAP analysis.

Pipeline shape:

```text
CelesTrak raw GP records
  -> Bronze: raw/source-shaped records with raw JSON and ingestion lineage
  -> Silver: normalized orbit snapshots with typed columns, deduplication, freshness, and quality labels
  -> Gold: OLAP-ready freshness/count metrics
  -> Databricks notebook definitions: Bronze/Silver/Gold table materialization structure
  -> Snowflake SQL contracts: warehouse/schema/table/load/query definitions for KPI analysis
```

Key files:

```text
src/mission_ops_lite/data_platform/medallion.py
src/mission_ops_lite/data_platform/run_local_medallion.py
notebooks/databricks/01_bronze_ingest.py
notebooks/databricks/02_silver_transform.py
notebooks/databricks/03_gold_metrics.py
sql/snowflake/01_create_olap_schema.sql
sql/snowflake/02_create_gold_tables.sql
sql/snowflake/03_load_gold_metrics.sql
sql/snowflake/04_analysis_queries.sql
data/sample/celestrak_active_gp_sample.json
```

Run the local PySpark pipeline:

```bash
uv run --extra data python -m mission_ops_lite.data_platform.run_local_medallion
```

Run the data-platform tests:

```bash
uv run --extra dev --extra data python -m pytest tests/test_data_platform_medallion.py tests/test_data_platform_sql_notebooks.py -q
```

The Databricks notebook files are implementation definitions that reuse the same transformation functions and call `saveAsTable(...)` for Bronze/Silver/Gold table materialization. The Snowflake SQL files define the OLAP schema, staged Parquet load contract, and analytical freshness/quality queries. They are pipeline and schema artifacts, not runtime evidence from a live Databricks or Snowflake workspace.

## Test strategy

The tests mock the CelesTrak HTTP response through `httpx.MockTransport`, so they can run without network access. They cover:

- CelesTrak client parsing.
- Normalized satellite/orbit record fields.
- Raw record preservation for traceability.
- EPOCH age and `fresh` / `stale` / `unknown` statuses.
- API response bounds so raw records are not exposed by default.
- SGP4-derived approximate position metadata, missing-satellite handling, and insufficient-orbit-element handling.
- Ground-station contact-window responses, empty-window handling, invalid time ranges, and missing-satellite handling.
- Simulated telemetry scenario generation, fixed-seed determinism, unknown scenario validation, and missing-satellite handling.
- Simulated event workflow thresholding, warning/critical event payloads, policy validation, and runbook-style summaries.
- Operations-policy comparison across conservative, balanced, and relaxed profiles using the same simulated telemetry stream.
- Frontend build verification for the local operator dashboard.
- Data-platform extension behavior: PySpark Bronze raw lineage preservation, Silver typed/deduplicated orbit snapshots, Gold OLAP freshness metrics, Databricks notebook reuse of shared transforms, and Snowflake OLAP SQL definitions.

## Dashboard workflow

The local dashboard under `frontend/` presents the existing backend flow:

1. Check backend health.
2. Load the cached catalog or trigger CelesTrak ingestion.
3. Search/select a satellite from the normalized catalog.
4. Review source attribution, source epoch, ingestion time, and freshness status.
5. Request an SGP4-derived approximate position for a chosen timestamp.
6. Enter a preset/manual ground station and estimate approximate contact windows.
7. Generate deterministic simulated telemetry for a selected scenario/seed.
8. Review subsystem health tiles, policy-driven event timeline, runbook-style summary, and policy comparison.
9. View a simple 2D map-style context panel for satellite and ground-station orientation.

Dashboard labels intentionally keep the same boundaries as the API: public orbit data in, approximate derived estimates and simulated telemetry out, no live telemetry, no validated scheduling, and no mission-grade claim.
