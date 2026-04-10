from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Parcel, ParcelSignal
from app.schemas import AppealScore, CompProperty, InsightHitList, ParcelAnalysis, ParcelRead


async def get_parcel(db: AsyncSession, par_id: str) -> Parcel | None:
    result = await db.execute(select(Parcel).where(Parcel.par_id == par_id))
    return result.scalar_one_or_none()


async def get_appeal_score(db: AsyncSession, par_id: str) -> AppealScore | None:
    parcel = await get_parcel(db, par_id)
    if not parcel:
        return None

    if not parcel.acres or parcel.acres <= 0 or not parcel.totl_appr:
        return AppealScore(
            par_id=par_id,
            address=parcel.prop_addr,
            lu_code=parcel.lu_code,
            prop_zip=parcel.prop_zip,
            totl_appr=parcel.totl_appr,
            appeal_score=0.0,
            recommendation="INSUFFICIENT_DATA",
        )

    vpa = parcel.totl_appr / parcel.acres

    # Get zip+lu median
    zip_median_result = await db.execute(
        select(
            func.percentile_cont(0.5)
            .within_group(
                (Parcel.totl_appr / Parcel.acres).asc()
            )
        ).where(
            Parcel.lu_code == parcel.lu_code,
            Parcel.prop_zip == parcel.prop_zip,
            Parcel.acres > 0,
            Parcel.totl_appr > 0,
        )
    )
    zip_median = zip_median_result.scalar_one_or_none()

    lu_median_result = await db.execute(
        select(
            func.percentile_cont(0.5)
            .within_group(
                (Parcel.totl_appr / Parcel.acres).asc()
            )
        ).where(
            Parcel.lu_code == parcel.lu_code,
            Parcel.acres > 0,
            Parcel.totl_appr > 0,
        )
    )
    lu_median = lu_median_result.scalar_one_or_none()

    pct_above_zip = ((vpa - zip_median) / zip_median) if zip_median else None
    pct_above_lu = ((vpa - lu_median) / lu_median) if lu_median else None

    asr = (
        parcel.totl_appr / parcel.sale_price
        if parcel.sale_price and parcel.sale_price > 0
        else None
    )
    above_sale = (
        bool(parcel.totl_appr > parcel.sale_price)
        if parcel.sale_price and parcel.sale_price > 0
        else None
    )

    zoning = parcel.zoning or ""
    lu = parcel.lu_code or ""
    mismatch = (lu.startswith("R") and not zoning.startswith("R")) or (
        lu.startswith("C") and not zoning.startswith("C")
    )

    score = max(
        0.0,
        min(
            100.0,
            (pct_above_zip or 0) * 30
            + (pct_above_lu or 0) * 20
            + (15.0 if above_sale else 0)
            + (15.0 if mismatch else 0),
        ),
    )

    if score >= 70:
        rec = "STRONG_CANDIDATE"
    elif score >= 40:
        rec = "MODERATE_CANDIDATE"
    elif mismatch:
        rec = "REVIEW_ZONING"
    else:
        rec = "NORMAL"

    return AppealScore(
        par_id=par_id,
        address=parcel.prop_addr,
        lu_code=parcel.lu_code,
        prop_zip=parcel.prop_zip,
        totl_appr=parcel.totl_appr,
        value_per_acre=vpa,
        zip_median_vpa=zip_median,
        lu_median_vpa=lu_median,
        pct_above_zip_median=pct_above_zip,
        pct_above_lu_median=pct_above_lu,
        assessment_to_sale_ratio=asr,
        assessed_above_sale=above_sale,
        zoning_lu_mismatch=mismatch,
        appeal_score=score,
        recommendation=rec,
    )


async def get_comps(
    db: AsyncSession,
    par_id: str,
    limit: int = 10,
) -> list[CompProperty]:
    parcel = await get_parcel(db, par_id)
    if not parcel or not parcel.acres:
        return []

    result = await db.execute(
        select(
            Parcel.par_id,
            Parcel.prop_addr,
            Parcel.acres,
            Parcel.totl_appr,
            Parcel.sale_price,
            Parcel.sale_date,
            (Parcel.totl_appr / Parcel.acres).label("value_per_acre"),
        )
        .where(
            Parcel.par_id != par_id,
            Parcel.lu_code == parcel.lu_code,
            Parcel.prop_zip == parcel.prop_zip,
            Parcel.acres.between(parcel.acres * 0.75, parcel.acres * 1.25),
            Parcel.acres > 0,
            Parcel.totl_appr > 0,
        )
        .order_by((Parcel.totl_appr / Parcel.acres).asc())
        .limit(limit)
    )
    rows = result.fetchall()
    return [
        CompProperty(
            par_id=r.par_id,
            prop_addr=r.prop_addr,
            acres=r.acres,
            totl_appr=r.totl_appr,
            value_per_acre=r.value_per_acre,
            sale_price=r.sale_price,
            sale_date=r.sale_date,
        )
        for r in rows
    ]


async def get_parcel_analysis(db: AsyncSession, par_id: str) -> ParcelAnalysis | None:
    parcel = await get_parcel(db, par_id)
    if not parcel:
        return None
    appeal = await get_appeal_score(db, par_id)
    comps = await get_comps(db, par_id)
    return ParcelAnalysis(
        parcel=ParcelRead.model_validate(parcel),
        appeal=appeal,
        comps=comps,
    )


async def get_hit_list(
    db: AsyncSession,
    lu_code: str | None = None,
    prop_zip: str | None = None,
    min_score: float = 50.0,
    limit: int = 100,
) -> InsightHitList:
    query = (
        select(
            Parcel.par_id,
            Parcel.prop_addr,
            Parcel.lu_code,
            Parcel.prop_zip,
            Parcel.totl_appr,
            (Parcel.totl_appr / Parcel.acres).label("value_per_acre"),
            ParcelSignal.z_score_zip,
            ParcelSignal.pct_above_zip_median,
            ParcelSignal.pct_above_lu_median,
            ParcelSignal.assessment_to_sale_ratio,
            ParcelSignal.assessed_above_sale,
            ParcelSignal.zoning_lu_mismatch,
            ParcelSignal.appeal_score,
            ParcelSignal.recommendation,
        )
        .join(ParcelSignal, Parcel.par_id == ParcelSignal.par_id)
        .where(ParcelSignal.appeal_score >= min_score)
    )

    if lu_code:
        query = query.where(Parcel.lu_code == lu_code)
    if prop_zip:
        query = query.where(Parcel.prop_zip == prop_zip)

    query = query.order_by(ParcelSignal.appeal_score.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.fetchall()

    parcels = [
        AppealScore(
            par_id=r.par_id,
            address=r.prop_addr,
            lu_code=r.lu_code,
            prop_zip=r.prop_zip,
            totl_appr=r.totl_appr,
            value_per_acre=r.value_per_acre,
            z_score_zip=r.z_score_zip,
            pct_above_zip_median=r.pct_above_zip_median,
            pct_above_lu_median=r.pct_above_lu_median,
            assessment_to_sale_ratio=r.assessment_to_sale_ratio,
            assessed_above_sale=r.assessed_above_sale,
            zoning_lu_mismatch=r.zoning_lu_mismatch,
            appeal_score=r.appeal_score,
            recommendation=r.recommendation,
        )
        for r in rows
    ]

    return InsightHitList(total=len(parcels), parcels=parcels)
