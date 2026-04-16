#!/usr/bin/env python3
"""
Property Tax Assessment Comparison Analysis Tool.

Finds comparable properties based on defined criteria and generates
a detailed comparison report with appeal recommendations.

Usage:
    python compare_property.py --address "1045 LYNNWOOD BLVD"
    python compare_property.py --parid "237054.0"
    python compare_property.py --address "1045 LYNNWOOD BLVD" --format json --output report.json
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.cloud import bigquery

# Configuration defaults
DEFAULT_YEAR_RANGE = 10
DEFAULT_SQFT_RANGE_PCT = 25
DEFAULT_MIN_COMPARABLES = 5
DEFAULT_MAX_COMPARABLES = 20
DEFAULT_SALE_DAYS = 730  # 2 years
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"


@dataclass
class SubjectProperty:
    """The property being analyzed."""
    parid: str
    stanpar: str
    address: str
    zip_code: str
    land_use: str
    total_appraisal: float
    land_appraisal: float
    improvement_appraisal: float
    acres: float
    latitude: Optional[float]
    longitude: Optional[float]
    year_built: Optional[int]
    finished_area: Optional[float]
    structure_type: Optional[str]
    exterior: Optional[str]
    sale_price: Optional[float]
    sale_date: Optional[str]

    @property
    def price_per_sqft(self) -> Optional[float]:
        if self.finished_area and self.finished_area > 0:
            return self.total_appraisal / self.finished_area
        return None

    @property
    def price_per_acre(self) -> Optional[float]:
        if self.acres and self.acres > 0:
            return self.total_appraisal / self.acres
        return None

    @property
    def assessment_to_sale_ratio(self) -> Optional[float]:
        """Ratio of assessment to sale price. >1.0 means over-assessed."""
        if self.sale_price and self.sale_price >= 10000:  # Filter nominal transfers
            return self.total_appraisal / self.sale_price
        return None


@dataclass
class ComparableProperty:
    """A comparable property with similarity metrics."""
    parid: str
    address: str
    zip_code: str
    total_appraisal: float
    acres: float
    year_built: Optional[int]
    finished_area: Optional[float]
    structure_type: Optional[str]
    exterior: Optional[str]
    price_per_sqft: Optional[float]
    similarity_score: float
    year_diff: Optional[int]
    sqft_diff_pct: Optional[float]
    distance_meters: Optional[float]
    sale_price: Optional[float]
    sale_date: Optional[str]
    assessment_to_sale_ratio: Optional[float]


@dataclass
class ComparisonCriteria:
    """The criteria used to find comparables."""
    zip_code: str
    land_use: str
    year_built_min: Optional[int]
    year_built_max: Optional[int]
    sqft_min: Optional[float]
    sqft_max: Optional[float]
    year_range: int
    sqft_range_pct: int


@dataclass
class ComparisonStatistics:
    """Statistical summary of comparable properties."""
    count: int
    mean_price_per_sqft: Optional[float]
    median_price_per_sqft: Optional[float]
    stddev_price_per_sqft: Optional[float]
    min_price_per_sqft: Optional[float]
    max_price_per_sqft: Optional[float]
    mean_total_appraisal: float
    median_total_appraisal: float
    subject_percentile: Optional[float]
    subject_z_score: Optional[float]
    comps_with_building_data: int
    comps_without_building_data: int


@dataclass
class SaleStatistics:
    """Statistical summary of comparable sales (market value approach)."""
    count: int
    mean_sale_price_per_sqft: Optional[float]
    median_sale_price_per_sqft: Optional[float]
    min_sale_price_per_sqft: Optional[float]
    max_sale_price_per_sqft: Optional[float]
    stddev_sale_price_per_sqft: Optional[float]
    mean_sale_price: float
    median_sale_price: float
    avg_assessment_to_sale_ratio: Optional[float]
    subject_vs_median_sale_pct: Optional[float]  # How much subject is over/under median sale $/sqft
    subject_market_percentile: Optional[float]  # % of sales with LOWER $/sqft than subject's assessment
    subject_market_z_score: Optional[float]  # Std devs above/below mean sale $/sqft


@dataclass
class AppealRecommendation:
    """Appeal recommendation based on analysis."""
    recommendation: str
    appeal_strength_score: float
    estimated_annual_savings: float
    key_findings: List[str]


@dataclass
class EnvironmentalFactors:
    """Environmental risk factors for a property."""
    flood_zone: Optional[str]
    flood_zone_subtype: Optional[str]
    flood_risk_level: str  # HIGH_RISK, MODERATE_RISK, MINIMAL_RISK, NOT_IN_FLOOD_ZONE, UNKNOWN
    is_special_flood_hazard_area: bool
    rail_distance_feet: Optional[float]
    rail_proximity_flag: str  # WITHIN_100M, WITHIN_250M, WITHIN_500M, WITHIN_1000M, BEYOND_1000M, UNKNOWN
    nearest_rail_owner: Optional[str]


@dataclass
class BuildingPermit:
    """A building permit record."""
    address: str
    permit_type: str
    purpose: str
    construction_cost: Optional[float]
    date_issued: Optional[str]


@dataclass
class PermitHistory:
    """Building permit history for a property."""
    permits: List[BuildingPermit]
    total_permits: int
    total_construction_cost: float
    has_major_renovation: bool  # Any permit > $50k


@dataclass
class ComparisonResult:
    """Complete result of a property comparison analysis."""
    subject: SubjectProperty
    criteria: ComparisonCriteria
    comparables: List[ComparableProperty]  # Assessment-based comps
    statistics: ComparisonStatistics  # Assessment statistics
    comparable_sales: List[ComparableProperty]  # Sales-based comps (COMPER style)
    sale_statistics: Optional[SaleStatistics]  # Sale price statistics
    environmental: Optional[EnvironmentalFactors]
    permit_history: Optional[PermitHistory]
    recommendation: AppealRecommendation
    warnings: List[str]
    generated_at: str


def lookup_property_by_address(client: bigquery.Client, address: str,
                                project: str, dataset: str) -> List[Dict]:
    """Look up properties matching an address pattern."""
    query = f"""
    SELECT
        p.ParID,
        p.STANPAR,
        p.PropAddr,
        p.PropZip,
        p.LUDesc,
        p.TotlAppr,
        p.LandAppr,
        p.ImprAppr,
        p.Acres,
        p.Lat,
        p.Lon,
        p.SalePrice,
        FORMAT_DATE('%Y-%m-%d', p.OwnDate) as SaleDate,
        b.year_built,
        b.finished_area,
        b.structure_type,
        b.exterior
    FROM `{project}.{dataset}.davidson_parcels` p
    LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b
        ON p.STANPAR = b.apn
    WHERE UPPER(p.PropAddr) LIKE UPPER(@address_pattern)
    LIMIT 10
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("address_pattern", "STRING", f"%{address}%")
        ]
    )

    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]


