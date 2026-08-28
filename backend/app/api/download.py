"""
FastAPI Router for Downloading Results
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles

from ..core.settings import settings
from ..core.logging import get_logger
from ..db.base import get_db_session, AsyncSessionLocal
from ..db.models import Job, ResolutionGroup

logger = get_logger(__name__)

router = APIRouter(prefix="/api/download", tags=["download"])


@router.get("/{job_id}/zip")
async def download_job_zip(job_id: int):
    """
    Download the complete ZIP archive for a job
    
    Args:
        job_id: ID of the job
        
    Returns:
        ZIP file for download
    """
    try:
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
            
            if not job.output_zip_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job has no output ZIP file yet"
                )
            
            zip_path = Path(job.output_zip_path)
            if not zip_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="ZIP file not found on disk"
                )
        
        # Return file response
        return FileResponse(
            path=str(zip_path),
            filename=f"{job.original_filename}.zip",
            media_type="application/zip"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading ZIP: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading ZIP: {str(e)}"
        )


@router.get("/{job_id}/resolution/{resolution_id}")
async def download_resolution_pdf(
    job_id: int,
    resolution_id: int
):
    """
    Download a single resolution PDF
    
    Args:
        job_id: ID of the job
        resolution_id: ID of the resolution group
        
    Returns:
        PDF file for download
    """
    try:
        async with AsyncSessionLocal() as session:
            group = await session.get(ResolutionGroup, resolution_id)
            if not group or group.job_id != job_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resolution group {resolution_id} not found for job {job_id}"
                )
            
            if not group.output_pdf_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Resolution PDF not generated yet"
                )
            
            pdf_path = Path(group.output_pdf_path)
            if not pdf_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDF file not found on disk"
                )
        
        # Return file response
        safe_code = group.resolution_code.replace("/", "_").replace("\\", "_")
        return FileResponse(
            path=str(pdf_path),
            filename=f"{safe_code}.pdf",
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resolution PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/{job_id}/resolution/by-code/{resolution_code}")
async def download_resolution_pdf_by_code(
    job_id: int,
    resolution_code: str
):
    """
    Download a resolution PDF by its code
    
    Args:
        job_id: ID of the job
        resolution_code: Resolution code
        
    Returns:
        PDF file for download
    """
    try:
        async with AsyncSessionLocal() as session:
            groups = (await session.execute(
                select(ResolutionGroup)
                .where(ResolutionGroup.job_id == job_id)
                .where(ResolutionGroup.resolution_code == resolution_code)
            )).scalars().all()
            
            if not groups:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resolution group with code '{resolution_code}' not found for job {job_id}"
                )
            
            group = groups[0]
            
            if not group.output_pdf_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Resolution PDF not generated yet"
                )
            
            pdf_path = Path(group.output_pdf_path)
            if not pdf_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDF file not found on disk"
                )
        
        # Return file response
        safe_code = resolution_code.replace("/", "_").replace("\\", "_")
        return FileResponse(
            path=str(pdf_path),
            filename=f"{safe_code}.pdf",
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resolution PDF by code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/{job_id}/page/{page_number}")
async def download_page_image(
    job_id: int,
    page_number: int
):
    """
    Download the OCR image for a specific page
    (For debugging/verification purposes)
    
    Args:
        job_id: ID of the job
        page_number: Page number
        
    Returns:
        PNG image of the page
    """
    try:
        from ..db.models import Page
        
        async with AsyncSessionLocal() as session:
            page = (await session.execute(
                select(Page)
                .where(Page.job_id == job_id)
                .where(Page.page_number == page_number)
            )).scalar_one_or_none()
            
            if not page:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Page {page_number} not found for job {job_id}"
                )
            
            if not page.image_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Page image not generated yet"
                )
            
            image_path = Path(page.image_path)
            if not image_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image file not found on disk"
                )
        
        # Return file response
        return FileResponse(
            path=str(image_path),
            filename=f"page_{page_number}.png",
            media_type="image/png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading page image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading image: {str(e)}"
        )


@router.get("/{job_id}/ocr-text/{page_number}")
async def get_page_ocr_text(
    job_id: int,
    page_number: int
):
    """
    Get the OCR text for a specific page
    (For debugging/verification purposes)
    
    Args:
        job_id: ID of the job
        page_number: Page number
        
    Returns:
        OCR text for the page
    """
    try:
        from ..db.models import Page
        
        async with AsyncSessionLocal() as session:
            page = (await session.execute(
                select(Page)
                .where(Page.job_id == job_id)
                .where(Page.page_number == page_number)
            )).scalar_one_or_none()
            
            if not page:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Page {page_number} not found for job {job_id}"
                )
        
        return {
            "page_number": page_number,
            "ocr_text": page.ocr_text or "",
            "confidence": page.ocr_confidence,
            "engine": page.ocr_engine,
            "resolution_code": page.resolution_code
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OCR text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving OCR text: {str(e)}"
        )


@router.get("/{job_id}/statistics")
async def get_job_statistics(job_id: int):
    """
    Get detailed statistics for a job
    
    Args:
        job_id: ID of the job
        
    Returns:
        Detailed statistics including throughput, latency, etc.
    """
    try:
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
        
        progress = await orchestrator.get_job_progress(job_id)
        system_stats = await orchestrator.get_system_stats()
        
        return {
            "job_id": job_id,
            "total_pages": job.total_pages,
            "progress": progress or {},
            "system": system_stats,
            "detailed_stats": {
                "avg_render_latency": progress.get('avg_latency', {}).get('render', 0.0) if progress else 0.0,
                "avg_ocr_latency": progress.get('avg_latency', {}).get('ocr', 0.0) if progress else 0.0,
                "avg_ai_latency": progress.get('avg_latency', {}).get('ai', 0.0) if progress else 0.0,
                "throughput": progress.get('throughput', 0.0) if progress else 0.0,
                "eta_seconds": progress.get('eta_seconds') if progress else None,
                "error_rate": progress.get('error_rate', 0.0) if progress else 0.0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving statistics: {str(e)}"
        )
