import numpy as np
import logging
import faiss
from typing import List, Dict, Any, Optional
from smart_travel_planner.rag.embeddings import get_embedding
from smart_travel_planner.rag.faiss_index import load_faiss_index
from smart_travel_planner.rag.metadata_storage import get_chunk_by_vector_id
from smart_travel_planner.rag.duplicate_detection import haversine_distance

logger = logging.getLogger(__name__)

def match_filter(place: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Evaluates if a place matches all the specified query filters."""
    if not filters:
        return True
        
    # 1. Country filter
    if "country" in filters and filters["country"]:
        val = filters["country"].lower()
        if val not in place.get("country", "").lower():
            return False
            
    # 2. State filter
    if "state" in filters and filters["state"]:
        val = filters["state"].lower()
        if val not in place.get("state_or_province", "").lower():
            return False
            
    # 3. District filter
    if "district" in filters and filters["district"]:
        val = filters["district"].lower()
        if val not in place.get("district", "").lower():
            return False
            
    # 4. City filter
    if "city" in filters and filters["city"]:
        val = filters["city"].lower()
        if val not in place.get("city", "").lower():
            return False
            
    # 5. Tourist category filter
    if "category" in filters and filters["category"]:
        # Category can be a string or a list
        val_cat = filters["category"]
        if isinstance(val_cat, str):
            val_cats = [val_cat.lower()]
        else:
            val_cats = [c.lower() for c in val_cat]
            
        place_cats = [c.lower() for c in place.get("tourist_category", [])]
        # Match if any filtered category matches
        if not any(c in place_cats for c in val_cats):
            return False
            
    # 6. Budget level filter (Budget, Mid-range, Luxury)
    if "budget" in filters and filters["budget"]:
        val = filters["budget"].lower()
        if val not in place.get("approximate_budget_category", "").lower():
            return False
            
    # 7. Climate filter (e.g. 'cool', 'tropical', 'hilly')
    if "climate" in filters and filters["climate"]:
        val = filters["climate"].lower()
        weather_info = place.get("weather_climate_info", "").lower()
        desc = place.get("detailed_description", "").lower()
        if val not in weather_info and val not in desc:
            return False
            
    # 8. Best visiting month filter
    if "best_month" in filters and filters["best_month"]:
        val = filters["best_month"].lower()
        best_time = place.get("best_time_to_visit", "").lower()
        if val not in best_time:
            return False
            
    # 9. Suitability filters
    if filters.get("family_only") and not place.get("family_suitability"):
        return False
    if filters.get("solo_only") and not place.get("solo_travel_suitability"):
        return False
        
    # 10. Activity type filter
    if "activity" in filters and filters["activity"]:
        val_act = filters["activity"].lower()
        activities = [a.lower() for a in place.get("available_activities", [])]
        if not any(val_act in act for act in activities):
            return False
            
    # 11. Accessibility filter
    if filters.get("accessible_only"):
        access_info = place.get("accessibility_information", "").lower()
        if "wheelchair" not in access_info and "ramp" not in access_info and "accessible" not in access_info:
            return False
            
    # 12. Maximum distance filter (requires reference coordinates and max km)
    if "max_distance_km" in filters and "ref_coords" in filters:
        max_dist = float(filters["max_distance_km"])
        ref_lat, ref_lng = filters["ref_coords"]
        
        place_lat = place.get("latitude")
        place_lng = place.get("longitude")
        
        if place_lat is not None and place_lng is not None:
            dist = haversine_distance(ref_lat, ref_lng, place_lat, place_lng)
            if dist > max_dist:
                return False
        else:
            return False
            
    # 13. Suggested visit duration (e.g. 'days', 'hours')
    if "duration" in filters and filters["duration"]:
        val = filters["duration"].lower()
        dur = place.get("recommended_visit_duration", "").lower()
        if val not in dur:
            return False
            
    return True

def search_index_for_scope(
    query_vector: np.ndarray, 
    scope: str, 
    k: int = 10, 
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Loads a specific FAISS index, queries it, applies filters, and returns ranked records."""
    index = load_faiss_index(scope)
    if index is None or index.ntotal == 0:
        return []
        
    # Search FAISS index
    # query_vector must be normalized and 2D
    query_vector_2d = np.array([query_vector], dtype=np.float32)
    faiss.normalize_L2(query_vector_2d)
    
    similarities, indices = index.search(query_vector_2d, k)
    
    results = []
    seen_places = set()
    
    for score, idx in zip(similarities[0], indices[0]):
        if idx == -1:
            continue
            
        # Get chunk and metadata from SQLite
        chunk_data = get_chunk_by_vector_id(int(idx), scope)
        if not chunk_data:
            continue
            
        place_id = chunk_data["place_id"]
        
        # Deduplicate same place across multiple chunk matches
        if place_id in seen_places:
            continue
            
        # Check filters
        if not match_filter(chunk_data, filters):
            continue
            
        seen_places.add(place_id)
        
        # Calculate final boosted ranking score
        final_score = float(score)
        
        # Apply ranking boosts
        # City match boost
        if filters and "city" in filters and filters["city"]:
            if filters["city"].lower() in chunk_data.get("city", "").lower():
                final_score += 0.2
        # Country match boost
        if filters and "country" in filters and filters["country"]:
            if filters["country"].lower() in chunk_data.get("country", "").lower():
                final_score += 0.1
        # Data freshness / confidence boost
        confidence = chunk_data.get("confidence_score", 1.0)
        final_score += 0.05 * confidence
        
        results.append({
            "place": chunk_data,
            "matching_section": chunk_data["section"],
            "matching_chunk_content": chunk_data["content"],
            "score": round(final_score, 4),
            "faiss_similarity": round(float(score), 4)
        })
        
    return results

def retrieve_tourist_places(
    query: str, 
    scope: Optional[str] = None, 
    limit: int = 5, 
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Retrieves ranked tourist places using hierarchical fallback search and filters."""
    # Convert query text to embedding
    logger.info(f"Generating query embedding for search: '{query}'")
    query_vector = get_embedding(query, task_type="retrieval_query")
    
    results = []
    
    # 1. Scope selection
    if scope:
        scope = scope.lower().strip()
        if scope in ["tamil_nadu", "india", "world"]:
            results = search_index_for_scope(query_vector, scope, k=limit * 2, filters=filters)
    else:
        # If no scope is selected, search hierarchically: Tamil Nadu -> India -> World
        # Combine results from all indices but deduplicate across indices.
        seen_place_ids = set()
        
        for cur_scope in ["tamil_nadu", "india", "world"]:
            logger.info(f"Hierarchical fallback: querying scope '{cur_scope}'...")
            scope_results = search_index_for_scope(query_vector, cur_scope, k=limit * 2, filters=filters)
            
            for res in scope_results:
                pid = res["place"]["place_id"]
                if pid not in seen_place_ids:
                    seen_place_ids.add(pid)
                    results.append(res)
                    
            if len(results) >= limit:
                break
                
    # Sort final combined results by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
