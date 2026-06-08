# Operator Dashboard Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a lightweight operator-facing dashboard for the existing Mission Ops Lite backend.

**Architecture:** Keep the backend API unchanged except for browser CORS support and API wording cleanup. Add a standalone React/Vite frontend under `frontend/` that calls the local FastAPI backend and renders the ingestion → satellite selection → position → contact-window flow with clear source/freshness/limitation labels.

**Tech Stack:** FastAPI, pytest, React, TypeScript, Vite, CSS, GitHub Actions.

---

### Task 1: Pre-dashboard repo quality pass

**Objective:** Establish baseline verification and CI before frontend implementation.

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `src/mission_ops_lite/api.py`

**Steps:**
1. Run `uv run --extra dev python -m pytest -q` and confirm backend baseline passes.
2. Add GitHub Actions CI with backend pytest and frontend build jobs.
3. Update FastAPI app description to reflect current capabilities beyond PR1.
4. Add README commands for backend and frontend development.
5. Run public wording scan before commit.

### Task 2: Frontend shell and API client

**Objective:** Add a Vite React frontend and typed API helpers.

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`

**Steps:**
1. Create React/Vite project files under `frontend/`.
2. Define TypeScript response types matching current API responses.
3. Implement API helpers for health, ingest, satellites, satellite detail, position, and contact windows.
4. Configure `VITE_API_BASE_URL` with default `http://127.0.0.1:8000`.

### Task 3: Dashboard UX and components

**Objective:** Implement the operator-facing dashboard flow.

**Files:**
- Create/Modify: `frontend/src/App.tsx`
- Create/Modify: `frontend/src/styles.css`

**Steps:**
1. Build a dashboard header with limitation and lineage labels.
2. Add backend health and ingest refresh controls.
3. Add satellite search/list and selected satellite details.
4. Add approximate position query panel.
5. Add manual/preset ground-station contact-window panel.
6. Add a simple 2D map-style visualization with approximate satellite and ground station markers.
7. Keep browser geolocation absent by default.

### Task 4: Docs and QA evidence

**Objective:** Document local use and verify the milestone.

**Files:**
- Modify: `README.md`
- Modify: `docs/QA_REPORT.md`
- Modify: `docs/DECISIONS.md`

**Steps:**
1. Document dashboard setup/run/build commands.
2. Record mentor direction and dashboard decisions.
3. Run `uv run --extra dev python -m pytest -q`.
4. Run `cd frontend && npm run build`.
5. Run public wording scan for disallowed public-facing terms and overclaiming.
6. Use Ouroboros QA against the Seed acceptance criteria.
