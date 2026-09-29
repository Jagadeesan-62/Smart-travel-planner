import sqlite3
import json
import os
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from smart_travel_planner.rag.config import DB_PATH

@contextmanager
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initializes the SQLite database tables if they do not exist."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        
        # Canonical structured place database table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS places (
                place_id TEXT PRIMARY KEY,
                place_name TEXT NOT NULL,
                alternative_names TEXT,
                country TEXT NOT NULL,
                state_or_province TEXT,
                district TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                tourist_category TEXT,
                short_description TEXT,
                detailed_description TEXT,
                historical_cultural_importance TEXT,
                major_attractions TEXT,
                available_activities TEXT,
                best_time_to_visit TEXT,
                recommended_visit_duration TEXT,
                opening_closing_hours TEXT,
                entry_fee TEXT,
                weekly_closing_day TEXT,
                weather_climate_info TEXT,
                nearest_airport TEXT,
                nearest_railway_station TEXT,
                road_accessibility TEXT,
                local_transport_options TEXT,
                nearby_hotels TEXT,
                local_food_restaurants TEXT,
                approximate_budget_category TEXT,
                family_suitability INTEGER,
                solo_travel_suitability INTEGER,
                accessibility_information TEXT,
                safety_notes TEXT,
                required_permits TEXT,
                nearby_tourist_places TEXT,
                source_url TEXT,
                source_name TEXT,
                last_verified_date TEXT,
                scope TEXT NOT NULL,
                confidence_score REAL,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Document chunks table mapped to FAISS vectors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS place_chunks (
                chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT,
                section TEXT NOT NULL,
                content TEXT NOT NULL,
                vector_id INTEGER,
                scope TEXT NOT NULL,
                FOREIGN KEY (place_id) REFERENCES places (place_id) ON DELETE CASCADE
            )
        """)
        
        # Index on vector_id and scope for fast retrieval during FAISS searches
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_vector ON place_chunks (scope, vector_id)
        """)
        
        # FAISS indexes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faiss_indices (
                scope TEXT PRIMARY KEY,
                index_data BLOB NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()

def save_place(place: Dict[str, Any]) -> str:
    """Saves or updates a tourist place in the SQLite database."""
    # Ensure lists/dicts are serialized to JSON strings
    def serialize(val):
        if val is None:
            return None
        if isinstance(val, (list, dict)):
            return json.dumps(val)
        return val

    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO places (
                place_id, place_name, alternative_names, country, state_or_province,
                district, city, latitude, longitude, tourist_category,
                short_description, detailed_description, historical_cultural_importance,
                major_attractions, available_activities, best_time_to_visit,
                recommended_visit_duration, opening_closing_hours, entry_fee,
                weekly_closing_day, weather_climate_info, nearest_airport,
                nearest_railway_station, road_accessibility, local_transport_options,
                nearby_hotels, local_food_restaurants, approximate_budget_category,
                family_suitability, solo_travel_suitability, accessibility_information,
                safety_notes, required_permits, nearby_tourist_places,
                source_url, source_name, last_verified_date, scope, confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            place["place_id"],
            place["place_name"],
            serialize(place.get("alternative_names")),
            place["country"],
            place.get("state_or_province"),
            place.get("district"),
            place.get("city"),
            place.get("latitude"),
            place.get("longitude"),
            serialize(place.get("tourist_category")),
            place.get("short_description"),
            place.get("detailed_description"),
            place.get("historical_cultural_importance"),
            serialize(place.get("major_attractions")),
            serialize(place.get("available_activities")),
            place.get("best_time_to_visit"),
            place.get("recommended_visit_duration"),
            place.get("opening_closing_hours"),
            place.get("entry_fee"),
            place.get("weekly_closing_day"),
            place.get("weather_climate_info"),
            place.get("nearest_airport"),
            place.get("nearest_railway_station"),
            place.get("road_accessibility"),
            place.get("local_transport_options"),
            serialize(place.get("nearby_hotels")),
            serialize(place.get("local_food_restaurants")),
            place.get("approximate_budget_category"),
            1 if place.get("family_suitability") else 0,
            1 if place.get("solo_travel_suitability") else 0,
            place.get("accessibility_information"),
            place.get("safety_notes"),
            place.get("required_permits"),
            serialize(place.get("nearby_tourist_places")),
            place.get("source_url"),
            place.get("source_name"),
            place.get("last_verified_date"),
            place["scope"],
            place.get("confidence_score", 1.0)
        ))
        conn.commit()
    return place["place_id"]

def get_place(place_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single place by ID, deserializing JSON fields."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM places WHERE place_id = ?", (place_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict_from_row(row)

def get_all_places(scope: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all places, optionally filtered by scope."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        if scope:
            cursor.execute("SELECT * FROM places WHERE scope = ?", (scope,))
        else:
            cursor.execute("SELECT * FROM places")
        return [dict_from_row(row) for row in cursor.fetchall()]

def save_chunk(place_id: str, section: str, content: str, vector_id: int, scope: str):
    """Saves a generated chunk and associates it with a FAISS vector ID."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO place_chunks (place_id, section, content, vector_id, scope)
            VALUES (?, ?, ?, ?, ?)
        """, (place_id, section, content, vector_id, scope))
        conn.commit()

def clear_chunks_for_scope(scope: str):
    """Clears all chunk assignments for a specific scope (useful before rebuild)."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM place_chunks WHERE scope = ?", (scope,))
        conn.commit()

def get_chunk_by_vector_id(vector_id: int, scope: str) -> Optional[Dict[str, Any]]:
    """Retrieves a chunk and its corresponding place details by FAISS vector_id and scope."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pc.section, pc.content, p.* 
            FROM place_chunks pc
            JOIN places p ON pc.place_id = p.place_id
            WHERE pc.vector_id = ? AND pc.scope = ?
        """, (vector_id, scope))
        row = cursor.fetchone()
        if not row:
            return None
        return dict_from_row(row)

def dict_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Helper to convert sqlite3.Row to Dict and parse JSON fields."""
    d = dict(row)
    json_fields = [
        "alternative_names", "tourist_category", "major_attractions",
        "available_activities", "nearby_hotels", "local_food_restaurants",
        "nearby_tourist_places"
    ]
    for field in json_fields:
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                d[field] = []
        else:
            d[field] = []
            
    # Convert booleans
    d["family_suitability"] = bool(d.get("family_suitability", 0))
    d["solo_travel_suitability"] = bool(d.get("solo_travel_suitability", 0))
    return d

def save_faiss_index_to_db(scope: str, index_bytes: bytes):
    """Saves or updates the serialized FAISS index for a scope in SQLite."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO faiss_indices (scope, index_data, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (scope, sqlite3.Binary(index_bytes)))
        conn.commit()

def load_faiss_index_from_db(scope: str) -> Optional[bytes]:
    """Retrieves the serialized FAISS index bytes for a scope from SQLite."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT index_data FROM faiss_indices WHERE scope = ?", (scope,))
        row = cursor.fetchone()
        if not row:
            return None
        return row["index_data"]
