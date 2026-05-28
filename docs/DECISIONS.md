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
