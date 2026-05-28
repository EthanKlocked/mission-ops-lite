from __future__ import annotations

from typing import Any, Optional, Protocol

import httpx
from fastapi import FastAPI, HTTPException, Query

from .catalog import SatelliteCatalog
from .celestrak import CelesTrakClient
from .models import SatelliteListResponse, SatelliteOrbitRecord, SatelliteResponse


class CelesTrakFetcher(Protocol):
    async def fetch_active_gp_records(self) -> list[dict[str, Any]]: ...


def _to_response(record: SatelliteOrbitRecord, *, include_raw: bool = False) -> SatelliteResponse:
    return SatelliteResponse(
        object_name=record.object_name,
        object_id=record.object_id,
        norad_cat_id=record.norad_cat_id,
        epoch=record.epoch,
        mean_motion=record.mean_motion,
        inclination=record.inclination,
        eccentricity=record.eccentricity,
        source=record.source,
        ingested_at=record.ingested_at,
        epoch_age_hours=record.epoch_age_hours,
        freshness_status=record.freshness_status,
        raw_record_available=bool(record.raw_record),
        raw_record=record.raw_record if include_raw else None,
    )


def create_app(
    catalog: Optional[SatelliteCatalog] = None,
    celestrak_client: Optional[CelesTrakFetcher] = None,
) -> FastAPI:
    app = FastAPI(
        title="Mission Ops Lite",
        version="0.1.0",
        description=(
            "PR1 API for public CelesTrak satellite catalog ingestion, normalization, "
            "and EPOCH freshness modeling."
        ),
    )
    app.state.catalog = catalog or SatelliteCatalog.empty()
    app.state.celestrak_client = celestrak_client or CelesTrakClient()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest/celestrak", response_model=SatelliteListResponse, response_model_exclude_none=True)
    async def ingest_celestrak() -> SatelliteListResponse:
        try:
            records = await app.state.celestrak_client.fetch_active_gp_records()
        except httpx.HTTPStatusError as exc:
            detail = f"CelesTrak request failed with HTTP {exc.response.status_code}"
            if exc.response.status_code == 403:
                detail += "; CelesTrak may reject repeated downloads until data updates"
            raise HTTPException(status_code=502, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="CelesTrak request failed") from exc
        app.state.catalog = SatelliteCatalog.from_records(records)
        return SatelliteListResponse(
            count=len(app.state.catalog.list_satellites()),
            items=[_to_response(record) for record in app.state.catalog.list_satellites()],
        )

    @app.get("/satellites", response_model=SatelliteListResponse, response_model_exclude_none=True)
    def list_satellites() -> SatelliteListResponse:
        records = app.state.catalog.list_satellites()
        return SatelliteListResponse(count=len(records), items=[_to_response(record) for record in records])

    @app.get("/satellites/{norad_cat_id}", response_model=SatelliteResponse, response_model_exclude_none=True)
    def get_satellite(
        norad_cat_id: int, include_raw: bool = Query(default=False, description="Include trace raw source record")
    ) -> SatelliteResponse:
        record = app.state.catalog.get_satellite(norad_cat_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Satellite not found")
        return _to_response(record, include_raw=include_raw)

    return app


app = create_app()
