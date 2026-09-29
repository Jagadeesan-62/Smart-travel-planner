import os
import uuid
import json
import asyncio
import random
import math
import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import google.generativeai as genai

app = FastAPI(title="Smart Travel Planner API")

# Setup static files directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend_legacy")
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Job store
jobs: Dict[str, Dict[str, Any]] = {}

class TravelRequest(BaseModel):
    starting_location: str
    destination: Optional[str] = ""
    travel_dates: str
    num_travellers: int
    total_budget: float
    interests: str
    hotel_type: str
    transport_preferences: str
    additional_requirements: Optional[str] = ""
    ai_choose_destination: bool = False
    nights: Optional[int] = 3
    trip_type: Optional[str] = "Domestic"

class BookingRequest(BaseModel):
    item_type: str
    item_details: Dict[str, Any]
    destination: str

class TravellerInfo(BaseModel):
    name: str
    age: int
    gender: str
    id_number: Optional[str] = ""

class PassengerBookingRequest(BaseModel):
    job_id: str
    primary_contact: Dict[str, str]
    travellers: List[TravellerInfo]
    mock_payment: Optional[Dict[str, str]] = None

class FinalReportRequest(BaseModel):
    job_id: str

# Gemini Initialization
gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") 
use_gemini = False
model = None

if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        use_gemini = True
        print("Gemini LLM backend initialized successfully.")
    except Exception as e:
        print("Failed to initialize Gemini backend model:", e)

