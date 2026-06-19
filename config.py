import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")
    WEAVIATE_COLLECTION = os.getenv("WEAVIATE_COLLECTION", "DocumentNode")
    WEAVIATE_COLLECTION_NAME = os.getenv("WEAVIATE_COLLECTION_NAME", "DocuMindNode")
    WEAVIATE_EMBEDDING_MODEL = os.getenv("WEAVIATE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

    ENABLE_VISION = os.getenv("ENABLE_VISION", "false").lower() == "true"
    ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true"
    ENABLE_WEAVIATE = os.getenv("ENABLE_WEAVIATE", "false").lower() == "true"

    ENABLE_OCR = os.getenv("ENABLE_OCR", "false").lower() == "true"
    ENABLE_TABLE_STRUCTURE = os.getenv("ENABLE_TABLE_STRUCTURE", "true").lower() == "true"

    UPLOADS_DIR = os.path.join(os.getcwd(), "data", "uploads")
    PROCESSED_DIR = os.path.join(os.getcwd(), "data", "processed")

    @classmethod
    def validate(cls):
        if not cls.GROQ_API_KEY:
            print("[WARNING] GROQ_API_KEY is not set in environment variables.")
        if not cls.WEAVIATE_URL:
            raise ValueError("[ERROR] WEAVIATE_URL is not set.")
        if not cls.WEAVIATE_API_KEY:
            print("[WARNING] WEAVIATE_API_KEY is not set (continuing).")
        return True
