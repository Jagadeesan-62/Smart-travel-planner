import argparse
import sys
import json
import logging
import os
from typing import Dict, Any

from smart_travel_planner.rag.config import DB_PATH, METADATA_MAPPING_PATH
from smart_travel_planner.rag import metadata_storage
from smart_travel_planner.rag import data_collection
from smart_travel_planner.rag import data_cleaning
from smart_travel_planner.rag import duplicate_detection
from smart_travel_planner.rag import faiss_index
from smart_travel_planner.rag import retrieval
from smart_travel_planner.rag import rag_generation

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RAGManager")

def handle_ingest(args):
    """Handles the ingestion of sample data into the database and vector indexes."""
    logger.info("Initializing metadata database...")
    metadata_storage.init_db()
    
    # 1. Get raw places
    raw_places = data_collection.get_sample_places()
    
    # Filter by scope if specified
    if args.scope:
        scope_filter = args.scope.lower().strip()
        raw_places = [p for p in raw_places if p.get("scope") == scope_filter]
        if not raw_places:
            logger.warning(f"No sample places found for scope '{args.scope}'.")
            return
            
    logger.info(f"Loaded {len(raw_places)} sample place records. Cleaning and deduplicating...")
    
    ingested_count = 0
    
    # 2. Load existing places to check for duplicates
    existing_places = metadata_storage.get_all_places()
    
    for raw in raw_places:
        cleaned = data_cleaning.clean_place_record(raw)
        if not cleaned:
            continue
            
        # Check for duplicates in existing database
        is_dup = False
        for existing in existing_places:
            if duplicate_detection.is_duplicate(cleaned, existing):
                # Merge records
                merged = duplicate_detection.merge_records(existing, cleaned)
                metadata_storage.save_place(merged)
                logger.info(f"Merged duplicate place: {cleaned['place_name']} with existing ID {existing['place_id']}")
                is_dup = True
                break
                
        if not is_dup:
            # Generate a stable ID and save as new
            place_id = duplicate_detection.generate_stable_id(
                cleaned["place_name"], cleaned["country"], cleaned["state_or_province"]
            )
            cleaned["place_id"] = place_id
            metadata_storage.save_place(cleaned)
            logger.info(f"Ingested new place: {cleaned['place_name']} with ID {place_id}")
            # Add to temporary lists to detect duplicates within the same batch
            existing_places.append(cleaned)
            ingested_count += 1
            
    logger.info(f"Ingestion of {ingested_count} new places completed. Rebuilding indices...")
    faiss_index.rebuild_all_indices()
    logger.info("Ingestion and indexing complete!")

def handle_rebuild(args):
    """Rebuilds the FAISS indexes from scratch using SQLite database records."""
    logger.info("Rebuilding all FAISS indices from SQLite database...")
    faiss_index.rebuild_all_indices()
    logger.info("FAISS indices successfully rebuilt!")

def handle_query(args):
    """Executes a search query and prints the synthesized RAG response."""
    # Build filter dictionary
    filters = {}
    if args.country: filters["country"] = args.country
    if args.state: filters["state"] = args.state
    if args.district: filters["district"] = args.district
    if args.city: filters["city"] = args.city
    if args.category: filters["category"] = args.category.split(",")
    if args.budget: filters["budget"] = args.budget
    if args.climate: filters["climate"] = args.climate
    if args.month: filters["best_month"] = args.month
    if args.family: filters["family_only"] = True
    if args.solo: filters["solo_only"] = True
    if args.activity: filters["activity"] = args.activity
    if args.accessible: filters["accessible_only"] = True
    if args.duration: filters["duration"] = args.duration
    
    if args.lat and args.lng and args.max_dist:
        filters["ref_coords"] = (float(args.lat), float(args.lng))
        filters["max_distance_km"] = float(args.max_dist)
        
    logger.info(f"Executing search for query: '{args.query}' | Scope: {args.scope or 'Hierarchical Fallback'}...")
    retrieved = retrieval.retrieve_tourist_places(
        query=args.query,
        scope=args.scope,
        limit=args.limit,
        filters=filters
    )
    
    if not retrieved:
        print("\n=== SEARCH RESULTS ===")
        print("No tourist places found matching the filters and query.")
        return
        
    logger.info(f"Retrieved {len(retrieved)} matching chunks. Generating RAG summary...")
    
    # Generate RAG response
    response = rag_generation.generate_rag_response(args.query, retrieved)
    
    print("\n" + "=" * 40)
    print("                RAG TRAVEL SUMMARY")
    print("=" * 40)
    print(response)
    print("=" * 40 + "\n")
    
    if args.debug:
        print("--- DEBUG RETRIEVED CHUNKS ---")
        for idx, res in enumerate(retrieved):
            print(f"{idx+1}. Place: {res['place']['place_name']} | Scope: {res['place']['scope']} | Score: {res['score']} | Match section: {res['matching_section']}")

