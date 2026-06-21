#!/usr/bin/env python3
"""
Extract parcel data from Williamson County (Franklin/Brentwood, TN) ArcGIS REST API.
Data source: http://arcgis2.williamsoncounty-tn.gov/arcgis/rest/services/IDT/DataPull/MapServer/10

Differences from Davidson:
- Geometry is a polygon (no explicit Lat/Lon fields); centroid is computed from rings
- Date fields: pxfer_date, pxfer_da_1 (both epoch ms)
- Assessment fields: total_asse (assessed), total_mark (market), considerat (sale price)
"""

import requests
import pandas as pd
from pathlib import Path
import argparse
import time
from datetime import datetime, timezone

PARCELS_URL = "http://arcgis2.williamsoncounty-tn.gov/arcgis/rest/services/IDT/DataPull/MapServer/10/query"
LAYER_INFO_URL = "http://arcgis2.williamsoncounty-tn.gov/arcgis/rest/services/IDT/DataPull/MapServer/10"

DEFAULT_BQ_TABLE = "public-data-dev.property_tax.williamson_parcels"

DATE_COLUMNS = ["pxfer_date", "pxfer_da_1"]


def get_total_count():
    """Get total number of parcels available from the API."""
    params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    response = requests.get(PARCELS_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(f"API Error: {data['error']}")
    return data.get("count", 0)


def compute_centroid(rings):
    """Compute the centroid of a polygon from its outer ring."""
    if not rings:
        return None, None
    outer = rings[0]
    if not outer:
        return None, None
    lon = sum(p[0] for p in outer) / len(outer)
    lat = sum(p[1] for p in outer) / len(outer)
    return lat, lon


def fetch_batch(offset, batch_size):
    """
    Fetch one batch of parcels with geometry in WGS84 (outSR=4326)
    so we can compute lat/lon centroids.
    """
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": batch_size,
        "resultOffset": offset,
        "orderByFields": "OBJECTID ASC",
    }
    response = requests.get(PARCELS_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(f"API Error: {data['error']}")
    return data.get("features", [])


def extract_parcels(total_records, batch_size=1000):
    """Extract parcel data with pagination, computing lat/lon from polygon centroids."""
    all_records = []
    offset = 0

    print(f"Fetching up to {total_records} parcels from Williamson County...")

    while len(all_records) < total_records:
        remaining = total_records - len(all_records)
        fetch_count = min(batch_size, remaining)

        print(f"  Fetching records {offset}–{offset + fetch_count}...")
        features = fetch_batch(offset, fetch_count)

        if not features:
            print("  No more records available.")
            break

        for feature in features:
            attrs = feature.get("attributes", {})
            geometry = feature.get("geometry")

            # Compute centroid from polygon rings
            if geometry and "rings" in geometry:
                lat, lon = compute_centroid(geometry["rings"])
            else:
                lat, lon = None, None

            attrs["Lat"] = lat
            attrs["Lon"] = lon
            all_records.append(attrs)

        offset += len(features)

        if len(all_records) < total_records:
            time.sleep(0.5)

    print(f"Fetched {len(all_records)} total records.")
    return pd.DataFrame(all_records)


def clean_for_bigquery(df):
    """Clean DataFrame for BigQuery — normalize nulls and convert epoch dates."""
    NULL_LIKE = {"", "null", "none", "n/a", "na", "nan"}

    def to_null(val):
        if val is None:
            return None
        if isinstance(val, str) and val.strip().lower() in NULL_LIKE:
            return None
        return val

    for col in df.columns:
        df[col] = df[col].apply(to_null)

    # Convert epoch ms timestamps to date strings
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], unit="ms", errors="coerce")
            df[col] = df[col].dt.strftime("%Y-%m-%d")
            df[col] = df[col].replace("NaT", None)

    # Drop geometry/shape columns that BigQuery doesn't need
    for col in ["Shape_Length", "Shape_Area"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df


def load_to_bigquery(df, table_id, truncate=False):
    """Load a DataFrame directly into the williamson_parcels BigQuery table."""
    from google.cloud import bigquery

    client = bigquery.Client()
    table = client.get_table(table_id)
    schema = table.schema

    df = df.copy()
    df["load_timestamp"] = datetime.now(timezone.utc).isoformat()

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
    job.result()

    table = client.get_table(table_id)
    print(f"Done. Table now has {table.num_rows} total rows.")


def main():
    parser = argparse.ArgumentParser(description="Extract Williamson County parcel data")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of parcels to extract (default: 100; use --all for full dataset)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract all parcels (fetches total count first)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save extracted data to a CSV file at this path (optional)"
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
        help="Truncate BigQuery table before loading (default: append)"
    )
    parser.add_argument(
        "--total-count",
        action="store_true",
        help="Print total number of parcels available and exit"
    )
    args = parser.parse_args()

    if args.total_count:
        count = get_total_count()
        print(f"Total parcels available: {count:,}")
        return

    total = get_total_count() if args.all else args.count
    if args.all:
        print(f"Full extract mode: {total:,} parcels available.")

    df = extract_parcels(total_records=total)

    if df.empty:
        print("No data retrieved.")
        return

    df = clean_for_bigquery(df)

    print(f"\nExtracted {len(df)} records.")

    # Optionally save to CSV
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")

    # Always load directly to BigQuery
    load_to_bigquery(df, args.bq_table, truncate=args.truncate)

    print("\nSample assessment data:")
    sample_cols = ["parcel_id", "ADDRESS", "total_asse", "total_mark", "considerat", "pxfer_date", "SQFT_ASSES", "AC", "Lat", "Lon"]
    available = [c for c in sample_cols if c in df.columns]
    print(df[available].head(5).to_string())


if __name__ == "__main__":
    main()
