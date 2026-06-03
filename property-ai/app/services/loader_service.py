import re
import httpx
import csv
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import (
    BuildingCharacteristic,
    BuildingFootprint,
    BuildingPermit,
    CellTower,
    CorrectionalFacility,
    FloodZone,
    Parcel,
    PostsecondarySchool,
    PrivateSchool,
    PublicSchool,
    PoliceReportingArea,
    SchoolPerformance,
    SchoolPovertyEstimate,
    CrimeIncident,
    RailLine,
    ZoningDistrict,
)

ARCGIS_PARCELS = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Parcels_view/FeatureServer/0/query"
)
ARCGIS_BUILDING_CHARS = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Parcels_with_Building_Characteristics_view/FeatureServer/0/query"
)
ARCGIS_PUBLIC_SCHOOLS = (
    "https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
    "Public_School_Locations_Current/FeatureServer/0/query"
)
ARCGIS_POSTSECONDARY_SCHOOLS = (
    "https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
    "Postsecondary_School_Locations_Current/FeatureServer/0/query"
)
ARCGIS_PRIVATE_SCHOOLS = (
    "https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
    "Private_School_Locations_Current/FeatureServer/0/query"
)
ARCGIS_SCHOOL_POVERTY = (
    "https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
    "School_Neighborhood_Poverty_Estimates_Current/FeatureServer/0/query"
)
USGS_CORRECTIONAL = (
    "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/19/query"
)
BTS_RAIL_LINES = (
    "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
    "NTAD_North_American_Rail_Network_Lines/FeatureServer/0/query"
)

# Davidson County FIPS — filters national datasets to local area only
DAVIDSON_CNTY_WHERE = "CNTY='47037'"
DAVIDSON_BBOX_WHERE = "LAT > 35.9 AND LAT < 36.5 AND LON > -87.1 AND LON < -86.5"

def _normalize_cols(row: dict) -> dict:
    return {
        re.sub(r"[^a-z0-9]", "_", k.lower().strip()).rstrip("_"): v
        for k, v in row.items()
    }


def _epoch_ms_to_date(val) -> str | None:
    if val is None:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return str(val)


