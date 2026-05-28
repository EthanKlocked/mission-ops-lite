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
