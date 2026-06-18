# Simulated Telemetry and Event Workflow Implementation Plan

> **For Hermes:** Use test-driven-development and requesting-code-review skills before commit.

**Goal:** Add a clearly labeled simulated telemetry and simulated event workflow layer on top of public CelesTrak orbit context.

**Architecture:** Keep public orbit ingestion, SGP4 position, contact-window estimates, and simulated telemetry as separate data layers. Implement deterministic scenario generation in a backend module, expose read-only FastAPI endpoints, and add modest dashboard panels for scenario controls, subsystem health, events, runbook summary, and policy comparison.

**Tech Stack:** FastAPI, Pydantic-compatible dict responses, pytest, React, TypeScript, Vite, CSS.

---

## Task 1: Add failing PR6 backend tests

**Objective:** Capture the PR6 acceptance criteria before implementation.

**Files:**
- Create: `tests/test_pr6_simulated_telemetry.py`
- Create: `tests/test_pr6_event_workflow.py`
- Create: `tests/test_pr6_policy_comparison.py`

**Verification:**

```bash
uv run --extra dev python -m pytest tests/test_pr6_simulated_telemetry.py tests/test_pr6_event_workflow.py tests/test_pr6_policy_comparison.py -q
```

Initial RED result: expected route-not-found failures before the endpoint implementation.

## Task 2: Implement deterministic simulated telemetry engine

**Objective:** Generate scenario-backed subsystem samples that are deterministic for a fixed satellite/scenario/seed/duration/step.

**Files:**
- Create: `src/mission_ops_lite/simulated_telemetry.py`

**Implementation notes:**
- Required scenarios: `nominal`, `thermal_drift`, `power_drop`, `comms_degradation`.
- Required subsystems: `power`, `thermal`, `communications`, `payload`, `attitude_mode`.
- Every response includes `data_kind`, `simulation_version`, `generated_at`, `seed`, satellite identity, source orbit epoch, limitations, and sample lineage fields.
- Limitations explicitly say this is not real/live spacecraft telemetry and not mission-grade operations software.

## Task 3: Implement policy event and comparison logic

**Objective:** Turn telemetry samples into warning/critical events under policy profiles and compare policies over the same stream.

**Files:**
- Modify: `src/mission_ops_lite/simulated_telemetry.py`

**Implementation notes:**
- Required policies: `conservative_ops`, `balanced_ops`, `relaxed_ops`.
- Policies differ by thresholds and persistence requirements.
- Event payloads include ID, event time, subsystem, severity, scenario, policy, triggering measurement, value, threshold, summary, recommended operator check, and `is_simulated`.
- Comparison output includes event counts, first warning/critical time, top affected subsystem, recommended action, and policy notes.

## Task 4: Expose read-only FastAPI endpoints

**Objective:** Add API routes without adding persistence, external services, secrets, or deployment dependencies.

**Files:**
- Modify: `src/mission_ops_lite/api.py`

**Endpoints:**

```http
GET /satellites/{norad_cat_id}/telemetry/simulated
GET /satellites/{norad_cat_id}/events/simulated
GET /satellites/{norad_cat_id}/ops-policy-comparison
```

**Verification:**

```bash
uv run --extra dev python -m pytest tests/test_pr6_simulated_telemetry.py tests/test_pr6_event_workflow.py tests/test_pr6_policy_comparison.py -q
```

GREEN result observed: `8 passed`.

## Task 5: Extend dashboard modestly

**Objective:** Add evidence-oriented simulated telemetry workflow panels without redesigning the dashboard.

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**UI elements:**
- Scenario selector.
- Policy selector.
- Seed/duration/step controls.
- Subsystem health tiles.
- Event timeline.
- Runbook-style summary.
- Policy comparison table.
- Clear simulated/not-live labels.

**Verification:**

```bash
cd frontend
npm audit --audit-level=moderate
npm run build
```

## Task 6: Update docs and PR evidence

**Objective:** Document safe public wording, endpoints, local run commands, test evidence, and limitations.

**Files:**
- Modify: `README.md`
- Modify: `docs/CREATOR_HANDOFF.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/QA_REPORT.md`
- Create: `.ouroboros/seeds/mission-ops-lite-pr6-simulated-telemetry-events.yaml`

**Final verification commands:**

```bash
uv run --extra dev python -m pytest -q
cd frontend && npm audit --audit-level=moderate && npm run build
git grep -n -i 'portfolio\|포트폴리오' -- ':!docs/QA_REPORT.md' ':!docs/DECISIONS.md' ':!docs/IMPLEMENTATION_PLAN.md' || true
git grep -n -i 'live telemetry\|real spacecraft health\|mission control\|flight operations system\|validated spacecraft anomaly detection' -- README.md docs src frontend || true
```
