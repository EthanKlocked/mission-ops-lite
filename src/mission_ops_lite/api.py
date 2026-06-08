from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol

import httpx
from fastapi import FastAPI, HTTPException, Query

from .catalog import SatelliteCatalog
from .celestrak import CelesTrakClient
from .models import SatelliteListResponse, SatelliteOrbitRecord, SatelliteResponse
from .store import SQLiteCatalogStore


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
    store: Optional[SQLiteCatalogStore] = None,
    cache_ttl_hours: float = 2.0,
) -> FastAPI:
    app = FastAPI(
        title="Mission Ops Lite",
        version="0.1.0",
        description=(
            "PR1 API for public CelesTrak satellite catalog ingestion, normalization, "
            "and EPOCH freshness modeling."
        ),
    )
    app.state.store = store
    app.state.cache_ttl_hours = cache_ttl_hours
    if catalog is not None:
        app.state.catalog = catalog
    elif store is not None:
        app.state.catalog = store.latest_catalog()
    else:
        app.state.catalog = SatelliteCatalog.empty()
    app.state.celestrak_client = celestrak_client or CelesTrakClient()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest/celestrak", response_model=SatelliteListResponse, response_model_exclude_none=True)
    async def ingest_celestrak(force: bool = Query(default=False)) -> SatelliteListResponse:
        if (
            app.state.store is not None
            and not force
            and app.state.store.has_recent_successful_ingestion(app.state.cache_ttl_hours)
        ):
            app.state.catalog = app.state.store.latest_catalog()
            return _list_response(app.state.catalog)
        try:
            records = await app.state.celestrak_client.fetch_active_gp_records()
        except httpx.HTTPStatusError as exc:
            detail = f"CelesTrak request failed with HTTP {exc.response.status_code}"
            if exc.response.status_code == 403:
                detail += "; CelesTrak may reject repeated downloads until data updates"
            if app.state.store is not None:
                app.state.store.save_failed_ingestion(detail, http_status=exc.response.status_code)
            raise HTTPException(status_code=502, detail=detail) from exc
        except httpx.HTTPError as exc:
            if app.state.store is not None:
                app.state.store.save_failed_ingestion("CelesTrak request failed")
            raise HTTPException(status_code=502, detail="CelesTrak request failed") from exc
        app.state.catalog = SatelliteCatalog.from_records(records)
        if app.state.store is not None:
            app.state.store.save_successful_ingestion(app.state.catalog)
        return _list_response(app.state.catalog)

    @app.get("/satellites", response_model=SatelliteListResponse, response_model_exclude_none=True)
    def list_satellites() -> SatelliteListResponse:
        records = app.state.catalog.list_satellites()
        return SatelliteListResponse(count=len(records), items=[_to_response(record) for record in records])

    @app.get("/ingestion-runs")
    def list_ingestion_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        if app.state.store is None:
            return {"count": 0, "items": []}
        runs = app.state.store.list_ingestion_runs(limit=limit)
        return {"count": len(runs), "items": runs}

    @app.get("/satellites/{norad_cat_id}", response_model=SatelliteResponse, response_model_exclude_none=True)
    def get_satellite(
        norad_cat_id: int, include_raw: bool = Query(default=False, description="Include trace raw source record")
    ) -> SatelliteResponse:
        record = app.state.catalog.get_satellite(norad_cat_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Satellite not found")
        return _to_response(record, include_raw=include_raw)

    return app


def _list_response(catalog: SatelliteCatalog) -> SatelliteListResponse:
    records = catalog.list_satellites()
    return SatelliteListResponse(count=len(records), items=[_to_response(record) for record in records])


app = create_app(store=SQLiteCatalogStore(Path("data/mission_ops_lite.db")))