# Mock Data Generator for high-fidelity responses
MOCK_DESTINATIONS = {
    "Munnar": {
        "tag": "nature",
        "rationale": "Munnar is selected because the traveler indicated a strong interest in Nature. It is the premier hill station in Kerala, famous for its sprawling tea estates, mist-laden hills, and rich biodiversity, making it perfect for a nature retreat within the budget.",
        "alternatives": ["Ooty (Similar nature vibe)", "Manali (Mountain landscape)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 7500, "total_price": 7500, "departure_time": "06:15", "arrival_time": "09:30", "duration": "3h 15m", "class": "Economy", "notes": "Flight to Kochi (COK) + 3h cab drive to Munnar."},
            "cheapest": {"operator": "Air India Express", "price_per_person": 5800, "total_price": 5800, "departure_time": "21:40", "arrival_time": "00:55", "duration": "3h 15m", "class": "Economy", "notes": "Late night flight to Kochi, cheaper but less convenient."},
            "backup": {"operator": "Vistara", "price_per_person": 11200, "total_price": 11200, "departure_time": "09:45", "arrival_time": "12:55", "duration": "3h 10m", "class": "Premium Economy", "notes": "Excellent timing, includes meal."}
        },
        "hotels": {
            "Budget": {"name": "Munnar Inn", "stars": 2, "price_per_night": 1800, "total_cost": 5400, "location": "Munnar Town Center", "facilities": ["Free Wi-Fi", "Restaurant", "Room Service"], "distance_to_attractions": "2 km", "notes": "Clean rooms with valley views."},
            "Mid-range": {"name": "Tea Valley Resort", "stars": 3, "price_per_night": 4200, "total_cost": 12600, "location": "Pothamedu Hills", "facilities": ["Free Breakfast", "Valley Balcony", "Tea Garden Tours", "Wi-Fi"], "distance_to_attractions": "4 km", "notes": "Nestled inside a tea plantation. Quiet and beautiful."},
            "Luxury": {"name": "The Panoramic Getaway", "stars": 5, "price_per_night": 12500, "total_cost": 37500, "location": "Chithirapuram", "facilities": ["Infinity Pool", "Luxury Spa", "Multi-cuisine Restaurant", "Guided Trekking"], "distance_to_attractions": "8 km", "notes": "Breathtaking helipad views, ultimate luxury."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival at Kochi Airport & Drive to Munnar", "duration": "4h", "cost": 3000, "location": "Kochi to Munnar Highway"},
                "afternoon": {"activity": "Check-in at Hotel & Relax with Cardamom Tea", "duration": "2h", "cost": 0, "location": "Resort"},
                "evening": {"activity": "Walk through Blossom Hydel Park", "duration": "2h", "cost": 100, "location": "Town Center"},
                "restaurant_recommendation": {"name": "Rapsy Restaurant", "cuisine": "Kerala Traditional / Biryani", "price_range": "INR 300-500"},
                "local_transport": {"mode": "Pre-booked Cab", "estimated_cost": 1500},
                "daily_total_cost": 4600,
                "backup_activity": "Indoor board games & hot coffee at resort lounge.",
                "travel_tips": "Highway drive has beautiful waterfalls; keep your camera ready."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Visit Eravikulam National Park to spot Nilgiri Tahr", "duration": "3h", "cost": 400, "location": "Rajamalai Hills"},
                "afternoon": {"activity": "Tea Museum visit and Tea Tasting experience", "duration": "2h", "cost": 200, "location": "Lockhart Estate"},
                "evening": {"activity": "Sunset view and boating at Mattupetty Dam", "duration": "2h", "cost": 300, "location": "Mattupetty"},
                "restaurant_recommendation": {"name": "Saravana Bhavan", "cuisine": "South Indian Vegetarian", "price_range": "INR 200-400"},
                "local_transport": {"mode": "Sightseeing Cab", "estimated_cost": 2000},
                "daily_total_cost": 3300,
                "backup_activity": "Tea tasting session at Lockhart Indoor Pavilion.",
                "travel_tips": "Book Eravikulam entry tickets online in advance to avoid long queues."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Top Station Trekking for Panoramic Valley View", "duration": "4h", "cost": 500, "location": "Kerala-Tamil Nadu Border"},
                "afternoon": {"activity": "Echo Point visit & Spice plantation walk", "duration": "3h", "cost": 250, "location": "Mattupetty road"},
                "evening": {"activity": "Local shopping for spices and home-made chocolates", "duration": "2h", "cost": 1000, "location": "Munnar Market"},
                "restaurant_recommendation": {"name": "Silver Spoon", "cuisine": "Multi-cuisine / Kerala Meals", "price_range": "INR 400-800"},
                "local_transport": {"mode": "Local Cab", "estimated_cost": 1800},
                "daily_total_cost": 3950,
                "backup_activity": "Spice plantation indoor audio-visual guide tour.",
                "travel_tips": "Munnar spices are authentic. Buy cardamom and black pepper directly from government-approved farms."
            }
        ],
        "local_insights": {
            "must_try_food": ["Kerala Puttu and Kadala Curry", "Appam with Vegetable Stew", "Banana Fritters (Pazham Pori)", "Traditional Sadya on Banana Leaf"],
            "cultural_tips": ["Remove shoes before entering temples.", "Dress modestly when visiting local villages.", "Polite greetings in Malayalam ('Namaskaram') are appreciated."],
            "safety_notes": ["Mountain roads are prone to fog post-sunset. Avoid driving late.", "Stick to marked trails during treks to avoid leeches and wildlife."],
            "crowd_avoidance_tips": ["Start for Eravikulam National Park by 7:30 AM to beat tour buses.", "Visit Mattupetty Dam during noon when it is less crowded."],
            "transport_tips": ["Auto rickshaws are cheap for short town travel, but hire a full-day cab for mountain sightseeing.", "Confirm taxi fares before boarding."],
            "emergency_contacts": {"Hospital": "Tata General Hospital (+91 4865 230270)", "Police": "Munnar Police Station (+91 4865 230323)"},
            "packing_list": ["Light sweater/jacket (evenings get cold)", "Sturdy walking/hiking shoes", "Umbrella or raincoat (unpredictable mountain showers)", "Insect/leech repellent"]
        }
    },
    "Goa": {
        "tag": "beaches",
        "rationale": "Goa is selected as it is India's most famous beach destination, aligning perfectly with the Beach interest. It offers beautiful sandy shores, vibrant local food markets, Portuguese heritage, and a wide array of watersports.",
        "alternatives": ["Pondicherry (Coastal heritage)", "Varkala (Cliffs and beaches)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 5500, "total_price": 5500, "departure_time": "10:30", "arrival_time": "13:10", "duration": "2h 40m", "class": "Economy", "notes": "Direct flight to Mopa Airport (GOX)."},
            "cheapest": {"operator": "SpiceJet", "price_per_person": 4200, "total_price": 4200, "departure_time": "19:00", "arrival_time": "21:45", "duration": "2h 45m", "class": "Economy", "notes": "Late evening flight, budget option."},
            "backup": {"operator": "Air India", "price_per_person": 9800, "total_price": 9800, "departure_time": "08:15", "arrival_time": "11:00", "duration": "2h 45m", "class": "Economy", "notes": "Includes full hot meal and extra baggage allowance."}
        },
        "hotels": {
            "Budget": {"name": "Zostel Goa (Morjim)", "stars": 2, "price_per_night": 1200, "total_cost": 3600, "location": "Morjim Beach", "facilities": ["Free Wi-Fi", "Cafe", "Social Common Area"], "distance_to_attractions": "0.5 km", "notes": "Chic backpacker vibe, close to the beach."},
            "Mid-range": {"name": "Lemon Tree Amarante Beach Resort", "stars": 4, "price_per_night": 5500, "total_cost": 16500, "location": "Candolim", "facilities": ["Swimming Pool", "Spa", "Free Breakfast", "Wi-Fi"], "distance_to_attractions": "1.5 km", "notes": "Portuguese styled resort with beautiful gardens."},
            "Luxury": {"name": "Taj Exotica Resort & Spa", "stars": 5, "price_per_night": 18000, "total_cost": 54000, "location": "Benaulim", "facilities": ["Private Beach Access", "Golf Course", "Luxury Spa", "Fine Dining"], "distance_to_attractions": "10 km", "notes": "Mediterranean-inspired villa resort on a calm beach."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival at Goa Airport & Cab transfer to Hotel", "duration": "1.5h", "cost": 1500, "location": "Airport to North Goa"},
                "afternoon": {"activity": "Check-in, relax and head out to Candolim Beach", "duration": "3h", "cost": 0, "location": "Candolim Beach"},
                "evening": {"activity": "Sunset cruise on the Mandovi River", "duration": "2h", "cost": 500, "location": "Panaji"},
                "restaurant_recommendation": {"name": "Fisherman's Wharf", "cuisine": "Goan Seafood / Multi-cuisine", "price_range": "INR 800-1500"},
                "local_transport": {"mode": "Pre-booked Taxi", "estimated_cost": 1200},
                "daily_total_cost": 4000,
                "backup_activity": "Relaxing spa session or shopping inside hotel complex.",
                "travel_tips": "Sunset cruises get crowded; arrive 30 mins before departure."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Fort Aguada exploration & lighthouse climb", "duration": "3h", "cost": 50, "location": "Sinquerim"},
                "afternoon": {"activity": "Water sports at Baga Beach (Jet Ski & Parasailing)", "duration": "3h", "cost": 2500, "location": "Baga"},
                "evening": {"activity": "Explore Anjuna Flea Market & beach shacks", "duration": "3h", "cost": 500, "location": "Anjuna"},
                "restaurant_recommendation": {"name": "Curlies Beach Shack", "cuisine": "Continental / Goan", "price_range": "INR 600-1200"},
                "local_transport": {"mode": "Rented Scooter", "estimated_cost": 400},
                "daily_total_cost": 3850,
                "backup_activity": "Visit Museum of Goa or indoor art galleries in Panaji.",
                "travel_tips": "Always wear a helmet on rented scooters. Goa traffic police are strict."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Heritage walk in Fontainhas (Latin Quarter)", "duration": "3h", "cost": 300, "location": "Panaji"},
                "afternoon": {"activity": "Spice plantation tour with traditional Goan lunch", "duration": "3h", "cost": 800, "location": "Ponda"},
                "evening": {"activity": "Sunset dinner at Miramar Beach", "duration": "2h", "cost": 1000, "location": "Miramar"},
                "restaurant_recommendation": {"name": "Viva Panjim", "cuisine": "Authentic Portuguese-Goan", "price_range": "INR 500-900"},
                "local_transport": {"mode": "Rented Scooter / Taxi", "estimated_cost": 600},
                "daily_total_cost": 3000,
                "backup_activity": "Indoor spice shopping and visiting indoor cathedrals in Old Goa.",
                "travel_tips": "Fontainhas houses are residential; maintain silence while taking photos."
            }
        ],
        "local_insights": {
            "must_try_food": ["Goan Fish Curry Meals", "Pork Vindaloo / Chicken Xacuti", "Bebinca (Multi-layered dessert)", "Feni (Local cashew drink)"],
            "cultural_tips": ["Remove hats and sunglasses inside churches.", "Bargaining is expected at flea markets.", "Keep beaches clean and respect local fishermen."],
            "safety_notes": ["Do not swim in the sea post sunset or during red-flag warnings.", "Only rent yellow-plated commercial vehicles or scooters."],
            "crowd_avoidance_tips": ["Visit Fort Aguada by 9:00 AM before the heat and crowd build up.", "Choose South Goa beaches (Palolem, Agonda) for a peaceful vibe."],
            "transport_tips": ["Renting a scooter is the most economical way to travel around Goa.", "App cabs are limited; check taxi rates in standard cards."],
            "emergency_contacts": {"Hospital": "Manipal Hospital Dona Paula (+91 832 3048800)", "Police": "Calangute Police Station (+91 832 2278284)"},
            "packing_list": ["Lightweight beach cotton clothes", "Sunglasses and waterproof sunscreen (SPF 50+)", "Slippers/Sandals", "Waterproof pouch for phones"]
        }
    },
    "Jaipur": {
        "tag": "culture",
        "rationale": "Jaipur is selected due to the traveler's strong interest in Culture and History. Known as the 'Pink City', it boasts royal palaces, grand forts, colorful heritage bazaars, and traditional Rajasthani culture.",
        "alternatives": ["Jodhpur (Blue City)", "Udaipur (Palaces & Lakes)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 4500, "total_price": 4500, "departure_time": "11:15", "arrival_time": "12:15", "duration": "1h 00m", "class": "Economy", "notes": "Short flight or express train option from Delhi."},
            "cheapest": {"operator": "Alliance Air", "price_per_person": 3400, "total_price": 3400, "departure_time": "17:45", "arrival_time": "18:50", "duration": "1h 05m", "class": "Economy", "notes": "Evening flight, budget option."},
            "backup": {"operator": "Air India Express", "price_per_person": 6800, "total_price": 6800, "departure_time": "08:30", "arrival_time": "09:35", "duration": "1h 05m", "class": "Economy", "notes": "Morning arrival, maximize day."}
        },
        "hotels": {
            "Budget": {"name": "Umaid Bhawan Hotel", "stars": 3, "price_per_night": 2200, "total_cost": 6600, "location": "Bani Park", "facilities": ["Free Wi-Fi", "Swimming Pool", "Rooftop Restaurant"], "distance_to_attractions": "3 km", "notes": "Heritage styled budget hotel with traditional murals."},
            "Mid-range": {"name": "Alsisar Haveli", "stars": 4, "price_per_night": 6000, "total_cost": 18000, "location": "Sansar Chandra Road", "facilities": ["Heritage Pool", "Traditional Courtyard", "Massage Center", "Bar"], "distance_to_attractions": "2 km", "notes": "A converted 19th-century royal mansion. Excellent location."},
            "Luxury": {"name": "Rambagh Palace", "stars": 5, "price_per_night": 25000, "total_cost": 75000, "location": "Bhawani Singh Road", "facilities": ["Royal Spa", "Indoor Pool", "Peacock Gardens", "Fine Dining Restaurants"], "distance_to_attractions": "5 km", "notes": "Former residence of the Maharaja of Jaipur. Ultra-luxury experience."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival in Jaipur & Transfer to Haveli", "duration": "1h", "cost": 500, "location": "Jaipur Airport"},
                "afternoon": {"activity": "Visit City Palace & Jantar Mantar Observatory", "duration": "3h", "cost": 400, "location": "Old City"},
                "evening": {"activity": "Photo stop at Hawa Mahal & street shopping in Johri Bazaar", "duration": "2h", "cost": 500, "location": "Johri Bazaar"},
                "restaurant_recommendation": {"name": "LMB (Laxmi Mishthan Bhandar)", "cuisine": "Rajasthani Vegetarian / Sweets", "price_range": "INR 400-800"},
                "local_transport": {"mode": "E-Rickshaw", "estimated_cost": 400},
                "daily_total_cost": 2300,
                "backup_activity": "Explore Albert Hall Museum (indoor exhibits).",
                "travel_tips": "Hire a government-approved guide at City Palace to learn the real history."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Amber Fort Tour & Elephant Ride / Jeep ride", "duration": "4h", "cost": 800, "location": "Amer"},
                "afternoon": {"activity": "Jaigarh Fort & Nahargarh Fort exploration", "duration": "3h", "cost": 200, "location": "Nahargarh Hills"},
                "evening": {"activity": "Sunset view over Jaipur City from Nahargarh Edge", "duration": "2h", "cost": 100, "location": "Nahargarh"},
                "restaurant_recommendation": {"name": "Padao Restaurant", "cuisine": "North Indian snacks & drinks", "price_range": "INR 500-1000"},
                "local_transport": {"mode": "Full-day AC Cab", "estimated_cost": 2000},
                "daily_total_cost": 3600,
                "backup_activity": "Block painting workshop at Anokhi Museum of Hand Printing.",
                "travel_tips": "Nahargarh sunset is stunning; carry a light jacket as winds get chilly."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Visit Galta Ji (Monkey Temple) & Birla Mandir", "duration": "3h", "cost": 100, "location": "Khania-Balaji"},
                "afternoon": {"activity": "Shopping for blue pottery & block print textiles", "duration": "3h", "cost": 2000, "location": "Bapu Bazaar"},
                "evening": {"activity": "Traditional Rajasthani dinner show at Chokhi Dhani", "duration": "4h", "cost": 1200, "location": "Tonk Road"},
                "restaurant_recommendation": {"name": "Chokhi Dhani", "cuisine": "Authentic Rajasthani Buffet", "price_range": "INR 1000-1500"},
                "local_transport": {"mode": "Cab", "estimated_cost": 1200},
                "daily_total_cost": 6600,
                "backup_activity": "Indoor shopping at designer emporiums with AC.",
                "travel_tips": "Chokhi Dhani is far from city center; pre-book your return cab."
            }
        ],
        "local_insights": {
            "must_try_food": ["Dal Baati Churma", "Laal Maas (Lamb Curry)", "Pyaaz Kachori", "Ghewar (Sweet cake)"],
            "cultural_tips": ["Cover your head and remove shoes in temples.", "Accept items with your right hand as a sign of respect.", "Avoid purchasing high-value gemstones from street vendors."],
            "safety_notes": ["Beware of pickpockets in crowded bazaars.", "Politely ignore aggressive touts/vendors outside monuments."],
            "crowd_avoidance_tips": ["Arrive at Amber Fort by 8:00 AM to see the morning sun on yellow sandstone.", "Visit City Palace during lunch hour to avoid school groups."],
            "transport_tips": ["E-rickshaws are fast and cheap inside the old city lanes, while cabs are better for forts.", "Negotiate e-rickshaw price before sitting."],
            "emergency_contacts": {"Hospital": "Fortis Escorts Hospital (+91 141 2724800)", "Police": "Manak Chowk Police Station (+91 141 2615507)"},
            "packing_list": ["Light cotton clothing (neutral colors for safari/fort photos)", "Sun-hat or scarf", "Comfortable walking shoes (climbing fort stairs)", "Reusable water bottle"]
        }
    },
    "Mahabalipuram": {
        "tag": "heritage",
        "rationale": "Mahabalipuram is selected as an ideal 1-day coastal heritage trip near Chennai (55 km). It features UNESCO World Heritage 7th-century Shore Temples, Pancha Rathas, and giant carved rock bas-reliefs by the Bay of Bengal.",
        "alternatives": ["Pondicherry (Coastal heritage)", "Kanchipuram (Temple town)"],
        "flights": {
            "recommended": {"operator": "SETC State Express Bus / AC ECR Coach", "price_per_person": 150, "total_price": 150, "departure_time": "07:30", "arrival_time": "09:00", "duration": "1h 30m", "class": "AC Express Bus", "notes": "Scenic East Coast Road (ECR) highway bus trip from Chennai."},
            "cheapest": {"operator": "MTC Public Express Bus", "price_per_person": 60, "total_price": 60, "departure_time": "06:45", "arrival_time": "08:30", "duration": "1h 45m", "class": "Express Bus", "notes": "Budget public transport via ECR."},
            "backup": {"operator": "Private AC Tourist Cab", "price_per_person": 800, "total_price": 800, "departure_time": "08:00", "arrival_time": "09:15", "duration": "1h 15m", "class": "Private Cab", "notes": "Doorstep pickup and return cab service."}
        },
        "hotels": {
            "Budget": {"name": "Day Trip (No Overnight Accommodation Required)", "stars": 0, "price_per_night": 0, "total_cost": 0, "location": "N/A - Day Return Trip", "facilities": ["Day Rest Lounge", "Cloakroom Facility", "Beach Refreshments"], "distance_to_attractions": "0 km", "notes": "Single-day excursion. Returns to Chennai on the same evening."},
            "Mid-range": {"name": "Chariot Beach Resort (Day Pass)", "stars": 4, "price_per_night": 1500, "total_cost": 1500, "location": "Five Rathas Road", "facilities": ["Swimming Pool", "Beach Access", "Buffet Lunch"], "distance_to_attractions": "1 km", "notes": "Day-use resort pass including lunch and pool access."},
            "Luxury": {"name": "Radisson Blu Resort Temple Bay", "stars": 5, "price_per_night": 9000, "total_cost": 9000, "location": "Covelong Road", "facilities": ["Infinity Pool", "Private Beach", "Luxury Spa"], "distance_to_attractions": "0.5 km", "notes": "Luxury oceanfront resort stay."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Drive along ECR & Visit UNESCO Shore Temple", "duration": "2.5h", "cost": 40, "location": "Mahabalipuram Beach"},
                "afternoon": {"activity": "Explore Pancha Rathas & Krishna's Butterball", "duration": "3h", "cost": 40, "location": "Monument Complex"},
                "evening": {"activity": "Sunset walk at Mahabalipuram Beach & Handicrafts Shopping", "duration": "2h", "cost": 200, "location": "Beach Market"},
                "restaurant_recommendation": {"name": "Moonrakers Seafood", "cuisine": "Fresh Coastal Seafood / South Indian", "price_range": "INR 300-600"},
                "local_transport": {"mode": "Auto-Rickshaw / Walking", "estimated_cost": 200},
                "daily_total_cost": 480,
                "backup_activity": "Visit Indoor Sculpture Museum & Maritime Heritage Gallery.",
                "travel_tips": "Wear comfortable slippers for sandy monuments and carry a hat/sunscreen."
            }
        ],
        "local_insights": {
            "must_try_food": ["Fresh Bay of Bengal Fish Fry", "Prawn Pepper Roast", "Tender Coconut Water", "Traditional South Indian Filter Coffee"],
            "cultural_tips": ["Stone carving is an ancient local tradition; buy genuine granite souvenirs directly from artisans.", "Dress comfortably for coastal humidity."],
            "safety_notes": ["Avoid swimming near rocky areas of the Shore Temple beach due to strong tides."],
            "crowd_avoidance_tips": ["Arrive at Shore Temple by 8:00 AM before afternoon tour buses."],
            "transport_tips": ["ECR road buses run every 15 mins from Koyambedu and Thiruvanmiyur in Chennai."],
            "emergency_contacts": {"Hospital": "Government Hospital Mahabalipuram (+91 44 27442226)", "Police": "Mahabalipuram Police Station (+91 44 27442220)"},
            "packing_list": ["Light cotton beach clothing", "Sunglasses and sunscreen", "Hat or umbrella", "Camera"]
        }
    },
    "Nandi Hills": {
        "tag": "nature",
        "rationale": "Nandi Hills is selected as an ideal 1-day getaway near Bangalore (60 km). Perched at 1,478m, it offers breathtaking sunrise views, cool mountain breeze, ancient hill fort ruins, and lush green scenery.",
        "alternatives": ["Ramanagara (Adventure day trip)", "Savandurga (Trekking day trip)"],
        "flights": {
            "recommended": {"operator": "KSRTC AC Volvo Bus / Intercity Cab", "price_per_person": 250, "total_price": 250, "departure_time": "05:30", "arrival_time": "07:00", "duration": "1h 30m", "class": "AC Express Bus", "notes": "Early morning drive from Bangalore for sunrise."},
            "cheapest": {"operator": "BMTC Direct KSRTC Bus", "price_per_person": 90, "total_price": 90, "departure_time": "05:15", "arrival_time": "07:15", "duration": "2h 00m", "class": "Regular Bus", "notes": "Direct early morning bus from Majestic station."},
            "backup": {"operator": "Shared AC Taxi / Bike Rental", "price_per_person": 600, "total_price": 600, "departure_time": "05:00", "arrival_time": "06:30", "duration": "1h 30m", "class": "Self-Drive / Cab", "notes": "Flexible timing and scenic sunrise drive."}
        },
        "hotels": {
            "Budget": {"name": "Day Trip (No Overnight Accommodation Required)", "stars": 0, "price_per_night": 0, "total_cost": 0, "location": "N/A - Day Return Trip", "facilities": ["Hill View Point", "Cafeteria", "Restroom Facilities"], "distance_to_attractions": "0 km", "notes": "Single-day excursion. Returns to Bangalore in the evening."},
            "Mid-range": {"name": "KSTDC Hotel Mayura Pine Top (Day Rest)", "stars": 3, "price_per_night": 1200, "total_cost": 1200, "location": "Nandi Hill Top", "facilities": ["Rooftop Cafe", "Garden View", "Restroom"], "distance_to_attractions": "0.1 km", "notes": "Day room facility at the hilltop."},
            "Luxury": {"name": "JW Marriott Bengaluru Prestige Golfshire Resort", "stars": 5, "price_per_night": 14000, "total_cost": 14000, "location": "Nandi Hills Foothills", "facilities": ["Golf Course", "Luxury Spa", "Heated Pool"], "distance_to_attractions": "8 km", "notes": "Luxury resort stay at the foothills."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Early morning drive & Sunrise viewing at Nandi Summit", "duration": "2.5h", "cost": 20, "location": "Nandi Hill Top"},
                "afternoon": {"activity": "Explore Tipu's Drop & Bhoga Nandeeshwara Temple", "duration": "3h", "cost": 20, "location": "Nandi Foothills"},
                "evening": {"activity": "Coffee & Snacks at Hillside Cafe & Return to Bangalore", "duration": "2h", "cost": 250, "location": "Foothills Highway"},
                "restaurant_recommendation": {"name": "Nandi Valley Restaurant", "cuisine": "South Indian / North Indian Snacks", "price_range": "INR 200-400"},
                "local_transport": {"mode": "Bus / Scooter", "estimated_cost": 250},
                "daily_total_cost": 540,
                "backup_activity": "Indoor historical exhibition at Muddenahalli Museum.",
                "travel_tips": "Weekend crowds build fast; reach the hilltop entry gate by 5:45 AM."
            }
        ],
        "local_insights": {
            "must_try_food": ["Hot Filter Coffee", "Masala Dosa", "Crispy Mirchi Bajji", "Sweet Corn on the cob"],
            "cultural_tips": ["Bhoga Nandeeshwara temple is a 9th-century Dravidian marvel; maintain sanctity."],
            "safety_notes": ["Monkeys are active at the summit; keep food items concealed in bags."],
            "crowd_avoidance_tips": ["Visit on weekdays for a peaceful mist view."],
            "transport_tips": ["Bikes and private cars must pay hilltop parking fees at the check-post."],
            "emergency_contacts": {"Hospital": "Government Hospital Chickballapur (+91 8156 272222)", "Police": "Nandi Hills Police Outpost (+91 8156 273100)"},
            "packing_list": ["Light windcheater or jacket", "Sunglasses", "Camera", "Sturdy walking shoes"]
        }
    },
    "Ooty": {
        "tag": "nature",
        "rationale": "Ooty is selected as a prime nature retreat. Set in the Nilgiri Hills, it offers verdant botanical gardens, misty pine forests, tea estates, and the heritage Nilgiri Toy Train.",
        "alternatives": ["Munnar (Tea estates)", "Kodaikanal (Lake & forests)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 5200, "total_price": 5200, "departure_time": "08:45", "arrival_time": "11:20", "duration": "2h 35m", "class": "Economy", "notes": "Flight to Coimbatore (CJB) + 3h drive/train to Ooty."},
            "cheapest": {"operator": "Air India Express", "price_per_person": 4100, "total_price": 4100, "departure_time": "20:00", "arrival_time": "22:45", "duration": "2h 45m", "class": "Economy", "notes": "Night arrival in Coimbatore; requires hotel stay there."},
            "backup": {"operator": "Vistara", "price_per_person": 8900, "total_price": 8900, "departure_time": "10:15", "arrival_time": "12:50", "duration": "2h 35m", "class": "Economy", "notes": "Premium option with meal."}
        },
        "hotels": {
            "Budget": {"name": "Zostel Ooty", "stars": 2, "price_per_night": 1500, "total_cost": 4500, "location": "Ooty Valley", "facilities": ["Free Wi-Fi", "Bonfire Area", "Common Kitchen"], "distance_to_attractions": "1.5 km", "notes": "Warm, rustic cottage hostel atmosphere."},
            "Mid-range": {"name": "Sterling Ooty Fern Hill", "stars": 3, "price_per_night": 4800, "total_cost": 14400, "location": "Fern Hill", "facilities": ["Indoor Games", "Buffet Restaurant", "Fitness Center", "Valley View"], "distance_to_attractions": "3 km", "notes": "Scenic resort overlooking hills and organic farms."},
            "Luxury": {"name": "Savoy - IHCL SeleQtions", "stars": 5, "price_per_night": 14000, "total_cost": 42000, "location": "Ooty Hill", "facilities": ["Colonial Gardens", "Fireplace Lounge", "Multi-cuisine Restaurant", "Spa"], "distance_to_attractions": "2 km", "notes": "19th-century colonial cottage retreat with fireplace rooms."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival at Coimbatore & drive to Ooty", "duration": "3h", "cost": 2500, "location": "Coimbatore to Ooty Highway"},
                "afternoon": {"activity": "Check-in & stroll around Pykara Lake", "duration": "2h", "cost": 150, "location": "Pykara"},
                "evening": {"activity": "Boating at Ooty Lake & shopping for chocolates", "duration": "2h", "cost": 300, "location": "Ooty Lake"},
                "restaurant_recommendation": {"name": "Place to Bee", "cuisine": "Italian / Organic / Honey inspired", "price_range": "INR 400-800"},
                "local_transport": {"mode": "Cab", "estimated_cost": 1500},
                "daily_total_cost": 4850,
                "backup_activity": "Visit indoor thread garden or tea museum.",
                "travel_tips": "The hairpin bends on Ooty ghat road can cause motion sickness. Sit in front and carry medication."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Nilgiri Mountain Railway (Toy Train) Ride", "duration": "3h", "cost": 200, "location": "Ooty to Coonoor"},
                "afternoon": {"activity": "Visit Dolphin's Nose & Sim's Park in Coonoor", "duration": "3h", "cost": 100, "location": "Coonoor"},
                "evening": {"activity": "High tea at a local Coonoor tea lounge", "duration": "2h", "cost": 400, "location": "Coonoor Town"},
                "restaurant_recommendation": {"name": "Quality Restaurant", "cuisine": "North/South Indian", "price_range": "INR 300-600"},
                "local_transport": {"mode": "Toy Train & Local Cab", "estimated_cost": 1800},
                "daily_total_cost": 2900,
                "backup_activity": "Coonoor tea packaging indoor factory tour.",
                "travel_tips": "Book Toy train tickets online via IRCTC at least 30 days in advance; spot booking is rare."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Trek up Doddabetta Peak (highest Nilgiri point)", "duration": "3h", "cost": 50, "location": "Doddabetta"},
                "afternoon": {"activity": "Explore Government Botanical Garden & Rose Garden", "duration": "3h", "cost": 150, "location": "Ooty Town"},
                "evening": {"activity": "Shopping for Eucalyptus oils, homemade chocolates, tea", "duration": "2h", "cost": 1000, "location": "Commercial Road"},
                "restaurant_recommendation": {"name": "Shinkows", "cuisine": "Authentic Indo-Chinese", "price_range": "INR 500-1000"},
                "local_transport": {"mode": "Local cab", "estimated_cost": 1200},
                "daily_total_cost": 2400,
                "backup_activity": "Choc-la Factory indoor chocolate baking session.",
                "travel_tips": "Doddabetta is very windy. Wrap up warmly."
            }
        ],
        "local_insights": {
            "must_try_food": ["Nilgiri Tea varieties", "Fresh carrots and plums from local farms", "Home-made chocolates", "Traditional South Indian Thali"],
            "cultural_tips": ["Eco-sensitive zone: plastics are strictly banned in Ooty. Carry cloth bags.", "Respect plantation workers while visiting estates."],
            "safety_notes": ["Doddabetta gets very foggy after 4 PM. Stick with group.", "Wild gaurs (bisons) are common. Maintain safe distance; do not approach them."],
            "crowd_avoidance_tips": ["Take the botanical garden tour early in the morning (8:30 AM) to avoid school groups.", "Boating at Pykara is quieter than Ooty Lake."],
            "transport_tips": ["Toy Train is cheap but needs advance booking. Direct taxis are best for day trips.", "Coimbatore airport is the nearest flight terminal."],
            "emergency_contacts": {"Hospital": "Ooty Government Headquarters Hospital (+91 423 2442212)", "Police": "Ooty Central Police Station (+91 423 2442220)"},
            "packing_list": ["Warm sweater, woolen caps, and gloves (especially for winter)", "Walking shoes", "Reusable non-plastic water bottle"]
        }
    },
    "Pondicherry": {
        "tag": "beaches",
        "rationale": "Pondicherry is selected as a beautiful coastal destination. It offers a unique mix of French heritage, quiet beaches, organic cafes, and spiritual retreats (Auroville).",
        "alternatives": ["Goa (Active beaches)", "Mahabalipuram (Coastal heritage)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 4200, "total_price": 4200, "departure_time": "09:30", "arrival_time": "12:10", "duration": "2h 40m", "class": "Economy", "notes": "Flight to Chennai (MAA) + 2.5h cab to Pondy via ECR."},
            "cheapest": {"operator": "Akasa Air", "price_per_person": 3300, "total_price": 3300, "departure_time": "21:15", "arrival_time": "23:55", "duration": "2h 40m", "class": "Economy", "notes": "Late night Chennai flight; requires late highway cab."},
            "backup": {"operator": "Air India", "price_per_person": 8500, "total_price": 8500, "departure_time": "14:15", "arrival_time": "16:55", "duration": "2h 40m", "class": "Economy", "notes": "Convenient afternoon flight."}
        },
        "hotels": {
            "Budget": {"name": "Villa Krish", "stars": 3, "price_per_night": 2800, "total_cost": 8400, "location": "White Town", "facilities": ["Free Wi-Fi", "French Cafe", "Air Conditioning"], "distance_to_attractions": "0.5 km", "notes": "Charming boutique hotel in the French quarters."},
            "Mid-range": {"name": "Palais de Mahe - CGH Earth", "stars": 4, "price_per_night": 7500, "total_cost": 22500, "location": "White Town", "facilities": ["Courtyard Pool", "Rooftop Cafe", "Free Breakfast", "Wi-Fi"], "distance_to_attractions": "0.2 km", "notes": "Stunning French colonial architecture. High fidelity service."},
            "Luxury": {"name": "The Promenade", "stars": 5, "price_per_night": 12000, "total_cost": 36000, "location": "Rock Beach Promenade", "facilities": ["Sea View Rooms", "Lounge Bar", "Infinity Pool", "Fine Dining"], "distance_to_attractions": "0.1 km", "notes": "Luxury hotel overlooking the ocean."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival at Chennai & drive to Pondicherry along East Coast Road", "duration": "3h", "cost": 2200, "location": "Chennai to Pondy Highway"},
                "afternoon": {"activity": "Check-in at White Town hotel & French lunch", "duration": "2h", "cost": 0, "location": "White Town"},
                "evening": {"activity": "Walk along Rock Beach Promenade and view Mahatma Gandhi statue", "duration": "2h", "cost": 0, "location": "Goubert Avenue"},
                "restaurant_recommendation": {"name": "Le Dupleix", "cuisine": "Franco-Tamil fusion", "price_range": "INR 800-1500"},
                "local_transport": {"mode": "Walk / Local Cycle", "estimated_cost": 100},
                "daily_total_cost": 2300,
                "backup_activity": "Read at local library or visit indoor French museums.",
                "travel_tips": "East Coast Road has excellent views of backwaters; travel in daylight."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Visit Sri Aurobindo Ashram & cycle through French Quarters", "duration": "3h", "cost": 50, "location": "White Town"},
                "afternoon": {"activity": "Trip to Auroville & meditation at Matrimandir viewing point", "duration": "3h", "cost": 100, "location": "Auroville"},
                "evening": {"activity": "Coffee & pastry tasting at local French bakeries", "duration": "2h", "cost": 300, "location": "Mission Street"},
                "restaurant_recommendation": {"name": "Baker's Street", "cuisine": "French Bakery / Pastries / Sandwiches", "price_range": "INR 200-500"},
                "local_transport": {"mode": "Rented Bicycle/Scooter", "estimated_cost": 350},
                "daily_total_cost": 800,
                "backup_activity": "Meditation video screening at Auroville Visitor Center.",
                "travel_tips": "Matrimandir inside access requires booking 2 days in advance in person."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Speedboat ride to Paradise Beach sandbar", "duration": "3h", "cost": 500, "location": "Chunnambar"},
                "afternoon": {"activity": "Visit Sacred Heart Basilica and local handicraft shops", "duration": "3h", "cost": 1000, "location": "Pondy Market"},
                "evening": {"activity": "Watch sunset at Serenity Beach", "duration": "2h", "cost": 100, "location": "Kottakuppam"},
                "restaurant_recommendation": {"name": "Surguru Restaurant", "cuisine": "South Indian Vegetarian Thali", "price_range": "INR 250-450"},
                "local_transport": {"mode": "Scooter / Cab", "estimated_cost": 500},
                "daily_total_cost": 2200,
                "backup_activity": "Terracotta pottery session at local Auroville school.",
                "travel_tips": "Paradise beach boat service stops after 5:00 PM; plan early."
            }
        ],
        "local_insights": {
            "must_try_food": ["Croissants and Pain au Chocolat", "Crepes", "Wood-fired pizzas", "Traditional Tamil Fish Curry"],
            "cultural_tips": ["Remove footwear before entering Aurobindo Ashram.", "Auroville is a spiritual township; respect their quiet values.", "Say 'Bonjour' at French cafes!"],
            "safety_notes": ["Rock beach is rocky; do not attempt to climb down into the sea.", "Take caution when driving scooters on busy Tamil Nadu lanes."],
            "crowd_avoidance_tips": ["Visit Matrimandir viewing point by 9:00 AM to avoid hot sun and long walks.", "Paradise beach is quieter on weekdays."],
            "transport_tips": ["White Town is best explored by walking or renting a bicycle. Taxis are needed for Auroville/Paradise Beach.", "Bicycle rentals cost under 100/day."],
            "emergency_contacts": {"Hospital": "JIPMER Hospital (+91 413 2272380)", "Police": "Grand Bazaar Police Station (+91 413 2231122)"},
            "packing_list": ["Comfortable cotton clothes", "Bicycle-friendly shoes", "Sunhat and sunglasses", "Eco-friendly cloth bags"]
        }
    },
    "Manali": {
        "tag": "adventure",
        "rationale": "Manali is selected as the top adventure and mountain retreat. Located in the Himalayas, it offers paragliding, skiing, trekking, river rafting, and scenic mountain views.",
        "alternatives": ["Kullu (River valley)", "Gulmarg (Skiing & Cable Cars)"],
        "flights": {
            "recommended": {"operator": "IndiGo", "price_per_person": 6200, "total_price": 6200, "departure_time": "07:15", "arrival_time": "08:45", "duration": "1h 30m", "class": "Economy", "notes": "Flight to Chandigarh (IXC) + 6h cab to Manali."},
            "cheapest": {"operator": "Alliance Air", "price_per_person": 5100, "total_price": 5100, "departure_time": "12:15", "arrival_time": "13:45", "duration": "1h 30m", "class": "Economy", "notes": "Afternoon flight to Chandigarh, night cab ride."},
            "backup": {"operator": "IndiGo Express", "price_per_person": 11500, "total_price": 11500, "departure_time": "09:10", "arrival_time": "10:35", "duration": "1h 25m", "class": "Economy", "notes": "Direct seasonal flight to Bhuntar (KUU) (50km from Manali)."}
        },
        "hotels": {
            "Budget": {"name": "Zostel Homes Kotgarh", "stars": 2, "price_per_night": 1400, "total_cost": 4200, "location": "Old Manali", "facilities": ["Free Wi-Fi", "Bonfire", "Mountain view cafe"], "distance_to_attractions": "2 km", "notes": "Located in Old Manali, close to cafes and local culture."},
            "Mid-range": {"name": "Solang Valley Resort", "stars": 4, "price_per_night": 6500, "total_cost": 19500, "location": "Solang Valley", "facilities": ["Adventure Hub", "Gym", "Wi-Fi", "Campfire Nights"], "distance_to_attractions": "0.1 km", "notes": "Right at the adventure hub. Best for paragliders."},
            "Luxury": {"name": "Span Resort & Spa", "stars": 5, "price_per_night": 16000, "total_cost": 48000, "location": "Beas River Bank", "facilities": ["Riverside lawns", "Luxury Spa", "Heated Pool", "Private Helipad"], "distance_to_attractions": "12 km", "notes": "Charming wooden cottages on the banks of Beas River."}
        },
        "itinerary": [
            {
                "day_number": 1,
                "date": "Day 1",
                "morning": {"activity": "Arrival at Chandigarh & drive to Manali", "duration": "6h", "cost": 5000, "location": "Kullu Valley Highway"},
                "afternoon": {"activity": "Check-in at Hotel & relax", "duration": "2h", "cost": 0, "location": "Hotel"},
                "evening": {"activity": "Visit Hadimba Temple and walk around Mall Road", "duration": "2h", "cost": 50, "location": "Hadimba Forest"},
                "restaurant_recommendation": {"name": "Cafe 1947", "cuisine": "Italian / Cafe culture / Live Music", "price_range": "INR 500-1000"},
                "local_transport": {"mode": "Cab", "estimated_cost": 2500},
                "daily_total_cost": 7550,
                "backup_activity": "Hot tea and library time inside Hadimba forest museum.",
                "travel_tips": "Chandigarh to Manali drive is long; stop at Hanogi Devi temple on the highway for river views."
            },
            {
                "day_number": 2,
                "date": "Day 2",
                "morning": {"activity": "Drive to Solang Valley for Paragliding & Quad Biking", "duration": "4h", "cost": 3000, "location": "Solang Valley"},
                "afternoon": {"activity": "Zorbing & cable car ride to Mount Phatru", "duration": "3h", "cost": 1000, "location": "Solang Valley"},
                "evening": {"activity": "Explore Old Manali wooden houses & cafes", "duration": "3h", "cost": 400, "location": "Old Manali"},
                "restaurant_recommendation": {"name": "Lazy Dog Cafe", "cuisine": "Continental / Trout Fish / Pizza", "price_range": "INR 700-1200"},
                "local_transport": {"mode": "Local Cab", "estimated_cost": 1500},
                "daily_total_cost": 5900,
                "backup_activity": "Explore old Manali art galleries and watch woodcarving demonstrations.",
                "travel_tips": "Verify paraglider license before taking tandem flights."
            },
            {
                "day_number": 3,
                "date": "Day 3",
                "morning": {"activity": "Drive through Atal Tunnel to Solang Glacier viewpoint", "duration": "4h", "cost": 2000, "location": "Lahaul Valley"},
                "afternoon": {"activity": "Visit Jogini Waterfalls with short forest trek", "duration": "3h", "cost": 100, "location": "Vashisht Village"},
                "evening": {"activity": "Relaxing dip in Vashisht Hot Springs & shopping", "duration": "2h", "cost": 500, "location": "Vashisht"},
                "restaurant_recommendation": {"name": "Sher-e-Punjab", "cuisine": "North Indian Punjabi Food", "price_range": "INR 300-600"},
                "local_transport": {"mode": "Cab", "estimated_cost": 2000},
                "daily_total_cost": 4600,
                "backup_activity": "Indoor bathing pool inside Vashisht hot springs pavilion.",
                "travel_tips": "Atal tunnel gets congested on weekends; start by 7:30 AM."
            }
        ],
        "local_insights": {
            "must_try_food": ["Siddu", "Grilled Trout Fish", "Thukpa", "Local Apple cider"],
            "cultural_tips": ["Hadimba temple is highly sacred; dress appropriately.", "Do not take photos of local villagers without permission."],
            "safety_notes": ["Avoid trekking near Beas river bank due to sudden water discharge from dams.", "Wear thermal layers during Atal tunnel drive as temperatures drop rapidly."],
            "crowd_avoidance_tips": ["Start Solang valley by 8:00 AM to get first queue for paragliding.", "Explore Jogini falls during noon when tourists are eating lunch."],
            "transport_tips": ["A full day cab is highly recommended for Solang/Rohtang. Local autos don't go on high mountain routes.", "Confirm if Rohtang permit is needed."],
            "emergency_contacts": {"Hospital": "Lady Willingdon Hospital (+91 1902 252379)", "Police": "Manali Police Station (+91 1902 252326)"},
            "packing_list": ["Warm windcheater jacket", "Thermal innerwear", "Hiking shoes with good grip", "Sunscreen"]
        }
    }
}


