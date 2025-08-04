from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import aiofiles
import uuid
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.processing_job import ProcessingJob, JobStatus
from pydantic import BaseModel

router = APIRouter()

class FileInfo(BaseModel):
    file_id: str
    filename: str
    file_type: str
    status: str
    created_at: str
    file_size: int

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a file for processing"""
    
    # Validate file type
    allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.mp4', '.avi', '.mov', '.mkv'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format"
        )
    
    # Check file size
    if file.size > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 100MB"
        )
    
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
    
    # Determine file type
    file_type = "video" if file_extension in {'.mp4', '.avi', '.mov', '.mkv'} else "audio"
    
    # Create processing job record
    job = ProcessingJob(
        file_id=file_id,
        user_id=current_user.id,
        original_filename=original_filename,
        file_path=str(file_path),
        file_type=file_type,
        status=JobStatus.PENDING
    )
    
    db.add(job)
    db.commit()
    
    return {
        "message": "File uploaded successfully",
        "file_id": file_id,
        "filename": original_filename,
        "file_type": file_type,
        "status": "pending"
    }

@router.get("/list", response_model=List[FileInfo])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all files for the current user"""
    
    jobs = db.query(ProcessingJob).filter(
        ProcessingJob.user_id == current_user.id
    ).order_by(ProcessingJob.created_at.desc()).all()
    
    files = []
    for job in jobs:
        file_path = Path(job.file_path)
        file_size = file_path.stat().st_size if file_path.exists() else 0
        
        files.append(FileInfo(
            file_id=job.file_id,
            filename=job.original_filename,
            file_type=job.file_type,
            status=job.status.value,
            created_at=job.created_at.isoformat(),
            file_size=file_size
        ))
    
    return files

@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a processed file"""
    
    job = db.query(ProcessingJob).filter(
        ProcessingJob.file_id == file_id,
        ProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File processing not completed"
        )
    
    if not job.processed_file_path or not Path(job.processed_file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processed file not found"
        )
    
    return FileResponse(
        path=job.processed_file_path,
        filename=f"enhanced_{job.original_filename}",
        media_type="application/octet-stream"
    )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a file and its processing job"""
    
    job = db.query(ProcessingJob).filter(
        ProcessingJob.file_id == file_id,
        ProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete files
    if Path(job.file_path).exists():
        Path(job.file_path).unlink()
    
    if job.processed_file_path and Path(job.processed_file_path).exists():
        Path(job.processed_file_path).unlink()
    
    # Delete job record
    db.delete(job)
    db.commit()
    
    return {"message": "File deleted successfully"}