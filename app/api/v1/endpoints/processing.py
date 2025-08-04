from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.processing_job import ProcessingJob, JobStatus
from app.services.audio_processor import AudioProcessor
from app.services.video_processor import VideoProcessor
from pydantic import BaseModel

router = APIRouter()

# Initialize processors
audio_processor = AudioProcessor()
video_processor = VideoProcessor()

class ProcessingStatus(BaseModel):
    file_id: str
    status: str
    progress: int
    error_message: str = None
    estimated_time_remaining: int = None

class ProcessingJobInfo(BaseModel):
    id: int
    file_id: str
    original_filename: str
    file_type: str
    status: str
    progress: int
    created_at: str
    updated_at: str

@router.get("/status/{file_id}", response_model=ProcessingStatus)
async def get_processing_status(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get processing status of a specific file"""
    
    job = db.query(ProcessingJob).filter(
        ProcessingJob.file_id == file_id,
        ProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found"
        )
    
    return ProcessingStatus(
        file_id=job.file_id,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message
    )

@router.get("/jobs", response_model=List[ProcessingJobInfo])
async def list_processing_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all processing jobs for the current user"""
    
    jobs = db.query(ProcessingJob).filter(
        ProcessingJob.user_id == current_user.id
    ).order_by(ProcessingJob.created_at.desc()).all()
    
    return [
        ProcessingJobInfo(
            id=job.id,
            file_id=job.file_id,
            original_filename=job.original_filename,
            file_type=job.file_type,
            status=job.status.value,
            progress=job.progress,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat() if job.updated_at else None
        )
        for job in jobs
    ]

@router.post("/process/{file_id}")
async def start_processing(
    file_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start processing a file"""
    
    job = db.query(ProcessingJob).filter(
        ProcessingJob.file_id == file_id,
        ProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found"
        )
    
    if job.status == JobStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is already being processed"
        )
    
    if job.status == JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File has already been processed"
        )
    
    # Update job status
    job.status = JobStatus.PROCESSING
    job.progress = 0
    db.commit()
    
    # Add background task for processing
    if job.file_type == "video":
        background_tasks.add_task(
            _process_video_job,
            job.id,
            Path(job.file_path),
            job.file_id,
            current_user.id,
            db
        )
    else:
        background_tasks.add_task(
            _process_audio_job,
            job.id,
            Path(job.file_path),
            job.file_id,
            current_user.id,
            db
        )
    
    return {
        "message": "Processing started",
        "file_id": file_id,
        "status": "processing"
    }

@router.delete("/cancel/{file_id}")
async def cancel_processing(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a processing job"""
    
    job = db.query(ProcessingJob).filter(
        ProcessingJob.file_id == file_id,
        ProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found"
        )
    
    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed or failed jobs"
        )
    
    # Update job status
    job.status = JobStatus.FAILED
    job.error_message = "Processing cancelled by user"
    db.commit()
    
    return {
        "message": "Processing cancelled",
        "file_id": file_id
    }

async def _process_audio_job(job_id: int, file_path: Path, file_id: str, user_id: int, db: Session):
    """Background task for processing audio files"""
    try:
        # Get fresh database session
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
        
        # Update progress
        job.progress = 10
        db.commit()
        
        # Process audio
        result = audio_processor.process_audio(file_path, file_id, user_id)
        
        if result["status"] == "completed":
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.processed_file_path = result["output_path"]
        else:
            job.status = JobStatus.FAILED
            job.error_message = result.get("error", "Unknown error")
        
        db.commit()
        
    except Exception as e:
        # Update job with error
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()

async def _process_video_job(job_id: int, file_path: Path, file_id: str, user_id: int, db: Session):
    """Background task for processing video files"""
    try:
        # Get fresh database session
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
        
        # Update progress
        job.progress = 10
        db.commit()
        
        # Process video
        result = video_processor.process_video(file_path, file_id, user_id)
        
        if result["status"] == "completed":
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.processed_file_path = result["output_path"]
        else:
            job.status = JobStatus.FAILED
            job.error_message = result.get("error", "Unknown error")
        
        db.commit()
        
    except Exception as e:
        # Update job with error
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()