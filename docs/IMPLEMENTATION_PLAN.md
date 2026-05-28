# Implementation Plan — PR 1

1. Create FastAPI/Python project skeleton.
2. Write TDD tests for normalization, freshness, CelesTrak client, and API response bounds.
3. Implement source models and normalization.
4. Implement CelesTrak client with injectable `httpx.AsyncClient` for mock testing.
5. Implement in-memory satellite catalog and APIs.
6. Add README limitations and run instructions.
7. Run tests and local API smoke check.
