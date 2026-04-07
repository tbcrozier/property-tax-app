#!/usr/bin/env python3
"""
Download and load FEMA NFHL Flood Hazard Area data to BigQuery for Davidson County, TN.
Data source: FEMA National Flood Hazard Layer (NFHL) via ArcGIS MapServer
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from pathlib import Path
import argparse
from datetime import datetime, timezone
import time

# FEMA NFHL ArcGIS MapServer endpoint for Flood Hazard Areas (S_FLD_HAZ_AR)
# Layer 28 is "Flood Hazard Zones" (polygon layer)
NFHL_BASE_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
FLOOD_HAZARD_LAYER = 28  # S_FLD_HAZ_AR layer
FLOOD_HAZARD_URL = f"{NFHL_BASE_URL}/{FLOOD_HAZARD_LAYER}/query"
LAYER_INFO_URL = f"{NFHL_BASE_URL}/{FLOOD_HAZARD_LAYER}"

# Davidson County, TN FIPS and DFIRM prefix
# DFIRM IDs for Davidson County start with "47037"
DAVIDSON_COUNTY_FIPS = "47037"

# BigQuery destination
DEFAULT_BQ_TABLE = "public-data-dev.property_tax.fema_floodzone"


def create_session():
    """Create a requests session with retry logic and proper headers."""
    session = requests.Session()

    # Retry strategy with exponential backoff
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Headers that help with government APIs
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PropertyTaxAnalysis/1.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    })

    return session


def get_layer_info():
    """Fetch the layer metadata to understand available fields."""
    session = create_session()
    params = {"f": "json"}

    for attempt in range(3):
        try:
            response = session.get(LAYER_INFO_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise Exception(f"API Error: {data['error']}")

            return data
        except requests.exceptions.ConnectionError as e:
            if attempt < 2:
                wait_time = (attempt + 1) * 5
                print(f"  Connection error, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise


def get_available_fields():
    """Get list of available fields from the API."""
    info = get_layer_info()
    fields = info.get("fields", [])
    return {f["name"]: f for f in fields}


def fetch_flood_zones(where_clause, offset=0, max_records=500, session=None):
    """
    Fetch flood hazard areas from the FEMA NFHL API.

    Args:
        where_clause: SQL WHERE clause for filtering (e.g., "DFIRM_ID LIKE '47037%'")
        offset: Starting record offset for pagination
        max_records: Maximum records per request
        session: Requests session (created if not provided)

    Returns:
        List of flood zone feature dictionaries with geometry
    """
    if session is None:
        session = create_session()

    params = {
        "where": where_clause,
        "outFields": "OBJECTID,DFIRM_ID,FLD_AR_ID,STUDY_TYP,FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,SOURCE_CIT,GFID",
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84 for BigQuery GEOGRAPHY
        "f": "geojson",
        "resultRecordCount": max_records,
        "resultOffset": offset,
    }

    for attempt in range(5):
        try:
            response = session.get(FLOOD_HAZARD_URL, params=params, timeout=180)
            response.raise_for_status()

            data = response.json()

            if "error" in data:
                raise Exception(f"API Error: {data['error']}")

            return data.get("features", [])

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < 4:
                wait_time = (attempt + 1) * 10
                print(f"    Connection error, retrying in {wait_time}s... (attempt {attempt + 1}/5)")
                time.sleep(wait_time)
            else:
                raise


def extract_flood_zones(county_fips=None, output_path=None):
    """
    Extract flood hazard areas for a given county using DFIRM_ID.

    Args:
        county_fips: County FIPS code (default: Davidson County 47037)
        output_path: Path to save incremental progress (optional)

    Returns:
        List of GeoJSON features
    """
    if county_fips is None:
        county_fips = DAVIDSON_COUNTY_FIPS

    where_clause = f"DFIRM_ID LIKE '{county_fips}%'"
    print(f"Fetching flood zones for county FIPS {county_fips}...")
    print(f"  WHERE clause: {where_clause}")

    # Create a shared session for all requests
    session = create_session()

    all_features = []
    offset = 0
    batch_size = 250  # Smaller batches to reduce server load
    consecutive_errors = 0

    while True:
        print(f"  Fetching records starting at {offset}...")
        try:
            features = fetch_flood_zones(where_clause, offset=offset, max_records=batch_size, session=session)
            consecutive_errors = 0  # Reset error counter on success
        except (requests.exceptions.RetryError, requests.exceptions.ConnectionError) as e:
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print(f"  Too many consecutive errors. Stopping at {len(all_features)} features.")
                break
            wait_time = consecutive_errors * 30
            print(f"    Server error, waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            continue

        if not features:
            break

        all_features.extend(features)
        print(f"    Got {len(features)} features (total: {len(all_features)})")
        offset += len(features)

        # Save progress incrementally if output path provided
        if output_path and len(all_features) % 2500 == 0:
            records = features_to_newline_json(all_features)
            save_newline_json(records, output_path)
            print(f"    Progress saved to {output_path}")

        # If we got fewer than requested, we're done
        if len(features) < batch_size:
            break

        # Longer delay between batches to avoid overwhelming the server
        time.sleep(3)

    print(f"Fetched {len(all_features)} flood zone polygons.")
    return all_features


def get_zone_description(flood_zone, zone_subtype, sfha_tf):
    """
    Generate a human-readable description for the flood zone.

    Args:
        flood_zone: The flood zone code (A, AE, X, etc.)
        zone_subtype: The zone subtype
        sfha_tf: Special Flood Hazard Area True/False

    Returns:
        Human-readable description string
    """
    descriptions = {
        "A": "High-risk area with 1% annual flood chance (100-year floodplain)",
        "AE": "High-risk area with base flood elevations determined",
        "AH": "High-risk shallow flooding area (1-3 feet) with base flood elevations",
        "AO": "High-risk area with sheet flow flooding (1-3 feet)",
        "AR": "Special flood hazard area previously protected by levee/flood control",
        "A99": "Area to be protected by federal flood control system under construction",
        "V": "High-risk coastal area with wave action",
        "VE": "High-risk coastal area with base flood elevations and wave action",
        "X": "Minimal flood hazard area (outside 500-year floodplain)" if zone_subtype in (None, "", "AREA OF MINIMAL FLOOD HAZARD") else "Moderate flood hazard area (500-year floodplain)",
        "D": "Possible flood hazard area (undetermined risk)",
    }

    base_desc = descriptions.get(flood_zone, f"Flood zone {flood_zone}")

    if sfha_tf:
        return f"SFHA: {base_desc}"
    else:
        return base_desc


def features_to_newline_json(features):
    """
    Convert GeoJSON features to newline-delimited JSON for BigQuery.

    Each line contains a record with:
    - All attribute fields
    - geom: GeoJSON geometry as string (BigQuery will parse this)
    """
    records = []

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        flood_zone = props.get("FLD_ZONE")
        zone_subtype = props.get("ZONE_SUBTY")
        sfha_tf = props.get("SFHA_TF") == "T"  # Convert string to boolean

        record = {
            "object_id": props.get("OBJECTID"),
            "dfirm_id": props.get("DFIRM_ID"),
            "flood_area_id": props.get("FLD_AR_ID"),
            "study_type": props.get("STUDY_TYP"),
            "flood_zone": flood_zone,
            "zone_subtype": zone_subtype,
            "sfha_tf": sfha_tf,
            "static_bfe": props.get("STATIC_BFE"),
            "source_citation": props.get("SOURCE_CIT"),
            "gfid": props.get("GFID"),
            "zone_description": get_zone_description(flood_zone, zone_subtype, sfha_tf),
            "geom": json.dumps(geom) if geom else None,
            "load_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)

    return records


def save_newline_json(records, output_path):
    """Save records as newline-delimited JSON."""
    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def load_to_bigquery(json_path, table_id, truncate=False):
    """
    Load newline-delimited JSON to BigQuery with GEOGRAPHY conversion.

    Uses a staging table pattern to avoid conflicts with Terraform-managed schema:
    1. Load JSON to a temporary staging table (geom as STRING)
    2. INSERT into final table with ST_GEOGFROMGEOJSON conversion
    3. Delete staging table

    Args:
        json_path: Path to the newline-delimited JSON file
        table_id: Fully qualified BigQuery table ID
        truncate: If True, replace existing data; if False, append
    """
    from google.cloud import bigquery

    client = bigquery.Client()

    # Parse table_id to get project.dataset.table components
    parts = table_id.split(".")
    if len(parts) != 3:
        raise ValueError(f"table_id must be project.dataset.table format, got: {table_id}")
    project, dataset, table_name = parts
    staging_table_id = f"{project}.{dataset}.{table_name}_staging"

    # Step 1: Load to staging table with geom as STRING
    print(f"Step 1: Loading data to staging table {staging_table_id}...")

    staging_schema = [
        bigquery.SchemaField("object_id", "INTEGER"),
        bigquery.SchemaField("dfirm_id", "STRING"),
        bigquery.SchemaField("flood_area_id", "STRING"),
        bigquery.SchemaField("study_type", "STRING"),
        bigquery.SchemaField("flood_zone", "STRING"),
        bigquery.SchemaField("zone_subtype", "STRING"),
        bigquery.SchemaField("sfha_tf", "BOOLEAN"),
        bigquery.SchemaField("static_bfe", "FLOAT64"),
        bigquery.SchemaField("source_citation", "STRING"),
        bigquery.SchemaField("gfid", "STRING"),
        bigquery.SchemaField("zone_description", "STRING"),
        bigquery.SchemaField("geom", "STRING"),  # GeoJSON as string
        bigquery.SchemaField("load_timestamp", "TIMESTAMP"),
    ]

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=staging_schema,
    )

    with open(json_path, "rb") as f:
        job = client.load_table_from_file(f, staging_table_id, job_config=job_config)
        job.result()

    staging_table = client.get_table(staging_table_id)
    print(f"  Loaded {staging_table.num_rows} rows to staging table.")

    # Step 2: Truncate target table if requested
    if truncate:
        print(f"Step 2: Truncating target table {table_id}...")
        truncate_query = f"TRUNCATE TABLE `{table_id}`"
        client.query(truncate_query).result()
        print("  Table truncated.")
    else:
        print("Step 2: Appending to target table (no truncate)...")

    # Step 3: Insert from staging to final table with GEOGRAPHY conversion
    print(f"Step 3: Inserting into {table_id} with GEOGRAPHY conversion...")

    insert_query = f"""
    INSERT INTO `{table_id}` (
        object_id, dfirm_id, flood_area_id, study_type, flood_zone,
        zone_subtype, sfha_tf, static_bfe, source_citation, gfid,
        zone_description, geom, load_timestamp
    )
    SELECT
        object_id, dfirm_id, flood_area_id, study_type, flood_zone,
        zone_subtype, sfha_tf, static_bfe, source_citation, gfid,
        zone_description,
        ST_GEOGFROMGEOJSON(geom, make_valid => TRUE) AS geom,
        load_timestamp
    FROM `{staging_table_id}`
    """

    client.query(insert_query).result()

    final_table = client.get_table(table_id)
    print(f"  Target table now has {final_table.num_rows} rows.")

    # Step 4: Clean up staging table
    print(f"Step 4: Deleting staging table {staging_table_id}...")
    client.delete_table(staging_table_id)
    print("  Staging table deleted.")

    print(f"\nDone! Flood zones loaded to {table_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and load FEMA NFHL Flood Hazard Areas to BigQuery"
    )
    parser.add_argument(
        "--county",
        type=str,
        default=DAVIDSON_COUNTY_FIPS,
        help=f"County FIPS code (default: {DAVIDSON_COUNTY_FIPS} for Davidson County, TN)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/flood_zones.json",
        help="Output JSON file path (default: data/flood_zones.json)",
    )
    parser.add_argument(
        "--show-fields",
        action="store_true",
        help="Show available fields and exit",
    )
    parser.add_argument(
        "--load-bq",
        action="store_true",
        help="Load JSON data to BigQuery",
    )
    parser.add_argument(
        "--bq-table",
        type=str,
        default=DEFAULT_BQ_TABLE,
        help=f"BigQuery table ID (default: {DEFAULT_BQ_TABLE})",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate table before loading (default: append)",
    )
    args = parser.parse_args()

    # Show available fields if requested
    if args.show_fields:
        print("Fetching available fields from API...")
        fields = get_available_fields()
        print(f"\nAvailable fields ({len(fields)}):\n")
        for name, info in sorted(fields.items()):
            field_type = info.get("type", "unknown")
            alias = info.get("alias", name)
            print(f"  {name} ({field_type}): {alias}")
        return

    # Load JSON to BigQuery if requested
    if args.load_bq:
        json_path = Path(args.output)
        if not json_path.exists():
            print(f"Error: JSON file not found at {json_path}")
            print("Run without --load-bq first to extract data.")
            return
        load_to_bigquery(json_path, args.bq_table, truncate=args.truncate)
        return

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract flood zones with incremental saves
    features = extract_flood_zones(county_fips=args.county, output_path=output_path)

    if not features:
        print("No flood zones found.")
        return

    # Convert to newline-delimited JSON
    records = features_to_newline_json(features)

    # Save to JSON
    save_newline_json(records, output_path)
    print(f"\nSaved {len(records)} flood zone polygons to {output_path}")

    # Show summary by zone type
    print("\nFlood zones by type:")
    zone_counts = {}
    sfha_count = 0
    for record in records:
        zone = record["flood_zone"] or "Unknown"
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
        if record["sfha_tf"]:
            sfha_count += 1

    for zone, count in sorted(zone_counts.items()):
        print(f"  {zone}: {count} polygons")

    print(f"\nSpecial Flood Hazard Areas (SFHA): {sfha_count} of {len(records)} polygons")


if __name__ == "__main__":
    main()
