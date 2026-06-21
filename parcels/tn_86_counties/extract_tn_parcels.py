#!/usr/bin/env python3
"""
Extract parcel data for 86 Tennessee counties from the statewide ArcGIS endpoint.
Uses OBJECTID-range pagination (more reliable than offset at 2M+ records).

Coverage: 86 of 95 TN counties. The 9 self-maintained counties
(Chester, Davidson, Hamilton, Hickman, Knox, Montgomery, Rutherford, Shelby,
Williamson) are not present in this service.

Usage:
    python extract_tn_parcels.py                     # full extract -> BigQuery
    python extract_tn_parcels.py --county-id 1       # single county test (Anderson)
    python extract_tn_parcels.py --total-count        # print total records and exit
"""

import requests
import pandas as pd
import argparse
import time
from datetime import datetime, timezone

BASE_URL = (
    "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services"
    "/Tennessee_Property_Boundaries_Public_Use/FeatureServer/0/query"
)
DEFAULT_BQ_TABLE = "public-data-dev.property_tax.tn_parcels_86_counties"
BATCH_SIZE = 2000  # API maxRecordCount

OUT_FIELDS = ",".join([
    "OBJECTID", "COUNTY_ID", "COUNTY_NAME", "PARCEL_TYPE",
    "GISLINK", "PARCELID", "PARCEL", "ADDRESS",
    "OWNER", "OWNER2", "DEEDAC", "SUBDIV", "LOT",
    "LINK_TPAD", "LINK_TPV",
])


def get_oid_range(county_id=None):
    """Get min OID, max OID, and total count to drive range-based pagination."""
    where = f"COUNTY_ID={county_id}" if county_id else "1=1"
    params = {
        "where": where,
        "outStatistics": (
            '[{"statisticType":"min","onStatisticField":"OBJECTID","outStatisticFieldName":"min_oid"},'
            '{"statisticType":"max","onStatisticField":"OBJECTID","outStatisticFieldName":"max_oid"},'
            '{"statisticType":"count","onStatisticField":"OBJECTID","outStatisticFieldName":"total"}]'
        ),
        "f": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    attrs = resp.json()["features"][0]["attributes"]
    return int(attrs["min_oid"]), int(attrs["max_oid"]), int(attrs["total"])


def compute_centroid(rings):
    """Compute centroid of a polygon from its outer ring."""
    if not rings:
        return None, None
    outer = rings[0]
    if not outer:
        return None, None
    lon = sum(p[0] for p in outer) / len(outer)
    lat = sum(p[1] for p in outer) / len(outer)
    return lat, lon


def fetch_batch(oid_start, oid_end, county_id=None):
    """Fetch one OBJECTID-range batch with geometry reprojected to WGS84."""
    where = f"OBJECTID >= {oid_start} AND OBJECTID < {oid_end}"
    if county_id:
        where += f" AND COUNTY_ID={county_id}"
    params = {
        "where": where,
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise Exception(f"API error: {data['error']}")
    return data.get("features", [])


def extract_all(county_id=None, limit=None):
    """Extract parcels using OBJECTID-range pagination and compute lat/lon centroids."""
    min_oid, max_oid, total = get_oid_range(county_id)
    scope = f"county_id={county_id}" if county_id else "all 86 counties"
    print(f"Extracting {total:,} parcels ({scope}) | OID range {min_oid:,}–{max_oid:,}")
    if limit:
        print(f"Limit: {limit} records")
    estimated_batches = (max_oid - min_oid) // BATCH_SIZE + 1
    print(f"Estimated batches: {estimated_batches:,} (at {BATCH_SIZE} OIDs per batch)\n")

    all_records = []
    current_oid = min_oid
    batch_num = 0

    while current_oid <= max_oid:
        if limit and len(all_records) >= limit:
            break

        next_oid = current_oid + BATCH_SIZE
        batch_num += 1

        if batch_num % 100 == 1:
            pct = (len(all_records) / total * 100) if total > 0 else 0
            print(f"  Batch {batch_num:,} | OID {current_oid:,}–{next_oid:,} | "
                  f"fetched: {len(all_records):,} ({pct:.1f}%)")

        features = fetch_batch(current_oid, next_oid, county_id)

        for feature in features:
            attrs = feature.get("attributes", {})
            geometry = feature.get("geometry")
            if geometry and "rings" in geometry:
                lat, lon = compute_centroid(geometry["rings"])
            else:
                lat, lon = None, None
            attrs["Lat"] = lat
            attrs["Lon"] = lon
            all_records.append(attrs)
            if limit and len(all_records) >= limit:
                break

        current_oid = next_oid
        time.sleep(0.1)

    print(f"\nFetched {len(all_records):,} total records.")
    return pd.DataFrame(all_records)


def load_to_bigquery(df, table_id, truncate=False):
    """Load DataFrame directly into BigQuery."""
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

    print(f"Loading {len(df):,} rows to {table_id}...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()

    table = client.get_table(table_id)
    print(f"Done. Table now has {table.num_rows:,} total rows.")


def main():
    parser = argparse.ArgumentParser(
        description="Extract TN 86-county parcel boundaries into BigQuery"
    )
    parser.add_argument(
        "--county-id",
        type=int,
        help="Extract a single county by COUNTY_ID (e.g. 1 = Anderson). Useful for testing."
    )
    parser.add_argument(
        "--total-count",
        action="store_true",
        help="Print total record count and exit"
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
        help="Truncate the BigQuery table before loading (default: append)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Stop after N records (useful for testing)"
    )
    args = parser.parse_args()

    if args.total_count:
        _, _, total = get_oid_range(args.county_id)
        scope = f"county_id={args.county_id}" if args.county_id else "all counties"
        print(f"Total parcels ({scope}): {total:,}")
        return

    df = extract_all(county_id=args.county_id, limit=args.limit)

    if df.empty:
        print("No data retrieved.")
        return

    load_to_bigquery(df, args.bq_table, truncate=args.truncate)

    print("\nSample:")
    sample_cols = ["COUNTY_NAME", "PARCELID", "ADDRESS", "OWNER", "DEEDAC", "GISLINK", "Lat", "Lon"]
    available = [c for c in sample_cols if c in df.columns]
    print(df[available].head(5).to_string())


if __name__ == "__main__":
    main()
