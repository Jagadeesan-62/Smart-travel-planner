import os
import time
import logging
from typing import List, Union
import google.generativeai as genai
from smart_travel_planner.rag.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Fallback API Key used in server.py
DEFAULT_API_KEY = "AIzaSyCsehVYbggmlA-HE76XbUaIT0GnEDVgzfE"
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or DEFAULT_API_KEY

genai.configure(api_key=api_key)

# Global tracking variable for active model to support dynamic fallback on daily quota exhaustion
CURRENT_EMBEDDING_MODEL = EMBEDDING_MODEL
DAILY_QUOTA_EXHAUSTED = False

def get_embedding(text: str, task_type: str = "retrieval_document") -> List[float]:
    """Generates an embedding vector for a single text chunk using Gemini API."""
    global CURRENT_EMBEDDING_MODEL, DAILY_QUOTA_EXHAUSTED
    if DAILY_QUOTA_EXHAUSTED:
        return [0.0] * 768
        
    if not text.strip():
        # Return dummy vector for empty texts
        return [0.0] * 768
        
    for attempt in range(10):
        try:
            response = genai.embed_content(
                model=CURRENT_EMBEDDING_MODEL,
                content=text,
                task_type=task_type,
                output_dimensionality=768
            )
            return response["embedding"]
        except Exception as e:
            logger.warning(f"Error generating embedding (attempt {attempt + 1}/10): {e}")
            err_str = str(e)
            if "ResourceExhausted" in str(type(e)) or "429" in err_str or "quota" in err_str.lower():
                if "EmbedContentRequestsPerDay" in err_str or "daily" in err_str.lower() or "limit: 1000" in err_str:
                    if CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-2":
                        logger.info("Daily quota exceeded for gemini-embedding-2. Falling back to gemini-embedding-001...")
                        CURRENT_EMBEDDING_MODEL = "models/gemini-embedding-001"
                        time.sleep(2.0)
                        continue
                    elif CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-001":
                        logger.info("Daily quota exceeded for gemini-embedding-001. Falling back to gemini-embedding-2-preview...")
                        CURRENT_EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
                        time.sleep(2.0)
                        continue
                    elif CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-2-preview":
                        logger.warning("Daily quota exceeded for all fallback embedding models! Switching to local zero-vector mode.")
                        DAILY_QUOTA_EXHAUSTED = True
                        return [0.0] * 768
                logger.info("Rate limit hit. Sleeping for 60 seconds...")
                time.sleep(60.0)
            else:
                if attempt < 9:
                    time.sleep(2.0)
                else:
                    raise e
    return [0.0] * 768

def get_embeddings_batch(texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
    """Generates embeddings for a batch of text chunks, handles batch size limits."""
    global CURRENT_EMBEDDING_MODEL, DAILY_QUOTA_EXHAUSTED
    if not texts:
        return []
        
    if DAILY_QUOTA_EXHAUSTED:
        return [[0.0] * 768 for _ in texts]
        
    # Gemini API can accept list of strings. Limit batch size to 20 to avoid size issues or rate limits.
    batch_size = 20
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        chunk_batch = texts[i:i+batch_size]
        # Clean empty texts in batch
        cleaned_batch = [t if t.strip() else "empty text" for t in chunk_batch]
        
        if DAILY_QUOTA_EXHAUSTED:
            embeddings.extend([[0.0] * 768 for _ in cleaned_batch])
            continue
            
        for attempt in range(10):
            try:
                response = genai.embed_content(
                    model=CURRENT_EMBEDDING_MODEL,
                    content=cleaned_batch,
                    task_type=task_type,
                    output_dimensionality=768
                )
                embeddings.extend(response["embedding"])
                break
            except Exception as e:
                logger.warning(f"Error generating batch embeddings (attempt {attempt + 1}/10): {e}")
                err_str = str(e)
                if "ResourceExhausted" in str(type(e)) or "429" in err_str or "quota" in err_str.lower():
                    if "EmbedContentRequestsPerDay" in err_str or "daily" in err_str.lower() or "limit: 1000" in err_str:
                        if CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-2":
                            logger.info("Daily quota exceeded for gemini-embedding-2. Falling back to gemini-embedding-001...")
                            CURRENT_EMBEDDING_MODEL = "models/gemini-embedding-001"
                            time.sleep(2.0)
                            continue
                        elif CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-001":
                            logger.info("Daily quota exceeded for gemini-embedding-001. Falling back to gemini-embedding-2-preview...")
                            CURRENT_EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
                            time.sleep(2.0)
                            continue
                        elif CURRENT_EMBEDDING_MODEL == "models/gemini-embedding-2-preview":
                            logger.warning("Daily quota exceeded for all fallback embedding models! Switching to local zero-vector mode.")
                            DAILY_QUOTA_EXHAUSTED = True
                            # fill remainder of this batch with zero vectors
                            needed = len(cleaned_batch) - (len(embeddings) % batch_size) if len(embeddings) > 0 else len(cleaned_batch)
                            embeddings.extend([[0.0] * 768 for _ in range(needed)])
                            break
                    logger.info("Rate limit hit. Sleeping for 60 seconds...")
                    time.sleep(60.0)
                else:
                    if attempt < 9:
                        time.sleep(2.0)
                    else:
                        # Fallback to single requests if batch fails
                        for text in cleaned_batch:
                            embeddings.append(get_embedding(text, task_type))
        
        # Respect rate limits
        if i + batch_size < len(texts):
            time.sleep(1.0)
                        
    return embeddings
