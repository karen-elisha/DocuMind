import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")
    
    # Ingestion & data storage directories
    UPLOADS_DIR = os.path.join(os.getcwd(), "data", "uploads")
    PROCESSED_DIR = os.path.join(os.getcwd(), "data", "processed")

    @classmethod
    def validate(cls):
        """Simple checks to alert if necessary variables are missing."""
        if not cls.GROQ_API_KEY:
            print("[WARNING] GROQ_API_KEY is not set in environment variables.")
