from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import uvicorn
import os
import uuid
from pathlib import Path
import aiofiles
from datetime import datetime
import json

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.api import api_router
from app.services.audio_processor import AudioProcessor
from app.services.video_processor import VideoProcessor
from app.models.user import User
from app.core.security import get_current_user

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AudioEnhance Pro",
    description="Professional Audio/Video Noise Cleaning and Enhancement SaaS",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Initialize processors
audio_processor = AudioProcessor()
video_processor = VideoProcessor()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with upload interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user)):
    """User dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": current_user})

@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload and process audio/video file"""
    
    # Validate file type
    allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.mp4', '.avi', '.mov', '.mkv'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    # Create unique filename
    file_id = str(uuid.uuid4())
    original_filename = file.filename
    processed_filename = f"{file_id}{file_extension}"
    
    # Save uploaded file
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / processed_filename
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Determine processing type
    is_video = file_extension in {'.mp4', '.avi', '.mov', '.mkv'}
    
    # Add background task for processing
    if is_video:
        background_tasks.add_task(
            video_processor.process_video,
            file_path,
            file_id,
            current_user.id
        )
    else:
        background_tasks.add_task(
            audio_processor.process_audio,
            file_path,
            file_id,
            current_user.id
        )
    
    return {
        "message": "File uploaded successfully",
        "file_id": file_id,
        "filename": original_filename,
        "processing": True
    }

@app.get("/status/{file_id}")
async def get_processing_status(file_id: str, current_user: User = Depends(get_current_user)):
    """Get processing status of a file"""
    # This would typically query a database for status
    # For now, return a mock response
    return {
        "file_id": file_id,
        "status": "processing",
        "progress": 75
    }

@app.get("/download/{file_id}")
async def download_processed_file(file_id: str, current_user: User = Depends(get_current_user)):
    """Download processed file"""
    # This would typically query a database and return the processed file
    # For now, return a mock response
    return {"message": "File ready for download", "file_id": file_id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AudioEnhance Pro",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )