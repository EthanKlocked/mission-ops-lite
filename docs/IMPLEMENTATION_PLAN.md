# Approximate 3D Orbit Playback Implementation Plan

**Goal:** Add approximate 3D orbit playback using existing SGP4 propagation and local dashboard rendering.

**Architecture:** Keep the backend as a read-only derived data API over public CelesTrak GP orbit records. Add an `/orbit-track` endpoint that samples existing SGP4 propagation across a bounded time range. Render the track locally in the React dashboard with Three.js/React Three Fiber using a procedural globe, orbit path, moving satellite marker, and playback controls.

**Tech Stack:** FastAPI, Pydantic-compatible response models, pytest, React, TypeScript, Vite, Three.js, React Three Fiber, local CSS.

---

## Task 1: Add failing PR9 backend tests

**Objective:** Capture the `/orbit-track` acceptance criteria before implementation.

**Files:**
- Create: `tests/test_pr9_orbit_track.py`

**Test coverage:**
- Happy path returns deterministic sampled track points with timestamps, TEME `position_km`, approximate geodetic coordinates, sequence indexes, lineage, and limitations.
- Unknown satellite returns 404.
- Invalid time range and invalid step/sample bounds return 422.
- Response wording states approximate public-orbit-derived playback, not live tracking or mission-grade validation.

**RED verification:**

```bash
uv run --extra dev python -m pytest tests/test_pr9_orbit_track.py -q
```

Expected initial result: route-not-found failure before endpoint implementation.

## Task 2: Implement orbit-track propagation helper

**Objective:** Reuse `propagate_sgp4_position` to build a bounded sequence of track points.

**Files:**
- Modify: `src/mission_ops_lite/propagation.py`
- Modify: `src/mission_ops_lite/models.py`

**Implementation notes:**
- Add parser for start/end/step parameters or reuse timestamp parsing where appropriate.
- Generate inclusive samples from start to end while capping total points.
- Preserve SGP4/TEME terminology and approximate geodetic conversion.
- Return limitations that prohibit live tracking/mission-grade interpretation.

## Task 3: Expose read-only FastAPI endpoint

**Objective:** Add an API route without persistence, external map services, tokens, or deployment dependencies.

**Endpoint:**

```http
GET /satellites/{norad_cat_id}/orbit-track?start=<iso>&end=<iso>&step_seconds=120
```

**Files:**
- Modify: `src/mission_ops_lite/api.py`

**GREEN verification:**

```bash
uv run --extra dev python -m pytest tests/test_pr9_orbit_track.py -q
uv run --extra dev python -m pytest -q
```

## Task 4: Add Three.js/React Three Fiber dashboard playback

**Objective:** Render approximate local orbit playback in the existing dashboard.

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**UI elements:**
- Approximate 3D orbit playback card.
- Procedural globe, orbit path, and moving satellite marker.
- Start/end/step controls plus load track button.
- Play/pause, reset, speed, and scrub controls.
- Visible copy: public orbit-derived, approximate, no external map service, not live tracking, not mission-grade.

## Task 5: Update docs and QA evidence

**Files:**
- Modify: `README.md`
- Modify: `docs/CREATOR_HANDOFF.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/QA_REPORT.md`
- Create local-only seed: `.ouroboros/seeds/mission-ops-lite-pr9-approx-3d-orbit-playback.yaml`

**Final verification commands:**

```bash
uv run --extra dev python -m pytest -q
cd frontend && npm audit --audit-level=moderate && npm run build
git grep -n -i 'portfolio\|포트폴리오' -- ':!docs/QA_REPORT.md' ':!docs/DECISIONS.md' ':!docs/IMPLEMENTATION_PLAN.md' || true
git grep -n -i 'Cesium\|Ion\|token\|external map\|live tracking\|mission-grade' -- README.md docs src frontend || true
```

Allowed occurrences of prohibited terms must be explicit non-goal/boundary statements only.
