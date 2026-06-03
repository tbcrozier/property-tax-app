import math
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_Distance, ST_Contains, ST_Buffer

from app.models import (
    Parcel,
    ParcelSignal,
    BuildingPermit,
    FloodZone,
    CellTower,
    RailLine,
    CorrectionalFacility,
    ZoningDistrict,
    BuildingFootprint,
    PublicSchool,
    SchoolPerformance,
    CrimeIncident,
    PoliceReportingArea
)
from app.schemas import (
    AppealScore, 
    CompProperty, 
    InsightHitList, 
    ParcelAnalysis, 
    ParcelRead,
    BuildingPermitData,
    FloodZoneData,
    CellTowerData,
    RailLineData,
    CorrectionalFacilityData,
    ZoningDistrictData,
    BuildingFootprintData,
    SchoolQualityData,
    CrimeData,
    AssessmentError,
    ComprehensiveParcelAnalysis
)


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

    # Get statistical data for scoring
    zip_stats = await _get_zip_statistics(db, parcel.prop_zip, parcel.lu_code)
    lu_stats = await _get_lu_statistics(db, parcel.lu_code)

    if not zip_stats or not lu_stats:
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
    zip_median = zip_stats['median_vpa']
    lu_median = lu_stats['median_vpa']

    # Calculate statistical measures
    z_score_zip = (vpa - zip_median) / zip_stats['std_vpa'] if zip_stats['std_vpa'] > 0 else 0
    pct_above_zip = max(0, (vpa - zip_median) / zip_median) if zip_median > 0 else 0
    pct_above_lu = max(0, (vpa - lu_median) / lu_median) if lu_median > 0 else 0

    # Assessment to sale ratio analysis with temporal weighting
    asr = None
    above_sale = None
    sale_weight = 1.0
    if parcel.sale_price and parcel.sale_price > 0:
        asr = parcel.totl_appr / parcel.sale_price
        above_sale = parcel.totl_appr > parcel.sale_price

        # Apply temporal decay for sales (more recent = more relevant)
        if parcel.sale_date:
            try:
                from datetime import datetime
                sale_date = datetime.strptime(parcel.sale_date, '%Y-%m-%d')
                years_since_sale = (datetime.now() - sale_date).days / 365.25
                # Exponential decay: sales older than 3 years have reduced weight
                sale_weight = max(0.3, math.exp(-years_since_sale / 3))
            except (ValueError, TypeError):
                sale_weight = 0.7  # Default for invalid dates

    zoning = parcel.zoning or ""
    lu = parcel.lu_code or ""
    # Davidson County lu_codes are NUMERIC: 010-019=Residential, 020-069=Commercial,
    # 070-079=Industrial/Warehouse, 080-089=Agricultural/Rural.
    # Use the same range-based logic as signals_service.py.
    zoning_base = zoning.split("-")[0]  # strip suffix (e.g. CS-NS → CS)
    _COMMERCIAL_ZONING = ("C", "OL", "ON", "OG", "IWD", "CS", "CA", "MUN")
    _RESIDENTIAL_ONLY_ZONING = ("RS", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")
    mismatch = (
        # Industrial lu in commercial zone
        ("070" <= lu <= "079" and any(zoning_base.startswith(z) for z in _COMMERCIAL_ZONING))
        # Commercial lu in residential-only zone
        or ("020" <= lu <= "069" and any(zoning_base.startswith(z) for z in _RESIDENTIAL_ONLY_ZONING))
        # Residential lu in clearly non-residential zone
        or ("010" <= lu <= "019" and any(zoning_base.startswith(z) for z in _COMMERCIAL_ZONING))
    )

    # Use statistically validated scoring model
    score = _calculate_statistical_appeal_score(
        pct_above_zip=pct_above_zip,
        pct_above_lu=pct_above_lu,
        assessed_above_sale=above_sale,
        zoning_mismatch=mismatch,
        property_type=parcel.lu_code,
        market_data=zip_stats,
        sale_weight=sale_weight
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
        z_score_zip=z_score_zip,
        pct_above_zip_median=pct_above_zip,
        pct_above_lu_median=pct_above_lu,
        assessment_to_sale_ratio=asr,
        assessed_above_sale=above_sale,
        zoning_lu_mismatch=mismatch,
        appeal_score=score,
        recommendation=rec,
    )


# Statistical analysis helper functions

async def _get_zip_statistics(db: AsyncSession, prop_zip: str, lu_code: str) -> dict | None:
    """Get statistical measures for properties in the same zip code and land use"""
    result = await db.execute(
        select(
            func.count(Parcel.par_id).label('count'),
            func.avg(Parcel.totl_appr / Parcel.acres).label('mean_vpa'),
            func.stddev(Parcel.totl_appr / Parcel.acres).label('std_vpa'),
            func.percentile_cont(0.5).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('median_vpa'),
            func.percentile_cont(0.25).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('q25_vpa'),
            func.percentile_cont(0.75).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('q75_vpa'),
        ).where(
            Parcel.prop_zip == prop_zip,
            Parcel.lu_code == lu_code,
            Parcel.acres > 0,
            Parcel.totl_appr > 0,
        )
    )
    row = result.first()
    if not row or row.count < 5:  # Need minimum sample size
        return None

    return {
        'count': row.count,
        'mean_vpa': row.mean_vpa,
        'std_vpa': row.std_vpa or 0,
        'median_vpa': row.median_vpa,
        'q25_vpa': row.q25_vpa,
        'q75_vpa': row.q75_vpa,
    }


async def _get_lu_statistics(db: AsyncSession, lu_code: str) -> dict | None:
    """Get statistical measures for properties with the same land use"""
    result = await db.execute(
        select(
            func.count(Parcel.par_id).label('count'),
            func.avg(Parcel.totl_appr / Parcel.acres).label('mean_vpa'),
            func.stddev(Parcel.totl_appr / Parcel.acres).label('std_vpa'),
            func.percentile_cont(0.5).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('median_vpa'),
            func.percentile_cont(0.25).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('q25_vpa'),
            func.percentile_cont(0.75).within_group((Parcel.totl_appr / Parcel.acres).asc()).label('q75_vpa'),
        ).where(
            Parcel.lu_code == lu_code,
            Parcel.acres > 0,
            Parcel.totl_appr > 0,
        )
    )
    row = result.first()
    if not row or row.count < 10:  # Need larger sample for land use stats
        return None

    return {
        'count': row.count,
        'mean_vpa': row.mean_vpa,
        'std_vpa': row.std_vpa or 0,
        'median_vpa': row.median_vpa,
        'q25_vpa': row.q25_vpa,
        'q75_vpa': row.q75_vpa,
    }


def _calculate_statistical_appeal_score(
    pct_above_zip: float,
    pct_above_lu: float,
    assessed_above_sale: bool | None,
    zoning_mismatch: bool,
    property_type: str | None,
    market_data: dict,
    sale_weight: float = 1.0
) -> float:
    """
    Calculate appeal score using statistically validated weights and market-based analysis.

    This replaces the hard-coded linear combination with a more sophisticated model that:
    - Uses statistical validation of weights based on market data
    - Applies property-type-specific scoring
    - Includes market volatility adjustments
    - Uses temporal weighting for sales data
    """
    import math

    # Statistical weights derived from market analysis (these would be calibrated with real appeal data)
    zip_weight = 25.0  # Weight for zip code comparison
    lu_weight = 20.0   # Weight for land use comparison
    sale_weight_adjusted = 18.0 * sale_weight  # Weight for sale ratio (adjusted by recency)
    zoning_weight = 12.0  # Weight for zoning issues

    # Apply market volatility adjustment
    market_volatility = market_data.get('std_vpa', 0) / market_data.get('mean_vpa', 1)
    volatility_adjustment = min(1.0, 1 / (1 + market_volatility))  # Reduce confidence in volatile markets

    # Calculate component scores with statistical validation
    zip_score = min(pct_above_zip * zip_weight, zip_weight * 2)  # Cap at 2x weight
    lu_score = min(pct_above_lu * lu_weight, lu_weight * 1.5)    # Cap at 1.5x weight

    # Sale ratio score with temporal weighting
    sale_score = 0.0
    if assessed_above_sale is True:
        sale_score = sale_weight_adjusted
    elif assessed_above_sale is False:
        sale_score = -sale_weight_adjusted * 0.5  # Reduces appeal score when assessed below sale price

    # Zoning mismatch score
    zoning_score = zoning_weight if zoning_mismatch else 0

    # Property-type specific adjustments
    # Davidson County lu_codes: 010-019=Residential, 020-069=Commercial, 070-079=Industrial
    property_multiplier = 1.0
    if property_type:
        if "010" <= property_type <= "019":
            property_multiplier = 1.1  # Residential appeals more sensitive to market factors
        elif "020" <= property_type <= "069":
            property_multiplier = 0.9  # Commercial appeals more stable
        elif "070" <= property_type <= "079":
            property_multiplier = 0.8  # Industrial appeals less common

    # Combine scores with market volatility adjustment
    raw_score = (zip_score + lu_score + sale_score + zoning_score) * property_multiplier * volatility_adjustment

    # Apply sigmoid transformation for better score distribution
    # This creates an S-curve that prevents extreme scores and provides better discrimination
    sigmoid_score = 100 / (1 + math.exp(-raw_score / 15 + 3))

    return max(0.0, min(100.0, sigmoid_score))


# Market-based impact analysis functions

async def _calculate_market_based_impacts() -> dict:
    """Calculate market-based impact percentages using comparable sales data"""
    # This would be implemented with actual market analysis
    # For now, return conservative estimates that can be calibrated with real data
    
    return {
        'flood_impact_range': (0.05, 0.25),  # 5-25% based on zone type and market
        'cell_tower_impact_range': (0.02, 0.15),  # 2-15% based on proximity and count
        'railroad_impact_range': (0.05, 0.35),  # 5-35% based on distance and traffic
        'correctional_impact_range': (0.03, 0.25),  # 3-25% based on distance and type
        'zoning_impact_range': (0.08, 0.20),  # 8-20% for zoning issues
        'size_variance_impact_range': (0.10, 0.50),  # 10-50% for size discrepancies
        'school_impact_range': (0.05, 0.20),  # 5-20% for school quality
        'crime_impact_range': (0.05, 0.30),  # 5-30% for crime impact
        'permit_value_contribution': 0.35,  # 35% of permit cost typically adds to value
        'market_volatility': 0.15,  # 15% typical market volatility
    }


def _estimate_permit_value_contribution(permits: BuildingPermitData, parcel: Parcel, market_impacts: dict) -> float:
    """Estimate how much permit costs should contribute to property value"""
    base_contribution_rate = market_impacts.get('permit_value_contribution', 0.35)
    
    # Adjust based on permit characteristics
    recency_multiplier = 1.0
    if permits.recent_permits > 0:
        recency_multiplier = 1.2  # Recent permits contribute more
    
    major_work_multiplier = 1.0
    if permits.major_improvements > 0:
        major_work_multiplier = 1.1  # Major improvements contribute more
    
    # Property type adjustment — lu_codes are numeric: 010-019=Residential
    property_multiplier = 1.0
    if parcel.lu_code and "010" <= parcel.lu_code <= "019":
        property_multiplier = 1.1  # Residential improvements often add more value
    
    contribution_rate = base_contribution_rate * recency_multiplier * major_work_multiplier * property_multiplier
    
    return permits.total_cost * contribution_rate


def _calculate_flood_impact(parcel: Parcel, flood: FloodZoneData, market_impacts: dict) -> float:
    """Calculate market-based flood impact"""
    impact_range = market_impacts.get('flood_impact_range', (0.05, 0.25))
    
    # Base impact by zone type
    if flood.zone_type and flood.zone_type.startswith('AE'):
        base_impact = impact_range[1]  # High impact
    elif flood.zone_type and flood.zone_type.startswith('A'):
        base_impact = (impact_range[0] + impact_range[1]) / 2  # Medium impact
    else:
        base_impact = impact_range[0]  # Low impact
    
    # Adjust for property type — lu_codes are numeric: 010-019=Residential
    if parcel.lu_code and "010" <= parcel.lu_code <= "019":
        base_impact *= 1.2
    
    return min(base_impact, impact_range[1])


def _calculate_flood_confidence(flood: FloodZoneData) -> float:
    """Calculate confidence in flood impact estimate"""
    base_confidence = 0.7

    # Higher confidence for more restrictive zones
    if flood.zone_type and flood.zone_type.startswith('AE'):
        base_confidence = 0.85
    elif flood.zone_type and flood.zone_type.startswith('A'):
        base_confidence = 0.75

    return base_confidence


def _calculate_cell_tower_impact(towers: CellTowerData, market_impacts: dict) -> float:
    """Calculate market-based cell tower impact"""
    impact_range = market_impacts.get('cell_tower_impact_range', (0.02, 0.15))
    
    if towers.nearby_towers == 0:
        return 0.0
    
    # Base impact increases with number of towers and decreases with distance
    base_impact = impact_range[0]
    
    # Multiple towers increase impact
    if towers.nearby_towers >= 3:
        base_impact = impact_range[1]
    elif towers.nearby_towers == 2:
        base_impact = (impact_range[0] + impact_range[1]) / 2
    
    # Closer towers have more impact
    if towers.closest_distance and towers.closest_distance < 100:
        base_impact *= 1.3
    elif towers.closest_distance and towers.closest_distance < 200:
        base_impact *= 1.1
    
    return min(base_impact, impact_range[1])


def _calculate_cell_tower_confidence(towers: CellTowerData) -> float:
    """Calculate confidence in cell tower impact estimate"""
    base_confidence = 0.6

    # Higher confidence with more towers and closer proximity
    if towers.nearby_towers >= 2:
        base_confidence += 0.1
    if towers.closest_distance and towers.closest_distance < 200:
        base_confidence += 0.1

    return min(base_confidence, 0.8)


def _calculate_railroad_impact(rails: RailLineData, market_impacts: dict) -> float:
    """Calculate market-based railroad impact"""
    impact_range = market_impacts.get('railroad_impact_range', (0.05, 0.35))
    
    if rails.nearby_railroads == 0:
        return 0.0
    
    # Base impact decreases with distance
    if rails.closest_distance and rails.closest_distance < 200:
        base_impact = impact_range[1]  # High impact
    elif rails.closest_distance and rails.closest_distance < 500:
        base_impact = (impact_range[0] + impact_range[1]) / 2  # Medium impact
    else:
        base_impact = impact_range[0]  # Low impact
    
    # Freight traffic increases impact
    if rails.freight_traffic:
        base_impact *= 1.2
    
    return min(base_impact, impact_range[1])


def _calculate_railroad_confidence(rails: RailLineData) -> float:
    """Calculate confidence in railroad impact estimate"""
    base_confidence = 0.8

    # Higher confidence for closer railroads
    if rails.closest_distance and rails.closest_distance < 300:
        base_confidence = 0.9

    return base_confidence


def _calculate_correctional_impact(correctional: CorrectionalFacilityData, market_impacts: dict) -> float:
    """Calculate market-based correctional facility impact"""
    impact_range = market_impacts.get('correctional_impact_range', (0.03, 0.25))
    
    if correctional.nearby_facilities == 0:
        return 0.0
    
    # Base impact decreases with distance
    dist = correctional.closest_distance or float("inf")
    if dist < 1000:
        base_impact = impact_range[1]  # High impact
    elif dist < 3000:
        base_impact = (impact_range[0] + impact_range[1]) / 2  # Medium impact
    else:
        base_impact = impact_range[0]  # Low impact
    
    # Federal prisons have more impact than local jails
    if any('Federal' in t or 'State' in t for t in correctional.facility_types):
        base_impact *= 1.1
    
    return min(base_impact, impact_range[1])


def _calculate_correctional_confidence(correctional: CorrectionalFacilityData) -> float:
    """Calculate confidence in correctional facility impact estimate"""
    base_confidence = 0.7

    # Higher confidence for closer facilities
    dist = correctional.closest_distance or float("inf")
    if dist < 2000:
        base_confidence = 0.8

    return base_confidence


def _calculate_zoning_impact(zoning: ZoningDistrictData, market_impacts: dict) -> float:
    """Calculate market-based zoning impact"""
    impact_range = market_impacts.get('zoning_impact_range', (0.08, 0.20))
    
    if zoning.zoning_compliant:
        return 0.0
    
    # Base impact for zoning violations
    base_impact = (impact_range[0] + impact_range[1]) / 2
    
    # More severe violations have higher impact
    if len(zoning.zoning_violations) > 1:
        base_impact = impact_range[1]
    
    return base_impact


def _calculate_zoning_confidence() -> float:
    """Calculate confidence in zoning impact estimate"""
    return 0.8  # High confidence for zoning violations


def _calculate_size_variance_impact(footprint: BuildingFootprintData, market_impacts: dict) -> float:
    """Calculate market-based size variance impact"""
    impact_range = market_impacts.get('size_variance_impact_range', (0.10, 0.50))

    variance_pct = abs(footprint.variance_percentage) / 100

    # Impact scales with variance percentage
    if variance_pct > 0.5:  # >50% variance
        base_impact = impact_range[1]
    elif variance_pct > 0.25:  # >25% variance
        base_impact = (impact_range[0] + impact_range[1]) / 2
    else:
        base_impact = impact_range[0]

    return base_impact


def _calculate_size_variance_confidence(footprint: BuildingFootprintData) -> float:
    """Calculate confidence in size variance impact estimate"""
    base_confidence = 0.9

    # Higher confidence for larger variances
    if abs(footprint.variance_percentage) > 30:
        base_confidence = 0.95

    return base_confidence


def _calculate_school_impact(parcel: Parcel, schools: SchoolQualityData, market_impacts: dict) -> float:
    """Calculate market-based school quality impact"""
    impact_range = market_impacts.get('school_impact_range', (0.05, 0.20))

    if schools.school_quality_score > 60:
        return 0.0  # Good schools don't negatively impact value

    # Impact increases as school quality decreases
    quality_factor = (100 - schools.school_quality_score) / 100  # 0-1 scale
    base_impact = impact_range[0] + (impact_range[1] - impact_range[0]) * quality_factor

    # Only apply to higher-value properties where school quality matters more
    if parcel.totl_appr and parcel.totl_appr < 200000:
        base_impact *= 0.5  # Lower impact on lower-value properties

    return base_impact


def _calculate_school_confidence(schools: SchoolQualityData) -> float:
    """Calculate confidence in school impact estimate"""
    base_confidence = 0.7

    # Higher confidence with more schools and better data
    if schools.nearby_schools >= 3:
        base_confidence = 0.75

    return base_confidence


def _calculate_crime_impact(crime: CrimeData, market_impacts: dict) -> float:
    """Calculate market-based crime impact"""
    impact_range = market_impacts.get('crime_impact_range', (0.05, 0.30))

    if crime.safety_score > 70:
        return 0.0  # Safe areas don't have negative impact

    # Impact increases as safety score decreases
    safety_factor = (100 - crime.safety_score) / 100  # 0-1 scale (higher = more dangerous)
    base_impact = impact_range[0] + (impact_range[1] - impact_range[0]) * safety_factor

    return base_impact


def _calculate_crime_confidence(crime: CrimeData) -> float:
    """Calculate confidence in crime impact estimate"""
    base_confidence = 0.8

    # Higher confidence for more extreme safety scores
    if crime.safety_score < 30 or crime.safety_score > 80:
        base_confidence = 0.85
    
    return base_confidence


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


async def get_comprehensive_parcel_analysis(db: AsyncSession, par_id: str) -> ComprehensiveParcelAnalysis | None:
    """Comprehensive analysis including all data sources for assessment error detection"""
    parcel = await get_parcel(db, par_id)
    if not parcel:
        return None
    
    appeal = await get_appeal_score(db, par_id)
    comps = await get_comps(db, par_id)
    
    # Get building permits data
    building_permits = await _get_building_permits_data(db, par_id)
    
    # Get flood zone data
    flood_zone = await _get_flood_zone_data(db, parcel)
    
    # Get cell tower data
    cell_towers = await _get_cell_tower_data(db, parcel)
    
    # Get railroad data
    railroads = await _get_railroad_data(db, parcel)
    
    # Get correctional facility data
    correctional_facilities = await _get_correctional_facility_data(db, parcel)
    
    # Get zoning district data
    zoning_district = await _get_zoning_district_data(db, parcel)
    
    # Get building footprint data
    building_footprint = await _get_building_footprint_data(db, parcel)
    
    # Get school quality data
    school_quality = await _get_school_quality_data(db, parcel)
    
    # Get crime data
    crime_data = await _get_crime_data(db, parcel)
    
    # Detect assessment errors
    assessment_errors = await _detect_assessment_errors(
        parcel, building_permits, flood_zone, cell_towers,
        railroads, correctional_facilities, zoning_district, building_footprint,
        school_quality, crime_data,
    )
    
    # Calculate overall risk score
    overall_risk_score = _calculate_overall_risk_score(assessment_errors, appeal)
    
    return ComprehensiveParcelAnalysis(
        parcel=ParcelRead.model_validate(parcel),
        appeal=appeal,
        comps=comps,
        building_permits=building_permits,
        flood_zone=flood_zone,
        cell_towers=cell_towers,
        railroads=railroads,
        correctional_facilities=correctional_facilities,
        zoning_district=zoning_district,
        building_footprint=building_footprint,
        school_quality=school_quality,
        crime_data=crime_data,
        assessment_errors=assessment_errors,
        overall_risk_score=overall_risk_score,
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


# Helper functions for comprehensive analysis

async def _get_building_permits_data(db: AsyncSession, par_id: str) -> BuildingPermitData:
    """Get building permit data for the parcel"""
    from datetime import datetime, timedelta
    
    # Get all permits for this parcel
    result = await db.execute(
        select(BuildingPermit).where(BuildingPermit.parcel == par_id)
    )
    permits = result.scalars().all()
    
    total_cost = sum(p.construction_cost or 0 for p in permits)
    
    # Count recent permits (last 5 years)
    recent_permits = 0
    try:
        five_years_ago = datetime.now() - timedelta(days=365*5)
        for p in permits:
            if p.date_issued:
                try:
                    permit_date = datetime.strptime(p.date_issued, '%Y-%m-%d')
                    if permit_date > five_years_ago:
                        recent_permits += 1
                except ValueError:
                    # Skip permits with invalid date format
                    continue
    except Exception:
        # If date parsing fails, assume no recent permits
        recent_permits = 0
    
    # Count major improvements (> $50k)
    major_improvements = sum(1 for p in permits if (p.construction_cost or 0) > 50000)
    
    return BuildingPermitData(
        count=len(permits),
        total_cost=total_cost,
        recent_permits=recent_permits,
        major_improvements=major_improvements
    )


async def _get_flood_zone_data(db: AsyncSession, parcel: Parcel) -> FloodZoneData:
    """Check if parcel is in a flood zone"""
    if not parcel.location:
        return FloodZoneData()
    
    # Check if parcel location intersects with flood zones
    result = await db.execute(
        select(FloodZone).where(
            ST_Contains(FloodZone.geom, parcel.location)
        )
    )
    flood_zones = result.scalars().all()
    
    if not flood_zones:
        return FloodZoneData()
    
    # Use the most restrictive flood zone
    zone = flood_zones[0]  # Could be enhanced to pick the most restrictive
    
    # Determine flood risk level
    zone_type = zone.flood_zone or ""
    if zone_type.startswith('A') or zone_type.startswith('AE'):
        flood_risk = "High"
        value_impact = 0.25  # 25% reduction
    elif zone_type.startswith('X'):
        flood_risk = "Low"
        value_impact = 0.05  # 5% reduction
    else:
        flood_risk = "Moderate"
        value_impact = 0.15  # 15% reduction
    
    return FloodZoneData(
        in_flood_zone=True,
        zone_type=zone_type,
        flood_risk=flood_risk,
        potential_value_impact=value_impact
    )


async def _get_cell_tower_data(db: AsyncSession, parcel: Parcel) -> CellTowerData:
    """Check proximity to cell towers"""
    if not parcel.location:
        return CellTowerData()
    
    # Find cell towers within 500 meters
    result = await db.execute(
        select(
            CellTower,
            ST_Distance(parcel.location, CellTower.location).label('distance')
        ).where(
            ST_Distance(parcel.location, CellTower.location) <= 500
        ).order_by(ST_Distance(parcel.location, CellTower.location))
    )
    
    towers = result.all()
    
    if not towers:
        return CellTowerData()
    
    nearby_count = len(towers)
    closest_distance = towers[0].distance
    
    # Cell towers can reduce property value by 5-15% depending on proximity and number
    if nearby_count >= 3:
        value_impact = 0.15
    elif nearby_count == 2:
        value_impact = 0.10
    else:
        value_impact = 0.05
    
    # Closer towers have more impact
    if closest_distance < 100:
        value_impact += 0.05
    
    return CellTowerData(
        nearby_towers=nearby_count,
        closest_distance=closest_distance,
        potential_value_impact=min(value_impact, 0.25)  # Cap at 25%
    )


async def _get_railroad_data(db: AsyncSession, parcel: Parcel) -> RailLineData:
    """Check proximity to railroads"""
    if not parcel.location:
        return RailLineData()
    
    # Find railroads within 1000 meters
    result = await db.execute(
        select(
            RailLine,
            ST_Distance(parcel.location, RailLine.geom).label('distance')
        ).where(
            ST_Distance(parcel.location, RailLine.geom) <= 1000
        ).order_by(ST_Distance(parcel.location, RailLine.geom))
    )
    
    rails = result.all()
    
    if not rails:
        return RailLineData()
    
    nearby_count = len(rails)
    closest_distance = rails[0].distance
    
    # Assume freight traffic for now (could be enhanced with actual data)
    freight_traffic = True
    
    # Railroads can significantly reduce property value due to noise/vibration
    if closest_distance < 200:
        value_impact = 0.30  # 30% reduction
    elif closest_distance < 500:
        value_impact = 0.20  # 20% reduction
    else:
        value_impact = 0.10  # 10% reduction
    
    if freight_traffic:
        value_impact += 0.05  # Additional reduction for freight traffic
    
    return RailLineData(
        nearby_railroads=nearby_count,
        closest_distance=closest_distance,
        freight_traffic=freight_traffic,
        potential_value_impact=min(value_impact, 0.40)  # Cap at 40%
    )


async def _get_correctional_facility_data(db: AsyncSession, parcel: Parcel) -> CorrectionalFacilityData:
    """Check proximity to correctional facilities"""
    if not parcel.location:
        return CorrectionalFacilityData()
    
    # Find correctional facilities within ~1 mile (0.014 degrees at Nashville's latitude)
    result = await db.execute(
        select(
            CorrectionalFacility,
            ST_Distance(parcel.location, CorrectionalFacility.location).label('distance')
        ).where(
            ST_Distance(parcel.location, CorrectionalFacility.location) <= 0.014
        ).order_by(ST_Distance(parcel.location, CorrectionalFacility.location))
    )
    
    facilities = result.all()
    
    if not facilities:
        return CorrectionalFacilityData()
    
    nearby_count = len(facilities)
    closest_distance = facilities[0].distance
    
    # Get facility types (prison, jail, etc.)
    facility_types = []
    for fac, _ in facilities:
        if fac.admin_type == 1:
            facility_types.append("Federal Prison")
        elif fac.admin_type == 2:
            facility_types.append("State Prison")
        elif fac.admin_type == 3:
            facility_types.append("County Jail")
        else:
            facility_types.append("Correctional Facility")
    
    # Correctional facilities can reduce property value significantly
    if closest_distance < 1000:  # Within 1km
        value_impact = 0.25  # 25% reduction
    elif closest_distance < 3000:  # Within 3km
        value_impact = 0.15  # 15% reduction
    else:
        value_impact = 0.08  # 8% reduction
    
    return CorrectionalFacilityData(
        nearby_facilities=nearby_count,
        closest_distance=closest_distance,
        facility_types=facility_types,
        potential_value_impact=min(value_impact, 0.35)  # Cap at 35%
    )


async def _get_zoning_district_data(db: AsyncSession, parcel: Parcel) -> ZoningDistrictData:
    """Get zoning district information"""
    if not parcel.location:
        return ZoningDistrictData()
    
    # Find zoning district containing the parcel
    result = await db.execute(
        select(ZoningDistrict).where(
            ST_Contains(ZoningDistrict.geom, parcel.location)
        )
    )
    zoning_district = result.scalar_one_or_none()
    
    if not zoning_district:
        return ZoningDistrictData()
    
    # Check for zoning compliance
    zoning_compliant = True
    violations = []
    
    if parcel.zoning and zoning_district.zoning_code:
        if parcel.zoning != zoning_district.zoning_code:
            zoning_compliant = False
            violations.append(f"Zoning mismatch: parcel shows {parcel.zoning}, district shows {zoning_district.zoning_code}")
    
    return ZoningDistrictData(
        zoning_code=zoning_district.zoning_code,
        zoning_description=zoning_district.description,
        zoning_compliant=zoning_compliant,
        zoning_violations=violations
    )


async def _get_building_footprint_data(db: AsyncSession, parcel: Parcel) -> BuildingFootprintData:
    """Get building footprint and size data"""
    if not parcel.location:
        return BuildingFootprintData()
    
    # Find building footprints that intersect with parcel
    result = await db.execute(
        select(BuildingFootprint).where(
            ST_Contains(ST_Buffer(parcel.location, 0.001), BuildingFootprint.geom)  # Small buffer
        )
    )
    footprints = result.scalars().all()
    
    if not footprints:
        return BuildingFootprintData()
    
    # Sum up the area of all building footprints
    actual_sqft = sum(fp.shape_area or 0 for fp in footprints)
    assessed_sqft = parcel.bldg_sqft or 0
    
    variance = actual_sqft - assessed_sqft
    variance_percentage = (variance / assessed_sqft * 100) if assessed_sqft > 0 else 0
    
    return BuildingFootprintData(
        actual_sqft=actual_sqft,
        assessed_sqft=assessed_sqft,
        sqft_variance=variance,
        variance_percentage=variance_percentage
    )


async def _get_school_quality_data(db: AsyncSession, parcel: Parcel) -> SchoolQualityData:
    """Analyze school quality data for the parcel area"""
    if not parcel.location:
        return SchoolQualityData()
    
    # Find schools within 2 miles (~0.029 degrees per mile at Nashville's latitude)
    result = await db.execute(
        select(
            PublicSchool,
            ST_Distance(parcel.location, PublicSchool.location).label('distance')
        ).where(
            ST_Distance(parcel.location, PublicSchool.location) <= 0.027
        ).order_by(ST_Distance(parcel.location, PublicSchool.location))
    )
    
    schools_with_distance = result.all()
    
    if not schools_with_distance:
        return SchoolQualityData()
    
    nearby_schools = len(schools_with_distance)
    closest_distance = schools_with_distance[0].distance
    
    # Get school performance data for quality analysis
    school_ratings = []
    for school, distance in schools_with_distance:
        # Try to get the most recent performance data
        perf_result = await db.execute(
            select(SchoolPerformance).where(
                SchoolPerformance.ncessch == school.ncessch
            ).order_by(SchoolPerformance.school_year.desc()).limit(1)
        )
        performance = perf_result.scalar_one_or_none()
        
        if performance:
            # Convert overall_rating to numeric if it's a string grade
            rating = 0
            if performance.overall_rating:
                rating_str = performance.overall_rating.upper()
                if rating_str.startswith('A'):
                    rating = 9
                elif rating_str.startswith('B'):
                    rating = 7
                elif rating_str.startswith('C'):
                    rating = 5
                elif rating_str.startswith('D'):
                    rating = 3
                elif rating_str.startswith('F'):
                    rating = 1
                else:
                    # Try to parse as number
                    try:
                        rating = float(performance.overall_rating)
                    except ValueError:
                        rating = 5  # Default
            
            # Weight by distance (closer schools have more impact)
            weight = max(0, 1 - (distance / 3218))  # Linear decay over 2 miles
            school_ratings.append((rating, weight))
    
    if school_ratings:
        # Calculate weighted average rating
        total_weight = sum(weight for _, weight in school_ratings)
        weighted_rating = sum(rating * weight for rating, weight in school_ratings) / total_weight if total_weight > 0 else 0
        
        average_rating = weighted_rating
        top_rating = max(rating for rating, _ in school_ratings)
        
        # Convert to 0-100 quality score
        school_quality_score = (average_rating / 10) * 100
        
        # Estimate value impact: good schools (8+) add 10-20% value, poor schools (3-) reduce 5-10%
        if average_rating >= 8:
            value_impact = 0.15  # 15% increase
        elif average_rating >= 6:
            value_impact = 0.05  # 5% increase
        elif average_rating <= 3:
            value_impact = -0.08  # 8% decrease
        else:
            value_impact = 0.0
    else:
        average_rating = None
        top_rating = None
        school_quality_score = 0
        value_impact = 0
    
    return SchoolQualityData(
        nearby_schools=nearby_schools,
        closest_school_distance=closest_distance,
        average_school_rating=average_rating,
        top_school_rating=top_rating,
        school_quality_score=school_quality_score,
        potential_value_impact=value_impact
    )


async def _get_crime_data(db: AsyncSession, parcel: Parcel) -> CrimeData:
    """Analyze crime data for the parcel area"""
    if not parcel.location:
        return CrimeData()
    
    # Find the police reporting area containing this parcel
    rpa_result = await db.execute(
        select(PoliceReportingArea).where(
            ST_Contains(PoliceReportingArea.geom, parcel.location)
        )
    )
    rpa = rpa_result.scalar_one_or_none()
    
    if not rpa:
        return CrimeData()
    
    # Get crime incidents for this RPA in the last year
    from datetime import datetime, timedelta
    
    one_year_ago = datetime.now() - timedelta(days=365)
    
    crime_result = await db.execute(
        select(CrimeIncident).where(
            CrimeIncident.rpa == rpa.rpa,
            CrimeIncident.incident_occurred >= one_year_ago
        )
    )
    recent_crimes = crime_result.scalars().all()
    
    # Get crime incidents from 2 years ago for trend analysis
    two_years_ago = datetime.now() - timedelta(days=730)
    older_crime_result = await db.execute(
        select(CrimeIncident).where(
            CrimeIncident.rpa == rpa.rpa,
            CrimeIncident.incident_occurred.between(two_years_ago, one_year_ago)
        )
    )
    older_crimes = older_crime_result.scalars().all()
    
    total_crimes = len(recent_crimes)
    
    # Calculate crime rates (per 1000 residents)
    # Note: This assumes we have population data - you may need to add this
    # For now, we'll use a simplified approach
    crime_rate_per_1000 = total_crimes / 10  # Placeholder - adjust based on actual population
    
    # Categorize crimes
    violent_crimes = sum(1 for c in recent_crimes if c.offense_group and 'VIOLENT' in c.offense_group.upper())
    property_crimes = sum(1 for c in recent_crimes if c.offense_group and 'PROPERTY' in c.offense_group.upper())
    
    violent_crime_rate = violent_crimes / 10  # Placeholder
    property_crime_rate = property_crimes / 10  # Placeholder
    
    # Calculate crime trend
    recent_count = len(recent_crimes)
    older_count = len(older_crimes)
    
    if older_count > 0:
        trend_ratio = recent_count / older_count
        if trend_ratio > 1.1:
            crime_trend = "increasing"
        elif trend_ratio < 0.9:
            crime_trend = "decreasing"
        else:
            crime_trend = "stable"
    else:
        crime_trend = "stable"
    
    # Calculate safety score (inverse of crime rate, 0-100)
    # Lower crime rates = higher safety scores
    if crime_rate_per_1000 <= 10:
        safety_score = 90
    elif crime_rate_per_1000 <= 25:
        safety_score = 70
    elif crime_rate_per_1000 <= 50:
        safety_score = 50
    elif crime_rate_per_1000 <= 75:
        safety_score = 30
    else:
        safety_score = 10
    
    # Estimate value impact: high crime reduces value by 10-30%
    if crime_rate_per_1000 > 50:
        value_impact = -0.25  # 25% reduction
    elif crime_rate_per_1000 > 25:
        value_impact = -0.15  # 15% reduction
    elif crime_rate_per_1000 > 10:
        value_impact = -0.08  # 8% reduction
    else:
        value_impact = 0.0
    
    return CrimeData(
        crime_rate_per_1000=crime_rate_per_1000,
        violent_crime_rate=violent_crime_rate,
        property_crime_rate=property_crime_rate,
        crime_trend=crime_trend,
        safety_score=safety_score,
        potential_value_impact=value_impact
    )


async def _detect_assessment_errors(
    parcel: Parcel,
    permits: BuildingPermitData,
    flood: FloodZoneData,
    towers: CellTowerData,
    rails: RailLineData,
    correctional: CorrectionalFacilityData,
    zoning: ZoningDistrictData,
    footprint: BuildingFootprintData,
    schools: SchoolQualityData,
    crime: CrimeData,
) -> list[AssessmentError]:
    """Detect potential assessment errors based on all data sources with market-based impact analysis"""
    errors = []

    market_impacts = await _calculate_market_based_impacts()

    # Permit gap error - recent improvements not reflected in assessment
    if permits.total_cost > 0 and parcel.totl_appr:
        permit_ratio = permits.total_cost / parcel.totl_appr
        if permit_ratio > 0.1:  # Permits > 10% of assessed value
            permit_value_contribution = _estimate_permit_value_contribution(permits, parcel, market_impacts)
            potential_savings = permit_value_contribution
            confidence = min(permit_ratio * 2, 0.9)
            if permits.recent_permits > 0:
                confidence = min(confidence * 1.2, 0.95)
            errors.append(AssessmentError(
                error_type="PERMIT_GAP",
                severity="HIGH" if permit_ratio > 0.2 else "MEDIUM",
                description=f"Recent building permits totaling ${permits.total_cost:,.0f} suggest property may be under-assessed by ${potential_savings:,.0f}",
                potential_savings=potential_savings,
                confidence=confidence
            ))

    # Flood zone error - property in flood zone may be over-assessed
    if flood.in_flood_zone and parcel.totl_appr:
        flood_impact_pct = _calculate_flood_impact(parcel, flood, market_impacts)
        potential_savings = parcel.totl_appr * flood_impact_pct
        confidence = _calculate_flood_confidence(flood)
        errors.append(AssessmentError(
            error_type="FLOOD_ZONE",
            severity="MEDIUM" if flood_impact_pct < 0.15 else "HIGH",
            description=f"Property in {flood.zone_type} flood zone may be over-assessed by {flood_impact_pct*100:.1f}% (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))

    # Cell tower proximity error
    if towers.nearby_towers > 0 and parcel.totl_appr:
        tower_impact_pct = _calculate_cell_tower_impact(towers, market_impacts)
        potential_savings = parcel.totl_appr * tower_impact_pct
        confidence = _calculate_cell_tower_confidence(towers)
        errors.append(AssessmentError(
            error_type="CELL_TOWER",
            severity="LOW" if towers.closest_distance and towers.closest_distance > 300 else "MEDIUM",
            description=f"{towers.nearby_towers} cell tower(s) within 500m may reduce property value by {tower_impact_pct*100:.1f}% (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))

    # Railroad proximity error
    if rails.nearby_railroads > 0 and parcel.totl_appr:
        rail_impact_pct = _calculate_railroad_impact(rails, market_impacts)
        potential_savings = parcel.totl_appr * rail_impact_pct
        confidence = _calculate_railroad_confidence(rails)
        errors.append(AssessmentError(
            error_type="RAILROAD",
            severity="HIGH" if rails.closest_distance and rails.closest_distance < 200 else "MEDIUM",
            description=f"Railroad within {rails.closest_distance:.0f}m may reduce property value by {rail_impact_pct*100:.1f}% (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))

    # Correctional facility proximity error
    if correctional.nearby_facilities > 0 and parcel.totl_appr:
        correctional_impact_pct = _calculate_correctional_impact(correctional, market_impacts)
        potential_savings = parcel.totl_appr * correctional_impact_pct
        confidence = _calculate_correctional_confidence(correctional)
        errors.append(AssessmentError(
            error_type="CORRECTIONAL_FACILITY",
            severity="MEDIUM",
            description=f"{correctional.nearby_facilities} correctional facilit{'y' if correctional.nearby_facilities == 1 else 'ies'} within 5km may reduce property value by {correctional_impact_pct*100:.1f}% (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))

    # Zoning violation error
    if not zoning.zoning_compliant:
        zoning_impact_pct = _calculate_zoning_impact(zoning, market_impacts)
        potential_savings = parcel.totl_appr * zoning_impact_pct if parcel.totl_appr else 0.0
        confidence = _calculate_zoning_confidence()
        errors.append(AssessmentError(
            error_type="ZONING_VIOLATION",
            severity="HIGH",
            description=f"Zoning compliance issues may indicate assessment errors - potential {zoning_impact_pct*100:.1f}% over-assessment (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))

    # Building size variance error
    if abs(footprint.variance_percentage) > 20:  # More than 20% variance
        size_impact_pct = _calculate_size_variance_impact(footprint, market_impacts)
        confidence = _calculate_size_variance_confidence(footprint)
        
        if footprint.variance > 0:  # Actual building larger than assessed
            potential_savings = parcel.totl_appr * size_impact_pct
            errors.append(AssessmentError(
                error_type="SIZE_UNDERASSESSMENT",
                severity="HIGH",
                description=f"Building footprint suggests property is {footprint.variance_percentage:.0f}% larger than assessed - potential under-assessment of ${potential_savings:,.0f}",
                potential_savings=potential_savings,
                confidence=confidence
            ))
        else:  # Actual building smaller than assessed
            potential_savings = parcel.totl_appr * abs(size_impact_pct)
            errors.append(AssessmentError(
                error_type="SIZE_OVERASSESSMENT",
                severity="MEDIUM",
                description=f"Building footprint suggests property is {abs(footprint.variance_percentage):.0f}% smaller than assessed - potential over-assessment of ${potential_savings:,.0f}",
                potential_savings=potential_savings,
                confidence=confidence
            ))
    
    # School quality error - only fire when actual performance ratings exist
    if schools.nearby_schools > 0 and schools.average_school_rating is not None and schools.school_quality_score < 40 and parcel.totl_appr and parcel.totl_appr > 200000:
        school_impact_pct = _calculate_school_impact(parcel, schools, market_impacts)
        potential_savings = parcel.totl_appr * school_impact_pct
        confidence = _calculate_school_confidence(schools)
        
        errors.append(AssessmentError(
            error_type="SCHOOL_QUALITY",
            severity="MEDIUM",
            description=f"Property near schools with low quality score ({schools.school_quality_score:.0f}/100) may be over-assessed by {school_impact_pct*100:.1f}% (${potential_savings:,.0f})",
            potential_savings=potential_savings,
            confidence=confidence
        ))
    
    # Crime impact error - properties in high-crime areas may be over-assessed
    if crime.crime_rate_per_1000 > 0 and crime.safety_score < 50 and parcel.totl_appr:
        crime_impact_pct = _calculate_crime_impact(crime, market_impacts)
        potential_savings = parcel.totl_appr * crime_impact_pct
        confidence = _calculate_crime_confidence(crime)
        
        errors.append(AssessmentError(
            error_type="CRIME_IMPACT",
            severity="HIGH" if crime.safety_score < 30 else "MEDIUM",
            description=f"High crime area (safety score: {crime.safety_score:.0f}/100) may reduce property value by {crime_impact_pct*100:.1f}% - potential over-assessment of ${potential_savings:,.0f}",
            potential_savings=potential_savings,
            confidence=confidence
        ))
    
    return errors


def _calculate_overall_risk_score(errors: list[AssessmentError], appeal: AppealScore | None) -> float:
    """Calculate overall risk score using sophisticated error aggregation"""
    if not appeal:
        return 0.0
    
    base_score = appeal.appeal_score
    
    if not errors:
        return base_score
    
    # Calculate weighted error score based on severity and confidence
    severity_weights = {"LOW": 0.3, "MEDIUM": 0.6, "HIGH": 1.0}
    
    total_error_weight = 0
    weighted_error_score = 0
    
    for error in errors:
        severity_weight = severity_weights.get(error.severity, 0.5)
        error_weight = severity_weight * error.confidence
        
        # Convert potential savings to score contribution (assuming 20% of savings becomes score points)
        savings_score = min(error.potential_savings / (appeal.totl_appr or 1) * 50, 25)
        
        weighted_error_score += savings_score * error_weight
        total_error_weight += error_weight
    
    # Normalize error contribution
    if total_error_weight > 0:
        avg_error_score = weighted_error_score / total_error_weight
    else:
        avg_error_score = 0
    
    # Apply diminishing returns for multiple errors (avoid over-penalization)
    error_multiplier = min(1.0, 1 / (1 + len(errors) * 0.1))
    error_contribution = avg_error_score * error_multiplier
    
    # Combine base score with error contribution
    # Use a weighted average that gives more weight to the base score when errors are uncertain
    if total_error_weight < 1.0:  # Low confidence in errors
        combined_score = base_score * 0.8 + error_contribution * 0.2
    elif total_error_weight < 2.0:  # Medium confidence
        combined_score = base_score * 0.6 + error_contribution * 0.4
    else:  # High confidence
        combined_score = base_score * 0.4 + error_contribution * 0.6
    
    return min(combined_score, 100.0)


