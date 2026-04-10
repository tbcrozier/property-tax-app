from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Parcel(Base):
    __tablename__ = "parcels"

    par_id: Mapped[str] = mapped_column(String, primary_key=True)
    prop_addr: Mapped[str | None] = mapped_column(String)
    prop_city: Mapped[str | None] = mapped_column(String)
    prop_zip: Mapped[str | None] = mapped_column(String(10))
    owner_name: Mapped[str | None] = mapped_column(String)
    lu_code: Mapped[str | None] = mapped_column(String(20))
    lu_desc: Mapped[str | None] = mapped_column(String)
    zoning: Mapped[str | None] = mapped_column(String(20))
    nbhd: Mapped[str | None] = mapped_column(String(20))
    nbhd_desc: Mapped[str | None] = mapped_column(String)
    acres: Mapped[float | None] = mapped_column(Float)
    land_appr: Mapped[float | None] = mapped_column(Float)
    impr_appr: Mapped[float | None] = mapped_column(Float)
    totl_appr: Mapped[float | None] = mapped_column(Float)
    land_assd: Mapped[float | None] = mapped_column(Float)
    impr_assd: Mapped[float | None] = mapped_column(Float)
    totl_assd: Mapped[float | None] = mapped_column(Float)
    sale_price: Mapped[float | None] = mapped_column(Float)
    sale_date: Mapped[str | None] = mapped_column(String)
    sale_inst: Mapped[str | None] = mapped_column(String)
    tax_dist: Mapped[str | None] = mapped_column(String(20))
    school_dist: Mapped[str | None] = mapped_column(String(20))
    council_dist: Mapped[str | None] = mapped_column(String(20))
    census_tract: Mapped[str | None] = mapped_column(String(20))
    year_built: Mapped[int | None] = mapped_column(Integer)
    bldg_sqft: Mapped[float | None] = mapped_column(Float)
    num_rooms: Mapped[int | None] = mapped_column(Integer)
    num_beds: Mapped[int | None] = mapped_column(Integer)
    num_baths: Mapped[float | None] = mapped_column(Float)
    stories: Mapped[float | None] = mapped_column(Float)
    exterior: Mapped[str | None] = mapped_column(String)
    heat_type: Mapped[str | None] = mapped_column(String)
    legal_desc: Mapped[str | None] = mapped_column(String)
    map_book: Mapped[str | None] = mapped_column(String(20))
    map_page: Mapped[str | None] = mapped_column(String(20))
    location: Any = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_parcels_lu_zip", "lu_code", "prop_zip"),
        Index("ix_parcels_location", "location", postgresql_using="gist"),
    )


class BuildingCharacteristic(Base):
    __tablename__ = "building_characteristics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apn: Mapped[str | None] = mapped_column(String, index=True)
    finished_area: Mapped[float | None] = mapped_column(Float)
    year_built: Mapped[int | None] = mapped_column(Integer)
    structure_type: Mapped[str | None] = mapped_column(String)
    exterior: Mapped[str | None] = mapped_column(String)
    geom: Any = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class BuildingFootprint(Base):
    __tablename__ = "building_footprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_type: Mapped[str | None] = mapped_column(String)
    height: Mapped[float | None] = mapped_column(Float)
    bldg_id: Mapped[str | None] = mapped_column(String, index=True)
    roof_type: Mapped[str | None] = mapped_column(String)
    shape_area: Mapped[float | None] = mapped_column(Float)
    geom: Any = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class BuildingPermit(Base):
    __tablename__ = "building_permits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    permit_number: Mapped[str | None] = mapped_column(String, index=True)
    parcel: Mapped[str | None] = mapped_column(String, index=True)
    permit_type: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    date_issued: Mapped[str | None] = mapped_column(String)
    date_completed: Mapped[str | None] = mapped_column(String)
    construction_cost: Mapped[float | None] = mapped_column(Float)
    contractor: Mapped[str | None] = mapped_column(String)
    location: Any = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class CellTower(Base):
    __tablename__ = "cell_towers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[str | None] = mapped_column(String)
    fcc_site_id: Mapped[str | None] = mapped_column(String, index=True)
    height: Mapped[float | None] = mapped_column(Float)
    tower_type: Mapped[str | None] = mapped_column(String)
    location: Any = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class FloodZone(Base):
    __tablename__ = "flood_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flood_zone: Mapped[str | None] = mapped_column(String(20))
    sfha_tf: Mapped[bool | None] = mapped_column(Boolean)
    zone_description: Mapped[str | None] = mapped_column(Text)
    adopted_date: Mapped[str | None] = mapped_column(String)
    shape_area: Mapped[float | None] = mapped_column(Float)
    geom: Any = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class ZoningDistrict(Base):
    __tablename__ = "zoning_districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zoning_code: Mapped[str | None] = mapped_column(String(20), index=True)
    zoning_district: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    geom: Any = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class RailLine(Base):
    __tablename__ = "rail_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner: Mapped[str | None] = mapped_column(String)
    passenger_rail: Mapped[bool | None] = mapped_column(Boolean)
    tracks: Mapped[int | None] = mapped_column(Integer)
    miles: Mapped[float | None] = mapped_column(Float)
    geom: Any = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_rail_lines_geom", "geom", postgresql_using="gist"),
    )


class ParcelSignal(Base):
    __tablename__ = "parcel_signals"

    par_id: Mapped[str] = mapped_column(String, primary_key=True)
    z_score_zip: Mapped[float | None] = mapped_column(Float)
    pct_above_zip_median: Mapped[float | None] = mapped_column(Float)
    pct_above_lu_median: Mapped[float | None] = mapped_column(Float)
    zip_peer_count: Mapped[int | None] = mapped_column(Integer)
    assessment_to_sale_ratio: Mapped[float | None] = mapped_column(Float)
    assessed_above_sale: Mapped[bool | None] = mapped_column(Boolean)
    zoning_lu_mismatch: Mapped[bool | None] = mapped_column(Boolean)
    appeal_score: Mapped[float | None] = mapped_column(Float, index=True)
    recommendation: Mapped[str | None] = mapped_column(String(30), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Any = mapped_column(Vector(768), nullable=True)

    __table_args__ = (
        Index(
            "ix_documents_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
