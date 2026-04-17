"""
Load Dallas County Appraisal District (DCAD) CSV data to BigQuery.

Loads CSV files from DCAD2026_CURRENT directory into BigQuery tables
in the dallas dataset.

Usage:
    # Load all tables (truncate mode - replace existing data)
    python load_dcad.py --truncate

    # Load all tables (append mode)
    python load_dcad.py

    # Load specific table(s)
    python load_dcad.py --tables account_info res_detail

    # Dry run - show what would be loaded
    python load_dcad.py --dry-run
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

# Configuration
DEFAULT_PROJECT = "public-data-dev"
DEFAULT_DATASET = "dallas"
DATA_DIR = Path(__file__).parent / "DCAD2026_CURRENT"

# Mapping of table names to CSV filenames
TABLE_CSV_MAP = {
    "abatement_exempt": "ABATEMENT_EXEMPT.CSV",
    "account_apprl_year": "ACCOUNT_APPRL_YEAR.CSV",
    "account_info": "ACCOUNT_INFO.CSV",
    "account_tif": "ACCOUNT_TIF.CSV",
    "acct_exempt_value": "ACCT_EXEMPT_VALUE.CSV",
    "applied_std_exempt": "APPLIED_STD_EXEMPT.CSV",
    "com_detail": "COM_DETAIL.CSV",
    "freeport_exemption": "FREEPORT_EXEMPTION.CSV",
    "land": "LAND.CSV",
    "multi_owner": "MULTI_OWNER.CSV",
    "res_addl": "RES_ADDL.CSV",
    "res_detail": "RES_DETAIL.CSV",
    "taxable_object": "TAXABLE_OBJECT.CSV",
    "total_exemption": "TOTAL_EXEMPTION.CSV",
}


def get_table_schema(client: bigquery.Client, table_ref: str) -> list[bigquery.SchemaField]:
    """Get schema from existing BigQuery table, excluding load_timestamp for CSV load."""
    table = client.get_table(table_ref)
    # Exclude load_timestamp since it's not in the CSV - we add it after loading
    return [field for field in table.schema if field.name != "load_timestamp"]


def truncate_table(client: bigquery.Client, table_ref: str) -> None:
    """Delete all rows from a table while preserving schema.

    Args:
        client: BigQuery client
        table_ref: Full table reference (project.dataset.table)
    """
    query = f"TRUNCATE TABLE `{table_ref}`"
    client.query(query).result()


def load_csv_to_bigquery(
    client: bigquery.Client,
    csv_path: Path,
    table_ref: str,
    truncate: bool = False,
) -> bigquery.LoadJob:
    """Load a CSV file to BigQuery table.

    Args:
        client: BigQuery client
        csv_path: Path to CSV file
        table_ref: Full table reference (project.dataset.table)
        truncate: If True, delete existing data first; otherwise append

    Returns:
        Completed load job
    """
    # Truncate first if requested (preserves table schema including load_timestamp)
    if truncate:
        truncate_table(client, table_ref)

    # Get schema from existing table (without load_timestamp - not in CSV)
    schema = get_table_schema(client, table_ref)

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,  # Skip header row
        allow_quoted_newlines=True,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    with open(csv_path, "rb") as f:
        load_job = client.load_table_from_file(f, table_ref, job_config=job_config)

    return load_job.result()


def add_load_timestamp(client: bigquery.Client, table_ref: str, timestamp: str) -> None:
    """Update all rows with NULL load_timestamp to the given timestamp.

    Args:
        client: BigQuery client
        table_ref: Full table reference (project.dataset.table)
        timestamp: ISO format timestamp string
    """
    query = f"""
    UPDATE `{table_ref}`
    SET load_timestamp = TIMESTAMP('{timestamp}')
    WHERE load_timestamp IS NULL
    """
    client.query(query).result()


def load_table(
    client: bigquery.Client,
    table_name: str,
    project: str,
    dataset: str,
    truncate: bool = False,
    dry_run: bool = False,
) -> dict:
    """Load a single table from CSV to BigQuery.

    Args:
        client: BigQuery client
        table_name: Table name (e.g., 'account_info')
        project: GCP project ID
        dataset: BigQuery dataset ID
        truncate: If True, replace existing data
        dry_run: If True, only show what would be done

    Returns:
        Dict with load results
    """
    csv_filename = TABLE_CSV_MAP.get(table_name)
    if not csv_filename:
        return {"table": table_name, "status": "error", "message": f"Unknown table: {table_name}"}

    csv_path = DATA_DIR / csv_filename
    if not csv_path.exists():
        return {"table": table_name, "status": "error", "message": f"CSV not found: {csv_path}"}

    table_ref = f"{project}.{dataset}.{table_name}"
    file_size_mb = csv_path.stat().st_size / (1024 * 1024)

    if dry_run:
        return {
            "table": table_name,
            "status": "dry_run",
            "csv_file": str(csv_path),
            "file_size_mb": round(file_size_mb, 2),
            "target": table_ref,
            "mode": "truncate" if truncate else "append",
        }

    print(f"Loading {table_name} ({file_size_mb:.1f} MB)...")

    try:
        load_timestamp = datetime.now(timezone.utc).isoformat()

        # Load CSV data
        job = load_csv_to_bigquery(client, csv_path, table_ref, truncate)

        # Add load_timestamp to new rows
        add_load_timestamp(client, table_ref, load_timestamp)

        return {
            "table": table_name,
            "status": "success",
            "rows_loaded": job.output_rows,
            "file_size_mb": round(file_size_mb, 2),
        }
    except Exception as e:
        return {"table": table_name, "status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Load DCAD CSV files to BigQuery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT,
        help=f"GCP project ID (default: {DEFAULT_PROJECT})",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=DEFAULT_DATASET,
        help=f"BigQuery dataset ID (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=list(TABLE_CSV_MAP.keys()),
        help="Specific tables to load (default: all)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate tables before loading (default: append)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be loaded without actually loading",
    )

    args = parser.parse_args()

    # Determine which tables to load
    tables_to_load = args.tables if args.tables else list(TABLE_CSV_MAP.keys())

    print(f"Project: {args.project}")
    print(f"Dataset: {args.dataset}")
    print(f"Mode: {'truncate' if args.truncate else 'append'}")
    print(f"Tables: {len(tables_to_load)}")
    print()

    client = None if args.dry_run else bigquery.Client(project=args.project)

    results = []
    for table_name in tables_to_load:
        result = load_table(
            client=client,
            table_name=table_name,
            project=args.project,
            dataset=args.dataset,
            truncate=args.truncate,
            dry_run=args.dry_run,
        )
        results.append(result)

        if args.dry_run:
            print(f"  {result['table']}: {result['csv_file']} ({result['file_size_mb']} MB)")
        elif result["status"] == "success":
            print(f"  {result['table']}: {result['rows_loaded']:,} rows loaded")
        else:
            print(f"  {result['table']}: ERROR - {result.get('message', 'Unknown error')}")

    # Summary
    print()
    success_count = sum(1 for r in results if r["status"] in ("success", "dry_run"))
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"Complete: {success_count} succeeded, {error_count} failed")

    if error_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
