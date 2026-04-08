"""
Extracts building characteristics data from Nashville Open Data ArcGIS FeatureServer.

Data Source: Parcels with Building Characteristics (Davidson County)
API: https://services2.arcgis.com/HdTo6HJqh92wn4D8/ArcGIS/rest/services/Parcels_with_Building_Characteristics_view/FeatureServer/0

This script fetches building footprint polygons with attributes like structure type,
year built, finished area, exterior material, and floor number.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.cloud import bigquery

# API Configuration
API_BASE_URL = "https://services2.arcgis.com/HdTo6HJqh92wn4D8/ArcGIS/rest/services/Parcels_with_Building_Characteristics_view/FeatureServer/0"
QUERY_URL = f"{API_BASE_URL}/query"

# BigQuery Configuration
DEFAULT_BQ_TABLE = "public-data-dev.property_tax.davidson_building_characteristics"
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "data" / "building_characteristics.json"

# Extraction Configuration
DEFAULT_BATCH_SIZE = 1000
REQUEST_DELAY = 0.5  # seconds between API requests


def get_layer_info():
    """Fetch layer metadata from the ArcGIS service.

    Returns:
        dict: Layer metadata including fields, geometry type, etc.
    """
    params = {"f": "json"}
    response = requests.get(API_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise Exception(f"API error: {data['error']}")

    return data


def get_available_fields():
    """Get available fields and their types from the layer.

    Returns:
        dict: Mapping of field names to their types.
    """
    layer_info = get_layer_info()
    fields = {}
    for field in layer_info.get("fields", []):
        fields[field["name"]] = field["type"]
    return fields


def fetch_building_characteristics(offset=0, count=DEFAULT_BATCH_SIZE):
    """Fetch a batch of building characteristics features from the API.

    Args:
        offset: Number of records to skip.
        count: Number of records to fetch.

    Returns:
        list: List of GeoJSON features.
    """
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84 for BigQuery GEOGRAPHY compatibility
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": count,
    }

    response = requests.get(QUERY_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise Exception(f"API error: {data['error']}")

    return data.get("features", [])


def extract_building_characteristics(max_count=None, batch_size=DEFAULT_BATCH_SIZE):
    """Extract all building characteristics data with pagination.

    Args:
        max_count: Maximum number of records to fetch (None for all).
        batch_size: Number of records per API request.

    Returns:
        list: All extracted GeoJSON features.
    """
    all_features = []
    offset = 0

    while True:
        # Adjust batch size if we're near the max_count limit
        current_batch_size = batch_size
        if max_count is not None:
            remaining = max_count - len(all_features)
            if remaining <= 0:
                break
            current_batch_size = min(batch_size, remaining)

        print(f"Fetching records {offset} to {offset + current_batch_size}...")
        features = fetch_building_characteristics(offset=offset, count=current_batch_size)

        if not features:
            print("No more features returned.")
            break

        all_features.extend(features)
        print(f"  Retrieved {len(features)} features. Total: {len(all_features)}")

        offset += len(features)

        # Check if we've reached max_count
        if max_count is not None and len(all_features) >= max_count:
            break

        # Rate limiting
        time.sleep(REQUEST_DELAY)

    return all_features


def convert_epoch_to_date(epoch_ms):
    """Convert millisecond epoch timestamp to ISO date string.

    Args:
        epoch_ms: Milliseconds since Unix epoch.

    Returns:
        str: ISO format date string (YYYY-MM-DD) or None if invalid.
    """
    if epoch_ms is None:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return None


def features_to_newline_json(features):
    """Transform GeoJSON features to newline-delimited JSON records.

    Args:
        features: List of GeoJSON features.

    Returns:
        list: List of flat dictionary records.
    """
    records = []
    load_timestamp = datetime.now(timezone.utc).isoformat()

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        record = {
            "object_id": props.get("objectid"),
            "feature_type": props.get("featuretype"),
            "floor_number": props.get("floornumber"),
            "apn": props.get("APN"),
            "assessor_card_number": props.get("AssessorCardNumber"),
            "structure_type": props.get("StructureType"),
            "finished_area": props.get("FinishedArea"),
            "exterior": props.get("Exterior"),
            "year_built": props.get("YearBuilt"),
            "date_effective": convert_epoch_to_date(props.get("DateEffective")),
            "parcel_id": props.get("ParcelID"),
            "shape_area": props.get("Shape__Area"),
            "shape_length": props.get("Shape__Length"),
            "geom": json.dumps(geom) if geom else None,
            "load_timestamp": load_timestamp,
        }
        records.append(record)

    return records


def save_newline_json(records, output_path):
    """Save records as newline-delimited JSON file.

    Args:
        records: List of dictionary records.
        output_path: Path to output file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Saved {len(records)} records to {output_path}")


