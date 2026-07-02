# Mission Ops Lite — Creator Handoff

Source handoff copied from `/Users/ethanklocked/Desktop/Workspace/personal/space-career/handoffs/mission-ops-lite-current-implementation-request.md`.

## PR 1 Scope

- Project skeleton
- CelesTrak client for `https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json`
- Raw source record preservation
- Normalized satellite/orbit schema
- EPOCH-based freshness calculation
- `GET /satellites`
- `GET /satellites/{id}`
- Tests
- README limitations and real/simulated/derived data boundary

## PR 1 Non-goals

- Dashboard
- Automated summary
- Operations policy comparison
- Simulated telemetry implementation
- Live spacecraft/RF/telecommand integration

## PR 6 Simulated Telemetry and Event Workflow

Source handoff copied from `/Users/ethanklocked/Desktop/Workspace/personal/space-career/handoffs/mission-ops-lite-pr6-simulated-telemetry-creator-guidance.md`.

Scope implemented on stacked branch `feat/simulated-telemetry-events` from `feat/operator-dashboard`:

- Deterministic simulated spacecraft telemetry layered on public orbit context.
- Scenario profiles: `nominal`, `thermal_drift`, `power_drop`, `comms_degradation`.
- Operations policies: `conservative_ops`, `balanced_ops`, `relaxed_ops`.
- Warning/critical event generation with simulated event payloads and runbook-style summary.
- Policy comparison output showing event counts, first warning/critical timing, affected subsystem, recommendation, and notes.
- Dashboard controls for scenario/policy/seed plus subsystem health tiles, event timeline, and policy comparison.

PR 6 non-goals:

- No live spacecraft telemetry, RF/downlink, command/control, paid APIs, secrets, deployment, or mission-grade validation claim.

## PR 9 Approximate 3D Orbit Playback

Source direction received from SpaceOps Mentor/user in chat: PR #9 is Three.js/React Three Fiber based approximate 3D orbit playback.

Scope:

- Reuse existing SGP4 propagation to expose `GET /satellites/{norad_cat_id}/orbit-track`.
- Return bounded sampled track points with timestamps, TEME position/velocity, approximate geodetic position, source lineage, and limitations.
- Add dashboard 3D globe, orbit path, moving satellite marker, playback controls, speed control, and frame scrubber.
- Use local Three.js/React Three Fiber rendering only.

PR 9 non-goals:

- No Cesium, Cesium Ion token, external map service, live tracking claim, or mission-grade flight dynamics validation claim.