def lookup_property_by_parid(client: bigquery.Client, parid: str,
                              project: str, dataset: str) -> List[Dict]:
    """Look up a property by ParID."""
    query = f"""
    SELECT
        p.ParID,
        p.STANPAR,
        p.PropAddr,
        p.PropZip,
        p.LUDesc,
        p.TotlAppr,
        p.LandAppr,
        p.ImprAppr,
        p.Acres,
        p.Lat,
        p.Lon,
        p.SalePrice,
        FORMAT_DATE('%Y-%m-%d', p.OwnDate) as SaleDate,
        b.year_built,
        b.finished_area,
        b.structure_type,
        b.exterior
    FROM `{project}.{dataset}.davidson_parcels` p
    LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b
        ON p.STANPAR = b.apn
    WHERE p.ParID = @parid
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("parid", "STRING", parid)
        ]
    )

    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]


def dict_to_subject(row: Dict) -> SubjectProperty:
    """Convert a BigQuery row dict to SubjectProperty."""
    return SubjectProperty(
        parid=str(row.get("ParID", "")),
        stanpar=str(row.get("STANPAR", "")),
        address=row.get("PropAddr", ""),
        zip_code=row.get("PropZip", ""),
        land_use=row.get("LUDesc", ""),
        total_appraisal=float(row.get("TotlAppr") or 0),
        land_appraisal=float(row.get("LandAppr") or 0),
        improvement_appraisal=float(row.get("ImprAppr") or 0),
        acres=float(row.get("Acres") or 0),
        latitude=float(row.get("Lat")) if row.get("Lat") else None,
        longitude=float(row.get("Lon")) if row.get("Lon") else None,
        year_built=int(row.get("year_built")) if row.get("year_built") else None,
        finished_area=float(row.get("finished_area")) if row.get("finished_area") else None,
        structure_type=row.get("structure_type"),
        exterior=row.get("exterior"),
        sale_price=float(row.get("SalePrice")) if row.get("SalePrice") else None,
        sale_date=row.get("SaleDate"),
    )


def find_comparables(client: bigquery.Client, subject: SubjectProperty,
                     criteria: ComparisonCriteria, max_comps: int,
                     project: str, dataset: str) -> List[ComparableProperty]:
    """Find comparable properties based on criteria."""

    # Build the query with optional building characteristics filters
    query = f"""
    WITH comparables AS (
        SELECT
            p.ParID,
            p.PropAddr,
            p.PropZip,
            p.TotlAppr,
            p.Acres,
            p.Lat,
            p.Lon,
            p.SalePrice,
            FORMAT_DATE('%Y-%m-%d', p.OwnDate) as SaleDate,
            b.year_built,
            b.finished_area,
            b.structure_type,
            b.exterior,
            SAFE_DIVIDE(p.TotlAppr, b.finished_area) AS price_per_sqft,
            -- Assessment to sale ratio (only for valid sales >= $10k)
            CASE
                WHEN p.SalePrice >= 10000 THEN SAFE_DIVIDE(p.TotlAppr, p.SalePrice)
                ELSE NULL
            END AS assessment_to_sale_ratio,
            -- Year difference
            ABS(COALESCE(b.year_built, 0) - @subject_year_built) AS year_diff,
            -- Sqft difference percentage
            SAFE_DIVIDE(
                ABS(COALESCE(b.finished_area, 0) - @subject_sqft),
                NULLIF(@subject_sqft, 0)
            ) * 100 AS sqft_diff_pct,
            -- Distance from subject
            ST_DISTANCE(
                ST_GEOGPOINT(p.Lon, p.Lat),
                ST_GEOGPOINT(@subject_lon, @subject_lat)
            ) AS distance_meters
        FROM `{project}.{dataset}.davidson_parcels` p
        LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b
            ON p.STANPAR = b.apn
        WHERE
            p.ParID != @subject_parid
            AND p.PropZip = @zip_code
            AND p.LUDesc = @land_use
            AND p.TotlAppr > 0
            AND (
                @subject_year_built IS NULL
                OR b.year_built IS NULL
                OR (b.year_built BETWEEN @year_min AND @year_max)
            )
            AND (
                @subject_sqft IS NULL
                OR b.finished_area IS NULL
                OR (b.finished_area BETWEEN @sqft_min AND @sqft_max)
            )
    ),
    ranked AS (
        SELECT *,
            -- Composite similarity score (lower = more similar)
            COALESCE(year_diff / 10.0 * 0.3, 0.15) +
            COALESCE(sqft_diff_pct / 100.0 * 0.4, 0.2) +
            COALESCE(
                SAFE_DIVIDE(ABS(Acres - @subject_acres), NULLIF(@subject_acres, 0)) * 0.2,
                0.1
            ) +
            CASE WHEN structure_type = @subject_structure_type THEN 0 ELSE 0.1 END
            AS similarity_score
        FROM comparables
    )
    SELECT *
    FROM ranked
    ORDER BY similarity_score ASC
    LIMIT @max_comps
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("subject_parid", "STRING", subject.parid),
            bigquery.ScalarQueryParameter("zip_code", "STRING", criteria.zip_code),
            bigquery.ScalarQueryParameter("land_use", "STRING", criteria.land_use),
            bigquery.ScalarQueryParameter("subject_year_built", "INT64", subject.year_built),
            bigquery.ScalarQueryParameter("subject_sqft", "FLOAT64", subject.finished_area),
            bigquery.ScalarQueryParameter("subject_acres", "FLOAT64", subject.acres),
            bigquery.ScalarQueryParameter("subject_lat", "FLOAT64", subject.latitude or 0),
            bigquery.ScalarQueryParameter("subject_lon", "FLOAT64", subject.longitude or 0),
            bigquery.ScalarQueryParameter("subject_structure_type", "STRING", subject.structure_type),
            bigquery.ScalarQueryParameter("year_min", "INT64", criteria.year_built_min),
            bigquery.ScalarQueryParameter("year_max", "INT64", criteria.year_built_max),
            bigquery.ScalarQueryParameter("sqft_min", "FLOAT64", criteria.sqft_min),
            bigquery.ScalarQueryParameter("sqft_max", "FLOAT64", criteria.sqft_max),
            bigquery.ScalarQueryParameter("max_comps", "INT64", max_comps),
        ]
    )

    results = client.query(query, job_config=job_config).result()

    comparables = []
    for row in results:
        comp = ComparableProperty(
            parid=str(row.ParID),
            address=row.PropAddr,
            zip_code=row.PropZip,
            total_appraisal=float(row.TotlAppr),
            acres=float(row.Acres) if row.Acres else 0,
            year_built=int(row.year_built) if row.year_built else None,
            finished_area=float(row.finished_area) if row.finished_area else None,
            structure_type=row.structure_type,
            exterior=row.exterior,
            price_per_sqft=float(row.price_per_sqft) if row.price_per_sqft else None,
            similarity_score=float(row.similarity_score) if row.similarity_score else 0,
            year_diff=int(row.year_diff) if row.year_diff else None,
            sqft_diff_pct=float(row.sqft_diff_pct) if row.sqft_diff_pct else None,
            distance_meters=float(row.distance_meters) if row.distance_meters else None,
            sale_price=float(row.SalePrice) if row.SalePrice and row.SalePrice >= 10000 else None,
            sale_date=row.SaleDate if row.SalePrice and row.SalePrice >= 10000 else None,
            assessment_to_sale_ratio=float(row.assessment_to_sale_ratio) if row.assessment_to_sale_ratio else None,
        )
        comparables.append(comp)

    return comparables


