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
- Simulated telemetry summary and operations policy comparison are not implemented by design.

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

## PR 5 dashboard verification

### Backend regression, frontend audit, frontend build

Executed on `2026-06-08T08:59:59Z` from branch `feat/operator-dashboard`.

```bash
uv run --extra dev python -m pytest -q
cd frontend
npm audit --audit-level=moderate
npm run build
```

Result:

```text
15 passed
found 0 vulnerabilities
vite v6.4.3 building for production...
✓ built
```

### Local server smoke

Backend command used for smoke testing:

```bash
PYTHONPATH=src uv run python -m uvicorn mission_ops_lite.api:app --host 127.0.0.1 --port 8000
```

Frontend commands used for smoke testing:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
npm run dev -- --host 127.0.0.1 --port 5174
```

Local API smoke results:

```text
GET /health -> 200 {"status":"ok"}
GET /satellites -> 200, count 15630 after CelesTrak ingest/use-cache flow
GET /satellites/25544/position?at=2026-06-08T17:55:00Z -> 200, is_approximate true
GET /satellites/25544/contact-windows?... -> 200, count 0, is_approximate true
```

Additional browser CORS check on `2026-06-08T09:06:46Z`:

```text
OPTIONS /health from Origin http://127.0.0.1:5174 -> 200 with access-control-allow-origin: http://127.0.0.1:5174
```

### Browser smoke

Browser-tested dashboard at:

```text
http://127.0.0.1:5173
http://127.0.0.1:5174
```

Observed flow:

1. Dashboard loaded with backend health badge `Backend ok`.
2. `Ingest / use cache` / cached startup flow loaded CelesTrak GP active catalog data.
3. Search for `25544` returned `ISS (ZARYA)`.
4. Selected satellite detail displayed NORAD ID, object ID, source epoch, ingested time, epoch age, inclination, source lineage, and freshness.
5. Approximate position calculation displayed latitude, longitude, altitude, and TEME frame.
6. Contact-window estimate returned a valid zero-window table for the selected Pacific demo station/time range.
7. 2D context panel displayed satellite and ground-station markers and retained approximate/orientation-only framing.
8. Browser console reported no JavaScript errors during navigation, ingestion/cache load, selection, and calculation checks.

Issue found and fixed during smoke:

- The initial CORS allowlist only covered Vite port `5173`; a dev server running on `5174` showed `Backend offline` / `Failed to fetch` even though the backend was healthy.
- Fixed by changing the backend CORS configuration to allow local Vite dev origins matching `http://127.0.0.1:517[0-9]` and `http://localhost:517[0-9]`.
- Re-ran backend tests after the fix: `15 passed`.

Screenshot evidence:

```text
/Users/ethanklocked/.hermes/profiles/personal-creator/cache/screenshots/browser_screenshot_609fbe6ee8354551a654b25dcdd07370.png
/Users/ethanklocked/.hermes/profiles/personal-creator/cache/screenshots/browser_screenshot_02ce0154654843f5a50c138d67a41a17.png
```

### Public wording/framing scan

```bash
git grep -n -i 'portfolio\|포트폴리오' -- ':!docs/QA_REPORT.md' ':!docs/DECISIONS.md' ':!docs/IMPLEMENTATION_PLAN.md' || true
```

Result: no public-facing matches.

Overclaim scan found only explicit non-goal/limitation language for live telemetry, real-time tracking, RF/downlink, telecommand, and mission-grade claims.

