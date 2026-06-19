import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "")
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")
    WEAVIATE_COLLECTION_NAME = os.getenv("WEAVIATE_COLLECTION_NAME", "DocuMindNode")
    WEAVIATE_EMBEDDING_MODEL = os.getenv("WEAVIATE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    
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
            print("[WARNING] WEAVIATE_API_KEY is not set. Weaviate Cloud access will fail without it.")
