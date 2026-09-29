import unittest
import os
import json
import logging
from typing import Dict, Any

from smart_travel_planner.rag import config
from smart_travel_planner.rag import metadata_storage
from smart_travel_planner.rag import data_cleaning
from smart_travel_planner.rag import duplicate_detection
from smart_travel_planner.rag import document_chunking
from smart_travel_planner.rag import embeddings
from smart_travel_planner.rag import faiss_index
from smart_travel_planner.rag import retrieval
from smart_travel_planner.rag import rag_generation
from smart_travel_planner.rag import data_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGTest")

class TestTourismRAG(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up testing context."""
        cls.original_db_path = config.DB_PATH
        config.DB_PATH = os.path.join(config.DATA_DIR, "tourism_test.db")
        metadata_storage.DB_PATH = config.DB_PATH
        
        # Override embeddings helpers in the modules where they were imported
        cls.original_faiss_get_embeddings_batch = faiss_index.get_embeddings_batch
        cls.original_retrieval_get_embedding = retrieval.get_embedding
        
        def mock_get_embedding(text, task_type="retrieval_document"):
            # Simple mock: if text contains Ooty/hill/Eiffel, return distinct vectors for similarity tests
            vec = [0.0] * 768
            lower_text = text.lower()
            if "marina" in lower_text:
                vec[2] = 1.0
            elif "ooty" in lower_text or "hill station" in lower_text:
                vec[0] = 1.0
            elif "eiffel" in lower_text or "paris" in lower_text or "france" in lower_text or "international" in lower_text or "beach" in lower_text:
                vec[1] = 1.0
            return vec
            
        def mock_get_embeddings_batch(texts, task_type="retrieval_document"):
            return [mock_get_embedding(t, task_type) for t in texts]
            
        faiss_index.get_embeddings_batch = mock_get_embeddings_batch
        retrieval.get_embedding = mock_get_embedding
        
        # Remove old test DB if exists
        if os.path.exists(config.DB_PATH):
            try:
                os.remove(config.DB_PATH)
            except Exception:
                pass
                
        logger.info(f"Initializing test database at {config.DB_PATH}...")
        metadata_storage.init_db()

    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        # Restore mock functions
        faiss_index.get_embeddings_batch = cls.original_faiss_get_embeddings_batch
        retrieval.get_embedding = cls.original_retrieval_get_embedding
        
        test_db = config.DB_PATH
        config.DB_PATH = cls.original_db_path
        metadata_storage.DB_PATH = cls.original_db_path
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass

    def test_01_cleaning_and_normalization(self):
        """Test record cleaning, casing, and normalization."""
        raw_place = {
            "place_name": "  maRINa BEAcH   ",
            "country": "InDiA",
            "state_or_province": "tamil nadu",
            "latitude": "13.0500",
            "longitude": "80.2824",
            "tourist_category": ["BEACH", "Nature"],
            "short_description": "Clean long beach in Chennai",
            "source_url": "invalid-url", # Should be cleaned or empty
            "source_name": "Test Source",
            "last_verified_date": "2026-08-31"
        }
        
        cleaned = data_cleaning.clean_place_record(raw_place)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned["place_name"], "Marina Beach")
        self.assertEqual(cleaned["country"], "India")
        self.assertEqual(cleaned["state_or_province"], "Tamil Nadu")
        self.assertEqual(cleaned["latitude"], 13.0500)
        self.assertEqual(cleaned["longitude"], 80.2824)
        self.assertEqual(cleaned["tourist_category"], ["beach", "nature"])
        self.assertEqual(cleaned["source_url"], "") # Cleared since it is invalid
        self.assertEqual(cleaned["scope"], "tamil_nadu") # Standardized based on state

    def test_02_duplicate_detection_and_merging(self):
        """Test proximity duplicate verification and field merging."""
        place_a = {
            "place_name": "Ooty Lake",
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "latitude": 11.4082,
            "longitude": 76.6896,
            "major_attractions": ["Boating"],
            "source_name": "Source A"
        }
        
        place_b = {
            "place_name": "Ooty Boat House",
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "latitude": 11.4085, # 300 meters away
            "longitude": 76.6900,
            "alternative_names": ["Ooty Lake"],
            "major_attractions": ["Row boats", "Speed boats"],
            "source_name": "Source B"
        }
        
        # Check duplicate
        self.assertTrue(duplicate_detection.is_duplicate(place_a, place_b))
        
        # Merge
        merged = duplicate_detection.merge_records(place_a, place_b)
        self.assertIn("Boating", merged["major_attractions"])
        self.assertIn("Row boats", merged["major_attractions"])
        self.assertEqual(merged["source_name"], "Source A, Source B")

    def test_03_chunking(self):
        """Test chunking creates exactly 8 sections if fields are fully populated."""
        sample_place = {
            "place_id": "test_id_123",
            "place_name": "Test Destination",
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "tourist_category": ["temple"],
            "short_description": "Short desc",
            "detailed_description": "Detailed desc",
            "historical_cultural_importance": "History details",
            "major_attractions": ["A1"],
            "available_activities": ["Act1"],
            "best_time_to_visit": "Winter",
            "weather_climate_info": "Cool",
            "nearest_airport": "A1 Airport",
            "nearest_railway_station": "R1 Rail",
            "road_accessibility": "Good",
            "local_transport_options": "Autos",
            "nearby_hotels": ["H1"],
            "local_food_restaurants": ["R1"],
            "approximate_budget_category": "Budget",
            "entry_fee": "Free",
            "opening_closing_hours": "9-5",
            "weekly_closing_day": "Monday",
            "safety_notes": "Safe",
            "required_permits": "None",
            "nearby_tourist_places": ["N1"],
            "source_url": "https://example.com",
            "source_name": "Src",
            "last_verified_date": "2026-08-31",
            "scope": "tamil_nadu",
            "latitude": 11.0,
            "longitude": 77.0
        }
        
        chunks = document_chunking.chunk_place_record(sample_place)
        self.assertEqual(len(chunks), 8)
        
        # Check specific section headers and formats
        sections = [c["section"] for c in chunks]
        self.assertIn("overview_and_importance", sections)
        self.assertIn("attractions_and_activities", sections)
        self.assertIn("weather_and_best_time", sections)
        self.assertIn("transport_and_accessibility", sections)
        self.assertIn("accommodation_and_food", sections)
        self.assertIn("budget_and_entry", sections)
        self.assertIn("safety_and_permits", sections)
        self.assertIn("nearby_places", sections)

    def test_04_embedding_retrieval_and_filtering(self):
        """Test search retrieval hierarchy and filters."""
        # 1. Ingest sample data to run mock queries
        logger.info("Setting up database with sample records...")
        raw_places = data_collection.get_sample_places()
        for raw in raw_places:
            cleaned = data_cleaning.clean_place_record(raw)
            if cleaned:
                # Generate stable ID
                pid = duplicate_detection.generate_stable_id(
                    cleaned["place_name"], cleaned["country"], cleaned["state_or_province"]
                )
                cleaned["place_id"] = pid
                metadata_storage.save_place(cleaned)
                
        # Rebuild FAISS indexes
        faiss_index.rebuild_all_indices()
        
        # Test Query 1: Best hill stations in Tamil Nadu for a family trip
        res1 = retrieval.retrieve_tourist_places(
            query="Best hill stations in Tamil Nadu for a family trip",
            scope="tamil_nadu",
            filters={"category": "nature", "family_only": True}
        )
        self.assertTrue(len(res1) > 0)
        self.assertEqual(res1[0]["place"]["place_name"], "Ooty Botanical Gardens")
        
        # Test Query 2: High budget beach international destinations
        res2 = retrieval.retrieve_tourist_places(
            query="Affordable international beach destinations",
            scope="world",
            filters={"country": "France", "budget": "Luxury"}
        )
        self.assertTrue(len(res2) > 0)
        self.assertEqual(res2[0]["place"]["place_name"], "Eiffel Tower")

        # Test RAG Generation
        summary = rag_generation.generate_rag_response(
            query="Scenic parks in Ooty",
            retrieved_results=[res1[0]]
        )
        self.assertIn("Ooty Botanical Gardens", summary)
        self.assertIn("Tamil Nadu", summary)
        self.assertIn("Main Attractions", summary)

def run_sample_user_queries():
    """Runs and logs the user's specific sample queries requested in the prompt."""
    queries = [
        ("Best hill stations in Tamil Nadu for a family trip", {"scope": "tamil_nadu", "filters": {"category": "nature", "family_only": True}}),
        ("Tourist places near Chennai within ₹15,000", {"scope": "tamil_nadu", "filters": {"city": "Chennai", "budget": "Budget"}}),
        ("Adventure destinations in India during December", {"scope": "india", "filters": {"month": "December"}}),
        ("Affordable international beach destinations", {"scope": "world", "filters": {"category": "beach"}}),
        ("Historical places in Rajasthan", {"scope": "india", "filters": {"state": "Rajasthan"}}),
        ("Waterfalls near Coimbatore", {"scope": "tamil_nadu", "filters": {"district": "Coimbatore"}}),
        ("Three-day honeymoon destinations with cool weather", {"filters": {"climate": "cool"}})
    ]
    
    print("\n" + "=" * 50)
    print("      RUNNING USER SAMPLE RAG QUERIES")
    print("=" * 50)
    
    for q_text, opts in queries:
        scope = opts.get("scope")
        filters = opts.get("filters", {})
        
        print(f"\nQUERY: \"{q_text}\" (Scope: {scope or 'Hierarchical Fallback'}, Filters: {filters})")
        retrieved = retrieval.retrieve_tourist_places(query=q_text, scope=scope, limit=2, filters=filters)
        
        if not retrieved:
            print(" -> [No results found in mock dataset for these exact filters]")
            continue
            
        print(f" -> Found {len(retrieved)} place match(es):")
        for idx, r in enumerate(retrieved):
            print(f"    {idx+1}. {r['place']['place_name']} ({r['place']['city']}, {r['place']['state_or_province']}) | Match Section: {r['matching_section']} | Score: {r['score']}")
            
        # Run generative synthesis (displays first place details)
        summary = rag_generation.generate_rag_response(q_text, retrieved)
        print("\n--- Generative RAG Response ---\n")
        print(summary[:500] + "\n... (truncated for preview)\n")

if __name__ == "__main__":
    unittest.main(exit=False)
    run_sample_user_queries()