def _point(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    return f"SRID=4326;POINT({lon} {lat})"


async def _arcgis_fetch(url: str, offset: int, batch: int, where: str = "1=1") -> list[dict]:
    params = {
        "where": where,
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
    if "error" in data:
        print(f"ArcGIS error from {url}: {data['error']}")
        return []
    return data.get("features", [])


async def load_parcels_from_api(
    db: AsyncSession,
    total: int = 286000,
    batch_size: int = 500,
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

        rows = []
        for feat in features:
            attrs = _normalize_cols(feat.get("attributes", {}))
            par_id = str(attrs.get("stanpar") or attrs.get("parid") or "").strip()
            if not par_id:
                continue
            loc = _point(_float(attrs.get("lat")), _float(attrs.get("lon")))
            rows.append({
                "par_id": par_id,
                "prop_addr": attrs.get("propaddr"),
                "prop_city": attrs.get("propcity"),
                "prop_zip": str(attrs.get("propzip") or "")[:10],
                "owner_name": attrs.get("owner"),
                "lu_code": (str(attrs.get("lucode") or "")[:20] or None),
                "lu_desc": attrs.get("ludesc"),
                "zoning": (str(attrs.get("zoning") or "")[:20] or None),
                "nbhd": (str(attrs.get("tract") or "")[:20] or None),
                "nbhd_desc": None,
                "acres": _float(attrs.get("acres")),
                "land_appr": _float(attrs.get("landappr")),
                "impr_appr": _float(attrs.get("imprappr")),
                "totl_appr": _float(attrs.get("totlappr")),
                "land_assd": None,
                "impr_assd": None,
                "totl_assd": None,
                "sale_price": _float(attrs.get("saleprice")),
                "sale_date": _epoch_ms_to_date(attrs.get("propdate") or attrs.get("owndate")),
                "sale_inst": attrs.get("owninstr"),
                "tax_dist": (str(attrs.get("taxdist") or "")[:20] or None),
                "school_dist": None,
                "council_dist": (str(attrs.get("council") or "")[:20] or None),
                "census_tract": (str(attrs.get("tract") or "")[:20] or None),
                "year_built": None,
                "bldg_sqft": None,
                "num_rooms": None,
                "num_beds": None,
                "num_baths": None,
                "stories": None,
                "exterior": None,
                "heat_type": None,
                "legal_desc": attrs.get("legaldesc"),
                "map_book": None,
                "map_page": None,
                "location": loc,
            })

        if rows:
            stmt = pg_insert(Parcel.__table__).values(rows).on_conflict_do_nothing(index_elements=["par_id"])
            await db.execute(stmt)
            await db.commit()
            loaded += len(rows)
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

        rows = []
        for feat in features:
            attrs = _normalize_cols(feat.get("attributes", {}))
            rows.append({
                "apn": attrs.get("apn"),
                "finished_area": _float(attrs.get("finishedarea")),
                "year_built": _int(attrs.get("yearbuilt")),
                "structure_type": attrs.get("structuretype"),
                "exterior": attrs.get("exterior"),
            })

        if rows:
            await db.execute(text("INSERT INTO building_characteristics (apn, finished_area, year_built, structure_type, exterior) VALUES (:apn, :finished_area, :year_built, :structure_type, :exterior)"), rows)
            await db.commit()
            loaded += len(rows)
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


FEMA_NFHL_FLOOD_ZONES = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
)


def _fema_fetch_batch(offset: int, batch_size: int) -> list:
    """Synchronous FEMA fetch — run via asyncio.to_thread to avoid blocking the event loop."""
    import ssl
    import requests as _requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib3.util.ssl_ import create_urllib3_context
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Python 3.12 raises UNEXPECTED_EOF_WHILE_READING for TLS 1.3 on some gov servers.
    # Force TLS 1.2 and use OP_LEGACY_SERVER_CONNECT to work around this.
    ssl_ctx = create_urllib3_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    ssl_ctx.maximum_version = ssl.TLSVersion.TLSv1_2

    class LegacyTLSAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["ssl_context"] = ssl_ctx
            super().init_poolmanager(*args, **kwargs)

    session = _requests.Session()
    retry = Retry(total=3, backoff_factor=3, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", LegacyTLSAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PropertyTaxAnalysis/1.0",
        "Accept": "application/json",
    })

    params = {
        "where": "DFIRM_ID LIKE '47037%'",
        "outFields": "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF,STUDY_TYP,Shape__Area",
        "f": "geojson",
        "resultRecordCount": batch_size,
        "resultOffset": offset,
        "returnGeometry": "true",
        "outSR": "4326",
    }
    resp = session.get(FEMA_NFHL_FLOOD_ZONES, params=params, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"FEMA API error: {data['error']}")
    return data.get("features", [])


async def load_flood_zones_from_api(
    db: AsyncSession,
    batch_size: int = 250,
    truncate: bool = False,
) -> int:
    """Load FEMA NFHL flood zone polygons for Davidson County (DFIRM_ID LIKE '47037%')."""
    import asyncio as _asyncio
    import json as _json

    if truncate:
        await db.execute(text("TRUNCATE flood_zones CASCADE"))
        await db.commit()

    loaded = 0
    offset = 0

    while True:
        features = await _asyncio.to_thread(_fema_fetch_batch, offset, batch_size)
        if not features:
            break

        for feat in features:
            props = _normalize_cols(feat.get("properties", {}))
            geom_json = feat.get("geometry")

            sfha_raw = str(props.get("sfha_tf") or "").upper().strip()
            sfha = sfha_raw == "T"
            zone_desc = props.get("zone_subty") or props.get("study_typ")
            shape_area = _float(props.get("shape__area"))

            if geom_json:
                geom_json_str = _json.dumps(geom_json)
                await db.execute(
                    text(
                        "INSERT INTO flood_zones (flood_zone, sfha_tf, zone_description, adopted_date, shape_area, geom) "
                        "VALUES (:flood_zone, :sfha_tf, :zone_description, :adopted_date, :shape_area, "
                        "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)))"
                    ),
                    {
                        "flood_zone": (str(props.get("fld_zone") or "")[:20] or None),
                        "sfha_tf": sfha,
                        "zone_description": zone_desc,
                        "adopted_date": None,
                        "shape_area": shape_area,
                        "geom_json": geom_json_str,
                    },
                )
            else:
                await db.execute(
                    text(
                        "INSERT INTO flood_zones (flood_zone, sfha_tf, zone_description, adopted_date, shape_area) "
                        "VALUES (:flood_zone, :sfha_tf, :zone_description, :adopted_date, :shape_area)"
                    ),
                    {
                        "flood_zone": (str(props.get("fld_zone") or "")[:20] or None),
                        "sfha_tf": sfha,
                        "zone_description": zone_desc,
                        "adopted_date": None,
                        "shape_area": shape_area,
                    },
                )

        await db.commit()
        loaded += len(features)
        print(f"  flood zones loaded so far: {loaded}")

        if len(features) < batch_size:
            break
        offset += batch_size

    return loaded


async def load_flood_zones_from_json(db: AsyncSession, json_path: str, truncate: bool = False) -> int:
    """Load flood zones from the newline-delimited JSON produced by floodzone/load_floodzone.py."""
    import json as _json

    if truncate:
        await db.execute(text("TRUNCATE flood_zones CASCADE"))
        await db.commit()

    loaded = 0
    with open(json_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = _json.loads(line)
            geom_str = rec.get("geom")
            sfha = rec.get("sfha_tf") or False
            flood_zone = (str(rec.get("flood_zone") or "")[:20] or None)
            zone_desc = rec.get("zone_description")
            shape_area = _float(rec.get("shape_area") or rec.get("shape__area"))

            if geom_str:
                # geom is already a JSON string from the reference script
                geom_json = geom_str if isinstance(geom_str, str) else _json.dumps(geom_str)
                await db.execute(
                    text(
                        "INSERT INTO flood_zones (flood_zone, sfha_tf, zone_description, adopted_date, shape_area, geom) "
                        "VALUES (:flood_zone, :sfha_tf, :zone_description, :adopted_date, :shape_area, "
                        "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)))"
                    ),
                    {
                        "flood_zone": flood_zone,
                        "sfha_tf": sfha,
                        "zone_description": zone_desc,
                        "adopted_date": None,
                        "shape_area": shape_area,
                        "geom_json": geom_json,
                    },
                )
            else:
                await db.execute(
                    text(
                        "INSERT INTO flood_zones (flood_zone, sfha_tf, zone_description, adopted_date, shape_area) "
                        "VALUES (:flood_zone, :sfha_tf, :zone_description, :adopted_date, :shape_area)"
                    ),
                    {
                        "flood_zone": flood_zone,
                        "sfha_tf": sfha,
                        "zone_description": zone_desc,
                        "adopted_date": None,
                        "shape_area": shape_area,
                    },
                )
            loaded += 1
            if loaded % 500 == 0:
                await db.commit()
                print(f"  flood zones loaded so far: {loaded}")

    await db.commit()
    return loaded


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


async def load_public_schools(
    db: AsyncSession,
    total: int = 5000,
    batch_size: int = 2000,
    truncate: bool = False,
) -> int:
    if truncate:
        await db.execute(text("TRUNCATE public_schools CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        params = {
            "where": DAVIDSON_CNTY_WHERE,
            "outFields": "NCESSCH,LEAID,NAME,STREET,CITY,STATE,ZIP,CNTY,NMCNTY,LOCALE,LAT,LON,SCHOOLYEAR",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "returnGeometry": "false",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(ARCGIS_PUBLIC_SCHOOLS, params=params)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            print(f"ArcGIS error (public schools): {data['error']}")
            break
        features = data.get("features", [])
        if not features:
            break

        objects = []
        for feat in features:
            a = _normalize_cols(feat.get("attributes", {}))
            objects.append(
                PublicSchool(
                    ncessch=a.get("ncessch"),
                    leaid=a.get("leaid"),
                    name=a.get("name"),
                    street=a.get("street"),
                    city=a.get("city"),
                    state=a.get("state"),
                    zip=a.get("zip"),
                    cnty=a.get("cnty"),
                    nmcnty=a.get("nmcnty"),
                    locale=a.get("locale"),
                    school_year=a.get("schoolyear"),
                    location=_point(_float(a.get("lat")), _float(a.get("lon"))),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"Public schools loaded: {loaded}")

    return loaded


async def load_postsecondary_schools(
    db: AsyncSession,
    total: int = 5000,
    batch_size: int = 2000,
    truncate: bool = False,
) -> int:
    if truncate:
        await db.execute(text("TRUNCATE postsecondary_schools CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        params = {
            "where": DAVIDSON_CNTY_WHERE,
            "outFields": "UNITID,NAME,STREET,CITY,STATE,ZIP,CNTY,NMCNTY,LOCALE,LAT,LON,SCHOOLYEAR",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "returnGeometry": "false",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(ARCGIS_POSTSECONDARY_SCHOOLS, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        objects = []
        for feat in features:
            a = _normalize_cols(feat.get("attributes", {}))
            objects.append(
                PostsecondarySchool(
                    unitid=a.get("unitid"),
                    name=a.get("name"),
                    street=a.get("street"),
                    city=a.get("city"),
                    state=a.get("state"),
                    zip=a.get("zip"),
                    cnty=a.get("cnty"),
                    nmcnty=a.get("nmcnty"),
                    locale=a.get("locale"),
                    school_year=a.get("schoolyear"),
                    location=_point(_float(a.get("lat")), _float(a.get("lon"))),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"Postsecondary schools loaded: {loaded}")

    return loaded


async def load_private_schools(
    db: AsyncSession,
    total: int = 5000,
    batch_size: int = 2000,
    truncate: bool = False,
) -> int:
    if truncate:
        await db.execute(text("TRUNCATE private_schools CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        params = {
            "where": "CNTY='037' AND STATE='TN'",
            "outFields": "PPIN,NAME,STREET,CITY,STATE,ZIP,CNTY,NMCNTY,LOCALE,LAT,LON,SCHOOLYEAR",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "returnGeometry": "false",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(ARCGIS_PRIVATE_SCHOOLS, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        objects = []
        for feat in features:
            a = _normalize_cols(feat.get("attributes", {}))
            objects.append(
                PrivateSchool(
                    ppin=a.get("ppin"),
                    name=a.get("name"),
                    street=a.get("street"),
                    city=a.get("city"),
                    state=a.get("state"),
                    zip=a.get("zip"),
                    cnty=a.get("cnty"),
                    nmcnty=a.get("nmcnty"),
                    locale=a.get("locale"),
                    school_year=a.get("schoolyear"),
                    location=_point(_float(a.get("lat")), _float(a.get("lon"))),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"Private schools loaded: {loaded}")

    return loaded


async def load_school_poverty_estimates(
    db: AsyncSession,
    total: int = 5000,
    batch_size: int = 2000,
    truncate: bool = False,
) -> int:
    if truncate:
        await db.execute(text("TRUNCATE school_poverty_estimates CASCADE"))
        await db.commit()

    loaded = 0
    for offset in range(0, total, batch_size):
        params = {
            # poverty layer has no CNTY field — filter by Davidson County bbox
            "where": DAVIDSON_BBOX_WHERE,
            "outFields": "NCESSCH,LEAID,Name,IPR_EST,IPR_SE,LAT,LON,SCHOOLYEAR",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "returnGeometry": "false",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(ARCGIS_SCHOOL_POVERTY, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        objects = []
        for feat in features:
            a = _normalize_cols(feat.get("attributes", {}))
            objects.append(
                SchoolPovertyEstimate(
                    ncessch=a.get("ncessch"),
                    leaid=a.get("leaid"),
                    name=a.get("name"),
                    ipr_est=_int(a.get("ipr_est")),
                    ipr_se=_int(a.get("ipr_se")),
                    school_year=a.get("schoolyear"),
                    location=_point(_float(a.get("lat")), _float(a.get("lon"))),
                )
            )

        db.add_all(objects)
        await db.commit()
        loaded += len(objects)
        print(f"School poverty estimates loaded: {loaded}")

    return loaded


async def load_school_performance_csv(db: AsyncSession, csv_path: str) -> int:
    """Load school performance metrics from a CSV file."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            objects.append(
                SchoolPerformance(
                    ncessch=row.get("ncessch"),
                    school_year=row.get("school_year") or row.get("schoolyear"),
                    overall_rating=row.get("overall_rating") or row.get("rating"),
                    achievement_score=_float(row.get("achievement_score") or row.get("achievement")),
                    growth_score=_float(row.get("growth_score") or row.get("growth")),
                    graduation_rate=_float(row.get("graduation_rate") or row.get("grad_rate") or row.get("graduationrate")),
                    college_readiness=_float(row.get("college_readiness") or row.get("college_ready")),
                    test_scores_math=_float(row.get("test_scores_math") or row.get("math_score") or row.get("math")),
                    test_scores_reading=_float(row.get("test_scores_reading") or row.get("reading_score") or row.get("reading")),
                    student_teacher_ratio=_float(row.get("student_teacher_ratio") or row.get("student_teacher")),
                    free_lunch_pct=_float(row.get("free_lunch_pct") or row.get("free_lunch") or row.get("free_lunch_percent")),
                    created_at=_parse_datetime(row.get("created_at") or row.get("created") or row.get("date")),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_crime_incidents_csv(db: AsyncSession, csv_path: str) -> int:
    """Load crime incident records from a CSV file."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            lat = _float(row.get("latitude") or row.get("lat"))
            lon = _float(row.get("longitude") or row.get("lon"))
            objects.append(
                CrimeIncident(
                    incident_number=row.get("incident_number") or row.get("incident") or row.get("incident_num"),
                    incident_type=row.get("incident_type") or row.get("type"),
                    offense_description=row.get("offense_description") or row.get("description"),
                    offense_group=row.get("offense_group") or row.get("group") or row.get("offense_grouping"),
                    rpa=row.get("rpa") or row.get("reporting_police_area") or row.get("police_reporting_area"),
                    zone=row.get("zone") or row.get("district"),
                    investigation_status=row.get("investigation_status") or row.get("status"),
                    incident_occurred=_parse_datetime(row.get("incident_occurred") or row.get("date_occurred") or row.get("occurred_at")),
                    incident_reported=_parse_datetime(row.get("incident_reported") or row.get("date_reported") or row.get("reported_at")),
                    location=_point(lat, lon),
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_police_reporting_areas(db: AsyncSession, csv_path: str) -> int:
    """Load police reporting area boundaries from a CSV with WKT geometry."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        objects = []
        for raw in reader:
            row = _normalize_cols(raw)
            geom = row.get("geom") or row.get("wkt") or row.get("geometry")
            if not geom:
                continue
            if not geom.upper().startswith("SRID="):
                geom = f"SRID=4326;{geom}"

            objects.append(
                PoliceReportingArea(
                    rpa=row.get("rpa") or row.get("reporting_police_area") or row.get("police_reporting_area"),
                    precinct=row.get("precinct"),
                    sector=row.get("sector"),
                    beat=row.get("beat"),
                    geom=geom,
                )
            )

    db.add_all(objects)
    await db.commit()
    return len(objects)


async def load_correctional_facilities(
    db: AsyncSession,
    batch_size: int = 2000,
    truncate: bool = False,
) -> int:
    if truncate:
        await db.execute(text("TRUNCATE correctional_facilities CASCADE"))
        await db.commit()

    params = {
        "where": "STATE='TN'",
        "geometry": "-87.1,35.9,-86.5,36.5",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PERMANENT_IDENTIFIER,NAME,ADDRESS,CITY,STATE,ZIPCODE,FCODE,ADMINTYPE",
        "f": "json",
        "resultRecordCount": batch_size,
        "returnGeometry": "true",
        "outSR": "4326",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(USGS_CORRECTIONAL, params=params)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return 0

    objects = []
    for feat in features:
        a = _normalize_cols(feat.get("attributes", {}))
        geo = feat.get("geometry") or {}
        lat = geo.get("y")
        lon = geo.get("x")
        objects.append(
            CorrectionalFacility(
                permanent_identifier=a.get("permanent_identifier"),
                name=a.get("name"),
                address=a.get("address"),
                city=a.get("city"),
                state=a.get("state"),
                zipcode=a.get("zipcode"),
                fcode=_int(a.get("fcode")),
                admin_type=_int(a.get("admintype")),
                location=_point(lat, lon),
            )
        )

    db.add_all(objects)
    await db.commit()
    print(f"Correctional facilities loaded: {len(objects)}")
    return len(objects)


async def load_rail_lines_from_api(
    db: AsyncSession,
    batch_size: int = 1000,
    truncate: bool = False,
) -> int:
    """Load NARN rail lines for Davidson County from BTS NTAD ArcGIS API."""
    import json as _json

    if truncate:
        await db.execute(text("TRUNCATE rail_lines CASCADE"))
        await db.commit()

    loaded = 0
    offset = 0

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            params = {
                "where": "STCNTYFIPS = '47037'",
                "outFields": "OBJECTID,RROWNER1,PASSNGR,TRACKS,MILES",
                "f": "geojson",
                "resultRecordCount": batch_size,
                "resultOffset": offset,
                "returnGeometry": "true",
                "outSR": "4326",
            }
            resp = await client.get(BTS_RAIL_LINES, params=params)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                raise RuntimeError(f"BTS API error: {data['error']}")

            features = data.get("features", [])
            if not features:
                break

            objects = []
            for feat in features:
                props = _normalize_cols(feat.get("properties", {}))
                geom_json = feat.get("geometry")

                passenger = str(props.get("passngr") or "").upper() in ("Y", "YES", "1", "TRUE")
                tracks = None
                try:
                    tracks = int(props.get("tracks")) if props.get("tracks") is not None else None
                except (TypeError, ValueError):
                    pass

                geom_wkt = None
                if geom_json:
                    geom_str = _json.dumps(geom_json)
                    # Rail lines are LineStrings — wrap in ST_Multi for MULTILINESTRING column
                    await db.execute(
                        text(
                            "INSERT INTO rail_lines (owner, passenger_rail, tracks, miles, geom) "
                            "VALUES (:owner, :passenger_rail, :tracks, :miles, "
                            "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)))"
                        ),
                        {
                            "owner": props.get("rrowner1"),
                            "passenger_rail": passenger,
                            "tracks": tracks,
                            "miles": _float(props.get("miles")),
                            "geom_json": geom_str,
                        },
                    )
                    loaded += 1

            await db.commit()
            print(f"  rail lines loaded so far: {loaded}")

            if len(features) < batch_size:
                break
            offset += batch_size

    return loaded


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


def _parse_datetime(v: Any) -> datetime | None:
    if not v or v in ("", "null"):
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