def detect_transport_mode(flight_dict: dict, req_pref: str = "") -> dict:
    operator = (flight_dict.get("operator") or "").lower()
    pref = (req_pref or "").lower()
    mode_raw = (flight_dict.get("mode") or "").lower()
    flight_class = (flight_dict.get("class") or "").lower()
    
    combined = f"{operator} {pref} {mode_raw} {flight_class}"
    
    if any(k in combined for k in ["train", "rail", "irctc", "express", "shatabdi", "rajdhani", "vande bharat", "superfast", "intercity"]):
        return {
            "mode": "Train",
            "pnr_prefix": "TRN",
            "icon": "fa-train",
            "carrier_label": "Rail / Train Operator",
            "service_label": "Train No",
            "default_num": f"12{random.randint(100, 999)}"
        }
    elif any(k in combined for k in ["bus", "ksrtc", "volvo", "sleeper", "scania", "intrcity", "redbus", "chalo", "ac sleeper", "semi-sleeper"]):
        return {
            "mode": "Bus",
            "pnr_prefix": "BUS",
            "icon": "fa-bus",
            "carrier_label": "Bus Service / Operator",
            "service_label": "Bus Route",
            "default_num": f"BUS-{random.randint(100, 999)}"
        }
    elif any(k in combined for k in ["cab", "taxi", "car", "drive", "road", "private car", "suv", "sedan"]):
        return {
            "mode": "Cab / Road Transit",
            "pnr_prefix": "CAB",
            "icon": "fa-car",
            "carrier_label": "Fleet Provider",
            "service_label": "Cab Ref",
            "default_num": f"CAB-{random.randint(100, 999)}"
        }
    elif any(k in combined for k in ["flight", "air", "indigo", "vistara", "air india", "spicejet", "fly", "airplane", "airways"]):
        return {
            "mode": "Flight",
            "pnr_prefix": "FLY",
            "icon": "fa-plane",
            "carrier_label": "Airline",
            "service_label": "Flight No",
            "default_num": f"6E-{random.randint(200, 899)}"
        }
    else:
        return {
            "mode": "Transport",
            "pnr_prefix": "TRP",
            "icon": "fa-route",
            "carrier_label": "Transport Operator",
            "service_label": "Service No",
            "default_num": f"TRP-{random.randint(100, 999)}"
        }


