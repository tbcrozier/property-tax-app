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
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

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
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class BuildingFootprint(Base):
    __tablename__ = "building_footprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_type: Mapped[str | None] = mapped_column(String)
    height: Mapped[float | None] = mapped_column(Float)
    bldg_id: Mapped[str | None] = mapped_column(String, index=True)
    roof_type: Mapped[str | None] = mapped_column(String)
    shape_area: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


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
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class CellTower(Base):
    __tablename__ = "cell_towers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[str | None] = mapped_column(String)
    fcc_site_id: Mapped[str | None] = mapped_column(String, index=True)
    height: Mapped[float | None] = mapped_column(Float)
    tower_type: Mapped[str | None] = mapped_column(String)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class FloodZone(Base):
    __tablename__ = "flood_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flood_zone: Mapped[str | None] = mapped_column(String(20))
    sfha_tf: Mapped[bool | None] = mapped_column(Boolean)
    zone_description: Mapped[str | None] = mapped_column(Text)
    adopted_date: Mapped[str | None] = mapped_column(String)
    shape_area: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class ZoningDistrict(Base):
    __tablename__ = "zoning_districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zoning_code: Mapped[str | None] = mapped_column(String(20), index=True)
    zoning_district: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class RailLine(Base):
    __tablename__ = "rail_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner: Mapped[str | None] = mapped_column(String)
    passenger_rail: Mapped[bool | None] = mapped_column(Boolean)
    tracks: Mapped[int | None] = mapped_column(Integer)
    miles: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=True)

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


class ParcelRailProximity(Base):
    __tablename__ = "parcel_rail_proximity"

    par_id: Mapped[str] = mapped_column(String, primary_key=True)
    nearest_rail_owner: Mapped[str | None] = mapped_column(String)
    passenger_rail: Mapped[bool | None] = mapped_column(Boolean)
    rail_tracks: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    within_100m: Mapped[bool | None] = mapped_column(Boolean)
    within_250m: Mapped[bool | None] = mapped_column(Boolean)
    within_500m: Mapped[bool | None] = mapped_column(Boolean)
    within_1000m: Mapped[bool | None] = mapped_column(Boolean)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ParcelFloodZone(Base):
    __tablename__ = "parcel_flood_zone"

    par_id: Mapped[str] = mapped_column(String, primary_key=True)
    flood_zone: Mapped[str | None] = mapped_column(String(20))
    sfha_tf: Mapped[bool | None] = mapped_column(Boolean)
    zone_description: Mapped[str | None] = mapped_column(Text)
    flood_risk_category: Mapped[str | None] = mapped_column(String(30))
    in_flood_zone: Mapped[bool | None] = mapped_column(Boolean)
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
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=True)

    __table_args__ = (
        # Use HNSW indexing for better performance on larger datasets
        # HNSW (Hierarchical Navigable Small World) provides faster approximate nearest neighbor search
        Index(
            "ix_documents_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Keep IVFFlat as fallback/alternative indexing strategy
        Index(
            "ix_documents_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class PublicSchool(Base):
    __tablename__ = "public_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ncessch: Mapped[str | None] = mapped_column(String(12), index=True)
    leaid: Mapped[str | None] = mapped_column(String(7))
    name: Mapped[str | None] = mapped_column(String(60))
    street: Mapped[str | None] = mapped_column(String(60))
    city: Mapped[str | None] = mapped_column(String(30))
    state: Mapped[str | None] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(5))
    cnty: Mapped[str | None] = mapped_column(String(5))
    nmcnty: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(2))
    school_year: Mapped[str | None] = mapped_column(String(9))
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_public_schools_location", "location", postgresql_using="gist"),
    )


class PostsecondarySchool(Base):
    __tablename__ = "postsecondary_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unitid: Mapped[str | None] = mapped_column(String(8), index=True)
    name: Mapped[str | None] = mapped_column(String(93))
    street: Mapped[str | None] = mapped_column(String(73))
    city: Mapped[str | None] = mapped_column(String(23))
    state: Mapped[str | None] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(10))
    cnty: Mapped[str | None] = mapped_column(String(5))
    nmcnty: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(2))
    school_year: Mapped[str | None] = mapped_column(String(9))
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_postsecondary_schools_location", "location", postgresql_using="gist"),
    )


class PrivateSchool(Base):
    __tablename__ = "private_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ppin: Mapped[str | None] = mapped_column(String(8), index=True)
    name: Mapped[str | None] = mapped_column(String(50))
    street: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(8))
    zip: Mapped[str | None] = mapped_column(String(8))
    cnty: Mapped[str | None] = mapped_column(String(5))
    nmcnty: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(2))
    school_year: Mapped[str | None] = mapped_column(String(10))
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_private_schools_location", "location", postgresql_using="gist"),
    )


