import urllib.request
import urllib.parse
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def fetch_wikipedia_details(place_name: str) -> Optional[Dict[str, Any]]:
    """Fetches text description and coordinates from Wikipedia API for a given place."""
    try:
        # Search for page title
        search_query = urllib.parse.quote(place_name)
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"
        
        req = urllib.request.Request(search_url, headers={'User-Agent': 'SmartTravelPlanner/1.0 (contact@example.com)'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
        search_results = data.get("query", {}).get("search", [])
        if not search_results:
            return None
            
        page_title = search_results[0]["title"]
        page_title_encoded = urllib.parse.quote(page_title)
        
        # Get page content & coordinates
        content_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts|coordinates"
            f"&exintro=1&explaintext=1&titles={page_title_encoded}&format=json"
        )
        
        with urllib.request.urlopen(urllib.request.Request(content_url, headers={'User-Agent': 'SmartTravelPlanner/1.0'})) as response:
            content_data = json.loads(response.read().decode())
            
        pages = content_data.get("query", {}).get("pages", {})
        if not pages:
            return None
            
        page_id = list(pages.keys())[0]
        page = pages[page_id]
        
        extract = page.get("extract", "")
        coords = page.get("coordinates", [{}])[0]
        
        if not extract:
            return None
            
        lat = coords.get("lat")
        lon = coords.get("lon")
        
        return {
            "place_name": page_title,
            "description": extract,
            "latitude": lat,
            "longitude": lon,
            "source_url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
        }
    except Exception as e:
        logger.warning(f"Error fetching Wikipedia data for {place_name}: {e}")
        return None

def fetch_wikidata_tourist_attractions(region_name: str) -> List[Dict[str, Any]]:
    """Runs a SPARQL query against Wikidata to find tourist places in a region.
    Returns basic metadata that can be enriched via Wikipedia."""
    # We use a simple fallback if SPARQL endpoint is slow or rate-limited
    try:
        # Example query searching for places in Wikidata
        sparql_query = f"""
        SELECT ?item ?itemLabel ?coord ?image ?website WHERE {{
          ?item wdt:P31/wdt:P279* wd:Q570116. # Tourist attraction
          ?item wdt:P17 wd:Q668. # In India
          ?item ?border ?adminArea.
          ?adminArea rdfs:label "{region_name}"@en.
          ?item wdt:P625 ?coord.
          OPTIONAL {{ ?item wdt:P18 ?image. }}
          OPTIONAL {{ ?item wdt:P856 ?website. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }} LIMIT 10
        """
        url = "https://query.wikidata.org/sparql"
        params = {"query": sparql_query, "format": "json"}
        encoded_params = urllib.parse.urlencode(params)
        
        req = urllib.request.Request(f"{url}?{encoded_params}", headers={
            'User-Agent': 'SmartTravelPlanner/1.0 (contact@example.com)',
            'Accept': 'application/sparql-results+json'
        })
        
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode())
            
        results = data.get("results", {}).get("bindings", [])
        places = []
        for row in results:
            name = row.get("itemLabel", {}).get("value")
            coord_str = row.get("coord", {}).get("value", "")
            website = row.get("website", {}).get("value", "")
            wiki_url = row.get("item", {}).get("value", "")
            
            # Parse coordinate string point(long, lat)
            lat, lon = None, None
            if "Point" in coord_str:
                parts = coord_str.replace("Point(", "").replace(")", "").split(" ")
                if len(parts) == 2:
                    lon, lat = float(parts[0]), float(parts[1])
            
            if name and lat and lon:
                places.append({
                    "place_name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "source_url": website or wiki_url,
                    "source_name": "Wikidata"
                })
        return places
    except Exception as e:
        logger.warning(f"Error querying Wikidata SPARQL for {region_name}: {e}")
        return []