def load_to_bigquery(json_path, table_id, truncate=False):
    """Load newline-delimited JSON to BigQuery using staging table pattern.

    Uses a staging table to handle GEOGRAPHY type conversion from GeoJSON.

    Args:
        json_path: Path to newline-delimited JSON file.
        table_id: Full BigQuery table ID (project.dataset.table).
        truncate: If True, replace existing data; otherwise append.
    """
    client = bigquery.Client()
    staging_table_id = f"{table_id}_staging"

    # Define staging schema (geom as STRING for initial load)
    staging_schema = [
        bigquery.SchemaField("object_id", "INTEGER"),
        bigquery.SchemaField("feature_type", "STRING"),
        bigquery.SchemaField("floor_number", "STRING"),
        bigquery.SchemaField("apn", "STRING"),
        bigquery.SchemaField("assessor_card_number", "INTEGER"),
        bigquery.SchemaField("structure_type", "STRING"),
        bigquery.SchemaField("finished_area", "FLOAT64"),
        bigquery.SchemaField("exterior", "STRING"),
        bigquery.SchemaField("year_built", "INTEGER"),
        bigquery.SchemaField("date_effective", "DATE"),
        bigquery.SchemaField("parcel_id", "INTEGER"),
        bigquery.SchemaField("shape_area", "FLOAT64"),
        bigquery.SchemaField("shape_length", "FLOAT64"),
        bigquery.SchemaField("geom", "STRING"),  # Will be converted to GEOGRAPHY
        bigquery.SchemaField("load_timestamp", "TIMESTAMP"),
    ]

    # Load to staging table
    print(f"Loading data to staging table: {staging_table_id}")
    job_config = bigquery.LoadJobConfig(
        schema=staging_schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    with open(json_path, "rb") as f:
        load_job = client.load_table_from_file(f, staging_table_id, job_config=job_config)

    load_job.result()  # Wait for completion
    print(f"  Loaded {load_job.output_rows} rows to staging table.")

    # Handle truncate mode
    if truncate:
        print(f"Truncating target table: {table_id}")
        truncate_query = f"TRUNCATE TABLE `{table_id}`"
        client.query(truncate_query).result()

    # Insert from staging to target with GEOGRAPHY conversion
    print(f"Inserting data to target table: {table_id}")
    insert_query = f"""
    INSERT INTO `{table_id}` (
        object_id,
        feature_type,
        floor_number,
        apn,
        assessor_card_number,
        structure_type,
        finished_area,
        exterior,
        year_built,
        date_effective,
        parcel_id,
        shape_area,
        shape_length,
        geom,
        load_timestamp
    )
    SELECT
        object_id,
        feature_type,
        floor_number,
        apn,
        assessor_card_number,
        structure_type,
        finished_area,
        exterior,
        year_built,
        date_effective,
        parcel_id,
        shape_area,
        shape_length,
        ST_GEOGFROMGEOJSON(geom, make_valid => TRUE) as geom,
        load_timestamp
    FROM `{staging_table_id}`
    """
    client.query(insert_query).result()

    # Get row count
    count_query = f"SELECT COUNT(*) as cnt FROM `{table_id}`"
    result = client.query(count_query).result()
    row_count = list(result)[0].cnt
    print(f"  Target table now has {row_count} rows.")

    # Clean up staging table
    print(f"Dropping staging table: {staging_table_id}")
    client.delete_table(staging_table_id, not_found_ok=True)

    print("BigQuery load complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Extract building characteristics data from Nashville ArcGIS and optionally load to BigQuery."
    )
    parser.add_argument(
        "--show-fields",
        action="store_true",
        help="Show available fields from the API and exit.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum number of records to extract (default: all).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records per API request (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Output file path (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--load-bq",
        action="store_true",
        help="Load extracted data to BigQuery.",
    )
    parser.add_argument(
        "--bq-table",
        type=str,
        default=DEFAULT_BQ_TABLE,
        help=f"BigQuery table ID (default: {DEFAULT_BQ_TABLE}).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate target table before loading (default: append).",
    )

    args = parser.parse_args()

    # Show fields mode
    if args.show_fields:
        print("Available fields:")
        fields = get_available_fields()
        for name, field_type in fields.items():
            print(f"  {name}: {field_type}")
        return

    # Extract data
    print(f"Extracting building characteristics data...")
    features = extract_building_characteristics(
        max_count=args.count, batch_size=args.batch_size
    )

    if not features:
        print("No features extracted.")
        return

    print(f"Extracted {len(features)} features total.")

    # Transform and save
    records = features_to_newline_json(features)
    save_newline_json(records, args.output)

    # Load to BigQuery if requested
    if args.load_bq:
        load_to_bigquery(args.output, args.bq_table, truncate=args.truncate)


if __name__ == "__main__":
    main()
