import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import Config

# Initialize and validate configurations
Config.validate()
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
os.makedirs(Config.PROCESSED_DIR, exist_ok=True)

app = FastAPI(
    title="DocuMind Graph API",
    description="Agentic KG-RAG with Negative Graph Expansion",
    version="2.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema for query endpoint
class QueryRequest(BaseModel):
    query: str
    cross_doc: bool = False

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "message": "DocuMind Graph v2.0 API is running."
    }

@app.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts document uploads (PDF, DOCX) and saves them in the upload directory.
    """
    allowed_extensions = {".pdf", ".docx"}
    _, ext = os.path.splitext(file.filename.lower())
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {ext}. Only PDF and DOCX are allowed."
        )
    
    file_path = os.path.join(Config.UPLOADS_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "filename": file.filename,
            "status": "success",
            "message": "File uploaded successfully. Ingestion will follow."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

@app.post("/query")
async def query_pipeline(request: QueryRequest):
    """
    Query endpoint which will orchestrate Hybrid Search, Positive/Negative Graph Expansion, 
    and LLM generation (Day 2 task).
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty."
        )
        
    return {
        "query": request.query,
        "cross_doc": request.cross_doc,
        "response": "FastAPI skeleton response. Orchestration layer integration coming in Day 2.",
        "confidence_score": 0.0,
        "evidence": {
            "supporting": [],
            "exceptions": [],
            "contradictions": [],
            "risks": []
        },
        "risk_level": "None"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
