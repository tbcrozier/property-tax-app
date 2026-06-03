from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ParcelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    par_id: str
    prop_addr: str | None = None
    prop_city: str | None = None
    prop_zip: str | None = None
    owner_name: str | None = None
    lu_code: str | None = None
    lu_desc: str | None = None
    zoning: str | None = None
    acres: float | None = None
    land_appr: float | None = None
    impr_appr: float | None = None
    totl_appr: float | None = None
    totl_assd: float | None = None
    sale_price: float | None = None
    sale_date: str | None = None
    year_built: int | None = None
    bldg_sqft: float | None = None


class AppealScore(BaseModel):
    par_id: str
    address: str | None = None
    lu_code: str | None = None
    prop_zip: str | None = None
    totl_appr: float | None = None
    value_per_acre: float | None = None
    zip_median_vpa: float | None = None
    lu_median_vpa: float | None = None
    z_score_zip: float | None = None
    pct_above_zip_median: float | None = None
    pct_above_lu_median: float | None = None
    assessment_to_sale_ratio: float | None = None
    assessed_above_sale: bool | None = None
    zoning_lu_mismatch: bool | None = None
    appeal_score: Annotated[float, Field(ge=0, le=100)] = 0.0
    recommendation: str | None = None


class CompProperty(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    par_id: str
    prop_addr: str | None = None
    acres: float | None = None
    totl_appr: float | None = None
    value_per_acre: float | None = None
    sale_price: float | None = None
    sale_date: str | None = None


class ParcelAnalysis(BaseModel):
    parcel: ParcelRead
    appeal: AppealScore
    comps: list[CompProperty]


class BuildingPermitData(BaseModel):
    count: int = 0
    total_cost: float = 0.0
    recent_permits: int = 0  # permits in last 5 years
    major_improvements: int = 0  # permits > $50k


class FloodZoneData(BaseModel):
    in_flood_zone: bool = False
    zone_type: str | None = None
    flood_risk: str = "Low"  # Low, Moderate, High
    potential_value_impact: float = 0.0  # percentage reduction


class CellTowerData(BaseModel):
    nearby_towers: int = 0
    closest_distance: float | None = None  # meters
    potential_value_impact: float = 0.0  # percentage reduction


class RailLineData(BaseModel):
    nearby_railroads: int = 0
    closest_distance: float | None = None  # meters
    freight_traffic: bool = False
    potential_value_impact: float = 0.0  # percentage reduction


class CorrectionalFacilityData(BaseModel):
    nearby_facilities: int = 0
    closest_distance: float | None = None  # meters
    facility_types: list[str] = []
    potential_value_impact: float = 0.0  # percentage reduction


class ZoningDistrictData(BaseModel):
    zoning_code: str | None = None
    zoning_description: str | None = None
    zoning_compliant: bool = True
    zoning_violations: list[str] = []


class BuildingFootprintData(BaseModel):
    actual_sqft: float | None = None
    assessed_sqft: float | None = None
    sqft_variance: float = 0.0  # actual - assessed
    variance_percentage: float = 0.0


class SchoolQualityData(BaseModel):
    nearby_schools: int = 0
    closest_school_distance: float | None = None
    average_school_rating: float | None = None  # 1-10 scale
    top_school_rating: float | None = None  # Best school within 2 miles
    school_quality_score: float = 0.0  # 0-100, higher = better schools
    potential_value_impact: float = 0.0  # Expected value increase from good schools


class CrimeData(BaseModel):
    crime_rate_per_1000: float = 0.0  # Crimes per 1000 residents in area
    violent_crime_rate: float = 0.0
    property_crime_rate: float = 0.0
    crime_trend: str = "stable"  # increasing, decreasing, stable
    safety_score: float = 0.0  # 0-100, higher = safer
    potential_value_impact: float = 0.0  # Expected value reduction from crime


class AssessmentError(BaseModel):
    error_type: str  # PERMIT_GAP, FLOOD_ZONE, CELL_TOWER, etc.
    severity: str  # LOW, MEDIUM, HIGH
    description: str
    potential_savings: float = 0.0
    confidence: float = 0.0  # 0-1


class ComprehensiveParcelAnalysis(BaseModel):
    parcel: ParcelRead
    appeal: AppealScore
    comps: list[CompProperty]
    building_permits: BuildingPermitData
    flood_zone: FloodZoneData
    cell_towers: CellTowerData
    railroads: RailLineData
    correctional_facilities: CorrectionalFacilityData
    zoning_district: ZoningDistrictData
    building_footprint: BuildingFootprintData
    school_quality: SchoolQualityData
    crime_data: CrimeData
    assessment_errors: list[AssessmentError]
    overall_risk_score: float = 0.0  # 0-100, higher = more likely over-assessed


class InsightHitList(BaseModel):
    total: int
    parcels: list[AppealScore]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    parcel_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    sql_used: str | None = None       # The SQL that was generated and executed
    result_count: int | None = None   # Number of rows returned by the query
    query_id: int | None = None       # QueryFeedback ID for submitting feedback


class AnalystRequest(BaseModel):
    question: str
    max_iterations: int = 8


class ReportRequest(BaseModel):
    question: str
    parcel_id: str | None = None
    max_iterations: int = 10


class ReportResponse(BaseModel):
    report_path: str
    summary: str
    sql_queries: list[str] = []
    parcels_analyzed: int = 0


class SaveExampleRequest(BaseModel):
    question: str
    sql: str
    insight: str
    tags: list[str] = []


class ParcelSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    par_id: str
    z_score_zip: float | None = None
    pct_above_zip_median: float | None = None
    pct_above_lu_median: float | None = None
    zip_peer_count: int | None = None
    assessment_to_sale_ratio: float | None = None
    assessed_above_sale: bool | None = None
    zoning_lu_mismatch: bool | None = None
    appeal_score: float | None = None
    recommendation: str | None = None


# ============ FEEDBACK & ANALYTICS SCHEMAS ============


class QueryFeedbackRequest(BaseModel):
    """Feedback submission on a chat response"""

    rating: Annotated[int, Field(ge=1, le=5)]  # 1-5 stars
    comments: str | None = None


class QueryFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_text: str
    response_text: str
    parcel_id: str | None
    rating: int
    auto_score: float | None = None
    auto_score_reason: str | None = None
    sql_used: str | None = None
    result_count: int | None = None
    comments: str | None
    latency_ms: float | None
    created_at: str


class QueryMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_pattern: str
    total_queries: int
    avg_rating: float
    avg_latency_ms: float
    low_rating_count: int
    high_rating_count: int
    last_updated: str


class KnowledgeGapReport(BaseModel):
    """Report of queries with poor performance"""

    query_pattern: str
    total_queries: int
    avg_rating: float
    low_rating_queries: list[QueryFeedbackRead]
    suggested_improvement: str
