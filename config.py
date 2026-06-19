import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    # Groq models
    GROQ_VISION_MODEL = os.getenv(
        "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    )

    # Weaviate
    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    if "//" not in WEAVIATE_URL:
        if WEAVIATE_URL.startswith(("localhost", "127.0.0.1")):
            WEAVIATE_URL = f"http://{WEAVIATE_URL}"
        else:
            WEAVIATE_URL = f"https://{WEAVIATE_URL}"
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")
    WEAVIATE_COLLECTION = os.getenv("WEAVIATE_COLLECTION", "DocuMindNode")

    # Embeddings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # Chunking config (character-based)
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

    # Feature flags (dev-speed defaults: false)
    ENABLE_VISION = os.getenv("ENABLE_VISION", "false").lower() == "true"
    ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true"
    ENABLE_WEAVIATE = os.getenv("ENABLE_WEAVIATE", "false").lower() == "true"

    # Docling pipeline controls
    ENABLE_OCR = os.getenv("ENABLE_OCR", "false").lower() == "true"
    ENABLE_TABLE_STRUCTURE = os.getenv("ENABLE_TABLE_STRUCTURE", "true").lower() == "true"

    # Ingestion & data storage directories
    UPLOADS_DIR = os.path.join(os.getcwd(), "data", "uploads")
    PROCESSED_DIR = os.path.join(os.getcwd(), "data", "processed")

    @classmethod
    def validate(cls):
        """Simple checks to alert if necessary variables are missing."""
        if not cls.GROQ_API_KEY:
            print("[WARNING] GROQ_API_KEY is not set in environment variables.")
        if not cls.WEAVIATE_URL:
            raise ValueError("[ERROR] WEAVIATE_URL is not set.")
        if not cls.WEAVIATE_API_KEY:
            # Weaviate can still work for local/dev clusters without auth.
            print("[WARNING] WEAVIATE_API_KEY is not set in environment variables (continuing).")
        return True
