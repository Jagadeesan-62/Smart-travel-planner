import os
import json
import logging
import google.generativeai as genai
from typing import List, Dict, Any
from smart_travel_planner.rag.config import GENERATIVE_MODEL

logger = logging.getLogger(__name__)

# Fallback API Key used in server.py
DEFAULT_API_KEY = "AIzaSyCsehVYbggmlA-HE76XbUaIT0GnEDVgzfE"
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or DEFAULT_API_KEY

genai.configure(api_key=api_key)

def generate_rag_response(query: str, retrieved_results: List[Dict[str, Any]]) -> str:
    """Uses Gemini API to synthesize retrieved places into a high-fidelity markdown RAG response."""
    if not retrieved_results:
        return (
            "### No Results Found\n"
            "I couldn't find any tourist places in the database matching your criteria. "
            "Please try refining your search or broadening your filters."
        )
        
    # Format retrieved facts to feed into the prompt context
    context_str = ""
    for idx, res in enumerate(retrieved_results):
        p = res["place"]
        context_str += f"--- PLACE {idx + 1}: {p['place_name']} ---\n"
        context_str += f"Place ID: {p['place_id']}\n"
        context_str += f"Scope: {p['scope']}\n"
        context_str += f"Matching Chunk Context:\n{res['matching_chunk_content']}\n"
        
        # Include full details to allow the LLM to write a comprehensive report
        context_str += f"Full Details:\n"
        context_str += f"- Alternative Names: {', '.join(p.get('alternative_names', []))}\n"
        context_str += f"- Country: {p.get('country')}, State: {p.get('state_or_province')}, District: {p.get('district')}, City: {p.get('city')}\n"
        context_str += f"- Coordinates: {p.get('latitude')}, {p.get('longitude')}\n"
        context_str += f"- Short Description: {p.get('short_description')}\n"
        context_str += f"- Detailed Description: {p.get('detailed_description')}\n"
        context_str += f"- Historical/Cultural Importance: {p.get('historical_cultural_importance')}\n"
        context_str += f"- Major Attractions: {', '.join(p.get('major_attractions', []))}\n"
        context_str += f"- Available Activities: {', '.join(p.get('available_activities', []))}\n"
        context_str += f"- Best Time To Visit: {p.get('best_time_to_visit')}\n"
        context_str += f"- Suggested Duration: {p.get('recommended_visit_duration')}\n"
        context_str += f"- Budget Category: {p.get('approximate_budget_category')}\n"
        context_str += f"- Entry Fee: {p.get('entry_fee')}\n"
        context_str += f"- Nearest Transport: Airport: {p.get('nearest_airport')}, Railway: {p.get('nearest_railway_station')}\n"
        context_str += f"- Local Food: {', '.join(p.get('local_food_restaurants', []))}\n"
        context_str += f"- Family Suitability: {'Yes' if p.get('family_suitability') else 'No'}\n"
        context_str += f"- Solo Suitability: {'Yes' if p.get('solo_travel_suitability') else 'No'}\n"
        context_str += f"- Safety Notes: {p.get('safety_notes')}\n"
        context_str += f"- Permits Required: {p.get('required_permits')}\n"
        context_str += f"- Nearby Places: {', '.join(p.get('nearby_tourist_places', []))}\n"
        context_str += f"- Source: {p.get('source_name')} ({p.get('source_url')})\n"
        context_str += f"- Last Verified: {p.get('last_verified_date')}\n"
        context_str += f"- Search Confidence Score: {res.get('score')}\n\n"

    prompt = f"""You are a professional travel planner assistant. You are helping a user plan their travel database query.
    
User Query: "{query}"

Retrieved Tourism Database Records:
{context_str}

Please generate a comprehensive, structured response answering the query. Ensure the output strictly details the following blocks for each recommended place:
1. Recommended Place Name and Location
2. Why Each Place Matches (referencing their search query and coordinates/interests)
3. Best Time to Visit (including climate or seasonality details from context)
4. Main Attractions & Activities
5. Approximate Budget Category & Entry Fees
6. Suggested Visit Duration
7. Transport & Accessibility Information
8. Source References (Include clickable URL links in markdown from the source details provided)
9. Database Confidence Score (from the search score or data confidence provided)

Format the entire output as clean, beautifully rendered GitHub-style markdown. Avoid generic placeholders or fabricating any facts. If specific details are not provided in the context, write 'information unavailable'.
"""

    try:
        model = genai.GenerativeModel(GENERATIVE_MODEL)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Failed to generate RAG response via Gemini API: {e}. Falling back to structured string generator.")
        
        # Fallback generator
        fallback_md = f"# Search Results for: \"{query}\" (Simulated Fallback Mode)\n\n"
        for idx, res in enumerate(retrieved_results):
            p = res["place"]
            fallback_md += f"## {idx + 1}. {p['place_name']} - {p['city']}, {p['state_or_province']}, {p['country']}\n"
            fallback_md += f"- **Why it matches**: Matches query with search similarity score of {res['score']}.\n"
            fallback_md += f"- **Best Time to Visit**: {p['best_time_to_visit']} (Climate: {p['weather_climate_info']})\n"
            fallback_md += f"- **Main Attractions**: {', '.join(p['major_attractions'] or ['N/A'])}\n"
            fallback_md += f"- **Activities**: {', '.join(p['available_activities'] or ['N/A'])}\n"
            fallback_md += f"- **Approximate Budget**: {p['approximate_budget_category']} (Entry Fee: {p['entry_fee']})\n"
            fallback_md += f"- **Suggested Duration**: {p['recommended_visit_duration']}\n"
            fallback_md += f"- **Transport & Accessibility**: Nearest Airport: {p['nearest_airport']}. Railway: {p['nearest_railway_station']}. {p['road_accessibility']}.\n"
            fallback_md += f"- **Source References**: [{p['source_name']}]({p['source_url']}) (Verified: {p['last_verified_date']})\n"
            fallback_md += f"- **Confidence Score**: {p.get('confidence_score', 1.0)}\n\n"
        return fallback_md