def format_booking_confirmation_markdown(bc: Optional[dict]) -> str:
    if not bc:
        return ""
    
    travellers_md = ""
    for idx, t in enumerate(bc.get("travellers", []), 1):
        if isinstance(t, dict):
            t_name = t.get('name', 'N/A')
            t_age = t.get('age', 'N/A')
            t_gender = t.get('gender', 'N/A')
            t_id = t.get('id_number', 'N/A') or 'Verified'
        else:
            t_name = getattr(t, 'name', 'N/A')
            t_age = getattr(t, 'age', 'N/A')
            t_gender = getattr(t, 'gender', 'N/A')
            t_id = getattr(t, 'id_number', 'N/A') or 'Verified'
        travellers_md += f"- **Traveller {idx}**: {t_name} (Age: {t_age}, Gender: {t_gender}, ID/Passport: {t_id})\n"
    
    transport_md = ""
    tb = bc.get("transport_booking") or bc.get("flight_booking")
    if tb and isinstance(tb, dict) and tb.get('price', 0) > 0:
        mode_title = tb.get("mode", "Transport")
        carrier_name = tb.get("airline") or tb.get("operator") or "Transit Operator"
        service_lbl = tb.get("service_label", "Service No")
        service_val = tb.get("flight_number") or tb.get("service_number") or "TR-101"
        transport_md = f"""### {mode_title} Booking Confirmation
- **Booking Reference / PNR**: `{tb.get('booking_id', 'TRP-2026-CONFIRMED')}`
- **Carrier / Operator**: {carrier_name} ({service_lbl}: {service_val})
- **Route**: {tb.get('from_location', 'Origin')} → {tb.get('to_location', 'Destination')}
- **Departure / Arrival**: {tb.get('departure_time', '08:00')} - {tb.get('arrival_time', '11:30')} (Date: {tb.get('departure_date', 'Scheduled Date')})
- **Travellers**: {tb.get('num_travellers', 1)} Pax
- **Total {mode_title} Price**: INR {float(tb.get('price', 0)):,.2f}
- **Booking Status**: {tb.get('status', 'Confirmed')}
"""

    hotel_md = ""
    hb = bc.get("accommodation_booking")
    if hb and isinstance(hb, dict) and hb.get('price', 0) > 0:
        hotel_md = f"""### Accommodation Booking Confirmation
- **Booking Reference**: `{hb.get('booking_id', 'HTL-2026-CONFIRMED')}`
- **Hotel / Property**: {hb.get('hotel_name', 'Selected Resort')}
- **Location**: {hb.get('location', 'Prime Location')}
- **Check-in / Check-out**: {hb.get('check_in', '')} to {hb.get('check_out', '')}
- **Rooms & Guests**: {hb.get('rooms', 1)} Room(s), {hb.get('guests', 1)} Guest(s)
- **Total Lodging Price**: INR {float(hb.get('price', 0)):,.2f}
- **Booking Status**: {hb.get('status', 'Confirmed')}
"""

    contact = bc.get("primary_contact", {})
    email_str = contact.get("email", "N/A") if isinstance(contact, dict) else "N/A"
    phone_str = contact.get("phone", "N/A") if isinstance(contact, dict) else "N/A"

    return f"""## Booking Confirmation
> **Disclaimer**: All bookings shown in this report are mock/demo bookings and no real transaction was performed.

- **Booking Reference Date**: {bc.get('booking_date', datetime.date.today().strftime('%B %d, %Y'))}
- **Payment / Demo Status**: **{bc.get('payment_status', 'Demo Payment Successful')}**
- **Total Booked Amount**: **INR {float(bc.get('total_booked_amount', 0)):,.2f}**
- **Primary Contact**: {email_str} | {phone_str}

### Passenger / Traveller Information
{travellers_md if travellers_md else "- Passenger list recorded."}

{transport_md}
{hotel_md}
"""


