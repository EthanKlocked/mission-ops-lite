# QA Report — PR 1

## Commands run

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

- Catalog storage is in-memory only for PR 1.
- Live ingestion can be rate/update-window limited by CelesTrak.
- No dashboard, simulated telemetry summary, or operations policy comparison is implemented in PR 1 by design.