def get_sample_places() -> List[Dict[str, Any]]:
    """Returns a collection of rich, high-fidelity sample tourist place records for testing."""
    return [
        # === TAMIL NADU SAMPLES ===
        {
            "place_name": "Marina Beach",
            "alternative_names": ["Chennai Marina", "Marina"],
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "district": "Chennai",
            "city": "Chennai",
            "latitude": 13.0500,
            "longitude": 80.2824,
            "tourist_category": ["beach", "nature", "family"],
            "short_description": "Marina Beach in Chennai is the longest natural urban beach in the country along the Bay of Bengal.",
            "detailed_description": "Marina Beach is a natural urban beach in Chennai, Tamil Nadu, India, along the Bay of Bengal. The beach runs from near Fort St. George in the north to Foreshore Estate in the south, a distance of 6.0 km, making it the longest natural urban beach in the country. It is a major landmark of Chennai, attracting thousands of visitors daily. The promenade features historical statues, memorials, and food stalls selling local snacks.",
            "historical_cultural_importance": "The beach was developed and beautified by Mountstuart Elphinstone Grant Duff, the Governor of Madras, in the 1880s. It contains memorials for prominent Tamil leaders such as C. N. Annadurai, M. G. Ramachandran, and M. Karunanidhi.",
            "major_attractions": ["Victory War Memorial", "MGR Memorial", "Anna Memorial", "Light House", "Triumph of Labour Statue", "Mahatma Gandhi Statue"],
            "available_activities": ["Walking", "Pony rides", "Kite flying", "Street food tasting", "Viewing sunset"],
            "best_time_to_visit": "November to February when weather is pleasant.",
            "recommended_visit_duration": "2 hours",
            "opening_closing_hours": "Open 24 hours daily, but evening is highly recommended.",
            "entry_fee": "Free",
            "weekly_closing_day": "None",
            "weather_climate_info": "Tropical wet and dry climate. Hot and humid summers, warm winters with monsoon rains in October-December.",
            "nearest_airport": "Chennai International Airport (MAA)",
            "nearest_railway_station": "Puratchi Thalaivar Dr. M.G. Ramachandran Central Railway Station (MAS)",
            "road_accessibility": "Highly accessible via Kamarajar Salai, well connected by local buses, taxis, and autos.",
            "local_transport_options": "Metro, local trains (MRTS Chennai Beach-Velachery), city buses, cabs.",
            "nearby_hotels": ["Taj Connemara", "The Residency Towers", "Clarion Hotel President"],
            "local_food_restaurants": ["Nethili fry at beach stalls", "Sundal vendors", "Saravana Bhavan nearby", "Ratna Cafe"],
            "approximate_budget_category": "Budget",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Wheelchair ramp available near the Mahatma Gandhi statue.",
            "safety_notes": "Bathing and swimming in the sea are strictly prohibited due to strong undercurrents.",
            "required_permits": "None",
            "nearby_tourist_places": ["Kapaleeshwarar Temple", "Santhome Cathedral Basilica", "Fort St. George"],
            "source_url": "https://www.tamilnadutourism.travel/",
            "source_name": "Tamil Nadu Tourism Development Corporation",
            "last_verified_date": "2026-08-31",
            "scope": "tamil_nadu"
        },
        {
            "place_name": "Meenakshi Amman Temple",
            "alternative_names": ["Madurai Meenakshi Temple", "Meenakshi Sundareswarar Temple"],
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "district": "Madurai",
            "city": "Madurai",
            "latitude": 9.9195,
            "longitude": 78.1193,
            "tourist_category": ["temple", "heritage", "culture"],
            "short_description": "A historic Hindu temple located on the southern bank of the Vaigai River in the temple city of Madurai.",
            "detailed_description": "Meenakshi Temple, also referred to as Meenakshi Amman or Meenakshi-Sundareswarar Temple, is a historic Hindu temple located on the southern bank of the Vaigai River in the temple city of Madurai, Tamil Nadu, India. It is dedicated to Meenakshi, a form of Parvati, and her consort, Sundareswarar, a form of Shiva. The temple is at the center of the ancient temple city of Madurai mentioned in the Sangam literature, with a major temple complex built under the Pandyan and Nayak reigns. It houses 14 gopurams (gateway towers), ranging from 45 to 50 meters in height.",
            "historical_cultural_importance": "The temple was originally founded in the 6th century BC and rebuilt in its present form in the 16th and 17th centuries by Vishwanatha Nayakar. It is a masterpiece of Dravidian architecture.",
            "major_attractions": ["Hall of Thousand Pillars", "Golden Lotus Pond", "Ashta Shakti Mandapam", "Kalyana Mandapam", "Meenakshi and Sundareswarar shrines"],
            "available_activities": ["Religious darshan", "Architectural photography", "Exploring the museum", "Attending the evening prayer ceremony"],
            "best_time_to_visit": "October to March. Chithirai Festival in April is spectacular.",
            "recommended_visit_duration": "3-4 hours",
            "opening_closing_hours": "5:00 AM - 12:30 PM, 4:00 PM - 10:00 PM daily",
            "entry_fee": "Free for temple entry, INR 50 for Hall of Thousand Pillars.",
            "weekly_closing_day": "None",
            "weather_climate_info": "Hot semi-arid climate. Temperatures can go up to 40C in summer, winters are pleasant around 20-30C.",
            "nearest_airport": "Madurai Airport (IXM)",
            "nearest_railway_station": "Madurai Junction (MDU)",
            "road_accessibility": "Located in the heart of Madurai town, accessible by all city roads.",
            "local_transport_options": "Auto rickshaws, cycle rickshaws, local town buses, app cabs.",
            "nearby_hotels": ["Heritage Madurai", "The Gateway Hotel Pasumalai", "Courtyard by Marriott Madurai"],
            "local_food_restaurants": ["Murugan Idli Shop", "Jigarthanda stalls", "Modern Restaurant"],
            "approximate_budget_category": "Budget",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Wheelchair assistance available at the temple entrances.",
            "safety_notes": "Very crowded during festivals. Beware of pickpockets. Mobile phones and cameras are prohibited inside the temple premises.",
            "required_permits": "None. Dress code applies (traditional attire, shoulders and knees must be covered).",
            "nearby_tourist_places": ["Thirumalai Nayakkar Mahal", "Alagar Koyil", "Gandhi Memorial Museum"],
            "source_url": "https://maduraimeenakshi.org/",
            "source_name": "Arulmigu Meenakshi Sundareswarar Thirukoloil",
            "last_verified_date": "2026-08-31",
            "scope": "tamil_nadu"
        },
        {
            "place_name": "Ooty Botanical Gardens",
            "alternative_names": ["Government Botanical Garden", "Ooty Garden"],
            "country": "India",
            "state_or_province": "Tamil Nadu",
            "district": "Nilgiris",
            "city": "Ooty",
            "latitude": 11.4189,
            "longitude": 76.7111,
            "tourist_category": ["nature", "hill_station", "park"],
            "short_description": "A lush botanical garden laid out in 1848, located on the lower slopes of Doddabetta peak in Ooty.",
            "detailed_description": "The Government Botanical Garden is a botanical garden in Udhagamandalam (Ooty), Tamil Nadu, India, lying on the lower slopes of Doddabetta peak. The garden has a terraced layout and covers an area of around 55 hectares. Established in 1848, it is divided into six sections: Lower Garden, New Garden, Italian Garden, Conservatory, Fountain Terrace, and Nurseries. It houses a rich collection of exotic plants, orchids, ferns, and a 20-million-year-old fossil tree trunk.",
            "historical_cultural_importance": "Designed by architect William Graham McIvor in 1848 under British rule to supply vegetables to European residents at cheap rates. It is now maintained by the Horticultural Department of Tamil Nadu.",
            "major_attractions": ["Fossil Tree Trunk", "Glass House", "Italian Garden", "Fern House", "Sunken Garden"],
            "available_activities": ["Nature walks", "Flower photography", "Picnicking", "Attending the Annual Flower Show in May"],
            "best_time_to_visit": "April to June (Spring/Summer flower blooms) and September to November.",
            "recommended_visit_duration": "2 hours",
            "opening_closing_hours": "7:00 AM - 6:30 PM daily",
            "entry_fee": "INR 50 for adults, INR 30 for children, INR 100 for camera.",
            "weekly_closing_day": "None",
            "weather_climate_info": "Subtropical highland climate. Cool and pleasant throughout the year. Winter nights can get chilly (below 5C).",
            "nearest_airport": "Coimbatore International Airport (CJB)",
            "nearest_railway_station": "Udhagamandalam Railway Station (UAM) / Ooty Toy Train station",
            "road_accessibility": "Fully accessible via NH 181. Connected by cabs and local Ooty town buses.",
            "local_transport_options": "Auto rickshaws, local cabs, rented scooters.",
            "nearby_hotels": ["Savoy - IHCL SeleQtions", "Sterling Ooty Fern Hill", "WelcomHeritage Savoy"],
            "local_food_restaurants": ["Place to Bee", "Shinkows", "Ooty Bakery"],
            "approximate_budget_category": "Budget",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Paved pathways are accessible, but some sections are sloped and terraced.",
            "safety_notes": "Keep an eye on children near sloped edges. Plucking flowers is strictly prohibited.",
            "required_permits": "None",
            "nearby_tourist_places": ["Ooty Lake", "Doddabetta Peak", "Rose Garden"],
            "source_url": "https://www.tamilnadutourism.travel/destinations/ooty",
            "source_name": "Tamil Nadu Tourism",
            "last_verified_date": "2026-08-31",
            "scope": "tamil_nadu"
        },
        
        # === REST OF INDIA SAMPLES ===
        {
            "place_name": "Taj Mahal",
            "alternative_names": ["Taj", "Crown of the Palace"],
            "country": "India",
            "state_or_province": "Uttar Pradesh",
            "district": "Agra",
            "city": "Agra",
            "latitude": 27.1751,
            "longitude": 78.0421,
            "tourist_category": ["heritage", "culture", "monument"],
            "short_description": "An ivory-white marble mausoleum on the south bank of the Yamuna river in Agra, commissioned by Mughal Emperor Shah Jahan.",
            "detailed_description": "The Taj Mahal is an ivory-white marble mausoleum on the south bank of the Yamuna river in the Indian city of Agra. It was commissioned in 1632 by the Mughal emperor Shah Jahan to house the tomb of his favorite wife, Mumtaz Mahal; it also houses the tomb of Shah Jahan himself. The tomb is the centerpiece of a 17-hectare complex, which includes a mosque and a guest house, and is set in formal gardens bounded on three sides by a crenellated wall. The Taj Mahal is a UNESCO World Heritage Site and widely considered a masterpiece of Mughal architecture.",
            "historical_cultural_importance": "Built over 20 years by thousands of artisans. It represents the pinnacle of Mughal art and the eternal love story of Shah Jahan and Mumtaz Mahal.",
            "major_attractions": ["Main Mausoleum", "Taj Museum", "Mughal Garden", "Reflecting Pool", "Mehtab Bagh across the river"],
            "available_activities": ["Historical tours", "Sunrise/Sunset viewing", "Photography", "Buying local marble crafts"],
            "best_time_to_visit": "October to March. Sunrise is the absolute best time for low crowds and gorgeous light.",
            "recommended_visit_duration": "3 hours",
            "opening_closing_hours": "6:00 AM - 7:00 PM daily except Fridays",
            "entry_fee": "INR 50 for Indians, INR 1100 for Foreigners, INR 200 extra for entering the main mausoleum chamber.",
            "weekly_closing_day": "Friday",
            "weather_climate_info": "Humid subtropical climate. Scorching summers (up to 45C), cool winters around 10-20C. Foggy mornings in December-January.",
            "nearest_airport": "Indira Gandhi International Airport (DEL) in Delhi (3.5 hours drive)",
            "nearest_railway_station": "Agra Cantt Railway Station (AGC)",
            "road_accessibility": "Fully connected via Yamuna Expressway from Delhi. Battery-operated vehicles carry tourists to the entry gates from parking lots.",
            "local_transport_options": "E-rickshaws, auto rickshaws, cycle rickshaws, local cabs.",
            "nearby_hotels": ["The Oberoi Amarvilas", "Taj Hotel & Convention Centre", "DoubleTree by Hilton Agra"],
            "local_food_restaurants": ["Petha shops (Panchhi Petha)", "Pinch of Spice", "Esphahan"],
            "approximate_budget_category": "Mid-range",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Ramps and golf carts are available for disabled visitors.",
            "safety_notes": "Ignore aggressive guides and photographers outside the gates. Drone photography is strictly banned.",
            "required_permits": "None. Shoe covers are provided at entry and must be worn on the white marble platform.",
            "nearby_tourist_places": ["Agra Fort", "Fatehpur Sikri", "Itmad-ud-Daulah (Baby Taj)"],
            "source_url": "https://www.tajmahal.gov.in/",
            "source_name": "Archaeological Survey of India",
            "last_verified_date": "2026-08-31",
            "scope": "india"
        },
        {
            "place_name": "Munnar Tea Gardens",
            "alternative_names": ["Munnar Hills", "Pothanmedu Tea Garden"],
            "country": "India",
            "state_or_province": "Kerala",
            "district": "Idukki",
            "city": "Munnar",
            "latitude": 10.0889,
            "longitude": 77.0595,
            "tourist_category": ["hill_station", "nature", "nature"],
            "short_description": "Expansive emerald green tea estates carpeted across the hills of Munnar in Kerala.",
            "detailed_description": "Munnar is renowned for its vast, rolling tea plantations, which cover the landscape with a vibrant carpet of green. Located at an altitude of 1,600 meters in the Western Ghats, these tea estates were pioneered in the late 19th century. Visitors can walk through designated estate paths, witness the tea leaf harvesting process by local workers, and tour processing factories to learn about the journey of tea from leaf to cup.",
            "historical_cultural_importance": "Tea cultivation was initiated by British resident John Daniel Munro in the 1870s. The region is heavily shaped by the legacy of the Kannan Devan Hills Produce Company (now Tata Tea).",
            "major_attractions": ["Tata Tea Museum", "Lockhart Tea Factory", "Kolukkumalai Tea Estate (highest in the world)"],
            "available_activities": ["Tea tasting", "Plantation walks", "Trekking", "Shopping for freshly packed tea and spices"],
            "best_time_to_visit": "September to May for cool, pleasant climate.",
            "recommended_visit_duration": "4 hours",
            "opening_closing_hours": "Open 24 hours (plantations), Tea Museum open 9:00 AM - 5:00 PM closed on Mondays.",
            "entry_fee": "Free for walking around public plantation paths. INR 125 for Tea Museum.",
            "weekly_closing_day": "Monday (Museum only)",
            "weather_climate_info": "Highland climate. Moderate summers (15-25C), cold winters (5-15C). Heavy monsoons from June to August.",
            "nearest_airport": "Cochin International Airport (COK) (110 km away)",
            "nearest_railway_station": "Aluva Railway Station (110 km away)",
            "road_accessibility": "Connected by winding ghat roads via Kochi-Dhanushkodi highway (NH 85). Accessible by bus and private cabs.",
            "local_transport_options": "Auto rickshaws, local jeeps, rental motorbikes, tourist cabs.",
            "nearby_hotels": ["The Panoramic Getaway", "Tea Valley Resort", "Blanket Hotel & Spa"],
            "local_food_restaurants": ["Rapsy Restaurant", "Saravana Bhavan Munnar", "KTDC Tea County Restaurant"],
            "approximate_budget_category": "Mid-range",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Hilly terrain; may be difficult for wheelchair users off the main paved roads.",
            "safety_notes": "Watch out for leeches in wet weather during walks. Do not trespass deep into private estate areas.",
            "required_permits": "None for standard viewpoints; permission required for commercial photography or deep trekking.",
            "nearby_tourist_places": ["Eravikulam National Park", "Mattupetty Dam", "Anamudi Peak"],
            "source_url": "https://www.keralatourism.org/destination/munnar/308",
            "source_name": "Kerala Tourism Development Corporation",
            "last_verified_date": "2026-08-31",
            "scope": "india"
        },
        
        # === WORLDWIDE SAMPLES ===
        {
            "place_name": "Eiffel Tower",
            "alternative_names": ["La Tour Eiffel"],
            "country": "France",
            "state_or_province": "Île-de-France",
            "district": "Paris",
            "city": "Paris",
            "latitude": 48.8584,
            "longitude": 2.2945,
            "tourist_category": ["monument", "heritage", "culture"],
            "short_description": "An iconic 19th-century iron lattice tower situated on the Champ de Mars in Paris, France.",
            "detailed_description": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. It is named after the engineer Gustave Eiffel, whose company designed and built the tower. Locally nicknamed 'La dame de fer' (French for 'Iron Lady'), it was constructed from 1887 to 1889 as the centerpiece of the 1889 World's Fair. Standing at 330 meters, it is the tallest structure in Paris. The tower has three levels for visitors, with restaurants on the first and second levels, and an observation deck on the top level.",
            "historical_cultural_importance": "Built to celebrate the centennial of the French Revolution. Initially criticized by leading French artists, it has become a global cultural icon of France.",
            "major_attractions": ["First Floor glass floor", "Le Jules Verne restaurant", "Top Summit Observation Deck", "Champ de Mars gardens"],
            "available_activities": ["Tower climbing", "Fine dining", "Champagne toast at the summit", "Night light show viewing"],
            "best_time_to_visit": "Year-round. Spring (March-May) and Autumn (September-November) offer great weather and smaller crowds.",
            "recommended_visit_duration": "2-3 hours",
            "opening_closing_hours": "9:30 AM - 11:45 PM daily",
            "entry_fee": "EUR 10.50 to EUR 26.80 depending on the level (stairs vs lift) and age group.",
            "weekly_closing_day": "None",
            "weather_climate_info": "Temperate oceanic climate. Warm summers (15-25C), cold winters (3-8C), occasional light rain throughout the year.",
            "nearest_airport": "Paris Charles de Gaulle Airport (CDG) or Orly Airport (ORY)",
            "nearest_railway_station": "Gare du Nord / Bir-Hakeim Metro Station / Champ de Mars-Tour Eiffel RER station",
            "road_accessibility": "Fully accessible via Paris city transport network.",
            "local_transport_options": "Paris Metro, RER trains, public city buses, Seine River cruises, Uber.",
            "nearby_hotels": ["Hotel Pullmann Paris Tour Eiffel", "Shangri-La Paris", "Mercure Paris Centre Tour Eiffel"],
            "local_food_restaurants": ["Le Jules Verne (inside)", "58 Tour Eiffel", "Cafes along Rue de l'Université"],
            "approximate_budget_category": "Luxury",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Wheelchair accessible up to the second level. The summit is not wheelchair accessible for safety reasons.",
            "safety_notes": "Highly prone to pickpockets around the base. Purchase tickets online weeks in advance to avoid 3+ hour ticket lines.",
            "required_permits": "Pre-booked online tickets are strongly recommended.",
            "nearby_tourist_places": ["Louvre Museum", "Arc de Triomphe", "Seine River Cruise"],
            "source_url": "https://www.toureiffel.paris/en",
            "source_name": "La Société d'Exploitation de la Tour Eiffel (SETE)",
            "last_verified_date": "2026-08-31",
            "scope": "world"
        },
        {
            "place_name": "Kinkaku-ji",
            "alternative_names": ["Golden Pavilion", "Rokuon-ji"],
            "country": "Japan",
            "state_or_province": "Kansai",
            "district": "Kyoto Prefecture",
            "city": "Kyoto",
            "latitude": 35.0394,
            "longitude": 135.7292,
            "tourist_category": ["temple", "heritage", "culture"],
            "short_description": "A Zen Buddhist temple in Kyoto, Japan, famous for its top two floors covered completely in gold leaf.",
            "detailed_description": "Kinkaku-ji, officially named Rokuon-ji, is a Zen Buddhist temple in Kyoto, Japan. It is one of the most popular buildings in Kyoto, attracting a large number of visitors annually. It is designated as a National Historic Site and a National Special Landscape, and is one of 17 locations making up the Historic Monuments of Ancient Kyoto which are UNESCO World Heritage Sites. The pavilion is situated in a classical Japanese stroll garden and overlooks a large pond.",
            "historical_cultural_importance": "Built in 1397 as a retirement villa for Shogun Ashikaga Yoshimitsu. After his death, it was converted into a Zen temple. The temple was burned down in 1950 by a fanatic monk and rebuilt in 1955.",
            "major_attractions": ["The Golden Pavilion", "Kyoko-chi (Mirror Pond)", "Sekkatei Tea House", "Rikuon-ji temple gardens"],
            "available_activities": ["Strolling the Zen gardens", "Drinking matcha at the tea house", "Buying protective amulets (Omamori)"],
            "best_time_to_visit": "Autumn (November) for red maple leaves or Winter (January) for snow covering the golden roof.",
            "recommended_visit_duration": "1.5 hours",
            "opening_closing_hours": "9:00 AM - 5:00 PM daily",
            "entry_fee": "JPY 400 for adults, JPY 300 for children.",
            "weekly_closing_day": "None",
            "weather_climate_info": "Humid subtropical climate. Hot, humid summers, cold winters with occasional snowfall.",
            "nearest_airport": "Kansai International Airport (KIX) or Itami Airport (ITM) in Osaka",
            "nearest_railway_station": "Kyoto Station (JR Lines), connected by Kyoto City Bus 101 or 205 directly to the temple.",
            "road_accessibility": "Fully paved roads, access is easiest via bus or taxi. No public car parking available.",
            "local_transport_options": "Kyoto City Bus, Kyoto Subway, taxi.",
            "nearby_hotels": ["Kyoto Brighton Hotel", "The Ritz-Carlton Kyoto", "Rihga Royal Hotel Kyoto"],
            "local_food_restaurants": ["Kinkaku-ji Itadki", "Matcha soft serve stands outside", "Ramen shops nearby"],
            "approximate_budget_category": "Budget",
            "family_suitability": True,
            "solo_travel_suitability": True,
            "accessibility_information": "Main viewing path is flat and gravel-paved, but has some steps towards the exit garden exit.",
            "safety_notes": "Extremely crowded during midday. Large tour groups are common; go early in the morning.",
            "required_permits": "None",
            "nearby_tourist_places": ["Ryoan-ji Temple", "Ninna-ji Temple", "Arashiyama Bamboo Grove"],
            "source_url": "https://www.shokoku-ji.jp/en/kinkakuji/",
            "source_name": "Shokokuji Temple Sect",
            "last_verified_date": "2026-08-31",
            "scope": "world"
        }
    ]