class SchoolPovertyEstimate(Base):
    __tablename__ = "school_poverty_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ncessch: Mapped[str | None] = mapped_column(String(12), index=True)
    leaid: Mapped[str | None] = mapped_column(String(7))
    name: Mapped[str | None] = mapped_column(String(255))
    ipr_est: Mapped[int | None] = mapped_column(Integer)
    ipr_se: Mapped[int | None] = mapped_column(Integer)
    school_year: Mapped[str | None] = mapped_column(String(9))
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_school_poverty_location", "location", postgresql_using="gist"),
    )


class CorrectionalFacility(Base):
    __tablename__ = "correctional_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    permanent_identifier: Mapped[str | None] = mapped_column(String(40))
    name: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(75))
    city: Mapped[str | None] = mapped_column(String(40))
    state: Mapped[str | None] = mapped_column(String(2))
    zipcode: Mapped[str | None] = mapped_column(String(10))
    fcode: Mapped[int | None] = mapped_column(Integer)
    admin_type: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_correctional_facilities_location", "location", postgresql_using="gist"),
    )


class SchoolPerformance(Base):
    """School performance metrics for assessment analysis"""
    __tablename__ = "school_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ncessch: Mapped[str] = mapped_column(String(12), index=True)  # Links to PublicSchool.ncessch
    school_year: Mapped[str] = mapped_column(String(9), index=True)
    overall_rating: Mapped[str | None] = mapped_column(String(20))  # 1-5 stars or A-F grade
    achievement_score: Mapped[float | None] = mapped_column(Float)  # 0-100 scale
    growth_score: Mapped[float | None] = mapped_column(Float)  # Student growth metric
    graduation_rate: Mapped[float | None] = mapped_column(Float)  # Percentage
    college_readiness: Mapped[float | None] = mapped_column(Float)  # Percentage
    test_scores_math: Mapped[float | None] = mapped_column(Float)  # Average scale score
    test_scores_reading: Mapped[float | None] = mapped_column(Float)  # Average scale score
    student_teacher_ratio: Mapped[float | None] = mapped_column(Float)
    free_lunch_pct: Mapped[float | None] = mapped_column(Float)  # Percentage economically disadvantaged
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CrimeIncident(Base):
    """Crime incident data for safety analysis"""
    __tablename__ = "crime_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_number: Mapped[str | None] = mapped_column(String, index=True)
    incident_type: Mapped[str | None] = mapped_column(String(100))
    offense_description: Mapped[str | None] = mapped_column(Text)
    offense_group: Mapped[str | None] = mapped_column(String(50))  # Violent, Property, etc.
    rpa: Mapped[str | None] = mapped_column(String(10), index=True)  # Reporting Police Area
    zone: Mapped[str | None] = mapped_column(String(10))
    investigation_status: Mapped[str | None] = mapped_column(String(50))
    incident_occurred: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    incident_reported: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_crime_incidents_location", "location", postgresql_using="gist"),
    )


class PoliceReportingArea(Base):
    """Police reporting area boundaries"""
    __tablename__ = "police_reporting_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rpa: Mapped[str] = mapped_column(String(10), index=True, unique=True)
    precinct: Mapped[str | None] = mapped_column(String(50))
    sector: Mapped[str | None] = mapped_column(String(10))
    beat: Mapped[str | None] = mapped_column(String(10))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_police_reporting_areas_geom", "geom", postgresql_using="gist"),
    )


class QueryFeedback(Base):
    """Store user feedback on chat responses for continuous improvement"""

    __tablename__ = "query_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    parcel_id: Mapped[str | None] = mapped_column(String, index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1-5 stars, 0 = unrated
    auto_score: Mapped[float | None] = mapped_column(Float)  # computed automatically (1.0-5.0)
    auto_score_reason: Mapped[str | None] = mapped_column(Text)  # why it got that score
    sql_used: Mapped[str | None] = mapped_column(Text)  # SQL that was executed
    result_count: Mapped[int | None] = mapped_column(Integer)  # rows returned
    comments: Mapped[str | None] = mapped_column(Text)
    retrieved_docs: Mapped[str | None] = mapped_column(Text)  # JSON array of source docs
    latency_ms: Mapped[float | None] = mapped_column(Float)  # Response time in milliseconds
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_query_feedback_rating", "rating"),
        Index("ix_query_feedback_created_at", "created_at"),
    )


class SavedQuery(Base):
    """Library of successful question→SQL pairs for few-shot learning"""

    __tablename__ = "saved_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    result_preview: Mapped[str | None] = mapped_column(Text)  # JSON of first 3 rows
    result_count: Mapped[int | None] = mapped_column(Integer)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_saved_queries_rating", "avg_rating"),
    )


class QueryMetric(Base):
    """Aggregate metrics for query performance analysis"""

    __tablename__ = "query_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_pattern: Mapped[str] = mapped_column(String)  # e.g., "zoning compliance"
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    low_rating_count: Mapped[int] = mapped_column(Integer, default=0)  # count where rating < 3
    high_rating_count: Mapped[int] = mapped_column(Integer, default=0)  # count where rating >= 4
    most_common_docs: Mapped[str | None] = mapped_column(Text)  # JSON of top retrieved docs
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_query_metrics_pattern", "query_pattern"),
        Index("ix_query_metrics_avg_rating", "avg_rating"),
    )
