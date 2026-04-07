#!/usr/bin/env python3
"""
Download and load NARN Rail Lines data to BigQuery for Davidson County, TN.
Data source: BTS NTAD North American Rail Network (NARN) via ArcGIS FeatureServer
"""

import requests
import json
from pathlib import Path
import argparse
from datetime import datetime, timezone

# BTS NTAD ArcGIS FeatureServer endpoint for NARN Rail Lines
RAIL_LINES_URL = "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/FeatureServer/0/query"
LAYER_INFO_URL = "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/FeatureServer/0"

# Davidson County, TN FIPS code
DAVIDSON_COUNTY_FIPS = "47037"
TENNESSEE_FIPS = "47"

# BigQuery destination
DEFAULT_BQ_TABLE = "public-data-dev.property_tax.rail_lines"


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


def fetch_rail_lines(where_clause, offset=0, max_records=1000):
    """
    Fetch rail lines from the ArcGIS API.

    Args:
        where_clause: SQL WHERE clause for filtering
        offset: Starting record offset for pagination
        max_records: Maximum records per request

    Returns:
        List of rail line feature dictionaries with geometry
    """
    params = {
        "where": where_clause,
        "outFields": "OBJECTID,FRAARCID,STFIPS,CNTYFIPS,STCNTYFIPS,STATEAB,RROWNER1,RROWNER2,RROWNER3,PASSNGR,STRACNET,TRACKS,MILES,SUBDIV,DIVISION",
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84 for BigQuery GEOGRAPHY
        "f": "geojson",
        "resultRecordCount": max_records,
        "resultOffset": offset,
    }

    response = requests.get(RAIL_LINES_URL, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise Exception(f"API Error: {data['error']}")

    return data.get("features", [])


def extract_rail_lines(county_fips=DAVIDSON_COUNTY_FIPS, state_fips=None):
    """
    Extract rail lines for a given county or state.

    Args:
        county_fips: County FIPS code (state+county combined, e.g., '47037')
        state_fips: State FIPS code (e.g., '47' for Tennessee). If provided, gets entire state.

    Returns:
        List of GeoJSON features
    """
    if state_fips:
        where_clause = f"STFIPS = '{state_fips}'"
        location_desc = f"state FIPS {state_fips}"
    else:
        where_clause = f"STCNTYFIPS = '{county_fips}'"
        location_desc = f"county FIPS {county_fips}"

    print(f"Fetching rail lines for {location_desc}...")

    all_features = []
    offset = 0
    batch_size = 1000

    while True:
        print(f"  Fetching records starting at {offset}...")
        features = fetch_rail_lines(where_clause, offset=offset, max_records=batch_size)

        if not features:
            break

        all_features.extend(features)
        offset += len(features)

        # If we got fewer than requested, we're done
        if len(features) < batch_size:
            break

    print(f"Fetched {len(all_features)} rail line segments.")
    return all_features


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

        record = {
            "rail_id": props.get("OBJECTID"),
            "fra_arc_id": props.get("FRAARCID"),
            "state_fips": props.get("STFIPS"),
            "county_fips": props.get("CNTYFIPS"),
            "state_county_fips": props.get("STCNTYFIPS"),
            "state_abbrev": props.get("STATEAB"),
            "owner": props.get("RROWNER1"),
            "owner2": props.get("RROWNER2"),
            "owner3": props.get("RROWNER3"),
            "passenger_rail": props.get("PASSNGR"),
            "stracnet": props.get("STRACNET"),
            "tracks": props.get("TRACKS"),
            "miles": props.get("MILES"),
            "subdivision": props.get("SUBDIV"),
            "division": props.get("DIVISION"),
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
        bigquery.SchemaField("rail_id", "INTEGER"),
        bigquery.SchemaField("fra_arc_id", "INTEGER"),
        bigquery.SchemaField("state_fips", "STRING"),
        bigquery.SchemaField("county_fips", "STRING"),
        bigquery.SchemaField("state_county_fips", "STRING"),
        bigquery.SchemaField("state_abbrev", "STRING"),
        bigquery.SchemaField("owner", "STRING"),
        bigquery.SchemaField("owner2", "STRING"),
        bigquery.SchemaField("owner3", "STRING"),
        bigquery.SchemaField("passenger_rail", "STRING"),
        bigquery.SchemaField("stracnet", "STRING"),
        bigquery.SchemaField("tracks", "INTEGER"),
        bigquery.SchemaField("miles", "FLOAT64"),
        bigquery.SchemaField("subdivision", "STRING"),
        bigquery.SchemaField("division", "STRING"),
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
        rail_id, fra_arc_id, state_fips, county_fips, state_county_fips,
        state_abbrev, owner, owner2, owner3, passenger_rail, stracnet,
        tracks, miles, subdivision, division, geom, load_timestamp
    )
    SELECT
        rail_id, fra_arc_id, state_fips, county_fips, state_county_fips,
        state_abbrev, owner, owner2, owner3, passenger_rail, stracnet,
        tracks, miles, subdivision, division,
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

    print(f"\nDone! Rail lines loaded to {table_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and load NARN Rail Lines to BigQuery"
    )
    parser.add_argument(
        "--county",
        type=str,
        default=DAVIDSON_COUNTY_FIPS,
        help=f"County FIPS code (default: {DAVIDSON_COUNTY_FIPS} for Davidson County, TN)",
    )
    parser.add_argument(
        "--state",
        type=str,
        help="State FIPS code (e.g., '47' for Tennessee). Downloads entire state if provided.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/rail_lines.json",
        help="Output JSON file path (default: data/rail_lines.json)",
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

    # Extract rail lines
    features = extract_rail_lines(
        county_fips=args.county,
        state_fips=args.state,
    )

    if not features:
        print("No rail lines found.")
        return

    # Convert to newline-delimited JSON
    records = features_to_newline_json(features)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSON
    save_newline_json(records, output_path)
    print(f"\nSaved {len(records)} rail line segments to {output_path}")

    # Show sample
    print("\nSample of rail data:")
    for record in records[:5]:
        print(f"  Rail ID {record['rail_id']}: {record['owner']} - {record['miles']:.2f} miles")


if __name__ == "__main__":
    main()