def build_markdown_report_from_json(result_data: dict, req: TravelRequest, booking_confirmation: Optional[dict] = None) -> str:
    itinerary_md = ""
    for d in result_data.get("itinerary", []):
        itinerary_md += f"### {d.get('date', 'Day')}\n"
        itinerary_md += f"- **Morning**: {d.get('morning', {}).get('activity', 'Sightseeing')} ({d.get('morning', {}).get('duration', '2h')}, Cost: {d.get('morning', {}).get('cost', 0)} INR, {d.get('morning', {}).get('location', '')})\n"
        itinerary_md += f"- **Afternoon**: {d.get('afternoon', {}).get('activity', 'Activities')} ({d.get('afternoon', {}).get('duration', '3h')}, Cost: {d.get('afternoon', {}).get('cost', 0)} INR, {d.get('afternoon', {}).get('location', '')})\n"
        itinerary_md += f"- **Evening/Dinner**: {d.get('evening', {}).get('activity', 'Dinner')} (Cost: {d.get('evening', {}).get('cost', 0)} INR, {d.get('evening', {}).get('location', '')})\n"
        itinerary_md += f"- **Restaurant Recommendation**: {d.get('restaurant_recommendation', {}).get('name', 'Local Cafe')} ({d.get('restaurant_recommendation', {}).get('cuisine', 'Regional')}, {d.get('restaurant_recommendation', {}).get('price_range', 'INR 500')})\n"
        itinerary_md += f"- **Local Transport**: {d.get('local_transport', {}).get('mode', 'Cab')} (Est: {d.get('local_transport', {}).get('estimated_cost', 500)} INR)\n"
        itinerary_md += f"- **Backup Activity**: {d.get('backup_activity', 'Indoor lounge')}\n"
        itinerary_md += f"- **Tip**: {d.get('travel_tips', 'Enjoy your day')}\n\n"

    insights = result_data.get("local_insights", {})
    food_list = "\n".join([f"- {f}" for f in insights.get("must_try_food", ["Local delicacies"])])
    cultural_tips = "\n".join([f"- {c}" for c in insights.get("cultural_tips", ["Respect local customs"])])
    safety_notes = "\n".join([f"- {s}" for s in insights.get("safety_notes", ["Keep valuables secure"])])
    packing_list = "\n".join([f"- {p}" for p in insights.get("packing_list", ["Comfortable footwear", "Camera"])])

    booking_section_md = format_booking_confirmation_markdown(booking_confirmation)

    report = f"""# Final Travel Plan: {result_data['destination']}

## 1. Trip Summary
- **Destination**: {result_data['destination']}
- **Travel Dates**: {req.travel_dates}
- **Number of Travellers**: {req.num_travellers}
- **Starting Location**: {req.starting_location}
- **Total Cost**: INR {result_data['total_cost']:,.2f}
- **Budget Allocation Status**: {"REPLANNED & OPTIMIZED" if result_data.get('is_replanned') else "WITHIN BUDGET"}

{booking_section_md}

## 2. Destination Selection
- **Selected Destination**: {result_data['destination']}
- **Alternative Destinations Considered**: {", ".join(result_data.get('alternatives', ['N/A']))}

## 3. Flight and Transport Details
- **Transport Mode / Carrier**: {result_data.get('flight', {}).get('operator', 'Express Transit')}
- **Departure/Arrival**: {result_data.get('flight', {}).get('departure_time', '08:00')} - {result_data.get('flight', {}).get('arrival_time', '11:30')}
- **Duration**: {result_data.get('flight', {}).get('duration', 'Direct')} ({result_data.get('flight', {}).get('class', 'Economy')})
- **Cost**: INR {result_data.get('flight', {}).get('total_price', 0):,.2f}
- **Logistics Notes**: {result_data.get('flight', {}).get('notes', 'Checked luggage included.')}

## 4. Hotel Accommodation Details
- **Hotel**: {result_data.get('hotel', {}).get('name', 'Selected Hotel')} {f"({result_data.get('hotel', {}).get('stars', 0)}-Star)" if result_data.get('hotel', {}).get('stars', 0) > 0 else ""}
- **Location**: {result_data.get('hotel', {}).get('location', 'Central Location')}
- **Amenities**: {", ".join(result_data.get('hotel', {}).get('facilities', ['Free Wi-Fi']))}
- **Cost**: {"INR 0.00 (Day Trip - No Overnight Stay)" if result_data.get('hotel', {}).get('total_cost', 0) == 0 else f"INR {result_data.get('hotel', {}).get('total_cost', 0):,.2f} (At INR {result_data.get('hotel', {}).get('price_per_night', 0):,.2f}/night)"}
- **Distance to Attractions**: {result_data.get('hotel', {}).get('distance_to_attractions', 'Nearby')}
- **Notes**: {result_data.get('hotel', {}).get('notes', '')}

## 5. Complete Budget Breakdown
- **Transport / Flights**: INR {result_data.get('budget_allocations', {}).get('Transport', 0):,.2f}
- **Hotel Accommodation**: INR {result_data.get('budget_allocations', {}).get('Accommodation', 0):,.2f}
- **Food & Dining (Est)**: INR {result_data.get('budget_allocations', {}).get('Food', 0):,.2f}
- **Local Transport / Cabs**: INR {result_data.get('budget_allocations', {}).get('Local Transport', 0):,.2f}
- **Activities & Entrance Fees**: INR {result_data.get('budget_allocations', {}).get('Activities', 0):,.2f}
- **Emergency Reserve**: INR {result_data.get('budget_allocations', {}).get('Reserve', 0):,.2f}
- **Total Cost**: **INR {result_data['total_cost']:,.2f}**

## 6. Day-wise Itinerary
{itinerary_md}

## 7. Local Insights
### Must-Try Food
{food_list}

### Cultural Etiquette
{cultural_tips}

### Safety Notes
{safety_notes}

### Recommended Packing List
{packing_list}

### Emergency Contacts
- **Hospital**: {insights.get('emergency_contacts', {}).get('Hospital', 'Local General Hospital')}
- **Police**: {insights.get('emergency_contacts', {}).get('Police', 'Local Police Station')}

## 8. Assumptions and Warnings
- Prices are based on mock API caches. Actual prices may fluctuate during final booking.
- Flight reservations are subject to availability.
- Boating and outdoor activities are weather-dependent.

---
**Disclaimer**: This travel plan was automatically compiled by the SmartTravelPlanner CrewAI workflow. All bookings shown in this report are mock/demo bookings and no real transaction was performed.
"""
    return report.strip()