def find_comparable_sales(client: bigquery.Client, subject: SubjectProperty,
                          sale_days: int, max_comps: int,
                          sqft_range_pct: int,
                          project: str, dataset: str) -> List[ComparableProperty]:
    """Find comparable properties with recent sales, sorted by distance.

    This is the COMPER-style search that prioritizes:
    1. Recent sales (within sale_days)
    2. Geographic proximity (distance from subject)
    3. Same land use type
    4. Similar square footage (+/- sqft_range_pct)
    """

    # Calculate sqft range
    if subject.finished_area:
        sqft_min = subject.finished_area * (1 - sqft_range_pct / 100)
        sqft_max = subject.finished_area * (1 + sqft_range_pct / 100)
    else:
        sqft_min = None
        sqft_max = None

    query = f"""
    SELECT
        p.ParID,
        p.PropAddr,
        p.PropZip,
        p.TotlAppr,
        p.Acres,
        p.Lat,
        p.Lon,
        p.SalePrice,
        FORMAT_DATE('%Y-%m-%d', p.OwnDate) as SaleDate,
        b.year_built,
        b.finished_area,
        b.structure_type,
        b.exterior,
        SAFE_DIVIDE(p.TotlAppr, b.finished_area) AS price_per_sqft,
        SAFE_DIVIDE(p.SalePrice, b.finished_area) AS sale_price_per_sqft,
        SAFE_DIVIDE(p.TotlAppr, p.SalePrice) AS assessment_to_sale_ratio,
        -- Distance from subject in feet
        ST_DISTANCE(
            ST_GEOGPOINT(p.Lon, p.Lat),
            ST_GEOGPOINT(@subject_lon, @subject_lat)
        ) * 3.28084 AS distance_feet
    FROM `{project}.{dataset}.davidson_parcels` p
    LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b
        ON p.STANPAR = b.apn
    WHERE
        p.ParID != @subject_parid
        AND p.LUDesc = @land_use
        AND p.SalePrice >= 10000  -- Filter nominal transfers
        AND p.OwnDate >= DATE_SUB(CURRENT_DATE(), INTERVAL @sale_days DAY)
        AND p.Lat IS NOT NULL
        AND p.Lon IS NOT NULL
        AND (
            @sqft_min IS NULL
            OR b.finished_area IS NULL
            OR (b.finished_area BETWEEN @sqft_min AND @sqft_max)
        )
    ORDER BY distance_feet ASC
    LIMIT @max_comps
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("subject_parid", "STRING", subject.parid),
            bigquery.ScalarQueryParameter("land_use", "STRING", subject.land_use),
            bigquery.ScalarQueryParameter("subject_lat", "FLOAT64", subject.latitude or 0),
            bigquery.ScalarQueryParameter("subject_lon", "FLOAT64", subject.longitude or 0),
            bigquery.ScalarQueryParameter("sale_days", "INT64", sale_days),
            bigquery.ScalarQueryParameter("max_comps", "INT64", max_comps),
            bigquery.ScalarQueryParameter("sqft_min", "FLOAT64", sqft_min),
            bigquery.ScalarQueryParameter("sqft_max", "FLOAT64", sqft_max),
        ]
    )

    results = client.query(query, job_config=job_config).result()

    comparables = []
    for row in results:
        comp = ComparableProperty(
            parid=str(row.ParID),
            address=row.PropAddr,
            zip_code=row.PropZip,
            total_appraisal=float(row.TotlAppr),
            acres=float(row.Acres) if row.Acres else 0,
            year_built=int(row.year_built) if row.year_built else None,
            finished_area=float(row.finished_area) if row.finished_area else None,
            structure_type=row.structure_type,
            exterior=row.exterior,
            price_per_sqft=float(row.price_per_sqft) if row.price_per_sqft else None,
            similarity_score=0,  # Not used for sales-based search
            year_diff=None,
            sqft_diff_pct=None,
            distance_meters=float(row.distance_feet) / 3.28084 if row.distance_feet else None,
            sale_price=float(row.SalePrice),
            sale_date=row.SaleDate,
            assessment_to_sale_ratio=float(row.assessment_to_sale_ratio) if row.assessment_to_sale_ratio else None,
        )
        comparables.append(comp)

    return comparables


def lookup_environmental_factors(client: bigquery.Client, parid: str,
                                  project: str, dataset: str) -> EnvironmentalFactors:
    """Look up flood zone and rail proximity for a property."""

    # Query flood zone data
    flood_query = f"""
    SELECT
        flood_zone,
        zone_subtype,
        is_sfha,
        flood_risk
    FROM `{project}.{dataset}.v_parcel_floodzone_enrichment`
    WHERE parcel_id = @parid
    LIMIT 1
    """

    # Query rail proximity data
    rail_query = f"""
    SELECT
        distance_to_rail_ft,
        nearest_rail_owner,
        within_100m,
        within_250m,
        within_500m,
        within_1000m
    FROM `{project}.{dataset}.v_parcel_rail_enrichment`
    WHERE parcel_id = @parid
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("parid", "STRING", parid)
        ]
    )

    # Execute flood zone query
    flood_zone = None
    flood_zone_subtype = None
    flood_risk_level = "UNKNOWN"
    is_sfha = False

    try:
        flood_results = list(client.query(flood_query, job_config=job_config).result())
        if flood_results:
            row = flood_results[0]
            flood_zone = row.flood_zone
            flood_zone_subtype = row.zone_subtype
            is_sfha = bool(row.is_sfha) if row.is_sfha is not None else False
            flood_risk_level = row.flood_risk if row.flood_risk else "NOT_IN_FLOOD_ZONE"
    except Exception:
        pass  # View may not exist or other error

    # Execute rail proximity query
    rail_distance_feet = None
    rail_proximity_flag = "UNKNOWN"
    nearest_rail_owner = None

    try:
        rail_results = list(client.query(rail_query, job_config=job_config).result())
        if rail_results:
            row = rail_results[0]
            rail_distance_feet = float(row.distance_to_rail_ft) if row.distance_to_rail_ft else None
            nearest_rail_owner = row.nearest_rail_owner

            if row.within_100m:
                rail_proximity_flag = "WITHIN_100M"
            elif row.within_250m:
                rail_proximity_flag = "WITHIN_250M"
            elif row.within_500m:
                rail_proximity_flag = "WITHIN_500M"
            elif row.within_1000m:
                rail_proximity_flag = "WITHIN_1000M"
            elif rail_distance_feet is not None:
                rail_proximity_flag = "BEYOND_1000M"
    except Exception:
        pass  # View may not exist or other error

    return EnvironmentalFactors(
        flood_zone=flood_zone,
        flood_zone_subtype=flood_zone_subtype,
        flood_risk_level=flood_risk_level,
        is_special_flood_hazard_area=is_sfha,
        rail_distance_feet=rail_distance_feet,
        rail_proximity_flag=rail_proximity_flag,
        nearest_rail_owner=nearest_rail_owner,
    )


