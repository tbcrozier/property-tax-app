import asyncio
import json

import click
from sqlalchemy import text

from app.db import AsyncSessionLocal
from app.services.embed_service import embed_directory, optimize_vector_indexes
from app.services.loader_service import (
    load_building_characteristics_from_api,
    load_building_footprints,
    load_building_permits,
    load_cell_towers,
    load_correctional_facilities,
    load_rail_lines_from_api,
    load_crime_incidents_csv,
    load_flood_zones_csv,
    load_flood_zones_from_api,
    load_flood_zones_from_json,
    load_parcels_from_api,
    load_police_reporting_areas as load_police_reporting_areas_svc,
    load_postsecondary_schools,
    load_private_schools,
    load_public_schools,
    load_school_performance_csv,
    load_school_poverty_estimates,
    load_zoning_districts,
)
from app.services.signals_service import compute_parcel_signals
from app.services.analytics_service import (
    identify_knowledge_gaps,
    update_query_metrics,
    get_metrics_dashboard,
    get_low_rating_queries,
    suggest_doc_improvements,
)


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
@click.option("--school-performance", default="data/csv/school_performance.csv")
@click.option("--crime-incidents", default="data/csv/crime_incidents.csv")
@click.option("--police-reporting-areas", default="data/csv/police_reporting_areas.csv")
def load_csvs(permits, footprints, towers, floods, zoning, school_performance, crime_incidents, police_reporting_areas):
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
            n = await load_school_performance_csv(db, school_performance)
            print(f"School performance: {n}")
            n = await load_crime_incidents_csv(db, crime_incidents)
            print(f"Crime incidents: {n}")
            n = await load_police_reporting_areas_svc(db, police_reporting_areas)
            print(f"Police reporting areas: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--docs-dir", default="data/knowledge")
def embed_docs(docs_dir):
    """Embed all markdown knowledge documents into vector store."""

    async def run():
        async with AsyncSessionLocal() as db:
            results = await embed_directory(db, docs_dir)
            total_chunks = sum(results.values())
            print(f"Embedded {len(results)} files, {total_chunks} total chunks")
            
            # Optimize vector indexes after embedding
            await optimize_vector_indexes(db)
            print("Vector indexes optimized")

    asyncio.run(run())


@cli.command()
def kb_status():
    """Check knowledge base status and statistics."""

    async def run():
        async with AsyncSessionLocal() as db:
            # Get document statistics
            result = await db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_chunks,
                        COUNT(DISTINCT source) as total_documents,
                        AVG(LENGTH(content)) as avg_chunk_length,
                        MIN(LENGTH(content)) as min_chunk_length,
                        MAX(LENGTH(content)) as max_chunk_length
                    FROM documents
                """)
            )
            stats = result.first()
            
            if stats.total_chunks == 0:
                print("❌ Knowledge base is empty. Run 'embed-docs' to populate it.")
                return
            
            print("✅ Knowledge base status:")
            print(f"   Documents: {stats.total_documents}")
            print(f"   Total chunks: {stats.total_chunks}")
            print(f"   Avg chunk length: {stats.avg_chunk_length:.0f} chars")
            print(f"   Chunk length range: {stats.min_chunk_length} - {stats.max_chunk_length} chars")
            
            # Check if indexes exist
            index_result = await db.execute(
                text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'documents' AND indexname LIKE '%embedding%'
                """)
            )
            indexes = [row.indexname for row in index_result.fetchall()]
            print(f"   Vector indexes: {', '.join(indexes) if indexes else 'None'}")

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
@click.option("--truncate", is_flag=True, default=False)
def load_schools(truncate: bool):
    """Load all school datasets from NCES EDGE APIs."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_public_schools(db, truncate=truncate)
            print(f"Public schools: {n}")
            n = await load_postsecondary_schools(db, truncate=truncate)
            print(f"Postsecondary schools: {n}")
            n = await load_private_schools(db, truncate=truncate)
            print(f"Private schools: {n}")
            n = await load_school_poverty_estimates(db, truncate=truncate)
            print(f"School poverty estimates: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--path", default="data/csv/school_performance.csv")
def load_school_performance(path: str):
    """Load school quality metrics from CSV."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_school_performance_csv(db, path)
            print(f"School performance records loaded: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--path", default="data/csv/crime_incidents.csv")
def load_crime_incidents(path: str):
    """Load crime incident data from CSV."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_crime_incidents_csv(db, path)
            print(f"Crime incidents loaded: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--path", default="data/csv/police_reporting_areas.csv")
def load_police_reporting_areas(path: str):
    """Load police reporting area boundaries from CSV."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_police_reporting_areas_svc(db, path)
            print(f"Police reporting areas loaded: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--truncate", is_flag=True, default=False)
