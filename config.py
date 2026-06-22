import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    NVIDIA_API_KEY_VISION = os.getenv("NVIDIA_API_KEY_VISION", "")
    NVIDIA_API_KEY_CHAT = os.getenv("NVIDIA_API_KEY_CHAT", "")
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
    # Alias for backward compatibility with integration-branch code
    WEAVIATE_COLLECTION_NAME = WEAVIATE_COLLECTION

    # Embeddings — bge-small matches MiniLM dims (384) but retrieves facts better
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    # Alias for backward compatibility with integration-branch code
    WEAVIATE_EMBEDDING_MODEL = os.getenv("WEAVIATE_EMBEDDING_MODEL", EMBEDDING_MODEL)

    # Chunking config (character-based) — smaller chunks improve factual precision
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Docling parser limits
    MAX_DOCLING_PAGES = int(os.getenv("MAX_DOCLING_PAGES", "30"))
    DOCLING_TIMEOUT = int(os.getenv("DOCLING_TIMEOUT", "120"))  # seconds

    # Feature flags (dev-speed defaults: false)
    ENABLE_VISION = os.getenv("ENABLE_VISION", "false").lower() == "true"
    ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true"
    ENABLE_WEAVIATE = os.getenv("ENABLE_WEAVIATE", "false").lower() == "true"

    # Docling pipeline controls
    ENABLE_OCR = os.getenv("ENABLE_OCR", "false").lower() == "true"
    ENABLE_TABLE_STRUCTURE = os.getenv("ENABLE_TABLE_STRUCTURE", "true").lower() == "true"

    # Retrieval performance tuning
    RETRIEVAL_LIMIT = int(os.getenv("RETRIEVAL_LIMIT", "30"))
    RERANK_POOL_SIZE = int(os.getenv("RERANK_POOL_SIZE", "35"))
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "10"))
    RETRIEVAL_STRONG_SCORE = float(os.getenv("RETRIEVAL_STRONG_SCORE", "0.82"))
    RERANK_MAX_CHARS = int(os.getenv("RERANK_MAX_CHARS", "512"))

    # Ingestion & data storage directories
    UPLOADS_DIR = os.path.join(os.getcwd(), "data", "uploads")
    PROCESSED_DIR = os.path.join(os.getcwd(), "data", "processed")

    @classmethod
    def validate(cls):
        """Simple checks to alert if necessary variables are missing."""
        if not cls.GROQ_API_KEY:
            print("[WARNING] GROQ_API_KEY is not set in environment variables.")
        if not cls.WEAVIATE_URL:
            print("[WARNING] WEAVIATE_URL is not set. Point it to your Weaviate Cloud cluster URL.")
        if not cls.WEAVIATE_API_KEY:
            # Weaviate can still work for local/dev clusters without auth.
            print("[WARNING] WEAVIATE_API_KEY is not set in environment variables (continuing).")
        return True
