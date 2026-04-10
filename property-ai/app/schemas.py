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


class AnalystRequest(BaseModel):
    question: str
    max_iterations: int = 8


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
