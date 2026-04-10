from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.embed_service import embed_directory
from app.services.loader_service import (
    load_building_characteristics_from_api,
    load_parcels_from_api,
)
from app.services.signals_service import compute_parcel_signals, reset_signals_flag

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/load-parcels")
async def trigger_load_parcels(
    truncate: bool = False,
    db: AsyncSession = Depends(get_db),
):
    count = await load_parcels_from_api(db, truncate=truncate)
    reset_signals_flag()
    return {"loaded": count}


@router.post("/load-building-chars")
async def trigger_load_building_chars(
    truncate: bool = False,
    db: AsyncSession = Depends(get_db),
):
    count = await load_building_characteristics_from_api(db, truncate=truncate)
    return {"loaded": count}


@router.post("/embed-docs")
async def trigger_embed_docs(db: AsyncSession = Depends(get_db)):
    results = await embed_directory(db, "data/knowledge")
    return {"embedded": results}


@router.post("/signals/recompute")
async def recompute_signals(db: AsyncSession = Depends(get_db)):
    reset_signals_flag()
    count = await compute_parcel_signals(db)
    return {"computed": count}
