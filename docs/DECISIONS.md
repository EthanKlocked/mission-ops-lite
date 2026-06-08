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