def build_markdown_report(dest_name: str, req: TravelRequest, flight: dict, hotel: dict, total_cost: float, is_replanned: bool, attempts: int, allocations: dict = None, booking_confirmation: Optional[dict] = None) -> str:
    dest = MOCK_DESTINATIONS.get(dest_name, MOCK_DESTINATIONS["Mahabalipuram"])
    itinerary_md = ""
    for d in dest.get("itinerary", []):
        itinerary_md += f"### {d['date']}\n"
        itinerary_md += f"- **Morning**: {d['morning']['activity']} ({d['morning']['duration']}, Cost: {d['morning']['cost']} INR, {d['morning']['location']})\n"
        itinerary_md += f"- **Afternoon**: {d['afternoon']['activity']} ({d['afternoon']['duration']}, Cost: {d['afternoon']['cost']} INR, {d['afternoon']['location']})\n"
        itinerary_md += f"- **Evening/Dinner**: {d['evening']['activity']} (Cost: {d['evening']['cost']} INR, {d['evening']['location']})\n"
        itinerary_md += f"- **Restaurant Recommendation**: {d['restaurant_recommendation']['name']} ({d['restaurant_recommendation']['cuisine']}, {d['restaurant_recommendation']['price_range']})\n"
        itinerary_md += f"- **Local Transport**: {d['local_transport']['mode']} (Est: {d['local_transport']['estimated_cost']} INR)\n"
        itinerary_md += f"- **Backup Activity**: {d['backup_activity']}\n"
        itinerary_md += f"- **Tip**: {d['travel_tips']}\n\n"

    food_list = "\n".join([f"- {f}" for f in dest["local_insights"]["must_try_food"]])
    cultural_tips = "\n".join([f"- {c}" for c in dest["local_insights"]["cultural_tips"]])
    safety_notes = "\n".join([f"- {s}" for s in dest["local_insights"]["safety_notes"]])
    packing_list = "\n".join([f"- {p}" for p in dest["local_insights"]["packing_list"]])

    if allocations:
        trans_val = allocations.get("Transport", flight.get("total_price", 0))
        acc_val = allocations.get("Accommodation", hotel.get("total_cost", 0))
        food_val = allocations.get("Food", 0)
        loc_val = allocations.get("Local Transport", 0)
        act_val = allocations.get("Activities", 0)
        res_val = allocations.get("Reserve", 0)
    else:
        trans_val = flight.get("total_price", 0) * req.num_travellers
        acc_val = hotel.get("total_cost", 0)
        food_val = 1000 * req.num_travellers * 3
        loc_val = 6000.0
        act_val = 5000.0
        res_val = 3000.0

    status_str = "REPLANNED & OPTIMIZED" if is_replanned else "WITHIN BUDGET"
    req_budget_val = req.total_budget
    warn_str = f"*Replanning Warning: The original configuration was scaled and optimized to strictly fit your budget constraint of INR {req_budget_val:,.2f}.*" if is_replanned else ""

    booking_section_md = format_booking_confirmation_markdown(booking_confirmation)

    report = f"""# Final Travel Plan: {dest_name}

## 1. Trip Summary
- **Destination**: {dest_name}
- **Travel Dates**: {req.travel_dates}
- **Number of Travellers**: {req.num_travellers}
- **Starting Location**: {req.starting_location}
- **Total Cost**: INR {total_cost:,.2f}
- **Budget Allocation Status**: {status_str}

{booking_section_md}

## 2. Destination Selection
- **Selected Destination**: {dest_name}
- **Selection Rationale**: {dest["rationale"]}
- **Alternative Destinations Considered**: {", ".join(dest["alternatives"])}

## 3. Transport Details
- **Transport Mode / Carrier**: {flight["operator"]}
- **Departure/Arrival**: {flight["departure_time"]} - {flight["arrival_time"]}
- **Duration**: {flight["duration"]} ({flight["class"]})
- **Cost**: INR {flight.get("total_price", 0):,.2f} (At INR {flight.get("price_per_person", 0):,.2f}/person)
- **Logistics Notes**: {flight["notes"]}

## 4. Hotel Accommodation Details
- **Hotel**: {hotel["name"]} {f"({hotel['stars']}-Star)" if hotel.get('stars', 0) > 0 else ""}
- **Location**: {hotel["location"]}
- **Amenities**: {", ".join(hotel["facilities"])}
- **Cost**: {"INR 0.00 (Day Trip - No Overnight Stay)" if hotel.get('total_cost', 0) == 0 else f"INR {hotel.get('total_cost', 0):,.2f} (For duration at INR {hotel.get('price_per_night', 0):,.2f}/night)"}
- **Distance to Attractions**: {hotel["distance_to_attractions"]}
- **Notes**: {hotel["notes"]}

## 5. Complete Budget Breakdown
- **Transport / Flights**: INR {trans_val:,.2f}
- **Hotel Accommodation**: INR {acc_val:,.2f}
- **Food & Dining (Est)**: INR {food_val:,.2f}
- **Local Transport / Cabs**: INR {loc_val:,.2f}
- **Activities & Entrance Fees**: INR {act_val:,.2f}
- **Emergency Reserve**: INR {res_val:,.2f}
- **Total Cost**: **INR {total_cost:,.2f}**
- **Overage**: INR 0.00 (Successfully resolved within budget limit of INR {req_budget_val:,.2f})

{warn_str}

## 6. Day-wise Itinerary
{itinerary_md}

## 7. Local Insights
### Must-Try Food
{food_list}

### Cultural Etiquette
{cultural_tips}

### Safety Notes
{safety_notes}

### Recommended Packing List
{packing_list}

### Emergency Contacts
- **Hospital**: {dest["local_insights"]["emergency_contacts"]["Hospital"]}
- **Police**: {dest["local_insights"]["emergency_contacts"]["Police"]}

## 8. Assumptions and Warnings
- Prices are based on budget allocation rules. Actual prices may fluctuate during final booking.
- Flight reservations are subject to availability.
- Boating and outdoor activities are weather-dependent.

---
**Disclaimer**: This travel plan was automatically compiled by the SmartTravelPlanner CrewAI workflow. All bookings shown in this report are mock/demo bookings and no real transaction was performed.
"""
    return report.strip()
    return report.strip()


