import asyncio

import click

from app.db import AsyncSessionLocal
from app.services.embed_service import embed_directory
from app.services.loader_service import (
    load_building_characteristics_from_api,
    load_building_footprints,
    load_building_permits,
    load_cell_towers,
    load_flood_zones_csv,
    load_parcels_from_api,
    load_zoning_districts,
)
from app.services.signals_service import compute_parcel_signals


@click.group()
def cli():
    pass


@cli.command()
@click.option("--truncate", is_flag=True, default=False)
@click.option("--total", default=286000)
def load_parcels(truncate: bool, total: int):
    """Load parcels from ArcGIS API."""

    async def run():
        async with AsyncSessionLocal() as db:
            count = await load_parcels_from_api(db, total=total, truncate=truncate)
            print(f"Loaded {count} parcels")

    asyncio.run(run())


@cli.command()
@click.option("--truncate", is_flag=True, default=False)
def load_building_chars(truncate: bool):
    """Load building characteristics from ArcGIS API."""

    async def run():
        async with AsyncSessionLocal() as db:
            count = await load_building_characteristics_from_api(db, truncate=truncate)
            print(f"Loaded {count} building characteristics")

    asyncio.run(run())


@cli.command()
@click.option("--permits", default="data/csv/building_permits.csv")
@click.option("--footprints", default="data/csv/building_footprints.csv")
@click.option("--towers", default="data/csv/cell_towers.csv")
@click.option("--floods", default="data/csv/flood_zones.csv")
@click.option("--zoning", default="data/csv/zoning_districts.csv")
def load_csvs(permits, footprints, towers, floods, zoning):
    """Load all CSV datasets into the database."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_building_permits(db, permits)
            print(f"Permits: {n}")
            n = await load_building_footprints(db, footprints)
            print(f"Footprints: {n}")
            n = await load_cell_towers(db, towers)
            print(f"Cell towers: {n}")
            n = await load_flood_zones_csv(db, floods)
            print(f"Flood zones: {n}")
            n = await load_zoning_districts(db, zoning)
            print(f"Zoning districts: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--docs-dir", default="data/knowledge")
def embed_docs(docs_dir):
    """Embed all markdown knowledge documents into vector store."""

    async def run():
        async with AsyncSessionLocal() as db:
            results = await embed_directory(db, docs_dir)
            for src, count in results.items():
                print(f"{src}: {count} chunks")

    asyncio.run(run())


@cli.command()
def compute_signals():
    """Pre-compute parcel appeal signals."""

    async def run():
        async with AsyncSessionLocal() as db:
            count = await compute_parcel_signals(db)
            print(f"Computed signals for {count} parcels")

    asyncio.run(run())


@cli.command()
def load_all():
    """Run all load steps in sequence."""

    async def run():
        async with AsyncSessionLocal() as db:
            print("Step 1/5: Loading parcels from ArcGIS...")
            n = await load_parcels_from_api(db)
            print(f"  -> {n} parcels")

            print("Step 2/5: Loading building characteristics from ArcGIS...")
            n = await load_building_characteristics_from_api(db)
            print(f"  -> {n} records")

            print("Step 3/5: Loading CSV datasets...")
            # These paths assume CSVs are in data/csv/
            import os

            csv_dir = "data/csv"
            csv_loaders = [
                ("building_permits.csv", load_building_permits),
                ("building_footprints.csv", load_building_footprints),
                ("cell_towers.csv", load_cell_towers),
                ("flood_zones.csv", load_flood_zones_csv),
                ("zoning_districts.csv", load_zoning_districts),
            ]
            for fname, loader_fn in csv_loaders:
                path = os.path.join(csv_dir, fname)
                if os.path.exists(path):
                    n = await loader_fn(db, path)
                    print(f"  -> {fname}: {n} records")
                else:
                    print(f"  -> {fname}: SKIPPED (not found)")

            print("Step 4/5: Embedding knowledge documents...")
            results = await embed_directory(db, "data/knowledge")
            for src, count in results.items():
                print(f"  -> {src}: {count} chunks")

            print("Step 5/5: Computing parcel signals...")
            n = await compute_parcel_signals(db)
            print(f"  -> {n} signals computed")

            print("\nDone! All data loaded.")

    asyncio.run(run())


if __name__ == "__main__":
    cli()
