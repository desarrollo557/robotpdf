"""
FastAPI Router for PDF Upload and Job Creation
"""

import os
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import UploadFile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import JOB_CREATED
from ..db.base import get_db_session, AsyncSessionLocal
from ..db.models import Job, Page, JobStatus, PageStatus, ResolutionGroup
from ..pipeline.orchestrator import orchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/upload", response_model=dict)
async def upload_pdf(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Upload a PDF file and create a processing job
    
    Args:
        file: PDF file to upload
        
    Returns:
        Job information including ID and status
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_file_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(settings.allowed_file_extensions)}"
            )
        
        # Check file size
        file_size = 0
        try:
            # Get file size without loading entire file
            file_size = len(await file.read())
            await file.seek(0)  # Reset file pointer
        except:
            file_size = 0
        
        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                detail=f"File too large. Max: {settings.MAX_UPLOAD_SIZE_MB}MB"
            )
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = file.filename.replace(" ", "_")
        stored_filename = f"{timestamp}_{unique_id}_{safe_filename}"
        
        # Save file to upload directory
        upload_dir = settings.UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / stored_filename
        
        # Save file in chunks to avoid memory issues
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
        
        # Get page count
        try:
            from ..render.pdf_renderer import renderer
            page_count = await renderer.get_page_count(file_path)
            if page_count <= 0:
                raise ValueError("PDF has no pages")
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            # Try with PyMuPDF as fallback
            import fitz
            try:
                with fitz.open(str(file_path)) as pdf:
                    page_count = len(pdf)
            except Exception as e2:
                logger.error(f"Error getting page count with PyMuPDF: {e2}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid PDF file: {e2}"
                )
        
        # Create job in database
        job = Job(
            filename=stored_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            total_pages=page_count,
            processed_pages=0,
            failed_pages=0,
            status=JobStatus.PENDING
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Create pages in database
        pages = []
        for i in range(1, page_count + 1):
            page = Page(
                job_id=job.id,
                page_number=i,
                status=PageStatus.PENDING,
                retry_count=0
            )
            pages.append(page)
            db.add(page)
        
        await db.commit()
        
        # Record metrics
        JOB_CREATED.labels(status="created").inc()
        
        logger.info(
            f"Job created | ID={job.id} | File={file.filename} | "
            f"Pages={page_count} | Size={file_size / 1024 / 1024:.2f}MB"
        )
        
        # Submit job to pipeline
        # Use asyncio.create_task instead of background_tasks to maintain async context
        import asyncio
        asyncio.create_task(orchestrator.submit_job(job))
        
        return {
            "id": job.id,
            "filename": job.filename,
            "original_filename": job.original_filename,
            "total_pages": job.total_pages,
            "status": job.status.value,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "file_size": job.file_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


@router.get("/{job_id}/status")
async def get_job_status(job_id: int):
    """
    Get the status of a specific job
    
    Args:
        job_id: ID of the job
        
    Returns:
        Job status and progress information
    """
    try:
        # Get job from database
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
        
        # Get pipeline progress
        progress = await orchestrator.get_job_progress(job_id)
        
        return {
            "id": job.id,
            "filename": job.filename,
            "original_filename": job.original_filename,
            "total_pages": job.total_pages,
            "status": job.status.value,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "processed_pages": job.processed_pages,
            "failed_pages": job.failed_pages,
            "output_zip_path": job.output_zip_path,
            "error_message": job.error_message,
            "progress": progress or {
                "overall_progress": 0.0,
                "throughput": 0.0,
                "eta_seconds": None,
                "avg_latency": {"render": 0.0, "ocr": 0.0, "ai": 0.0},
                "error_rate": 0.0,
                "resolution_groups": []
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job status: {str(e)}"
        )


@router.get("/{job_id}/pages")
async def get_job_pages(job_id: int):
    """
    Get all pages for a job
    
    Args:
        job_id: ID of the job
        
    Returns:
        List of page information
    """
    try:
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
            
            pages = (await session.execute(
                select(Page).where(Page.job_id == job_id).order_by(Page.page_number)
            )).scalars().all()
        
        return [
            {
                "id": page.id,
                "page_number": page.page_number,
                "status": page.status.value,
                "resolution_code": page.resolution_code,
                "ocr_confidence": page.ocr_confidence,
                "ocr_engine": page.ocr_engine,
                "error_message": page.error_message,
                "error_type": page.error_type,
                "retry_count": page.retry_count
            }
            for page in pages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job pages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving pages: {str(e)}"
        )


@router.get("/{job_id}/resolutions")
async def get_job_resolutions(job_id: int):
    """
    Get all resolution groups for a job
    
    Args:
        job_id: ID of the job
        
    Returns:
        List of resolution groups with download links
    """
    try:
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
            
            groups = (await session.execute(
                select(ResolutionGroup).where(ResolutionGroup.job_id == job_id)
            )).scalars().all()
        
        return [
            {
                "id": group.id,
                "resolution_code": group.resolution_code,
                "start_page": group.start_page,
                "end_page": group.end_page,
                "page_count": group.page_count,
                "output_pdf_path": group.output_pdf_path,
                "file_size": group.file_size,
                "status": group.status
            }
            for group in groups
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job resolutions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving resolutions: {str(e)}"
        )


@router.get("/")
async def list_jobs(
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    List all jobs with optional filtering
    
    Args:
        status_filter: Filter by job status
        limit: Maximum number of jobs to return
        offset: Offset for pagination
        
    Returns:
        List of jobs
    """
    try:
        from sqlalchemy import select, desc
        from ..db.models import JobStatus
        
        async with AsyncSessionLocal() as session:
            query = select(Job).order_by(desc(Job.created_at)).limit(limit).offset(offset)
            
            if status_filter:
                # Convert string to JobStatus enum
                try:
                    filter_status = JobStatus(status_filter)
                    query = query.where(Job.status == filter_status)
                except ValueError:
                    # Invalid status filter, ignore it
                    pass
            
            result = await session.execute(query)
            jobs = result.scalars().all()
        
        return [
            {
                "id": job.id,
                "filename": job.filename,
                "original_filename": job.original_filename,
                "total_pages": job.total_pages,
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "processed_pages": job.processed_pages,
                "failed_pages": job.failed_pages
            }
            for job in jobs
        ]
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing jobs: {str(e)}"
        )


@router.delete("/{job_id}")
async def delete_job(job_id: int):
    """
    Delete a job and its associated files
    
    Args:
        job_id: ID of the job to delete
        
    Returns:
        Confirmation of deletion
    """
    try:
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
            
            # Delete file from disk
            if job.file_path and os.path.exists(job.file_path):
                os.remove(job.file_path)
                logger.info(f"Deleted file: {job.file_path}")
            
            # Delete output directory
            job_dir = settings.OUTPUT_DIR / f"job_{job_id}"
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Deleted output directory: {job_dir}")
            
            # Delete from database
            await session.delete(job)
            await session.commit()
        
        return {"message": f"Job {job_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting job: {str(e)}"
        )
