from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import InsightHitList, ParcelAnalysis, ParcelRead
from app.services.parcel_service import get_hit_list, get_parcel, get_parcel_analysis

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.get("/hit-list/search", response_model=InsightHitList)
async def hit_list(
    lu_code: str | None = Query(None),
    prop_zip: str | None = Query(None),
    min_score: float = Query(50.0, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await get_hit_list(db, lu_code=lu_code, prop_zip=prop_zip, min_score=min_score, limit=limit)


@router.get("/{par_id}", response_model=ParcelRead)
async def read_parcel(par_id: str, db: AsyncSession = Depends(get_db)):
    parcel = await get_parcel(db, par_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.get("/{par_id}/analysis", response_model=ParcelAnalysis)
async def parcel_analysis(par_id: str, db: AsyncSession = Depends(get_db)):
    analysis = await get_parcel_analysis(db, par_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return analysis