def handle_status(args):
    """Displays the status of SQLite database and FAISS indexes."""
    metadata_storage.init_db()
    places = metadata_storage.get_all_places()
    
    print("\n" + "=" * 30)
    print("   TOURISM DATABASE STATUS")
    print("=" * 30)
    print(f"SQLite DB Path: {DB_PATH}")
    print(f"Total Places Ingested: {len(places)}")
    
    # Count by scope
    scopes = {"tamil_nadu": 0, "india": 0, "world": 0}
    for p in places:
        scopes[p["scope"]] = scopes.get(p["scope"], 0) + 1
        
    print("\nPlace Counts by Scope:")
    for scope, count in scopes.items():
        index_status = "Not Found"
        vector_count = 0
        index = faiss_index.load_faiss_index(scope)
        if index:
            index_status = "Available"
            vector_count = index.ntotal
        print(f" - {scope.upper():<12}: {count:<4} places | FAISS Index: {index_status:<10} ({vector_count} vector chunks)")
        
    mapping_status = "Not Found"
    if os.path.exists(METADATA_MAPPING_PATH):
        mapping_status = "Available"
        
    print(f"\nMetadata Mapping file: {mapping_status}")
    print("=" * 30 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Tourism RAG Database Command Line Manager")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    
    # 1. Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Ingest sample places and build indices")
    parser_ingest.add_argument("--scope", choices=["tamil_nadu", "india", "world"], help="Limit ingestion to a specific scope")
    
    # 2. Rebuild command
    parser_rebuild = subparsers.add_parser("rebuild", help="Rebuild all FAISS indices from scratch")
    
    # 3. Query command
    parser_query = subparsers.add_parser("query", help="Query the RAG database")
    parser_query.add_argument("query", type=str, help="Search query text")
    parser_query.add_argument("--scope", choices=["tamil_nadu", "india", "world"], help="Explicitly select index scope")
    parser_query.add_argument("--limit", type=int, default=3, help="Max number of places to retrieve")
    parser_query.add_argument("--debug", action="store_true", help="Print debug vector details")
    
    # Filters
    parser_query.add_argument("--country", type=str, help="Filter by country")
    parser_query.add_argument("--state", type=str, help="Filter by state or province")
    parser_query.add_argument("--district", type=str, help="Filter by district")
    parser_query.add_argument("--city", type=str, help="Filter by city")
    parser_query.add_argument("--category", type=str, help="Filter by category (comma-separated)")
    parser_query.add_argument("--budget", choices=["Budget", "Mid-range", "Luxury"], help="Filter by budget level")
    parser_query.add_argument("--climate", type=str, help="Filter by climate keyword")
    parser_query.add_argument("--month", type=str, help="Filter by best month to visit")
    parser_query.add_argument("--family", action="store_true", help="Filter for family suitability")
    parser_query.add_argument("--solo", action="store_true", help="Filter for solo suitability")
    parser_query.add_argument("--activity", type=str, help="Filter by activity type")
    parser_query.add_argument("--accessible", action="store_true", help="Filter for wheelchair accessibility")
    parser_query.add_argument("--duration", type=str, help="Filter by visit duration keyword")
    
    # Geospatial parameters
    parser_query.add_argument("--lat", type=float, help="Reference latitude for distance filter")
    parser_query.add_argument("--lng", type=float, help="Reference longitude for distance filter")
    parser_query.add_argument("--max-dist", type=float, help="Max distance limit in kilometers")
    
    # 4. Status command
    parser_status = subparsers.add_parser("status", help="Show database and index stats")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        handle_ingest(args)
    elif args.command == "rebuild":
        handle_rebuild(args)
    elif args.command == "query":
        handle_query(args)
    elif args.command == "status":
        handle_status(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
