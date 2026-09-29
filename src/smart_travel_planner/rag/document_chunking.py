from typing import Dict, Any, List

def create_section_header(place: Dict[str, Any], section_name: str) -> str:
    """Generates a standardized header prefix for chunks to ensure context is preserved."""
    state = place.get('state_or_province', '')
    country = place.get('country', '')
    location = f"{place['place_name']}"
    if state and state != "information unavailable":
        location += f", {state}"
    if country and country != "information unavailable":
        location += f", {country}"
        
    categories = ", ".join(place.get("tourist_category", []))
    header = f"Place Name: {place['place_name']}\n"
    header += f"Location: {location}\n"
    header += f"Categories: {categories}\n"
    header += f"Section: {section_name}\n"
    header += "----------------------------------------\n"
    return header

def chunk_place_record(place: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Chunks a clean place record into 8 separate searchable sections with metadata."""
    chunks = []
    place_id = place["place_id"]
    place_name = place["place_name"]
    
    # Extract location details for chunk metadata
    metadata = {
        "place_id": place_id,
        "place_name": place_name,
        "country": place.get("country"),
        "state": place.get("state_or_province"),
        "district": place.get("district"),
        "city": place.get("city"),
        "category": place.get("tourist_category"),
        "scope": place.get("scope"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "source_url": place.get("source_url"),
        "last_verified": place.get("last_verified_date")
    }

    # Helper function to check if information exists
    def is_valid_info(text: Any) -> bool:
        if not text:
            return False
        if isinstance(text, str) and (text.lower().strip() in ["information unavailable", "null", "none", ""]):
            return False
        if isinstance(text, list) and len(text) == 0:
            return False
        return True

    # 1. Overview and importance
    overview_text = ""
    if is_valid_info(place.get("short_description")):
        overview_text += f"Short Description: {place['short_description']}\n"
    if is_valid_info(place.get("detailed_description")):
        overview_text += f"Detailed Description: {place['detailed_description']}\n"
    if is_valid_info(place.get("historical_cultural_importance")):
        overview_text += f"Historical and Cultural Importance: {place['historical_cultural_importance']}\n"
    
    if overview_text:
        content = create_section_header(place, "Overview and Importance") + overview_text
        chunks.append({
            "section": "overview_and_importance",
            "content": content,
            "metadata": {**metadata, "section": "overview_and_importance"}
        })

    # 2. Attractions and activities
    attraction_text = ""
    if is_valid_info(place.get("major_attractions")):
        attraction_text += "Major Attractions:\n" + "\n".join([f"- {a}" for a in place["major_attractions"]]) + "\n"
    if is_valid_info(place.get("available_activities")):
        attraction_text += "Available Activities:\n" + "\n".join([f"- {act}" for act in place["available_activities"]]) + "\n"
    
    if attraction_text:
        content = create_section_header(place, "Attractions and Activities") + attraction_text
        chunks.append({
            "section": "attractions_and_activities",
            "content": content,
            "metadata": {**metadata, "section": "attractions_and_activities"}
        })

    # 3. Best time, weather and climate
    weather_text = ""
    if is_valid_info(place.get("best_time_to_visit")):
        weather_text += f"Best Time to Visit: {place['best_time_to_visit']}\n"
    if is_valid_info(place.get("weather_climate_info")):
        weather_text += f"Weather and Climate: {place['weather_climate_info']}\n"
        
    if weather_text:
        content = create_section_header(place, "Best Time, Weather and Climate") + weather_text
        chunks.append({
            "section": "weather_and_best_time",
            "content": content,
            "metadata": {**metadata, "section": "weather_and_best_time"}
        })

    # 4. Transport and accessibility
    transport_text = ""
    if is_valid_info(place.get("nearest_airport")):
        transport_text += f"Nearest Airport: {place['nearest_airport']}\n"
    if is_valid_info(place.get("nearest_railway_station")):
        transport_text += f"Nearest Railway Station: {place['nearest_railway_station']}\n"
    if is_valid_info(place.get("road_accessibility")):
        transport_text += f"Road Accessibility: {place['road_accessibility']}\n"
    if is_valid_info(place.get("local_transport_options")):
        transport_text += f"Local Transport Options: {place['local_transport_options']}\n"
    if is_valid_info(place.get("accessibility_information")):
        transport_text += f"Accessibility Information: {place['accessibility_information']}\n"
        
    if transport_text:
        content = create_section_header(place, "Transport and Accessibility") + transport_text
        chunks.append({
            "section": "transport_and_accessibility",
            "content": content,
            "metadata": {**metadata, "section": "transport_and_accessibility"}
        })

    # 5. Accommodation and food
    lodging_text = ""
    if is_valid_info(place.get("nearby_hotels")):
        lodging_text += "Nearby Hotels:\n" + "\n".join([f"- {h}" for h in place["nearby_hotels"]]) + "\n"
    if is_valid_info(place.get("local_food_restaurants")):
        lodging_text += "Local Food & Restaurants:\n" + "\n".join([f"- {f}" for f in place["local_food_restaurants"]]) + "\n"
        
    if lodging_text:
        content = create_section_header(place, "Accommodation and Food") + lodging_text
        chunks.append({
            "section": "accommodation_and_food",
            "content": content,
            "metadata": {**metadata, "section": "accommodation_and_food"}
        })

    # 6. Budget and entry information
    budget_text = ""
    if is_valid_info(place.get("approximate_budget_category")):
        budget_text += f"Approximate Budget Category: {place['approximate_budget_category']}\n"
    if is_valid_info(place.get("entry_fee")):
        budget_text += f"Entry Fee: {place['entry_fee']}\n"
    if is_valid_info(place.get("opening_closing_hours")):
        budget_text += f"Opening and Closing Hours: {place['opening_closing_hours']}\n"
    if is_valid_info(place.get("weekly_closing_day")):
        budget_text += f"Weekly Closing Day: {place['weekly_closing_day']}\n"
        
    if budget_text:
        content = create_section_header(place, "Budget and Entry Information") + budget_text
        chunks.append({
            "section": "budget_and_entry",
            "content": content,
            "metadata": {**metadata, "section": "budget_and_entry"}
        })

    # 7. Safety, restrictions and permits
    safety_text = ""
    if is_valid_info(place.get("safety_notes")):
        safety_text += f"Safety Notes: {place['safety_notes']}\n"
    if is_valid_info(place.get("required_permits")):
        safety_text += f"Required Permits/Restrictions: {place['required_permits']}\n"
        
    if safety_text:
        content = create_section_header(place, "Safety, Restrictions and Permits") + safety_text
        chunks.append({
            "section": "safety_and_permits",
            "content": content,
            "metadata": {**metadata, "section": "safety_and_permits"}
        })

    # 8. Nearby places
    nearby_text = ""
    if is_valid_info(place.get("nearby_tourist_places")):
        nearby_text += "Nearby Tourist Places:\n" + "\n".join([f"- {p}" for p in place["nearby_tourist_places"]]) + "\n"
        
    if nearby_text:
        content = create_section_header(place, "Nearby Places") + nearby_text
        chunks.append({
            "section": "nearby_places",
            "content": content,
            "metadata": {**metadata, "section": "nearby_places"}
        })

    return chunks
