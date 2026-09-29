import re
from typing import Dict, Any, Optional

def normalize_text(text: Optional[str]) -> str:
    """Standardizes text values by trimming whitespace and normalizing casing."""
    if not text:
        return ""
    text = text.strip()
    # Normalize multiple whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text

def normalize_name(name: Optional[str]) -> str:
    """Normalizes place/state/city names to Title Case."""
    if not name:
        return ""
    # Capitalize the first letter of each word
    return normalize_text(name).title()

def parse_coordinates(lat: Any, lng: Any) -> tuple[Optional[float], Optional[float]]:
    """Validates and parses latitude and longitude to floats."""
    try:
        if lat is None or lng is None:
            return None, None
        
        flat_lat = float(lat)
        flat_lng = float(lng)
        
        # Validate ranges
        if -90.0 <= flat_lat <= 90.0 and -180.0 <= flat_lng <= 180.0:
            return flat_lat, flat_lng
        return None, None
    except (ValueError, TypeError):
        return None, None

def validate_url(url: Optional[str]) -> str:
    """Validates and normalizes URLs. Returns empty string if invalid."""
    if not url:
        return ""
    url = url.strip()
    # Basic URL validation regex
    url_pattern = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if url_pattern.match(url):
        return url
    return ""

def calculate_confidence(place: Dict[str, Any]) -> float:
    """Calculates data confidence score based on the completeness of fields (0.0 to 1.0)."""
    core_fields = [
        "place_name", "country", "latitude", "longitude", "tourist_category",
        "short_description", "detailed_description", "best_time_to_visit",
        "nearest_airport", "nearest_railway_station", "entry_fee", "source_url"
    ]
    
    filled_count = 0
    for field in core_fields:
        val = place.get(field)
        if val and val != "information unavailable" and val != "null":
            filled_count += 1
            
    # Calculate simple percentage-based score
    base_score = filled_count / len(core_fields)
    
    # Boost if coordinates are exact
    if place.get("latitude") and place.get("longitude"):
        base_score = min(1.0, base_score + 0.1)
        
    return round(base_score, 2)

def clean_place_record(place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Cleans, normalizes, and validates a raw place record. 
    Returns None if the record is invalid or incomplete."""
    
    # Must have place name and country to be a valid entry
    name = normalize_name(place.get("place_name"))
    country = normalize_name(place.get("country"))
    
    if not name or not country:
        return None
        
    lat, lng = parse_coordinates(place.get("latitude"), place.get("longitude"))
    if lat is None or lng is None:
        return None # Coordinates are essential for geospatial RAG
        
    # Clean standard fields
    cleaned = {
        "place_name": name,
        "alternative_names": [normalize_name(n) for n in place.get("alternative_names", []) if n],
        "country": country,
        "state_or_province": normalize_name(place.get("state_or_province")),
        "district": normalize_name(place.get("district")),
        "city": normalize_name(place.get("city")),
        "latitude": lat,
        "longitude": lng,
        "tourist_category": [t.lower().strip() for t in place.get("tourist_category", []) if t],
        "short_description": normalize_text(place.get("short_description")),
        "detailed_description": normalize_text(place.get("detailed_description")),
        "historical_cultural_importance": normalize_text(place.get("historical_cultural_importance")),
        "major_attractions": [normalize_text(a) for a in place.get("major_attractions", []) if a],
        "available_activities": [normalize_text(a) for a in place.get("available_activities", []) if a],
        "best_time_to_visit": normalize_text(place.get("best_time_to_visit")),
        "recommended_visit_duration": normalize_text(place.get("recommended_visit_duration")),
        "opening_closing_hours": normalize_text(place.get("opening_closing_hours")),
        "entry_fee": normalize_text(place.get("entry_fee")),
        "weekly_closing_day": normalize_name(place.get("weekly_closing_day")),
        "weather_climate_info": normalize_text(place.get("weather_climate_info")),
        "nearest_airport": normalize_name(place.get("nearest_airport")),
        "nearest_railway_station": normalize_name(place.get("nearest_railway_station")),
        "road_accessibility": normalize_text(place.get("road_accessibility")),
        "local_transport_options": normalize_text(place.get("local_transport_options")),
        "nearby_hotels": [normalize_text(h) for h in place.get("nearby_hotels", []) if h],
        "local_food_restaurants": [normalize_text(f) for f in place.get("local_food_restaurants", []) if f],
        "approximate_budget_category": normalize_name(place.get("approximate_budget_category")),
        "family_suitability": bool(place.get("family_suitability", True)),
        "solo_travel_suitability": bool(place.get("solo_travel_suitability", True)),
        "accessibility_information": normalize_text(place.get("accessibility_information")),
        "safety_notes": normalize_text(place.get("safety_notes")),
        "required_permits": normalize_text(place.get("required_permits")),
        "nearby_tourist_places": [normalize_name(p) for p in place.get("nearby_tourist_places", []) if p],
        "source_url": validate_url(place.get("source_url")),
        "source_name": normalize_name(place.get("source_name")),
        "last_verified_date": normalize_text(place.get("last_verified_date")) or "2026-08-31",
        "scope": place.get("scope", "world").lower().strip()
    }
    
    # Fill in missing fields with "information unavailable" or defaults
    for k, v in cleaned.items():
        if v == "" or v == [] or v is None:
            if k in ["alternative_names", "tourist_category", "major_attractions", 
                      "available_activities", "nearby_hotels", "local_food_restaurants", "nearby_tourist_places"]:
                cleaned[k] = []
            elif k in ["family_suitability", "solo_travel_suitability"]:
                cleaned[k] = True
            elif k in ["latitude", "longitude", "source_url"]:
                pass
            else:
                cleaned[k] = "information unavailable"
                
    # Normalize Scope based on geographic hierarchy
    state = cleaned["state_or_province"].lower()
    country_lower = cleaned["country"].lower()
    
    if "tamil nadu" in state or "tamilnadu" in state or "tamil nadu" in cleaned["place_name"].lower():
        cleaned["scope"] = "tamil_nadu"
    elif "india" in country_lower:
        cleaned["scope"] = "india"
    else:
        cleaned["scope"] = "world"
        
    cleaned["confidence_score"] = calculate_confidence(cleaned)
    return cleaned
