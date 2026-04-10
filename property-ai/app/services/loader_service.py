import re
import httpx
import csv
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.models import (
    BuildingCharacteristic,
    BuildingFootprint,
    BuildingPermit,
    CellTower,
    FloodZone,
    Parcel,
    ZoningDistrict,
)

ARCGIS_PARCELS = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Parcel_Viewer/FeatureServer/0/query"
)
ARCGIS_BUILDING_CHARS = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Building_Characteristics/FeatureServer/0/query"
)


def _normalize_cols(row: dict) -> dict:
    return {
        re.sub(r"[^a-z0-9]", "_", k.lower().strip()).rstrip("_"): v
        for k, v in row.items()
    }


def _point(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    return f"SRID=4326;POINT({lon} {lat})"


async def _arcgis_fetch(url: str, offset: int, batch: int) -> list[dict]:
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "json",
        "resultOffset": offset,
        "resultRecordCount": batch,
        "returnGeometry": "true",
        "outSR": "4326",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("features", [])


async def load_parcels_from_api(
    db: AsyncSession,
    total: int = 286000,
    batch_size: int = 1000,
    truncate: bool = False,
) -> int:
    from sqlalchemy import text

    if truncate:
        await db.execute(text("TRUNCATE parcels CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        features = await _arcgis_fetch(ARCGIS_PARCELS, offset, batch_size)
        if not features:
            break

        objects = []
        for feat in features:
            attrs = _normalize_cols(feat.get("attributes", {}))
            geo = feat.get("geometry") or {}
            lat = geo.get("y")
            lon = geo.get("x")
            objects.append(
                Parcel(
                    par_id=str(attrs.get("par_id", "")),
                    prop_addr=attrs.get("prop_addr"),
                    prop_city=attrs.get("prop_city"),
                    prop_zip=str(attrs.get("prop_zip", ""))[:10],
                    owner_name=attrs.get("owner_name"),
                    lu_code=attrs.get("lu_code"),
                    lu_desc=attrs.get("lu_desc"),
                    zoning=attrs.get("zoning"),
                    nbhd=attrs.get("nbhd"),
                    nbhd_desc=attrs.get("nbhd_desc"),
                    acres=_float(attrs.get("acres")),
                    land_appr=_float(attrs.get("land_appr")),
                    impr_appr=_float(attrs.get("impr_appr")),
                    totl_appr=_float(attrs.get("totl_appr")),
                    land_assd=_float(attrs.get("land_assd")),
                    impr_assd=_float(attrs.get("impr_assd")),
                    totl_assd=_float(attrs.get("totl_assd")),
                    sale_price=_float(attrs.get("sale_price")),
                    sale_date=attrs.get("sale_date"),
                    sale_inst=attrs.get("sale_inst"),
                    tax_dist=attrs.get("tax_dist"),
                    school_dist=attrs.get("school_dist"),
                    council_dist=attrs.get("council_dist"),
                    census_tract=attrs.get("census_tract"),
                    year_built=_int(attrs.get("year_built")),
                    bldg_sqft=_float(attrs.get("bldg_sqft")),
                    num_rooms=_int(attrs.get("num_rooms")),
                    num_beds=_int(attrs.get("num_beds")),
                    num_baths=_float(attrs.get("num_baths")),
                    stories=_float(attrs.get("stories")),
                    exterior=attrs.get("exterior"),
                    heat_type=attrs.get("heat_type"),
                    legal_desc=attrs.get("legal_desc"),
                    map_book=attrs.get("map_book"),
                    map_page=attrs.get("map_page"),
                    location=_point(lat, lon),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"Parcels loaded: {loaded}")

    return loaded


async def load_building_characteristics_from_api(
    db: AsyncSession,
    total: int = 300000,
    batch_size: int = 1000,
    truncate: bool = False,
) -> int:
    

    if truncate:
        await db.execute(text("TRUNCATE building_characteristics CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        features = await _arcgis_fetch(ARCGIS_BUILDING_CHARS, offset, batch_size)
        if not features:
            break

        objects = []
        for feat in features:
            attrs = _normalize_cols(feat.get("attributes", {}))
            objects.append(
                BuildingCharacteristic(
                    apn=attrs.get("apn"),
                    finished_area=_float(attrs.get("finished_area")),
                    year_built=_int(attrs.get("year_built")),
                    structure_type=attrs.get("structure_type"),
                    exterior=attrs.get("exterior"),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"Building chars loaded: {loaded}")

    return loaded


async def load_building_permits(db: AsyncSession, csv_path: str) -> int:

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            # "Permit_#" normalizes to "permit_"
            permit_num = row.get("permit_") or row.get("permit_number")
            lat = _float(row.get("latitude") or row.get("lat"))
            lon = _float(row.get("longitude") or row.get("lon"))
            objects.append(
                BuildingPermit(
                    permit_number=permit_num,
                    parcel=row.get("parcel"),
                    permit_type=row.get("permit_type"),
                    description=row.get("description"),
                    date_issued=row.get("date_issued"),
                    date_completed=row.get("date_completed"),
                    construction_cost=_float(row.get("construction_cost")),
                    contractor=row.get("contractor"),
                    location=_point(lat, lon),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_building_footprints(db: AsyncSession, csv_path: str) -> int:

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            objects.append(
                BuildingFootprint(
                    building_type=row.get("building_type"),
                    height=_float(row.get("height")),
                    bldg_id=row.get("bldg_id"),
                    roof_type=row.get("roof_type"),
                    shape_area=_float(row.get("shape_area")),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_cell_towers(db: AsyncSession, csv_path: str) -> int:

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            # Source CSV has "Lattitude" typo
            lat = _float(row.get("lattitude") or row.get("latitude"))
            lon = _float(row.get("longitude") or row.get("lon"))
            objects.append(
                CellTower(
                    company=row.get("company"),
                    fcc_site_id=row.get("fcc_site_id"),
                    height=_float(row.get("height")),
                    tower_type=row.get("tower_type"),
                    location=_point(lat, lon),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_flood_zones_csv(db: AsyncSession, csv_path: str) -> int:

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            sfha_raw = str(row.get("sfha_tf", "")).upper().strip()
            sfha = sfha_raw in ("T", "TRUE", "YES", "1")
            objects.append(
                FloodZone(
                    flood_zone=row.get("flood_zone") or row.get("fld_zone"),
                    sfha_tf=sfha,
                    zone_description=row.get("zone_description") or row.get("zonedesc"),
                    adopted_date=row.get("adopted_date"),
                    shape_area=_float(row.get("shape_area")),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_zoning_districts(db: AsyncSession, csv_path: str) -> int:

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            objects.append(
                ZoningDistrict(
                    zoning_code=row.get("zoning_code") or row.get("zoning"),
                    zoning_district=row.get("zoning_district"),
                    description=row.get("description"),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


def _float(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    try:
        return int(float(v)) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None
