import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Database path
DB_PATH = os.path.join(DATA_DIR, "tourism.db")


# Metadata mapping file path
METADATA_MAPPING_PATH = os.path.join(DATA_DIR, "metadata_mapping.json")

# Model definitions
EMBEDDING_MODEL = "models/gemini-embedding-2"
GENERATIVE_MODEL = "gemini-2.5-flash"