def load_corrections(truncate: bool):
    """Load correctional facilities from USGS National Map."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_correctional_facilities(db, truncate=truncate)
            print(f"Correctional facilities: {n}")

    asyncio.run(run())


@cli.command()
@click.argument("path")
@click.option("--truncate", is_flag=True, default=False)
def load_flood_zones_json(path: str, truncate: bool):
    """Load flood zones from a newline-delimited JSON file (from load_floodzone.py)."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_flood_zones_from_json(db, path, truncate=truncate)
            print(f"Flood zones loaded: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--truncate", is_flag=True, default=False)
def load_rail_lines(truncate: bool):
    """Load NARN rail lines for Davidson County from BTS NTAD API."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_rail_lines_from_api(db, truncate=truncate)
            print(f"Rail lines loaded: {n}")

    asyncio.run(run())


@cli.command()
@click.option("--truncate", is_flag=True, default=False)
def load_flood_zones_api(truncate: bool):
    """Load FEMA NFHL flood zones for Davidson County from API."""

    async def run():
        async with AsyncSessionLocal() as db:
            n = await load_flood_zones_from_api(db, truncate=truncate)
            print(f"Flood zones loaded: {n}")

    asyncio.run(run())


@cli.command()
def load_all():
    """Run all load steps in sequence."""

    async def run():
        async with AsyncSessionLocal() as db:
            print("Step 1/7: Loading parcels from ArcGIS...")
            n = await load_parcels_from_api(db)
            print(f"  -> {n} parcels")

            print("Step 2/7: Loading building characteristics from ArcGIS...")
            n = await load_building_characteristics_from_api(db)
            print(f"  -> {n} records")

            print("Step 3/7: Loading school datasets from NCES EDGE...")
            n = await load_public_schools(db)
            print(f"  -> Public schools: {n}")
            n = await load_postsecondary_schools(db)
            print(f"  -> Postsecondary schools: {n}")
            n = await load_private_schools(db)
            print(f"  -> Private schools: {n}")
            n = await load_school_poverty_estimates(db)
            print(f"  -> School poverty estimates: {n}")


            print("Step 4/7: Loading correctional facilities...")
            n = await load_correctional_facilities(db)
            print(f"  -> Correctional facilities: {n}")

            print("Step 5/7: Loading CSV datasets...")
            # These paths assume CSVs are in data/csv/
            import os

            csv_dir = "data/csv"
            csv_loaders = [
                ("building_permits.csv", load_building_permits),
                ("building_footprints.csv", load_building_footprints),
                ("cell_towers.csv", load_cell_towers),
                ("flood_zones.csv", load_flood_zones_csv),
                ("zoning_districts.csv", load_zoning_districts),
                ("school_performance.csv", load_school_performance_csv),
                ("crime_incidents.csv", load_crime_incidents_csv),
                ("police_reporting_areas.csv", load_police_reporting_areas_svc),
            ]
            for fname, loader_fn in csv_loaders:
                path = os.path.join(csv_dir, fname)
                if os.path.exists(path):
                    n = await loader_fn(db, path)
                    print(f"  -> {fname}: {n} records")
                else:
                    print(f"  -> {fname}: SKIPPED (not found)")

            print("Step 6/7: Embedding knowledge documents...")
            results = await embed_directory(db, "data/knowledge")
            for src, count in results.items():
                print(f"  -> {src}: {count} chunks")

            print("Step 7/7: Computing parcel signals...")
            n = await compute_parcel_signals(db)
            print(f"  -> {n} signals computed")

            print("\nDone! All data loaded.")

    asyncio.run(run())


# ============ ANALYTICS & VALIDATION COMMANDS ============


@cli.command()
def analyze_metrics():
    """Recalculate and display query performance metrics."""

    async def run():
        async with AsyncSessionLocal() as db:
            print("Updating query metrics...")
            await update_query_metrics(db)
            
            dashboard = await get_metrics_dashboard(db)
            
            print("\n=== ANALYTICS DASHBOARD ===")
            print(f"Total queries: {dashboard['total_queries']}")
            print(f"Average rating: {dashboard['avg_rating']}/5")
            print(f"Queries with low ratings (<3): {dashboard['low_rating_queries']}")
            print(f"System health score: {dashboard['health_score']}%")
            
            if dashboard['worst_patterns']:
                print("\n[LOWEST PERFORMING PATTERNS]")
                for pattern in dashboard['worst_patterns']:
                    print(f"  - '{pattern['pattern']}': {pattern['avg_rating']}/5 ({pattern['count']} queries)")
            
            if dashboard['best_patterns']:
                print("\n[HIGHEST PERFORMING PATTERNS]")
                for pattern in dashboard['best_patterns']:
                    print(f"  - '{pattern['pattern']}': {pattern['avg_rating']}/5 ({pattern['count']} queries)")

    asyncio.run(run())


@cli.command()
@click.option("--min-rating", default=2.5, help="Rating threshold for gaps")
@click.option("--min-count", default=3, help="Minimum query count to flag")
def identify_gaps(min_rating: float, min_count: int):
    """Identify knowledge base gaps from low-rated queries."""

    async def run():
        async with AsyncSessionLocal() as db:
            print("Identifying knowledge base gaps...")
            gaps = await identify_knowledge_gaps(
                db=db,
                min_query_count=min_count,
                min_avg_rating=min_rating
            )
            
            if not gaps:
                print("No knowledge gaps identified. System performing well!")
                return
            
            print(f"\n=== IDENTIFIED KNOWLEDGE GAPS ({len(gaps)}) ===")
            for gap in gaps:
                print(f"\nTopic: {gap['topic']}")
                print(f"  Avg Rating: {gap['avg_rating']}/5")
                print(f"  Occurrences: {gap['query_count']}")
                print(f"  Action: {gap['suggested_action']}")
                print(f"  Examples: {', '.join(gap['sample_queries'][:2])}...")

    asyncio.run(run())


@cli.command()
@click.option("--days", default=7, help="Look back N days")
def show_low_rated(days: int):
    """Show queries with low user ratings (for investigation)."""

    async def run():
        async with AsyncSessionLocal() as db:
            queries = await get_low_rating_queries(db=db, min_rating=3, days=days)
            
            if not queries:
                print(f"No low-rated queries in the last {days} days. Great!")
                return
            
            print(f"\n=== LOW-RATED QUERIES (past {days} days) ===")
            print(f"Total: {len(queries)}\n")
            
            for q in queries[:10]:  # Show top 10
                print(f"Rating: {q.rating}/5 | ParcelID: {q.parcel_id or 'None'}")
                print(f"Query: {q.query_text[:100]}...")
                if q.comments:
                    print(f"Comments: {q.comments}")
                print()

    asyncio.run(run())


@cli.command()
@click.option("--min-rating", default=2.0, help="Rating threshold for improvements")
@click.option("--min-count", default=5, help="Minimum query count to consider")
def suggest_doc_updates(min_rating: float, min_count: int):
    """Suggest improvements to knowledge documents based on feedback."""

    async def run():
        async with AsyncSessionLocal() as db:
            print("Analyzing feedback for document improvement suggestions...")
            suggestions = await suggest_doc_improvements(
                db=db,
                min_query_count=min_count,
                min_avg_rating=min_rating
            )
            
            if not suggestions:
                print("No document improvement suggestions at this time. Knowledge base performing well!")
                return
            
            print(f"\n=== DOCUMENT IMPROVEMENT SUGGESTIONS ({len(suggestions)}) ===")
            for sugg in suggestions:
                print(f"\nTopic: {sugg['topic']} (Priority: {sugg['priority']})")
                print(f"  Avg Rating: {sugg['avg_rating']}/5")
                print(f"  Query Count: {sugg['query_count']}")
                print(f"  Suggested Doc: {sugg['suggested_doc']}")
                print(f"  Sample Queries: {', '.join(sugg['sample_queries'][:2])}...")
                print("  Improvements:")
                for imp in sugg['suggested_improvements']:
                    print(f"    - {imp}")

    asyncio.run(run())


@cli.command()
@click.option("--test-file", required=True, help="JSON file with test queries")
def validate_queries(test_file: str):
    """
    Re-test historical queries to validate improvements.
    
    Test file format:
    [
        {"query": "Is RS5 lot smaller than 4000 sq ft compliant?", "parcel_id": "101-0123"},
        ...
    ]
    """

    async def run():
        from app.services.chat_service import handle_chat
        from app.schemas import ChatRequest, ChatMessage
        
        # Load test queries
        with open(test_file) as f:
            test_queries = json.load(f)
        
        async with AsyncSessionLocal() as db:
            print(f"Running {len(test_queries)} validation queries...\n")
            
            results = []
            for i, test in enumerate(test_queries, 1):
                try:
                    # Create chat request
                    message = ChatMessage(role="user", content=test["query"])
                    request = ChatRequest(
                        messages=[message],
                        parcel_id=test.get("parcel_id")
                    )
                    
                    # Run query
                    response = await handle_chat(db, request)
                    
                    # Log for metrics
                    from app.services.analytics_service import log_query_performance
                    await log_query_performance(
                        db=db,
                        query_text=test["query"],
                        response_text=response.answer,
                        parcel_id=test.get("parcel_id"),
                        retrieved_docs=response.sources,
                    )
                    
                    results.append({
                        "query": test["query"][:50],
                        "success": True,
                        "sources": len(response.sources),
                        "answer_length": len(response.answer),
                    })
                    
                    print(f"✓ {i}/{len(test_queries)}: {test['query'][:60]}...")
                except Exception as e:
                    results.append({
                        "query": test["query"][:50],
                        "success": False,
                        "error": str(e),
                    })
                    print(f"✗ {i}/{len(test_queries)}: {test['query'][:60]}...")
                    print(f"  Error: {str(e)}\n")
            
            # Summary
            passed = sum(1 for r in results if r["success"])
            print(f"\n=== VALIDATION RESULTS ===")
            print(f"Passed: {passed}/{len(test_queries)}")
            print(f"Success rate: {round(100*passed/len(test_queries), 1)}%")

    asyncio.run(run())


if __name__ == "__main__":
    cli()
