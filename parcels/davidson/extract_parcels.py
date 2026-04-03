#!/usr/bin/env python3
"""
Extract parcel data from Davidson County (Nashville) Property Assessor.
Data source: Nashville Open Data ArcGIS FeatureServer (Parcels_view)
"""

import requests
import pandas as pd
from pathlib import Path
import argparse
import time
from datetime import datetime, timezone

# Nashville ArcGIS FeatureServer endpoint for Parcels (public view)
PARCELS_URL = "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Parcels_view/FeatureServer/0/query"
LAYER_INFO_URL = "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Parcels_view/FeatureServer/0"

# BigQuery destination
DEFAULT_BQ_TABLE = "public-data-dev.property_tax.davidson_parcels"


def get_layer_info():
    """Fetch the layer metadata to understand available fields."""
    params = {"f": "json"}
    response = requests.get(LAYER_INFO_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise Exception(f"API Error: {data['error']}")

    return data


def get_available_fields():
    """Get list of available fields from the API."""
    info = get_layer_info()
    fields = info.get("fields", [])
    return {f["name"]: f for f in fields}


def fetch_parcels(max_records, offset=0, fields="*"):
    """
    Fetch parcels from the ArcGIS API.

    Args:
        max_records: Maximum number of records to fetch per request
        offset: Starting record offset for pagination
        fields: Comma-separated field names or "*" for all

    Returns:
        List of parcel feature dictionaries
    """
    params = {
        "where": "1=1",  # Get all records
        "outFields": fields,
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": max_records,
        "resultOffset": offset,
        "orderByFields": "OBJECTID ASC",
    }

    response = requests.get(PARCELS_URL, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise Exception(f"API Error: {data['error']}")

    return data.get("features", [])


def extract_parcels(total_records=100, batch_size=1000):
    """
    Extract parcel data, handling pagination.

    Args:
        total_records: Total number of records to extract
        batch_size: Records per API request

    Returns:
        DataFrame with parcel data
    """
    all_records = []
    offset = 0

    print(f"Fetching {total_records} parcels from Davidson County...")

    while len(all_records) < total_records:
        remaining = total_records - len(all_records)
        fetch_count = min(batch_size, remaining)

        print(f"  Fetching records {offset} to {offset + fetch_count}...")
        features = fetch_parcels(max_records=fetch_count, offset=offset)

        if not features:
            print("  No more records available.")
            break

        # Extract attributes from features
        records = [f["attributes"] for f in features]
        all_records.extend(records)

        offset += len(features)

        # Brief pause to be respectful to the API
        if len(all_records) < total_records:
            time.sleep(0.5)

    print(f"Fetched {len(all_records)} total records.")

    df = pd.DataFrame(all_records)
    return df


def clean_for_bigquery(df):
    """
    Clean DataFrame for BigQuery ingestion.
    - Convert timestamps to ISO format
    - Handle null values
    """
    # Common null-like values to normalize
    NULL_LIKE = {"", "null", "none", "n/a", "na", "nan"}

    def to_null(val):
        if val is None:
            return None
        if isinstance(val, str) and val.strip().lower() in NULL_LIKE:
            return None
        return val

    # Apply null normalization to all columns
    for col in df.columns:
        df[col] = df[col].apply(to_null)

    # Convert epoch timestamps (milliseconds) to ISO format
    # ArcGIS returns dates as Unix timestamps in milliseconds
    date_columns = ["OwnDate", "PropDate"]
    for col in date_columns:
        if col in df.columns:
            # Convert ms to datetime, then to date string
            df[col] = pd.to_datetime(df[col], unit="ms", errors="coerce")
            df[col] = df[col].dt.strftime("%Y-%m-%d")
            # Replace 'NaT' string with None
            df[col] = df[col].replace("NaT", None)

    return df


def load_to_bigquery(csv_path, table_id, truncate=False):
    """
    Load CSV data to BigQuery.

    Args:
        csv_path: Path to the CSV file
        table_id: Fully qualified BigQuery table ID (project.dataset.table)
        truncate: If True, replace existing data; if False, append
    """
    from google.cloud import bigquery

    client = bigquery.Client()

    # Get schema from existing table
    table = client.get_table(table_id)
    schema = table.schema

    # Read CSV with all columns as strings to avoid type issues
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df["load_timestamp"] = datetime.now(timezone.utc).isoformat()

    # Replace empty strings with None for proper NULL handling
    df = df.replace("", None)

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=(
            bigquery.WriteDisposition.WRITE_TRUNCATE
            if truncate
            else bigquery.WriteDisposition.WRITE_APPEND
        ),
    )

    print(f"Loading {len(df)} rows to {table_id}...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for completion

    table = client.get_table(table_id)
    print(f"Loaded {len(df)} rows. Table now has {table.num_rows} total rows.")


def main():
    parser = argparse.ArgumentParser(description="Extract Davidson County parcel data")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of parcels to extract (default: 100)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/features.csv",
        help="Output CSV file path (default: data/features.csv)"
    )
    parser.add_argument(
        "--show-fields",
        action="store_true",
        help="Show available fields and exit"
    )
    parser.add_argument(
        "--load-bq",
        action="store_true",
        help="Load CSV data to BigQuery"
    )
    parser.add_argument(
        "--bq-table",
        type=str,
        default=DEFAULT_BQ_TABLE,
        help=f"BigQuery table ID (default: {DEFAULT_BQ_TABLE})"
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate table before loading (default: append)"
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

    # Load CSV to BigQuery if requested
    if args.load_bq:
        csv_path = Path(args.output)
        if not csv_path.exists():
            print(f"Error: CSV file not found at {csv_path}")
            print("Run without --load-bq first to extract data.")
            return
        load_to_bigquery(csv_path, args.bq_table, truncate=args.truncate)
        return

    # Extract parcels
    df = extract_parcels(total_records=args.count)

    if df.empty:
        print("No data retrieved.")
        return

    # Clean for BigQuery
    df = clean_for_bigquery(df)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"\nSaved {len(df)} records to {output_path}")
    print(f"Columns: {list(df.columns)}")

    # Show sample of key assessment fields
    print("\nSample of assessment-related data:")
    assessment_cols = ["ParID", "PropAddr", "LandAppr", "ImprAppr", "TotlAppr", "Acres", "LUDesc"]
    available_cols = [c for c in assessment_cols if c in df.columns]
    print(df[available_cols].head(5).to_string())


if __name__ == "__main__":
    main()