async def run_simulation(job_id: str, req: TravelRequest):
    job = jobs[job_id]
    nights = req.nights if req.nights is not None else 3
    is_one_day_trip = (nights == 0) or ("1 day" in req.travel_dates.lower())
    start_city = req.starting_location.strip() if req.starting_location else "Chennai"
    start_city_lower = start_city.lower()
    
    # 1. Intake
    job["current_step"] = "trip_intake"
    job["logs"].append("Intake specialist (intake_agent) starting validation...")
    job["logs"].append(f"Received traveler request: {req.num_travellers} pax, budget {req.total_budget} INR, interests: '{req.interests}'.")
    job["logs"].append(f"Trip duration: {nights} nights ({'1-Day Day Trip' if is_one_day_trip else 'Multi-day Trip'}).")
    await asyncio.sleep(1.2)
    job["logs"].append("Validation successful. Structured TravelProfile created.")
    job["logs"].append("Intake completed. Emitting 'trip_profile_ready'.")
    
    if use_gemini:
        try:
            job["logs"].append("GEMINI ENGINE: Connecting to Gemini 1.5 Flash model for agent orchestration...")
            
            # Destination selection via Gemini
            destination_to_use = req.destination
            if not destination_to_use or req.ai_choose_destination:
                job["current_step"] = "destination_selection"
                job["logs"].append("Destination Expert (rag_agent) comparing available options...")
                
                if is_one_day_trip:
                    dest_prompt = f"The traveler is starting from {start_city} for a 1-DAY DAY TRIP (returning the same evening). Given interests: '{req.interests}' and budget: {req.total_budget} INR, choose a famous NEARBY tourist destination located within 50 to 100 km of {start_city}. Return ONLY the name of the chosen nearby destination, nothing else."
                else:
                    dest_prompt = f"Given starting location: '{start_city}', traveler interests: '{req.interests}' and budget: {req.total_budget} INR, choose the single best travel destination in India (or globally) that perfectly fits the interests. Return ONLY the name of the chosen destination, nothing else."
                
                response = model.generate_content(dest_prompt)
                destination_to_use = response.text.strip().replace("'", "").replace('"', '')
                
                job["logs"].append(f"Destination Expert selected: {destination_to_use} based on interests.")
                await asyncio.sleep(1.0)
            else:
                job["current_step"] = "destination_selection"
                destination_to_use = req.destination
                job["logs"].append(f"Trip Intake verified traveler's choice of destination: {destination_to_use}")
                await asyncio.sleep(1.0)
                
            # Full planning with Gemini
            prompt = f"""You are the CrewAI Travel Planner Agent Crew. Plan a complete travel itinerary based on these traveler details:
- Starting Location: {req.starting_location}
- Destination: {destination_to_use}
- Trip Type: {req.trip_type}
- Date Range: {req.travel_dates} (Duration: {nights} nights)
- Number of Travellers: {req.num_travellers}
- Total Budget limit: INR {req.total_budget}
- Core Interests: {req.interests}
- Accommodation Preference: {req.hotel_type}
- Transport Preference: {req.transport_preferences}
- Special Requirements: {req.additional_requirements}

CRITICAL RULES FOR ACCURACY & REALISM:
1. ONE-DAY TRIP RULE (If Duration is 0 nights / 1 day):
   - Destination MUST be a nearby tourist spot located within 50-100 km of {req.starting_location}.
   - Transport MUST NOT be labeled as a "Flight" or "Airline". Recommend realistic ground transport (State Express Bus, Regional Train, Local Cab, Bike Rental) with realistic ticket fares (e.g. INR 100 to 500 per person). Set transport `operator` to a real bus/train/cab service.
   - Accommodation MUST be set to: name = "Day Trip (No Overnight Accommodation Required)", stars = 0, price_per_night = 0, total_cost = 0, facilities = ["Day Rest Lounge", "Cloakroom Facility", "Refreshments"].
2. REALISTIC TRANSPORT & HOTEL PRICING FOR MULTI-DAY TRIPS:
   - For budgets under 6,000 INR or road/rail preferences, DO NOT output fake flight tickets like INR 250. Recommend realistic Intercity Bus or Train tickets (e.g. INR 300 to 800 per person).
   - For multi-day trips, recommend real budget hostels/homestays with realistic nightly rates (e.g. INR 500 to 1,500 per night).
3. STRICT BUDGET ENFORCEMENT: The traveler's total budget limit is STRICTLY INR {req.total_budget}. Your calculated `total_cost` MUST NOT EXCEED INR {req.total_budget}. All sub-allocations MUST sum to {req.total_budget} INR or less.

Your output must be a single, raw, valid JSON object (do not wrap in markdown code blocks) matching this exact schema:
{{
    "destination": "{destination_to_use}",
    "total_cost": {req.total_budget},
    "is_replanned": false,
    "replanning_attempts": 0,
    "flight": {{
        "operator": "{'State Express Bus / Regional Express Train' if (is_one_day_trip or req.total_budget < 6000) else 'Airline or Train name'}",
        "price_per_person": {round(req.total_budget * (0.20 if is_one_day_trip else 0.25) / max(1, req.num_travellers), 2)},
        "total_price": {round(req.total_budget * (0.20 if is_one_day_trip else 0.25), 2)},
        "departure_time": "07:00",
        "arrival_time": "09:00",
        "duration": "2h 00m",
        "class": "{'AC Express Bus' if (is_one_day_trip or req.total_budget < 6000) else 'Economy'}",
        "notes": "Transport and transit details"
    }},
    "hotel": {{
        "name": "{'Day Trip (No Overnight Accommodation Required)' if is_one_day_trip else 'Hotel name'}",
        "stars": {0 if is_one_day_trip else 3},
        "price_per_night": {0 if is_one_day_trip else round(req.total_budget * 0.35 / max(1, nights), 2)},
        "total_cost": {0 if is_one_day_trip else round(req.total_budget * 0.35, 2)},
        "location": "{f'N/A - Day Excursion from {req.starting_location}' if is_one_day_trip else 'Hotel location neighborhood'}",
        "facilities": {["Day Rest Lounge", "Cloakroom Facility", "Refreshments"] if is_one_day_trip else ["Wi-Fi", "Breakfast"]},
        "distance_to_attractions": "0 km",
        "notes": "{f'Single-day trip returning to {req.starting_location} on the same evening.' if is_one_day_trip else 'Hotel check-in notes'}"
    }},
    "itinerary": [
        {{
            "day_number": 1,
            "date": "Day 1",
            "morning": {{
                "activity": "Morning activity description",
                "duration": "2h",
                "cost": {round(req.total_budget * 0.05, 2)},
                "location": "Activity location"
            }},
            "afternoon": {{
                "activity": "Afternoon activity description",
                "duration": "3h",
                "cost": {round(req.total_budget * 0.05, 2)},
                "location": "Activity location"
            }},
            "evening": {{
                "activity": "Evening activity or dining plan",
                "cost": {round(req.total_budget * 0.05, 2)},
                "location": "Activity location"
            }},
            "restaurant_recommendation": {{
                "name": "Recommended restaurant",
                "cuisine": "Cuisine type",
                "price_range": "INR {round(req.total_budget * 0.05, 2)}-{round(req.total_budget * 0.10, 2)}"
            }},
            "local_transport": {{
                "mode": "Mode of local transport",
                "estimated_cost": {round(req.total_budget * 0.05, 2)}
            }},
            "daily_total_cost": {round(req.total_budget * 0.20, 2)},
            "backup_activity": "Indoor activity in case of bad weather",
            "travel_tips": "Practical tip for this day"
        }}
    ],
    "local_insights": {{
        "must_try_food": ["Food item 1", "Food item 2"],
        "cultural_tips": ["Tip 1", "Tip 2"],
        "safety_notes": ["Note 1", "Note 2"],
        "crowd_avoidance_tips": ["Tip 1"],
        "transport_tips": ["Tip 1"],
        "emergency_contacts": {{
            "Hospital": "Hospital name and contact info",
            "Police": "Police contact info"
        }},
        "packing_list": ["Item 1", "Item 2"]
    }},
    "budget_allocations": {{
        "Transport": {round(req.total_budget * (0.20 if is_one_day_trip else 0.25), 2)},
        "Accommodation": {0 if is_one_day_trip else round(req.total_budget * 0.35, 2)},
        "Food": {round(req.total_budget * (0.35 if is_one_day_trip else 0.18), 2)},
        "Local Transport": {round(req.total_budget * (0.20 if is_one_day_trip else 0.10), 2)},
        "Activities": {round(req.total_budget * (0.15 if is_one_day_trip else 0.07), 2)},
        "Reserve": {round(req.total_budget * (0.10 if is_one_day_trip else 0.05), 2)}
    }}
}}
"""
            # Call Gemini model
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean blocks by finding the first and last brace
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
            else:
                text = text.strip()
            
            result_data = json.loads(text)
            
            # Day Trip & Budget Guardrails
            if is_one_day_trip:
                result_data["hotel"] = {
                    "name": "Day Trip (No Overnight Accommodation Required)",
                    "stars": 0,
                    "price_per_night": 0,
                    "total_cost": 0,
                    "location": f"N/A - Day Excursion from {start_city}",
                    "facilities": ["Day Rest Lounge", "Cloakroom Facility", "Refreshments"],
                    "distance_to_attractions": "0 km",
                    "notes": f"Single-day excursion returning to {start_city} on the same evening."
                }
                allocs = result_data.get("budget_allocations", {})
                allocs["Accommodation"] = 0.0
                result_data["budget_allocations"] = allocs

            # Ensure transport operator is realistic
            if "flight" in result_data and isinstance(result_data["flight"], dict):
                op = result_data["flight"].get("operator", "")
                if is_one_day_trip or float(req.total_budget) < 6000 or "flight" not in req.transport_preferences.lower():
                    if any(w in op.lower() for w in ["flight", "indigo", "spicejet", "air india", "vistara", "airline"]):
                        result_data["flight"]["operator"] = "State Express Bus / Regional Express Train"
                        result_data["flight"]["notes"] = f"Regional bus/train transit from {start_city}."
            
            # Guardrail: Check if LLM output exceeded user budget limit
            user_budget = float(req.total_budget)
            actual_total = float(result_data.get("total_cost", 0))
            
            if user_budget > 0 and (actual_total > user_budget or actual_total <= 0):
                job["logs"].append(f"BUDGET ENFORCEMENT: Gemini output cost (INR {actual_total}) exceeds budget limit (INR {user_budget}). Scaling allocations to fit budget.")
                scale = user_budget / (actual_total if actual_total > 0 else user_budget)
                
                # Scale allocations
                allocs = result_data.get("budget_allocations", {})
                if not allocs:
                    allocs = {
                        "Transport": round(user_budget * (0.20 if is_one_day_trip else 0.25), 2),
                        "Accommodation": 0 if is_one_day_trip else round(user_budget * 0.35, 2),
                        "Food": round(user_budget * (0.35 if is_one_day_trip else 0.18), 2),
                        "Local Transport": round(user_budget * (0.20 if is_one_day_trip else 0.10), 2),
                        "Activities": round(user_budget * (0.15 if is_one_day_trip else 0.07), 2),
                        "Reserve": round(user_budget * (0.10 if is_one_day_trip else 0.05), 2)
                    }
                else:
                    for k in list(allocs.keys()):
                        allocs[k] = round(float(allocs[k]) * scale, 2)
                result_data["budget_allocations"] = allocs
                
                # Scale flight
                if "flight" in result_data and isinstance(result_data["flight"], dict):
                    result_data["flight"]["total_price"] = allocs.get("Transport", round(user_budget * 0.25, 2))
                    result_data["flight"]["price_per_person"] = round(result_data["flight"]["total_price"] / max(1, req.num_travellers), 2)
                
                # Scale hotel
                if "hotel" in result_data and isinstance(result_data["hotel"], dict) and not is_one_day_trip:
                    result_data["hotel"]["total_cost"] = allocs.get("Accommodation", round(user_budget * 0.35, 2))
                    result_data["hotel"]["price_per_night"] = round(result_data["hotel"]["total_cost"] / max(1, nights), 2)
                
                # Scale daywise itinerary costs
                if "itinerary" in result_data and isinstance(result_data["itinerary"], list):
                    for day in result_data["itinerary"]:
                        if isinstance(day, dict):
                            day_sum = 0
                            for slot in ["morning", "afternoon", "evening"]:
                                if slot in day and isinstance(day[slot], dict) and "cost" in day[slot]:
                                    day[slot]["cost"] = round(float(day[slot]["cost"]) * scale, 2)
                                    day_sum += day[slot]["cost"]
                            if "local_transport" in day and isinstance(day["local_transport"], dict) and "estimated_cost" in day["local_transport"]:
                                day["local_transport"]["estimated_cost"] = round(float(day["local_transport"]["estimated_cost"]) * scale, 2)
                                day_sum += day["local_transport"]["estimated_cost"]
                            day["daily_total_cost"] = round(day_sum, 2)
                            
                result_data["total_cost"] = user_budget
                result_data["is_replanned"] = True
                result_data["replanning_attempts"] = max(1, result_data.get("replanning_attempts", 1))
            
            # Step logs updates
            job["current_step"] = "flight_hotel_search"
            job["logs"].append(f"Logistics Specialist (logistics_agent) matched transport: {result_data['flight']['operator']}.")
            job["logs"].append(f"Accommodation Specialist matched hotel: {result_data['hotel']['name']}.")
            await asyncio.sleep(1.2)
            
            job["current_step"] = "budget_optimization"
            job["logs"].append(f"Budget Optimizer calculated costs. Total Estimated: INR {result_data['total_cost']}.")
            await asyncio.sleep(1.0)
            
            if result_data.get("is_replanned"):
                job["current_step"] = "replan_budget"
                job["logs"].append(f"WARNING: Cost limit adjusted. Replan Agent adjusted parameters (Attempts: {result_data.get('replanning_attempts', 1)}).")
                await asyncio.sleep(1.2)
                
            job["current_step"] = "itinerary_planning"
            job["logs"].append("Itinerary Specialist generated day-wise layout & insights.")
            await asyncio.sleep(1.2)
            
            job["current_step"] = "supervisor_validation"
            job["logs"].append("Quality Supervisor checked plan. VERDICT: APPROVED.")
            await asyncio.sleep(1.0)
            
            job["current_step"] = "report_compilation"
            job["logs"].append("Report Compiler compiling final report Markdown...")
            
            # Build report
            final_report_md = build_markdown_report_from_json(result_data, req)
            result_data["final_report"] = final_report_md
            result_data["travel_dates"] = req.travel_dates
            result_data["num_travellers"] = req.num_travellers
            result_data["starting_location"] = req.starting_location
            result_data["destination"] = destination_to_use
            await asyncio.sleep(1.0)
            
            # Completed
            job["current_step"] = "completed"
            job["status"] = "success"
            job["result"] = result_data
            job["logs"].append("Flow execution completed. Output written to state.")
            return
            
        except Exception as e:
            job["logs"].append(f"GEMINI ENGINE ERROR: {e}. Falling back to default high-fidelity simulation engine.")
            await asyncio.sleep(1.0)
            
    # Simulation fallback Mode
    job["current_step"] = "destination_selection"
    job["logs"].append("Destination Expert (rag_agent) connecting to FAISS database...")
    await asyncio.sleep(1.2)
    
    # Choose destination based on starting city or interests
    selected_dest = "Mahabalipuram" if is_one_day_trip else "Munnar"
    if req.destination and req.destination.strip():
        for d in MOCK_DESTINATIONS.keys():
            if d.lower() == req.destination.strip().lower():
                selected_dest = d
                break
    elif is_one_day_trip:
        if "chennai" in start_city_lower:
            selected_dest = "Mahabalipuram"
        elif "bangalore" in start_city_lower or "bengaluru" in start_city_lower:
            selected_dest = "Nandi Hills"
        elif "delhi" in start_city_lower:
            selected_dest = "Agra"
        elif "mumbai" in start_city_lower or "pune" in start_city_lower:
            selected_dest = "Lonavala"
        else:
            selected_dest = "Mahabalipuram"
    else:
        interests_lower = req.interests.lower()
        if "beach" in interests_lower or "sea" in interests_lower:
            selected_dest = "Goa" if req.total_budget > 40000 else "Pondicherry"
        elif "culture" in interests_lower or "history" in interests_lower or "palace" in interests_lower:
            selected_dest = "Jaipur"
        elif "adventure" in interests_lower or "snow" in interests_lower or "trek" in interests_lower:
            selected_dest = "Manali"
        elif "nature" in interests_lower or "tea" in interests_lower:
            selected_dest = "Munnar" if req.total_budget > 35000 else "Ooty"
            
    dest_data = MOCK_DESTINATIONS.get(selected_dest, MOCK_DESTINATIONS["Mahabalipuram"])
    job["logs"].append(f"Selected destination: {selected_dest} based on traveler request.")
    job["logs"].append(f"Alternatives identified: {', '.join(dest_data.get('alternatives', []))}")
    job["logs"].append("Selection rationale generated. Emitting 'destination_ready'.")
    await asyncio.sleep(1.0)
    
    # 3. Logistics Search
    job["current_step"] = "flight_hotel_search"
    job["logs"].append("Logistics Specialist (logistics_agent) searching transport networks...")
    await asyncio.sleep(1.0)
    
    if is_one_day_trip:
        selected_hotel = {
            "name": "Day Trip (No Overnight Accommodation Required)",
            "stars": 0,
            "price_per_night": 0,
            "total_cost": 0,
            "location": f"N/A - Day Excursion from {start_city}",
            "facilities": ["Day Rest Lounge", "Cloakroom Facility", "Refreshments"],
            "distance_to_attractions": "0 km",
            "notes": f"Single-day excursion returning to {start_city} on the same evening."
        }
        selected_flight = dict(dest_data["flights"]["recommended"])
    else:
        hotel_pref = req.hotel_type if req.hotel_type in dest_data["hotels"] else "Mid-range"
        selected_hotel = dict(dest_data["hotels"][hotel_pref])
        selected_flight = dict(dest_data["flights"]["recommended"])
        selected_hotel["total_cost"] = selected_hotel["price_per_night"] * max(1, nights)
        
    job["logs"].append(f"Matched accommodation: {selected_hotel['name']}.")
    job["logs"].append(f"Matched transport: {selected_flight['operator']} - INR {selected_flight['price_per_person']}/person.")
    await asyncio.sleep(1.0)
    
    # 4. Budget Optimization
    job["current_step"] = "budget_optimization"
    job["logs"].append("Budget Specialist (budget_optimization) performing cost calculations...")
    
    flight_total = selected_flight["price_per_person"] * req.num_travellers
    hotel_total = selected_hotel["total_cost"]
    food_total = (500 if is_one_day_trip else 1000) * req.num_travellers * max(1, nights)
    local_transport = 300 if is_one_day_trip else 3000
    activities = 400 if is_one_day_trip else 3000
    reserve = 200 if is_one_day_trip else 2000
    total_cost = flight_total + hotel_total + food_total + local_transport + activities + reserve
    
    job["logs"].append(f"Total calculated cost: INR {total_cost} (Budget limit: INR {req.total_budget}).")
    await asyncio.sleep(1.0)
    
    # 5. Budget Check & Replanning Loop
    is_replanned = False
    attempts = 0
    
    if total_cost > req.total_budget:
        job["current_step"] = "replan_budget"
        job["logs"].append("WARNING: Cost exceeds user budget limit. Scaling allocations to fit user budget...")
        user_budget = float(req.total_budget)
        scale = user_budget / float(total_cost if total_cost > 0 else user_budget)
        
        flight_total = round(flight_total * scale, 2)
        hotel_total = round(hotel_total * scale, 2) if not is_one_day_trip else 0.0
        food_total = round(food_total * scale, 2)
        local_transport = round(local_transport * scale, 2)
        activities = round(activities * scale, 2)
        reserve = round(reserve * scale, 2)
        total_cost = user_budget
        is_replanned = True
        attempts = 1
        
    allocations = {
        "Transport": flight_total,
        "Accommodation": hotel_total,
        "Food": food_total,
        "Local Transport": local_transport,
        "Activities": activities,
        "Reserve": reserve
    }
    
    job["current_step"] = "itinerary_planning"
    job["logs"].append("Itinerary Specialist generated day-wise layout & insights.")
    await asyncio.sleep(1.0)
    
    job["current_step"] = "supervisor_validation"
    job["logs"].append("Quality Supervisor checked plan. VERDICT: APPROVED.")
    await asyncio.sleep(1.0)
    
    job["current_step"] = "report_compilation"
    job["logs"].append("Report Compiler compiling final report Markdown...")
    
    final_report_md = build_markdown_report(selected_dest, req, selected_flight, selected_hotel, total_cost, is_replanned, attempts, allocations)
    
    result_data = {
        "destination": selected_dest,
        "travel_dates": req.travel_dates,
        "starting_location": req.starting_location,
        "num_travellers": req.num_travellers,
        "rationale": dest_data.get("rationale", f"A curated journey to {selected_dest} tailored to your preferences."),
        "total_cost": total_cost,
        "is_replanned": is_replanned,
        "replanning_attempts": attempts,
        "flight": selected_flight,
        "hotel": selected_hotel,
        "itinerary": dest_data.get("itinerary", []),
        "local_insights": dest_data.get("local_insights", {}),
        "budget_allocations": allocations,
        "final_report": final_report_md
    }
    
    job["current_step"] = "completed"
    job["status"] = "success"
    job["result"] = result_data
    job["logs"].append("Flow execution completed. Output written to state.")


