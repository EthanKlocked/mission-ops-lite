# Decisions

## PR 1

- Backend stack: Python + FastAPI + Pydantic + httpx.
- Package manager/test runner: `uv` with pytest.
- Data source: CelesTrak active GP JSON endpoint.
- Record identity for API path: `norad_cat_id`.
- Raw records are preserved internally on the normalized record but excluded from API responses by default.
- Detail API supports `?include_raw=true` for explicit trace inspection.
- Freshness thresholds for PR 1:
  - `fresh`: EPOCH age <= 72 hours at ingestion time.
  - `stale`: EPOCH age > 72 hours.
  - `unknown`: missing/unparseable EPOCH.
- Timestamp model:
  - `epoch`: source event time from CelesTrak EPOCH.
  - `ingested_at`: local ingestion time when source records are normalized.
  - `generated_at`: reserved for later simulated/derived data, not used in PR 1.

## PR 2

- Storage: SQLite via Python standard library `sqlite3`, with no external database service.
- Default local database path: `data/mission_ops_lite.db`.
- Database files are ignored by git; schema lives in code.
- Cache policy: successful CelesTrak ingestions are reused for 2 hours by default to avoid repeatedly downloading near-static source snapshots.
- `POST /ingest/celestrak?force=true` bypasses the cache for explicit refresh.
- Store ingestion run history, stable satellite identifiers, and orbit snapshots separately so later history queries or position propagation can build on the same schema.

## PR 3

- Next milestone: SGP4-derived approximate position endpoint.
- Endpoint: `GET /satellites/{norad_cat_id}/position?at=...`.
- Dependency: `sgp4` Python package, constrained to `>=2.23,<3.0`.
- Source data boundary: CelesTrak GP/TLE-style records provide public orbit elements at `EPOCH`, not direct latest latitude/longitude/altitude.
- Response framing: "SGP4-derived approximate position from public orbit elements."
- Coordinate output: return SGP4 position/velocity in TEME, plus an approximate geodetic convenience field for latitude, longitude, and altitude.
- Explicit non-goals: no live spacecraft telemetry, no real-time spacecraft tracking claim, no actual spacecraft position certification, no mission-grade flight dynamics validation, and no RF/downlink or command/control interface.
- Roadmap order after this milestone: ground-station visibility/contact-window calculation, then clearly labeled simulated telemetry plus anomaly/event workflow.

## PR 4

- Next milestone: ground-station visibility/contact-window calculation.
- Endpoint: `GET /satellites/{norad_cat_id}/contact-windows?...`.
- Inputs: ground-station latitude/longitude/altitude, display name, planning range start/end, sampling step, and minimum elevation.
- Calculation approach: sample SGP4-derived approximate geodetic positions over the requested range, convert satellite and ground-station coordinates to approximate ECEF, compute topocentric elevation, and group contiguous samples above the minimum elevation threshold.
- Response framing: "SGP4-derived approximate visibility from public orbit elements."
- Derived contact-window requests are read-only; results are not stored in SQLite.
- Explicit non-goals: no RF link budget, antenna mask, terrain, weather, scheduling conflicts, downlink/telecommand modeling, or mission-grade contact validation.
- Roadmap order after this milestone: frontend dashboard/2D visualization direction check, then simulated telemetry plus anomaly/event workflow if still prioritized.