def lookup_building_permits(client: bigquery.Client, address: str,
                            project: str, dataset: str) -> PermitHistory:
    """Look up building permits for a property by address."""

    # Clean up address for search - extract street name components
    # Address format is typically "123 MAIN ST"
    address_pattern = address.upper().strip()

    query = f"""
    SELECT
        Address,
        Permit_Type_Description,
        Purpose,
        Construction_Cost,
        FORMAT_DATE('%Y-%m-%d', Date_Issued) as date_issued
    FROM `{project}.{dataset}.building_permits_nashville`
    WHERE UPPER(Address) LIKE @address_pattern
    ORDER BY Date_Issued DESC
    LIMIT 20
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("address_pattern", "STRING", f"%{address_pattern}%")
        ]
    )

    permits = []
    total_cost = 0.0
    has_major = False

    try:
        results = client.query(query, job_config=job_config).result()
        for row in results:
            cost = float(row.Construction_Cost) if row.Construction_Cost else None
            permit = BuildingPermit(
                address=row.Address,
                permit_type=row.Permit_Type_Description or "",
                purpose=row.Purpose or "",
                construction_cost=cost,
                date_issued=row.date_issued,
            )
            permits.append(permit)

            if cost:
                total_cost += cost
                if cost > 50000:
                    has_major = True
    except Exception:
        pass  # Table may not exist or other error

    return PermitHistory(
        permits=permits,
        total_permits=len(permits),
        total_construction_cost=total_cost,
        has_major_renovation=has_major,
    )


def calculate_statistics(subject: SubjectProperty,
                         comparables: List[ComparableProperty]) -> ComparisonStatistics:
    """Calculate statistics for the comparable set."""
    if not comparables:
        return ComparisonStatistics(
            count=0,
            mean_price_per_sqft=None,
            median_price_per_sqft=None,
            stddev_price_per_sqft=None,
            min_price_per_sqft=None,
            max_price_per_sqft=None,
            mean_total_appraisal=0,
            median_total_appraisal=0,
            subject_percentile=None,
            subject_z_score=None,
            comps_with_building_data=0,
            comps_without_building_data=0,
        )

    # Filter comps with price per sqft data
    comps_with_pps = [c for c in comparables if c.price_per_sqft is not None]
    comps_without_pps = [c for c in comparables if c.price_per_sqft is None]

    # Price per sqft statistics
    if comps_with_pps:
        pps_values = sorted([c.price_per_sqft for c in comps_with_pps])
        mean_pps = sum(pps_values) / len(pps_values)
        median_pps = pps_values[len(pps_values) // 2]

        if len(pps_values) > 1:
            variance = sum((x - mean_pps) ** 2 for x in pps_values) / len(pps_values)
            stddev_pps = variance ** 0.5
        else:
            stddev_pps = 0

        min_pps = min(pps_values)
        max_pps = max(pps_values)

        # Subject's position
        if subject.price_per_sqft and stddev_pps > 0:
            subject_z_score = (subject.price_per_sqft - mean_pps) / stddev_pps
            count_below = sum(1 for p in pps_values if p < subject.price_per_sqft)
            subject_percentile = (count_below / len(pps_values)) * 100
        else:
            subject_z_score = None
            subject_percentile = None
    else:
        mean_pps = median_pps = stddev_pps = min_pps = max_pps = None
        subject_z_score = subject_percentile = None

    # Total appraisal statistics
    appr_values = sorted([c.total_appraisal for c in comparables])
    mean_appr = sum(appr_values) / len(appr_values)
    median_appr = appr_values[len(appr_values) // 2]

    return ComparisonStatistics(
        count=len(comparables),
        mean_price_per_sqft=round(mean_pps, 2) if mean_pps else None,
        median_price_per_sqft=round(median_pps, 2) if median_pps else None,
        stddev_price_per_sqft=round(stddev_pps, 2) if stddev_pps else None,
        min_price_per_sqft=round(min_pps, 2) if min_pps else None,
        max_price_per_sqft=round(max_pps, 2) if max_pps else None,
        mean_total_appraisal=round(mean_appr, 0),
        median_total_appraisal=round(median_appr, 0),
        subject_percentile=round(subject_percentile, 1) if subject_percentile is not None else None,
        subject_z_score=round(subject_z_score, 2) if subject_z_score is not None else None,
        comps_with_building_data=len(comps_with_pps),
        comps_without_building_data=len(comps_without_pps),
    )


def calculate_sale_statistics(subject: SubjectProperty,
                               comparable_sales: List[ComparableProperty]) -> Optional[SaleStatistics]:
    """Calculate statistics for comparable sales (market value approach)."""
    if not comparable_sales:
        return None

    # Filter sales with sqft data for $/sqft calculations
    sales_with_sqft = [c for c in comparable_sales if c.finished_area and c.finished_area > 0]

    # Sale price per sqft statistics
    if sales_with_sqft:
        sale_pps_values = sorted([c.sale_price / c.finished_area for c in sales_with_sqft])
        mean_sale_pps = sum(sale_pps_values) / len(sale_pps_values)
        median_sale_pps = sale_pps_values[len(sale_pps_values) // 2]
        min_sale_pps = min(sale_pps_values)
        max_sale_pps = max(sale_pps_values)

        # Calculate standard deviation
        if len(sale_pps_values) > 1:
            variance = sum((x - mean_sale_pps) ** 2 for x in sale_pps_values) / len(sale_pps_values)
            stddev_sale_pps = variance ** 0.5
        else:
            stddev_sale_pps = 0

        # How does subject compare to median sale $/sqft?
        if subject.price_per_sqft and median_sale_pps > 0:
            subject_vs_median = ((subject.price_per_sqft - median_sale_pps) / median_sale_pps) * 100
        else:
            subject_vs_median = None

        # Subject's market position (assessment $/sqft vs sale $/sqft)
        if subject.price_per_sqft and stddev_sale_pps > 0:
            # Percentile: % of sales with LOWER $/sqft than subject's assessment
            count_below = sum(1 for p in sale_pps_values if p < subject.price_per_sqft)
            subject_market_percentile = (count_below / len(sale_pps_values)) * 100
            # Z-score: how many std devs above/below mean
            subject_market_z_score = (subject.price_per_sqft - mean_sale_pps) / stddev_sale_pps
        else:
            subject_market_percentile = None
            subject_market_z_score = None
    else:
        mean_sale_pps = median_sale_pps = min_sale_pps = max_sale_pps = stddev_sale_pps = None
        subject_vs_median = None
        subject_market_percentile = None
        subject_market_z_score = None

    # Total sale price statistics
    sale_prices = sorted([c.sale_price for c in comparable_sales])
    mean_sale = sum(sale_prices) / len(sale_prices)
    median_sale = sale_prices[len(sale_prices) // 2]

    # Average assessment-to-sale ratio across comps
    ratios = [c.assessment_to_sale_ratio for c in comparable_sales if c.assessment_to_sale_ratio]
    avg_ratio = sum(ratios) / len(ratios) if ratios else None

    return SaleStatistics(
        count=len(comparable_sales),
        mean_sale_price_per_sqft=round(mean_sale_pps, 2) if mean_sale_pps else None,
        median_sale_price_per_sqft=round(median_sale_pps, 2) if median_sale_pps else None,
        min_sale_price_per_sqft=round(min_sale_pps, 2) if min_sale_pps else None,
        max_sale_price_per_sqft=round(max_sale_pps, 2) if max_sale_pps else None,
        stddev_sale_price_per_sqft=round(stddev_sale_pps, 2) if stddev_sale_pps else None,
        mean_sale_price=round(mean_sale, 0),
        median_sale_price=round(median_sale, 0),
        avg_assessment_to_sale_ratio=round(avg_ratio, 2) if avg_ratio else None,
        subject_vs_median_sale_pct=round(subject_vs_median, 1) if subject_vs_median is not None else None,
        subject_market_percentile=round(subject_market_percentile, 1) if subject_market_percentile is not None else None,
        subject_market_z_score=round(subject_market_z_score, 2) if subject_market_z_score is not None else None,
    )


def generate_recommendation(subject: SubjectProperty,
                            statistics: ComparisonStatistics,
                            sale_statistics: Optional[SaleStatistics] = None,
                            environmental: Optional[EnvironmentalFactors] = None,
                            permit_history: Optional[PermitHistory] = None) -> AppealRecommendation:
    """Generate appeal recommendation based on analysis."""
    findings = []
    score = 0.0

    if statistics.count == 0 and (sale_statistics is None or sale_statistics.count == 0):
        return AppealRecommendation(
            recommendation="INSUFFICIENT_DATA",
            appeal_strength_score=0,
            estimated_annual_savings=0,
            key_findings=["No comparable properties found for analysis"]
        )

    z_score = statistics.subject_z_score
    percentile = statistics.subject_percentile
    median_pps = statistics.median_price_per_sqft
    subject_pps = subject.price_per_sqft

    # Calculate percentage above median
    if subject_pps and median_pps and median_pps > 0:
        pct_above_median = ((subject_pps - median_pps) / median_pps) * 100
    else:
        pct_above_median = None

    # Score based on z-score (max 30 points)
    if z_score is not None:
        if z_score > 0:
            z_score_points = min(30, z_score * 15)
            score += z_score_points
            if z_score > 1.5:
                findings.append(f"Z-score of {z_score:+.2f} indicates assessment is {z_score:.1f} standard deviations above mean")

    # Score based on percentile (max 30 points)
    if percentile is not None and percentile > 50:
        percentile_points = min(30, (percentile - 50) * 0.6)
        score += percentile_points
        if percentile > 70:
            findings.append(f"Assessment is higher than {percentile:.0f}% of comparable properties")

    # Score based on percentage above median (max 20 points)
    if pct_above_median is not None and pct_above_median > 0:
        pct_points = min(20, pct_above_median * 0.5)
        score += pct_points
        if pct_above_median > 10:
            findings.append(f"Property is assessed {pct_above_median:.1f}% above neighborhood median")

    # Environmental factors - these could support LOWER assessments
    if environmental:
        if environmental.flood_risk_level == "HIGH_RISK":
            findings.append(f"Property is in FEMA flood zone {environmental.flood_zone} (high risk) - may support lower value argument")
        elif environmental.flood_risk_level == "MODERATE_RISK":
            findings.append(f"Property is in moderate flood risk zone - consider in valuation")

        if environmental.rail_proximity_flag == "WITHIN_100M":
            findings.append(f"Property is within 100m of rail line ({environmental.nearest_rail_owner}) - noise/vibration impact")
        elif environmental.rail_proximity_flag == "WITHIN_250M":
            findings.append(f"Property is within 250m of rail line - potential noise impact")

    # Sale price comparison - strong evidence if over-assessed vs sale
    sale_ratio = subject.assessment_to_sale_ratio
    if sale_ratio:
        if sale_ratio > 1.20:  # 20%+ over sale price
            score += 25  # Major boost to appeal score
            pct_over = (sale_ratio - 1) * 100
            findings.append(f"STRONG: Assessment is {pct_over:.0f}% above last sale price (${subject.sale_price:,.0f} on {subject.sale_date})")
        elif sale_ratio > 1.10:  # 10-20% over
            score += 15
            pct_over = (sale_ratio - 1) * 100
            findings.append(f"Assessment is {pct_over:.0f}% above last sale price (${subject.sale_price:,.0f})")
        elif sale_ratio > 1.05:  # 5-10% over
            score += 5
            pct_over = (sale_ratio - 1) * 100
            findings.append(f"Assessment is {pct_over:.0f}% above last sale price")
        elif sale_ratio < 0.95:  # Under-assessed
            findings.append(f"Assessment is below last sale price - appeal unlikely to succeed")

    # MARKET VALUE ANALYSIS - Compare subject to recent comparable sales (PRIMARY METRIC)
    if sale_statistics and sale_statistics.count > 0:
        median_sale_pps = sale_statistics.median_sale_price_per_sqft
        subject_vs_sales = sale_statistics.subject_vs_median_sale_pct

        if subject_vs_sales is not None:
            if subject_vs_sales > 30:  # 30%+ above market
                score += 35  # Major boost - this is strong evidence
                findings.insert(0, f"MARKET VALUE: Assessment is {subject_vs_sales:.0f}% above median sale $/sqft (${median_sale_pps:,.0f} vs your ${subject.price_per_sqft:,.0f})")
            elif subject_vs_sales > 20:  # 20-30% above market
                score += 25
                findings.insert(0, f"MARKET VALUE: Assessment is {subject_vs_sales:.0f}% above median comparable sale $/sqft")
            elif subject_vs_sales > 10:  # 10-20% above market
                score += 15
                findings.insert(0, f"Assessment is {subject_vs_sales:.0f}% above median comparable sale $/sqft")
            elif subject_vs_sales < -10:  # Below market
                findings.append(f"Assessment is {abs(subject_vs_sales):.0f}% BELOW median comparable sale $/sqft - appeal unlikely")

        # Add info about sales data quality
        findings.append(f"Based on {sale_statistics.count} comparable sales (median: ${sale_statistics.median_sale_price:,.0f})")

    # Determine recommendation (score-based with thresholds)
    # Sale statistics are weighted more heavily as they represent market reality
    subject_vs_sales = sale_statistics.subject_vs_median_sale_pct if sale_statistics else None

    if score >= 50 or (subject_vs_sales is not None and subject_vs_sales > 25):
        recommendation = "STRONG_CANDIDATE"
    elif score >= 30 or (subject_vs_sales is not None and subject_vs_sales > 15):
        recommendation = "MODERATE_CANDIDATE"
    elif score >= 15 or (subject_vs_sales is not None and subject_vs_sales > 5):
        recommendation = "WORTH_REVIEWING"
    elif statistics.count == 0 and (sale_statistics is None or sale_statistics.count == 0):
        recommendation = "INSUFFICIENT_DATA"
    else:
        recommendation = "LIKELY_FAIR"

    # Check if sales suggest under-assessment
    if subject_vs_sales is not None and subject_vs_sales < -10:
        recommendation = "LIKELY_FAIR"  # Don't recommend appealing if below market

    # Add summary finding
    if recommendation == "LIKELY_FAIR":
        findings.append("Assessment appears reasonable relative to market sales")
    elif recommendation == "STRONG_CANDIDATE":
        findings.append("Strong indicators suggest property may be over-assessed vs market")

    # Estimate savings - prefer sale price data if available
    estimated_savings = 0
    if sale_statistics and sale_statistics.median_sale_price_per_sqft and subject.finished_area:
        fair_value = sale_statistics.median_sale_price_per_sqft * subject.finished_area
        potential_reduction = subject.total_appraisal - fair_value
        if potential_reduction > 0:
            estimated_savings = potential_reduction * 0.25 * 0.03
    elif pct_above_median and pct_above_median > 0 and median_pps and subject.finished_area:
        fair_value = median_pps * subject.finished_area
        potential_reduction = subject.total_appraisal - fair_value
        if potential_reduction > 0:
            estimated_savings = potential_reduction * 0.25 * 0.03

    return AppealRecommendation(
        recommendation=recommendation,
        appeal_strength_score=round(min(100, score), 1),
        estimated_annual_savings=round(estimated_savings, 2),
        key_findings=findings if findings else ["No significant issues identified"]
    )


def format_text_report(result: ComparisonResult) -> str:
    """Format the comparison result as a text report."""
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("              PROPERTY TAX ASSESSMENT COMPARISON REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Subject Property
    s = result.subject
    lines.append("SUBJECT PROPERTY")
    lines.append("-" * 80)
    lines.append(f"  Address:        {s.address}, NASHVILLE TN {s.zip_code}")
    lines.append(f"  Parcel ID:      {s.parid}")
    lines.append(f"  Land Use:       {s.land_use}")
    if s.year_built:
        lines.append(f"  Year Built:     {s.year_built}")
    if s.finished_area:
        lines.append(f"  Square Feet:    {s.finished_area:,.0f}")
    if s.structure_type:
        lines.append(f"  Structure:      {s.structure_type}")
    if s.exterior:
        lines.append(f"  Exterior:       {s.exterior}")
    lines.append(f"  Acres:          {s.acres:.2f}")
    lines.append("")
    lines.append("  ASSESSMENT VALUES")
    lines.append(f"  Land:           ${s.land_appraisal:,.0f}")
    lines.append(f"  Improvements:   ${s.improvement_appraisal:,.0f}")
    lines.append(f"  Total:          ${s.total_appraisal:,.0f}")
    lines.append("")
    if s.price_per_sqft:
        lines.append(f"  Price/SqFt:     ${s.price_per_sqft:,.2f}")
    if s.price_per_acre:
        lines.append(f"  Price/Acre:     ${s.price_per_acre:,.0f}")
    lines.append("")

    # Sale price info (if available and valid)
    if s.sale_price and s.sale_price >= 10000:
        lines.append("  LAST SALE")
        lines.append(f"  Sale Price:     ${s.sale_price:,.0f}")
        if s.sale_date:
            lines.append(f"  Sale Date:      {s.sale_date}")
        ratio = s.assessment_to_sale_ratio
        if ratio:
            ratio_pct = (ratio - 1) * 100
            if ratio > 1.05:
                lines.append(f"  Assessment/Sale: {ratio:.2f}x (OVER-ASSESSED by {ratio_pct:.1f}%)")
            elif ratio < 0.95:
                lines.append(f"  Assessment/Sale: {ratio:.2f}x (under-assessed by {abs(ratio_pct):.1f}%)")
            else:
                lines.append(f"  Assessment/Sale: {ratio:.2f}x (close to sale price)")
        lines.append("")

    # Comparison Criteria
    c = result.criteria
    lines.append("COMPARISON CRITERIA")
    lines.append("-" * 80)
    lines.append(f"  Zip Code:       {c.zip_code}")
    lines.append(f"  Land Use:       {c.land_use}")
    if c.year_built_min and c.year_built_max:
        lines.append(f"  Year Built:     {c.year_built_min} - {c.year_built_max} (+/- {c.year_range} years)")
    if c.sqft_min and c.sqft_max:
        lines.append(f"  Square Feet:    {c.sqft_min:,.0f} - {c.sqft_max:,.0f} (+/- {c.sqft_range_pct}%)")
    lines.append("")

    # Statistics
    st = result.statistics
    lines.append(f"COMPARABLE STATISTICS ({st.count} properties)")
    lines.append("-" * 80)
    if st.mean_price_per_sqft:
        lines.append("                          Mean       Median     Std Dev      Min        Max")
        lines.append(f"  Price/SqFt          ${st.mean_price_per_sqft:>7,.2f}    ${st.median_price_per_sqft:>7,.2f}   ${st.stddev_price_per_sqft:>7,.2f}   ${st.min_price_per_sqft:>7,.2f}   ${st.max_price_per_sqft:>7,.2f}")
    lines.append(f"  Total Appraisal   ${st.mean_total_appraisal:>10,.0f}  ${st.median_total_appraisal:>10,.0f}")
    lines.append("")
    lines.append(f"  Properties with building data: {st.comps_with_building_data} of {st.count}")
    lines.append("")

    # Environmental Factors
    if result.environmental:
        env = result.environmental
        lines.append("ENVIRONMENTAL FACTORS")
        lines.append("-" * 80)

        # Flood zone
        if env.flood_zone:
            risk_display = env.flood_risk_level.replace("_", " ")
            lines.append(f"  Flood Zone:     {env.flood_zone} ({risk_display})")
            if env.flood_zone_subtype:
                lines.append(f"  Zone Subtype:   {env.flood_zone_subtype}")
            sfha_status = "YES" if env.is_special_flood_hazard_area else "NO"
            lines.append(f"  SFHA (High Risk): {sfha_status}")
        else:
            lines.append(f"  Flood Zone:     NOT IN FLOOD ZONE")

        # Rail proximity
        if env.rail_distance_feet is not None:
            distance_miles = env.rail_distance_feet / 5280
            proximity = env.rail_proximity_flag.replace("_", " ")
            lines.append(f"  Rail Distance:  {env.rail_distance_feet:,.0f} ft ({distance_miles:.2f} mi) - {proximity}")
            if env.nearest_rail_owner:
                lines.append(f"  Rail Owner:     {env.nearest_rail_owner}")
        else:
            lines.append(f"  Rail Distance:  Data unavailable")

        lines.append("")

    # Building Permits
    if result.permit_history:
        ph = result.permit_history
        lines.append("BUILDING PERMITS")
        lines.append("-" * 80)
        lines.append(f"  Total Permits:      {ph.total_permits}")
        if ph.total_construction_cost > 0:
            lines.append(f"  Total Cost:         ${ph.total_construction_cost:,.0f}")
        lines.append(f"  Major Renovations:  {'YES' if ph.has_major_renovation else 'NO'} (>$50k)")

        if ph.permits:
            lines.append("")
            lines.append("  Recent Permits:")
            for permit in ph.permits[:5]:
                cost_str = f"${permit.construction_cost:,.0f}" if permit.construction_cost else "N/A"
                date_str = permit.date_issued or "N/A"
                lines.append(f"    - {date_str}: {permit.permit_type} - {cost_str}")
                if permit.purpose:
                    lines.append(f"      Purpose: {permit.purpose[:60]}")
        elif ph.total_permits == 0:
            lines.append("  (No permits found - may be outside Nashville permit system)")

        lines.append("")

    # Subject Position
    if st.subject_percentile is not None or st.subject_z_score is not None:
        lines.append("SUBJECT POSITION")
        lines.append("-" * 80)
        if st.subject_percentile is not None:
            lines.append(f"  Percentile:     {st.subject_percentile:.0f}th (higher than {st.subject_percentile:.0f}% of comparables)")
        if st.subject_z_score is not None:
            lines.append(f"  Z-Score:        {st.subject_z_score:+.2f}")
        lines.append("")

    # Comparable Properties
    if result.comparables:
        lines.append(f"COMPARABLE PROPERTIES ({len(result.comparables)} total)")
        lines.append("-" * 80)
        lines.append("  Address                         Year   SqFt    $/SqFt    Appraisal    Score")
        lines.append("  " + "-" * 76)
        for comp in result.comparables:
            addr = (comp.address[:30] if len(comp.address) > 30 else comp.address).ljust(30)
            year = str(comp.year_built) if comp.year_built else "N/A"
            sqft = f"{comp.finished_area:,.0f}" if comp.finished_area else "N/A"
            pps = f"${comp.price_per_sqft:,.2f}" if comp.price_per_sqft else "N/A"
            lines.append(f"  {addr} {year:>5}  {sqft:>6}  {pps:>8}  ${comp.total_appraisal:>10,.0f}  {comp.similarity_score:.2f}")
        lines.append("")

    # MARKET VALUE ANALYSIS - Recent comparable sales (COMPER-style, distance-based)
    if result.comparable_sales:
        lines.append("=" * 80)
        lines.append("                    MARKET VALUE ANALYSIS (Primary)")
        lines.append("=" * 80)
        lines.append(f"RECENT COMPARABLE SALES ({len(result.comparable_sales)} nearby sales, sorted by distance)")
        lines.append("-" * 80)
        lines.append("  Address                       Distance   Sale Date      SqFt   Sale Price  $/SqFt")
        lines.append("  " + "-" * 84)
        for comp in result.comparable_sales:
            addr = (comp.address[:28] if len(comp.address) > 28 else comp.address).ljust(28)
            if comp.distance_meters:
                dist_ft = comp.distance_meters * 3.28084
                if dist_ft < 5280:
                    dist_str = f"{dist_ft:,.0f} ft"
                else:
                    dist_str = f"{dist_ft/5280:.2f} mi"
            else:
                dist_str = "N/A"
            date = comp.sale_date if comp.sale_date else "N/A"
            sqft = f"{comp.finished_area:,.0f}" if comp.finished_area else "N/A"
            sale_pps = f"${comp.sale_price / comp.finished_area:,.0f}" if comp.finished_area and comp.finished_area > 0 else "N/A"
            lines.append(f"  {addr} {dist_str:>9}   {date:>10}  {sqft:>6}  ${comp.sale_price:>10,.0f}  {sale_pps:>7}")
        lines.append("")

        # Sale statistics summary
        if result.sale_statistics:
            ss = result.sale_statistics
            lines.append("MARKET STATISTICS")
            lines.append("-" * 80)
            if ss.median_sale_price_per_sqft:
                lines.append(f"  Median Sale $/SqFt:   ${ss.median_sale_price_per_sqft:,.0f}")
                lines.append(f"  Range:                ${ss.min_sale_price_per_sqft:,.0f} - ${ss.max_sale_price_per_sqft:,.0f}")
            lines.append(f"  Median Sale Price:    ${ss.median_sale_price:,.0f}")
            if ss.subject_vs_median_sale_pct is not None:
                pct = ss.subject_vs_median_sale_pct
                if pct > 0:
                    lines.append(f"  Your Assessment vs Market: {pct:+.1f}% ABOVE median sale $/sqft")
                else:
                    lines.append(f"  Your Assessment vs Market: {pct:+.1f}% below median sale $/sqft")
            lines.append("")

            # Market Value Position (subject assessment vs market sales)
            if ss.subject_market_percentile is not None or ss.subject_market_z_score is not None:
                lines.append("MARKET VALUE POSITION")
                lines.append("-" * 80)
                if ss.subject_market_percentile is not None:
                    pctl = ss.subject_market_percentile
                    lines.append(f"  Percentile:     {pctl:.0f}th (your assessment $/sqft is higher than {pctl:.0f}% of recent sales)")
                if ss.subject_market_z_score is not None:
                    lines.append(f"  Z-Score:        {ss.subject_market_z_score:+.2f}")
                lines.append("")
                # Interpretation
                if ss.subject_market_percentile is not None:
                    if ss.subject_market_percentile >= 80:
                        lines.append("  Interpretation: Your assessment is in the TOP 20% vs market - strong appeal case")
                    elif ss.subject_market_percentile >= 60:
                        lines.append("  Interpretation: Your assessment is ABOVE AVERAGE vs market - moderate appeal case")
                    elif ss.subject_market_percentile >= 40:
                        lines.append("  Interpretation: Your assessment is NEAR AVERAGE vs market")
                    else:
                        lines.append("  Interpretation: Your assessment is BELOW AVERAGE vs market - weak appeal case")
                    lines.append("")

    # Appeal Recommendation
    r = result.recommendation
    lines.append("APPEAL RECOMMENDATION")
    lines.append("-" * 80)
    lines.append(f"  Recommendation:         {r.recommendation}")
    lines.append(f"  Appeal Strength Score:  {r.appeal_strength_score:.0f}/100")
    lines.append("")
    lines.append("  Key Findings:")
    for finding in r.key_findings:
        lines.append(f"    - {finding}")
    lines.append("")
    if r.estimated_annual_savings > 0:
        lines.append(f"  Estimated Annual Savings if Assessed at Median: ${r.estimated_annual_savings:,.2f}")
        lines.append("  (Assumes 25% assessment ratio, 3% tax rate)")
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("WARNINGS")
        lines.append("-" * 80)
        for warning in result.warnings:
            lines.append(f"  ! {warning}")
        lines.append("")

    # Footer
    lines.append("=" * 80)
    lines.append(f"  Generated: {result.generated_at}")
    lines.append("  Data Source: Nashville Property Assessor via BigQuery")
    lines.append("=" * 80)

    return "\n".join(lines)


def format_json_report(result: ComparisonResult) -> str:
    """Format the comparison result as JSON."""

    def to_serializable(obj):
        """Convert dataclasses to dicts recursively."""
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_serializable(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: to_serializable(v) for k, v in obj.items()}
        else:
            return obj

    data = to_serializable(result)
    return json.dumps(data, indent=2)


def analyze_single_property(client: bigquery.Client, subject: SubjectProperty,
                            args, project: str, dataset: str) -> ComparisonResult:
    """Analyze a single property and return the comparison result."""
    warnings = []

    # Build comparison criteria
    if subject.year_built:
        year_min = subject.year_built - args.year_range
        year_max = subject.year_built + args.year_range
    else:
        year_min = year_max = None
        warnings.append("No year built data available; year range filter not applied")

    if subject.finished_area:
        sqft_min = subject.finished_area * (1 - args.sqft_range / 100)
        sqft_max = subject.finished_area * (1 + args.sqft_range / 100)
    else:
        sqft_min = sqft_max = None
        warnings.append("No square footage data available; comparison will use value per acre instead")

    criteria = ComparisonCriteria(
        zip_code=subject.zip_code,
        land_use=subject.land_use,
        year_built_min=year_min,
        year_built_max=year_max,
        sqft_min=sqft_min,
        sqft_max=sqft_max,
        year_range=args.year_range,
        sqft_range_pct=args.sqft_range,
    )

    # Find comparables
    comparables = find_comparables(
        client, subject, criteria, args.max_comps, project, dataset
    )

    if len(comparables) < DEFAULT_MIN_COMPARABLES:
        warnings.append(f"Only {len(comparables)} comparables found (recommended minimum: {DEFAULT_MIN_COMPARABLES})")

    # Calculate statistics
    statistics = calculate_statistics(subject, comparables)

    # Find comparable SALES (COMPER-style, distance-based, recent sales only, similar sqft)
    comparable_sales = find_comparable_sales(
        client, subject, args.sale_days, args.max_comps, args.sqft_range, project, dataset
    )

    if len(comparable_sales) < DEFAULT_MIN_COMPARABLES:
        warnings.append(f"Only {len(comparable_sales)} recent sales found within {args.sale_days} days")

    # Calculate sale statistics
    sale_statistics = calculate_sale_statistics(subject, comparable_sales)

    # Look up environmental factors
    environmental = lookup_environmental_factors(
        client, subject.parid, project, dataset
    )

    # Look up building permits
    permit_history = lookup_building_permits(
        client, subject.address, project, dataset
    )

    # Generate recommendation
    recommendation = generate_recommendation(
        subject, statistics, sale_statistics, environmental, permit_history
    )

    # Build result
    return ComparisonResult(
        subject=subject,
        criteria=criteria,
        comparables=comparables,
        statistics=statistics,
        comparable_sales=comparable_sales,
        sale_statistics=sale_statistics,
        environmental=environmental,
        permit_history=permit_history,
        recommendation=recommendation,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare a property's assessment to similar properties"
    )

    # Property identification (mutually exclusive)
    id_group = parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument(
        "--address",
        type=str,
        help="Property address to analyze (e.g., '1045 LYNNWOOD BLVD')"
    )
    id_group.add_argument(
        "--parid",
        type=str,
        help="Parcel ID to analyze"
    )
    id_group.add_argument(
        "--input-file",
        type=str,
        help="Path to file with list of addresses or ParIDs (one per line)"
    )
    parser.add_argument(
        "--input-type",
        choices=["address", "parid"],
        default="address",
        help="Type of identifiers in input file (default: address)"
    )

    # Comparison criteria overrides
    parser.add_argument(
        "--year-range",
        type=int,
        default=DEFAULT_YEAR_RANGE,
        help=f"Year built range +/- (default: {DEFAULT_YEAR_RANGE})"
    )
    parser.add_argument(
        "--sqft-range",
        type=int,
        default=DEFAULT_SQFT_RANGE_PCT,
        help=f"Square footage range +/- percent (default: {DEFAULT_SQFT_RANGE_PCT})"
    )
    parser.add_argument(
        "--max-comps",
        type=int,
        default=DEFAULT_MAX_COMPARABLES,
        help=f"Maximum comparables to return (default: {DEFAULT_MAX_COMPARABLES})"
    )
    parser.add_argument(
        "--sale-days",
        type=int,
        default=DEFAULT_SALE_DAYS,
        help=f"Only include sales within this many days (default: {DEFAULT_SALE_DAYS})"
    )

    # Output options
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)"
    )

    # BigQuery options
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_BQ_PROJECT,
        help=f"GCP project ID (default: {DEFAULT_BQ_PROJECT})"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=DEFAULT_BQ_DATASET,
        help=f"BigQuery dataset (default: {DEFAULT_BQ_DATASET})"
    )

    args = parser.parse_args()

    # Initialize BigQuery client
    client = bigquery.Client(project=args.project)

    # Handle batch processing from input file
    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
            sys.exit(1)

        identifiers = [line.strip() for line in input_path.read_text().splitlines() if line.strip()]
        if not identifiers:
            print("Error: Input file is empty", file=sys.stderr)
            sys.exit(1)

        print(f"Processing {len(identifiers)} properties from {args.input_file}...", file=sys.stderr)

        results = []
        errors = []

        for i, identifier in enumerate(identifiers, 1):
            print(f"\n[{i}/{len(identifiers)}] Processing: {identifier}", file=sys.stderr)

            try:
                # Look up property
                if args.input_type == "address":
                    matches = lookup_property_by_address(
                        client, identifier, args.project, args.dataset
                    )
                else:
                    matches = lookup_property_by_parid(
                        client, identifier, args.project, args.dataset
                    )

                if not matches:
                    errors.append(f"{identifier}: No property found")
                    continue
                if len(matches) > 1:
                    errors.append(f"{identifier}: Multiple matches ({len(matches)})")
                    continue

                subject = dict_to_subject(matches[0])
                print(f"  Found: {subject.address}", file=sys.stderr)

                # Analyze property
                result = analyze_single_property(
                    client, subject, args, args.project, args.dataset
                )
                results.append(result)
                print(f"  Recommendation: {result.recommendation.recommendation}", file=sys.stderr)

            except Exception as e:
                errors.append(f"{identifier}: {str(e)}")

        # Output results
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"Processed: {len(results)} successful, {len(errors)} errors", file=sys.stderr)

        if errors:
            print("\nErrors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)

        # Format and output
        if args.format == "json":
            output_data = {
                "summary": {
                    "total_processed": len(results),
                    "total_errors": len(errors),
                    "errors": errors,
                },
                "results": [json.loads(format_json_report(r)) for r in results]
            }
            output = json.dumps(output_data, indent=2)
        else:
            output_parts = []
            for result in results:
                output_parts.append(format_text_report(result))
            output = "\n\n".join(output_parts)

            # Add summary
            if len(results) > 1:
                output += "\n\n" + "=" * 80
                output += "\n                         BATCH SUMMARY"
                output += "\n" + "=" * 80
                output += f"\n  Total Properties: {len(results)}"

                strong = sum(1 for r in results if r.recommendation.recommendation == "STRONG_CANDIDATE")
                moderate = sum(1 for r in results if r.recommendation.recommendation == "MODERATE_CANDIDATE")
                review = sum(1 for r in results if r.recommendation.recommendation == "WORTH_REVIEWING")
                fair = sum(1 for r in results if r.recommendation.recommendation == "LIKELY_FAIR")

                output += f"\n  Strong Candidates: {strong}"
                output += f"\n  Moderate Candidates: {moderate}"
                output += f"\n  Worth Reviewing: {review}"
                output += f"\n  Likely Fair: {fair}"

                if errors:
                    output += f"\n  Errors: {len(errors)}"
                output += "\n" + "=" * 80

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"\nReport saved to {output_path}", file=sys.stderr)
        else:
            print(output)

    else:
        # Single property analysis
        print("Looking up property...", file=sys.stderr)

        if args.address:
            matches = lookup_property_by_address(
                client, args.address, args.project, args.dataset
            )
            if not matches:
                print(f"Error: No properties found matching '{args.address}'", file=sys.stderr)
                sys.exit(1)
            if len(matches) > 1:
                print(f"Error: Multiple properties match '{args.address}':", file=sys.stderr)
                print("", file=sys.stderr)
                for m in matches:
                    print(f"  ParID: {m['ParID']:<15} Address: {m['PropAddr']}", file=sys.stderr)
                print("", file=sys.stderr)
                print("Please re-run with --parid to specify the exact property.", file=sys.stderr)
                sys.exit(1)
            subject_row = matches[0]
        else:
            matches = lookup_property_by_parid(
                client, args.parid, args.project, args.dataset
            )
            if not matches:
                print(f"Error: No property found with ParID '{args.parid}'", file=sys.stderr)
                sys.exit(1)
            subject_row = matches[0]

        subject = dict_to_subject(subject_row)
        print(f"Found: {subject.address}", file=sys.stderr)
        print("Finding comparable properties...", file=sys.stderr)

        # Analyze property
        result = analyze_single_property(
            client, subject, args, args.project, args.dataset
        )

        print(f"Found {len(result.comparables)} comparables", file=sys.stderr)

        # Format output
        if args.format == "json":
            output = format_json_report(result)
        else:
            output = format_text_report(result)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"Report saved to {output_path}", file=sys.stderr)
        else:
            print(output)


if __name__ == "__main__":
    main()