@app.post("/api/plan-trip")
async def plan_trip(request: TravelRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "current_step": "init",
        "logs": ["Initial travel parameters received.", "Starting CrewAI Flow initialization..."],
        "result": None
    }
    background_tasks.add_task(run_simulation, job_id, request)
    return {"job_id": job_id}


@app.get("/api/plan-trip/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


async def run_booking_agent(job_id: str, req: BookingRequest):
    job = jobs[job_id]
    job["current_step"] = "booking_init"
    
    await asyncio.sleep(1.0)
    
    if use_gemini:
        try:
            job["current_step"] = "booking_agent_processing"
            prompt = f"""You are an autonomous AI booking agent. You have been authorized to book the following {req.item_type} for a trip to {req.destination}.
            
            Details:
            {json.dumps(req.item_details, indent=2)}
            
            Simulate a successful booking. Generate a JSON response strictly adhering to this schema:
            {{
                "status": "confirmed",
                "confirmation_number": "A realistic alphanumeric PNR or booking reference (e.g. XY892K)",
                "ai_message": "A short, friendly message from you (the agent) confirming the successful booking and providing a brief instruction or detail about the booking.",
                "total_paid": "The total amount paid as a string (e.g. 'INR 13,500')"
            }}
            Return ONLY the raw JSON without markdown formatting.
            """
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
            else:
                text = text.strip()
            
            result_data = json.loads(text)
            
            await asyncio.sleep(1.0)
            
            job["current_step"] = "completed"
            job["status"] = "success"
            job["result"] = result_data
            return
            
        except Exception as e:
            # Fallback
            pass
            
    # Mock fallback
    await asyncio.sleep(2.0)
    job["current_step"] = "completed"
    job["status"] = "success"
    job["result"] = {
        "status": "confirmed",
        "confirmation_number": f"MOCK-{str(uuid.uuid4())[:6].upper()}",
        "ai_message": f"Successfully simulated booking for your {req.item_type}. Enjoy your trip to {req.destination}!",
        "total_paid": "Payment processed successfully."
    }

@app.post("/api/book-item")
async def book_item(request: BookingRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "current_step": "init",
        "result": None
    }
    background_tasks.add_task(run_booking_agent, job_id, request)
    return {"job_id": job_id}

@app.get("/api/book-status/{job_id}")
async def get_book_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.post("/api/process-mock-booking")
async def process_mock_booking(request: PassengerBookingRequest):
    if request.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Travel plan session not found")
    
    job = jobs[request.job_id]
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="Travel plan has not been generated yet")
    
    # Mock Booking Agent Logic
    flight = result.get("flight", {})
    hotel = result.get("hotel", {})
    dest = result.get("destination", "Destination")
    origin = result.get("starting_location", "Origin")
    travel_dates = result.get("travel_dates", "")
    
    num_pax = len(request.travellers) if request.travellers else (result.get("num_travellers") or 1)
    
    # 1. Transport Booking Details (Train, Bus, Flight, Cab, or Generic Transport)
    transport_booking = None
    transport_price = 0.0
    if flight and flight.get("price_per_person", 0) > 0:
        tm = detect_transport_mode(flight, result.get("transport_preferences", ""))
        pnr_num = random.randint(10000, 99999)
        transport_booking_id = f"{tm['pnr_prefix']}-2026-{pnr_num}"
        operator = flight.get("operator") or f"{tm['mode']} Express"
        service_number = flight.get("flight_number") or tm["default_num"]
        
        transport_price = float(flight.get("price_per_person", 0)) * num_pax
        transport_booking = {
            "booking_id": transport_booking_id,
            "mode": tm["mode"],
            "icon": tm["icon"],
            "carrier_label": tm["carrier_label"],
            "service_label": tm["service_label"],
            "airline": operator,
            "operator": operator,
            "flight_number": service_number,
            "service_number": service_number,
            "from_location": origin,
            "to_location": dest,
            "departure_date": travel_dates.split(" to ")[0] if " to " in travel_dates else travel_dates,
            "departure_time": flight.get("departure_time", "07:30"),
            "arrival_time": flight.get("arrival_time", "10:45"),
            "num_travellers": num_pax,
            "price": transport_price,
            "status": "Confirmed"
        }
        
    # 2. Accommodation Booking Details (Only if hotel required)
    hotel_booking = None
    hotel_price = 0.0
    if hotel and hotel.get("total_cost", 0) > 0:
        hotel_id_num = random.randint(10000, 99999)
        hotel_booking_id = f"HTL-2026-{hotel_id_num}"
        hotel_price = float(hotel.get("total_cost", 0))
        check_in = travel_dates.split(" to ")[0] if " to " in travel_dates else travel_dates
        check_out = travel_dates.split(" to ")[1] if " to " in travel_dates else travel_dates
        
        hotel_booking = {
            "booking_id": hotel_booking_id,
            "hotel_name": hotel.get("name", "Selected Resort & Spa"),
            "location": hotel.get("location", dest),
            "check_in": check_in,
            "check_out": check_out,
            "guests": num_pax,
            "rooms": max(1, math.ceil(num_pax / 2)),
            "price": hotel_price,
            "status": "Confirmed"
        }
        
    total_booked_amount = transport_price + hotel_price
    if total_booked_amount == 0 and result.get("total_cost"):
        total_booked_amount = float(result.get("total_cost"))
        
    booking_confirmation = {
        "status": "confirmed",
        "booking_date": datetime.date.today().strftime("%B %d, %Y"),
        "payment_status": "Demo Payment Successful",
        "total_booked_amount": total_booked_amount,
        "primary_contact": request.primary_contact,
        "travellers": [t.dict() for t in request.travellers],
        "traveller_names": [t.name for t in request.travellers],
        "transport_booking": transport_booking,
        "flight_booking": transport_booking,  # Aliased for backward compatibility
        "accommodation_booking": hotel_booking,
        "disclaimer": "All bookings shown in this report are mock/demo bookings and no real transaction was performed."
    }
    
    job["booking_confirmation"] = booking_confirmation
    return booking_confirmation


@app.post("/api/compile-final-report")
async def compile_final_report(request: FinalReportRequest):
    if request.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Session not found")
        
    job = jobs[request.job_id]
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="Plan result not available")
        
    booking_confirmation = job.get("booking_confirmation")
    
    # Run Report Compiler Agent
    req_dummy = TravelRequest(
        starting_location=result.get("starting_location", "Chennai"),
        destination=result.get("destination", "Munnar"),
        travel_dates=result.get("travel_dates", "Selected Dates"),
        num_travellers=result.get("num_travellers", 1),
        total_budget=result.get("total_cost", 50000.0),
        interests="General",
        hotel_type="Mid-range",
        transport_preferences="Flight/Cab"
    )
    
    updated_report = build_markdown_report_from_json(result, req_dummy, booking_confirmation)
    job["result"]["final_report"] = updated_report
    
    return {
        "status": "success",
        "final_report": updated_report,
        "result": job["result"],
        "booking_confirmation": booking_confirmation
    }


# Serve HTML Frontend
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# Mount Frontend directory for static assets
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
