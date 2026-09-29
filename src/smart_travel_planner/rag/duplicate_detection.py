import math
import hashlib
from typing import Dict, Any, List

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points in kilometers."""
    # Radius of the Earth in km
    R = 6371.0
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
        
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def generate_stable_id(name: str, country: str, state: str) -> str:
    """Generates a stable, reproducible 16-character hexadecimal place ID."""
    clean_key = f"{name.strip().lower()}_{country.strip().lower()}_{state.strip().lower()}"
    hasher = hashlib.sha256(clean_key.encode('utf-8'))
    return hasher.hexdigest()[:16]

def is_duplicate(place1: Dict[str, Any], place2: Dict[str, Any], threshold_km: float = 1.0) -> bool:
    """Checks if two places are duplicates based on name match and coordinate proximity."""
    name1 = place1["place_name"].lower()
    name2 = place2["place_name"].lower()
    
    # Direct name match
    name_match = (name1 == name2) or (name1 in name2) or (name2 in name1)
    
    if not name_match:
        # Also check alternative names
        alt1 = [n.lower() for n in place1.get("alternative_names", [])]
        alt2 = [n.lower() for n in place2.get("alternative_names", [])]
        if not (set(alt1) & set(alt2) or name1 in alt2 or name2 in alt1):
            return False
            
    # Proximity check
    lat1, lon1 = place1["latitude"], place1["longitude"]
    lat2, lon2 = place2["latitude"], place2["longitude"]
    
    dist = haversine_distance(lat1, lon1, lat2, lon2)
    return dist <= threshold_km

def merge_records(primary: Dict[str, Any], duplicate: Dict[str, Any]) -> Dict[str, Any]:
    """Merges two duplicate records, preserving the richest details and logging both sources."""
    merged = primary.copy()
    
    # Merge lists without duplicates
    list_fields = [
        "alternative_names", "tourist_category", "major_attractions",
        "available_activities", "nearby_hotels", "local_food_restaurants",
        "nearby_tourist_places"
    ]
    for field in list_fields:
        merged_list = list(set(primary.get(field, []) + duplicate.get(field, [])))
        merged[field] = sorted(merged_list)
        
    # Take longer description
    desc_fields = ["short_description", "detailed_description", "historical_cultural_importance"]
    for field in desc_fields:
        p_desc = primary.get(field, "")
        d_desc = duplicate.get(field, "")
        if len(d_desc) > len(p_desc) and d_desc != "information unavailable":
            merged[field] = d_desc
            
    # Merge sources
    p_src = primary.get("source_name", "")
    d_src = duplicate.get("source_name", "")
    if d_src and d_src != p_src:
        merged["source_name"] = f"{p_src}, {d_src}"
        
    p_url = primary.get("source_url", "")
    d_url = duplicate.get("source_url", "")
    if d_url and d_url != p_url:
        merged["source_url"] = f"{p_url}; {d_url}" if p_url else d_url
        
    # Recalculate confidence score after merging
    from smart_travel_planner.rag.data_cleaning import calculate_confidence
    merged["confidence_score"] = calculate_confidence(merged)
    
    return merged
