import faiss
import numpy as np
import os
import json
import logging
from typing import Dict, List, Any, Optional
from smart_travel_planner.rag.config import METADATA_MAPPING_PATH
from smart_travel_planner.rag.embeddings import get_embeddings_batch
from smart_travel_planner.rag.document_chunking import chunk_place_record
from smart_travel_planner.rag import metadata_storage

logger = logging.getLogger(__name__)

def create_new_index(dim: int = 768) -> faiss.IndexFlatIP:
    """Creates a new FAISS Flat Inner Product index for Cosine similarity search."""
    return faiss.IndexFlatIP(dim)

def save_faiss_index(index: faiss.Index, scope: str):
    """Saves the FAISS index to the SQLite database."""
    try:
        serialized = faiss.serialize_index(index)
        index_bytes = serialized.tobytes()
        metadata_storage.save_faiss_index_to_db(scope, index_bytes)
        logger.info(f"FAISS index for scope '{scope}' successfully saved to SQLite database.")
    except Exception as e:
        logger.error(f"Failed to save FAISS index for scope '{scope}' to database: {e}")
        raise e

def load_faiss_index(scope: str) -> Optional[faiss.IndexFlatIP]:
    """Loads the FAISS index from the SQLite database."""
    try:
        index_bytes = metadata_storage.load_faiss_index_from_db(scope)
        if index_bytes is None:
            logger.warning(f"FAISS index for scope '{scope}' not found in database.")
            return None
        serialized_np = np.frombuffer(index_bytes, dtype=np.uint8)
        index = faiss.deserialize_index(serialized_np)
        logger.info(f"FAISS index for scope '{scope}' successfully loaded from SQLite database.")
        return index
    except Exception as e:
        logger.error(f"Failed to load FAISS index for scope '{scope}' from database: {e}")
        return None

def update_metadata_mapping_file():
    """Builds a metadata mapping JSON file connecting FAISS vector IDs to SQLite records."""
    mapping = {"tamil_nadu": {}, "india": {}, "world": {}}
    
    with metadata_storage.get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT vector_id, scope, place_id, section FROM place_chunks WHERE vector_id IS NOT NULL")
        rows = cursor.fetchall()
        
        for row in rows:
            scope = row["scope"]
            vector_id = str(row["vector_id"])
            if scope in mapping:
                mapping[scope][vector_id] = {
                    "place_id": row["place_id"],
                    "section": row["section"]
                }
                
    with open(METADATA_MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    logger.info(f"Metadata mapping file updated at {METADATA_MAPPING_PATH}")

def rebuild_all_indices():
    """Rebuilds the FAISS indexes for all scopes from scratch using SQLite database records."""
    # Ensure tables exist
    metadata_storage.init_db()
    
    scopes = ["tamil_nadu", "india", "world"]
    
    for scope in scopes:
        logger.info(f"Rebuilding index for scope: {scope}...")
        
        # Get all places matching the scope
        places = metadata_storage.get_all_places(scope=scope)
        if not places:
            logger.warning(f"No places found in DB for scope: {scope}. Creating empty index.")
            index = create_new_index()
            save_faiss_index(index, scope)
            continue
            
        # Clear existing chunk metadata in SQLite for this scope
        metadata_storage.clear_chunks_for_scope(scope=scope)
        
        # Collect all chunks across all places in this scope
        all_chunks = []
        for place in places:
            chunks = chunk_place_record(place)
            all_chunks.extend(chunks)
            
        if not all_chunks:
            logger.warning(f"No chunks generated for scope: {scope}. Saving empty index.")
            index = create_new_index()
            save_faiss_index(index, scope)
            continue
            
        # Generate embeddings
        texts_to_embed = [c["content"] for c in all_chunks]
        logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks in scope {scope}...")
        embeddings = get_embeddings_batch(texts_to_embed)
        
        # Build FAISS index
        index = create_new_index()
        embeddings_np = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_np) # Normalize for Cosine Similarity
        
        index.add(embeddings_np)
        save_faiss_index(index, scope)
        
        # Save mappings in SQLite
        for idx, chunk in enumerate(all_chunks):
            metadata_storage.save_chunk(
                place_id=chunk["metadata"]["place_id"],
                section=chunk["section"],
                content=chunk["content"],
                vector_id=idx,
                scope=scope
            )
            
    # Dump mapping file
    update_metadata_mapping_file()
    logger.info("All indexes rebuilt successfully.")

def increment_index(scope: str, place_dict: Dict[str, Any]) -> int:
    """Incrementally indexes a single place record and appends its chunks to FAISS index."""
    # 1. Clean and save to SQLite
    from smart_travel_planner.rag.data_cleaning import clean_place_record
    cleaned_place = clean_place_record(place_dict)
    if not cleaned_place:
        logger.error(f"Failed to clean place record during incremental indexing: {place_dict.get('place_name')}")
        return 0
        
    place_id = metadata_storage.save_place(cleaned_place)
    
    # 2. Chunk the record
    chunks = chunk_place_record(cleaned_place)
    if not chunks:
        return 0
        
    # 3. Load existing index
    index = load_faiss_index(scope)
    if index is None:
        index = create_new_index()
        
    # Current vector count determines the starting vector ID
    start_vector_id = index.ntotal
    
    # 4. Generate embeddings for new chunks
    texts_to_embed = [c["content"] for c in chunks]
    embeddings = get_embeddings_batch(texts_to_embed)
    
    embeddings_np = np.array(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings_np)
    
    # 5. Add to FAISS and save
    index.add(embeddings_np)
    save_faiss_index(index, scope)
    
    # 6. Save mapping in SQLite
    for i, chunk in enumerate(chunks):
        metadata_storage.save_chunk(
            place_id=place_id,
            section=chunk["section"],
            content=chunk["content"],
            vector_id=start_vector_id + i,
            scope=scope
        )
        
    # 7. Update JSON mapping file
    update_metadata_mapping_file()
    logger.info(f"Incrementally added {cleaned_place['place_name']} with {len(chunks)} chunks to {scope} index.")
    return len(chunks)
