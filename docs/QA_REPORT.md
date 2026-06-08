# QA Report

## PR 1 verification

### TDD red check

```bash
uv run --extra dev pytest tests/test_pr1_catalog.py -q
```

Initial result: failed during collection because `mission_ops_lite` package did not exist yet. This was the expected RED state for the new implementation.

### Unit/API tests

```bash
uv run --extra dev pytest
```

Result:

```text
5 passed in 0.16s
```

Coverage by behavior:

- CelesTrak client parses active GP JSON with injected mock transport.
- Normalization preserves required fields and raw source traceability.
- Freshness model returns `fresh`, `stale`, and `unknown`.
- Mocked `POST /ingest/celestrak` populates catalog, then `GET /satellites` and `GET /satellites/{id}` return normalized records.
- API excludes `raw_record` by default and includes it only with explicit detail query `include_raw=true`.

### Specification review

Result:

```text
PR 1 acceptance criteria were reviewed against the implementation plan, tests, local smoke checks, and remaining limitations.
```

### Live CelesTrak client smoke

First live client smoke succeeded:

```text
{'count': 15487, 'sample_keys': ['ECCENTRICITY', 'EPOCH', 'INCLINATION', 'MEAN_MOTION', 'NORAD_CAT_ID', 'OBJECT_ID', 'OBJECT_NAME'], 'sample_norad': 900}
```

Later repeated live downloads returned CelesTrak `403 Forbidden` with message that GP data had not updated since the last successful download and updates once every 2 hours. The backend now maps upstream HTTP/network failures to `502` instead of returning an internal server error.

### Local app smoke

```bash
uv run uvicorn mission_ops_lite.api:app --host 127.0.0.1 --port 8017
```

Then:

```text
GET /health -> {"status":"ok"}
GET /satellites -> {"count":0,"items":[]}
```

The empty catalog before ingestion is expected.

### Independent QA

Standalone QA verdict:

```text
Score: 0.93 / 1.00 [PASS]
Verdict: pass
```

Follow-up actions from QA were addressed by adding mocked end-to-end ingestion API coverage and documenting CelesTrak repeated-download `403` behavior.

## Limitations remaining

- Catalog storage now persists locally in SQLite, but there is still no managed remote database.
- Live ingestion can be rate/update-window limited by CelesTrak.
- SGP4 position and contact-window outputs are approximate derived data from public orbit elements, not live telemetry or mission-grade flight dynamics/contact validation.
- Contact-window calculation does not model RF link budget, antenna masks, terrain, weather, scheduling conflicts, or operational constraints.
- No dashboard, simulated telemetry summary, or operations policy comparison is implemented by design.

## PR 2 verification

```bash
uv run --extra dev pytest
```

Result:

```text
8 passed in 0.20s
```

Additional coverage:

- SQLite-backed latest catalog persists across app instances.
- Recent successful ingestion uses the cache instead of re-fetching.
- `?force=true` bypasses the cache.
- `GET /ingestion-runs` reports stored ingestion history.

## PR 3 verification

### TDD red check

```bash
uv run --extra dev pytest tests/test_pr3_sgp4_position.py -q
```

Initial result: failed because `GET /satellites/{norad_cat_id}/position` was not implemented yet and returned `404`. This was the expected RED state for the new endpoint.

### Targeted SGP4 position tests

```bash
uv run --extra dev python -m pytest tests/test_pr3_sgp4_position.py -q
```

Result:

```text
3 passed
```

Additional coverage:

- Successful SGP4-derived approximate position response from a representative CelesTrak GP record.
- Response metadata includes source epoch, requested timestamp, time delta from epoch, propagator, coordinate frame, TEME position/velocity, approximate geodetic fields, freshness status, and limitations.
- Unknown satellite returns `404`.
- Records missing required orbit elements return `422`.

### Full regression suite

```bash
uv run --extra dev python -m pytest
```

Result:

```text
11 passed in 0.20s
```

### Local endpoint smoke

A local `TestClient` smoke check for `GET /satellites/25544/position?at=2026-05-28T03:00:00Z` returned `200` with:

```text
{'norad_cat_id': 25544, 'propagator': 'SGP4', 'coordinate_frame': 'TEME', 'is_approximate': True}
```

## PR 4 verification

### TDD red check

```bash
uv run --extra dev python -m pytest tests/test_pr4_contact_windows.py -q
```

Initial result: failed because `GET /satellites/{norad_cat_id}/contact-windows` was not implemented yet and returned `404`. The first assertion expected `200` for the representative visibility request but received `404`; the missing-satellite detail assertion also saw FastAPI's generic `Not Found` because the route did not exist yet. This was the expected RED state for the new endpoint.

### Targeted contact-window tests

```bash
uv run --extra dev python -m pytest tests/test_pr4_contact_windows.py -q
```

Result:

```text
4 passed
```

Additional coverage:

- Successful SGP4-derived approximate contact-window response from a representative CelesTrak GP record.
- Response metadata includes ground station, planning range, step size, minimum elevation, source epoch, freshness status, limitations, and grouped visibility windows.
- Representative case uses a fixed orbit record, fixed ground-station coordinates near the sampled subpoint, and broad assertions for at least one window, peak timestamp, duration, and maximum elevation above the requested threshold.
- No-visibility scenarios return an empty `windows` list with `count: 0`.
- Invalid time ranges return `422`.
- Unknown satellite returns `404`.

### Full regression suite

```bash
uv run --extra dev python -m pytest -q
```

Result:

```text
15 passed
```

### Local endpoint smoke

A local `TestClient` smoke check for `GET /satellites/25544/contact-windows?...` returned `200` with:

```text
{'norad_cat_id': 25544, 'count': 1, 'first_window': [{'start': '2026-05-28T02:57:00Z', 'end': '2026-05-28T03:03:00Z', 'peak_at': '2026-05-28T03:00:00Z', 'duration_seconds': 360.0, 'max_elevation_deg': 89.97014741275501}], 'is_approximate': True}
```
