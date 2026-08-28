"""
Processing Pipeline Orchestrator
3-Stage Decoupled Pipeline: Render+OCR -> AI Classification -> Grouping+PDF
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
from enum import Enum

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import (
    STAGE1_QUEUE_SIZE, STAGE2_QUEUE_SIZE, STAGE3_QUEUE_SIZE,
    ACTIVE_WORKERS, PAGES_PER_MINUTE
)
from sqlalchemy.orm import selectinload

from ..db.models import Job, Page, JobStatus, PageStatus, ResolutionGroup
from ..db.base import AsyncSessionLocal
from ..render.pdf_renderer import renderer
from ..ocr.engines import extract_text_from_image
from ..ai.deepseek_client import classify_batch, classify_resolution
from ..pdf.assembler import assembler, create_zip_archive

logger = get_logger(__name__)


class PipelineStage(Enum):
    RENDER_OCR = "render_ocr"
    AI_CLASSIFICATION = "ai_classification"
    GROUPING_PDF = "grouping_pdf"


@dataclass
class PageData:
    """Data for a single page in the pipeline"""
    job_id: int
    page_id: int
    page_number: int
    image_path: Optional[Path] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    ocr_engine: Optional[str] = None
    resolution_code: Optional[str] = None
    render_time: float = 0.0
    ocr_time: float = 0.0
    ai_time: float = 0.0
    stage1_complete: bool = False
    stage2_complete: bool = False
    error: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'page_id': self.page_id,
            'page_number': self.page_number,
            'image_path': str(self.image_path) if self.image_path else None,
            'ocr_text': self.ocr_text,
            'ocr_confidence': self.ocr_confidence,
            'ocr_engine': self.ocr_engine,
            'resolution_code': self.resolution_code,
            'render_time': self.render_time,
            'ocr_time': self.ocr_time,
            'ai_time': self.ai_time,
            'stage1_complete': self.stage1_complete,
            'stage2_complete': self.stage2_complete,
            'error': self.error,
            'retry_count': self.retry_count
        }


@dataclass
class Stage1Task:
    """Task for Stage 1 (Render + OCR)"""
    job_id: int
    page_id: int
    page_number: int
    pdf_path: Path
    temp_dir: Path
    
    def __hash__(self):
        return hash((self.job_id, self.page_id))
    
    def __eq__(self, other):
        return (self.job_id, self.page_id) == (other.job_id, other.page_id)


@dataclass
class Stage2Task:
    """Task for Stage 2 (AI Classification)"""
    job_id: int
    page_id: int
    page_number: int
    ocr_text: str
    confidence: float
    engine: str
    
    def __hash__(self):
        return hash((self.job_id, self.page_id))
    
    def __eq__(self, other):
        return (self.job_id, self.page_id) == (other.job_id, other.page_id)


@dataclass
class JobProgress:
    """Track progress for a job"""
    job_id: int
    total_pages: int
    stage1_pending: int = 0
    stage1_processing: int = 0
    stage1_completed: int = 0
    stage1_failed: int = 0
    stage2_pending: int = 0
    stage2_processing: int = 0
    stage2_completed: int = 0
    stage2_failed: int = 0
    stage3_pending: int = 0
    stage3_completed: int = 0
    stage3_failed: int = 0
    
    # Throughput tracking
    pages_processed_last_minute: int = 0
    ai_requests_last_minute: int = 0
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    
    # Resolution groups
    resolution_groups: Dict[str, List[int]] = field(default_factory=dict)
    
    # Latency tracking
    render_times: List[float] = field(default_factory=list)
    ocr_times: List[float] = field(default_factory=list)
    ai_times: List[float] = field(default_factory=list)
    
    def get_overall_progress(self) -> float:
        """Get overall progress percentage"""
        completed = self.stage3_completed
        total = self.total_pages
        return (completed / total * 100) if total > 0 else 0.0
    
    def get_throughput(self) -> float:
        """Get pages per minute throughput"""
        elapsed = max(1, time.time() - self.start_time)
        return self.stage3_completed / (elapsed / 60)
    
    def get_eta(self) -> Optional[float]:
        """Get estimated time remaining in seconds"""
        throughput = self.get_throughput()
        if throughput <= 0:
            return None
        
        remaining_pages = self.total_pages - self.stage3_completed
        if remaining_pages <= 0:
            return 0.0
        
        return (remaining_pages / throughput) * 60
    
    def get_avg_latency(self, stage: str) -> float:
        """Get average latency for a stage"""
        if stage == "render" and self.render_times:
            return sum(self.render_times) / len(self.render_times)
        elif stage == "ocr" and self.ocr_times:
            return sum(self.ocr_times) / len(self.ocr_times)
        elif stage == "ai" and self.ai_times:
            return sum(self.ai_times) / len(self.ai_times)
        return 0.0
    
    def get_error_rate(self) -> float:
        """Get error rate as percentage"""
        total = self.stage1_completed + self.stage1_failed
        if total == 0:
            return 0.0
        errors = self.stage1_failed + self.stage2_failed + self.stage3_failed
        return (errors / total * 100) if total > 0 else 0.0


class PipelineOrchestrator:
    """
    Orchestrates the 3-stage processing pipeline
    
    Stage 1 (CPU-bound): Render PDF pages to images + OCR
    Stage 2 (I/O-bound): AI classification via DeepSeek API
    Stage 3 (Light): Group pages by resolution code + create PDFs
    
    Uses asyncio queues with backpressure and concurrent processing
    """
    
    def __init__(self):
        """Initialize the orchestrator"""
        self._stage1_queue: asyncio.Queue = asyncio.Queue(
            maxsize=settings.STAGE1_QUEUE_SIZE
        )
        self._stage2_queue: asyncio.Queue = asyncio.Queue(
            maxsize=settings.STAGE2_QUEUE_SIZE
        )
        self._stage3_queue: asyncio.Queue = asyncio.Queue(
            maxsize=settings.STAGE3_QUEUE_SIZE
        )
        
        # Process pools
        self._stage1_pool = None
        self._stage2_semaphore = asyncio.Semaphore(settings.AI_MAX_CONCURRENCY)
        
        # Progress tracking
        self._progress: Dict[int, JobProgress] = {}
        self._stage3_enqueued: set = set()
        self._running = False
        self._shutdown = False
        
        # Statistics
        self._stats_lock = asyncio.Lock()
        self._pages_per_minute = 0
        self._ai_requests_per_minute = 0
        self._last_stats_update = time.time()
        
        logger.info(
            f"PipelineOrchestrator initialized | "
            f"Stage1Queue={settings.STAGE1_QUEUE_SIZE} | "
            f"Stage2Queue={settings.STAGE2_QUEUE_SIZE} | "
            f"Stage3Queue={settings.STAGE3_QUEUE_SIZE} | "
            f"MaxAIConcurrency={settings.AI_MAX_CONCURRENCY}"
        )
    
    async def start(self):
        """Start the processing pipeline"""
        self._running = True
        self._shutdown = False
        
        # Start stage processors
        self._stage1_pool = asyncio.Queue(
            maxsize=settings.WORKER_PROCESS_COUNT or 10
        )
        
        # Create worker tasks
        stage1_workers = [
            asyncio.create_task(self._stage1_worker(i))
            for i in range(settings.WORKER_PROCESS_COUNT or 4)
        ]
        
        stage2_workers = [
            asyncio.create_task(self._stage2_worker())
            for _ in range(5)  # 5 AI workers
        ]
        
        stage3_worker = asyncio.create_task(self._stage3_worker())
        
        logger.info("Pipeline started with workers for all stages")
        
        return {
            'stage1_workers': stage1_workers,
            'stage2_workers': stage2_workers,
            'stage3_worker': stage3_worker
        }
    
    async def stop(self):
        """Stop the processing pipeline gracefully"""
        self._shutdown = True
        self._running = False
        
        logger.info("Pipeline shutdown initiated")
    
    async def submit_job(self, job: Job) -> bool:
        """
        Submit a new job to the pipeline
        
        Args:
            job: Job object with pages to process
            
        Returns:
            True if job was submitted successfully
        """
        if not self._running:
            logger.warning(f"Cannot submit job {job.id}: pipeline not running")
            return False
        
        try:
            # Reload job with pages to avoid detached instance error
            async with AsyncSessionLocal() as session:
                result = await session.get(
                    Job, job.id, options=[selectinload(Job.pages)]
                )
                if not result:
                    logger.error(f"Job {job.id} not found in database")
                    return False

                # Initialize progress tracking
                progress = JobProgress(
                    job_id=result.id,
                    total_pages=result.total_pages
                )
                self._progress[result.id] = progress
                self._stage3_enqueued.discard(result.id)

                # Submit all pages to Stage 1
                for page in result.pages:
                    task = Stage1Task(
                        job_id=result.id,
                        page_id=page.id,
                        page_number=page.page_number,
                        pdf_path=Path(result.file_path),
                        temp_dir=settings.TEMP_DIR
                    )

                    # Wait if queue is full (backpressure)
                    await self._stage1_queue.put(task)
                    progress.stage1_pending += 1

                # Update job status
                result.status = JobStatus.PROCESSING
                result.started_at = datetime.utcnow()
                await session.commit()

            logger.info(
                f"Job {job.id} submitted | "
                f"File={job.filename} | "
                f"Pages={job.total_pages}"
            )

            return True
            
        except Exception as e:
            logger.error(f"Error submitting job {job.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _stage1_worker(self, worker_id: int):
        """
        Worker for Stage 1: Render + OCR
        CPU-bound, runs in process pool via run_in_executor
        """
        logger.info(f"Stage1 worker {worker_id} started")
        
        while not self._shutdown:
            try:
                # Get task from queue
                task: Stage1Task = await self._stage1_queue.get()
                
                if task is None:
                    break
                
                progress = self._progress.get(task.job_id)
                if progress:
                    progress.stage1_pending -= 1
                    progress.stage1_processing += 1
                    STAGE1_QUEUE_SIZE.set(self._stage1_queue.qsize())
                
                # Process the task
                result = await self._process_stage1(task)
                
                if result:
                    # Submit to Stage 2
                    stage2_task = Stage2Task(
                        job_id=task.job_id,
                        page_id=task.page_id,
                        page_number=task.page_number,
                        ocr_text=result['ocr_text'] or "",
                        confidence=result.get('ocr_confidence', 0.0),
                        engine=result.get('ocr_engine', 'unknown')
                    )
                    await self._stage2_queue.put(stage2_task)
                    
                    if progress:
                        progress.stage1_completed += 1
                        progress.stage1_processing -= 1
                        if result.get('render_time'):
                            progress.render_times.append(result['render_time'])
                        if result.get('ocr_time'):
                            progress.ocr_times.append(result['ocr_time'])
                else:
                    if progress:
                        progress.stage1_failed += 1
                        progress.stage1_processing -= 1
                
                self._stage1_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stage1 worker {worker_id} error: {e}")
        
        logger.info(f"Stage1 worker {worker_id} stopped")
    
    async def _process_stage1(self, task: Stage1Task) -> Optional[Dict]:
        """
        Process a Stage 1 task (Render + OCR)
        
        Args:
            task: Stage1Task to process
            
        Returns:
            Dict with results or None on failure
        """
        import time
        
        try:
            start_time = time.time()
            
            # Create temporary image path
            image_path = task.temp_dir / f"job_{task.job_id}" / f"page_{task.page_number}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Render page to image
            image, render_time = await renderer.render_page(
                task.pdf_path,
                task.page_number,
                image_path
            )
            
            # Extract text with OCR
            ocr_text, ocr_confidence, ocr_time, ocr_engine = await extract_text_from_image(
                image,
                settings.OCR_ENGINE
            )
            
            total_time = time.time() - start_time
            
            # Save results to database
            async with AsyncSessionLocal() as session:
                page = await session.get(Page, task.page_id)
                if page:
                    page.ocr_text = ocr_text
                    page.ocr_confidence = ocr_confidence
                    page.ocr_engine = ocr_engine
                    page.image_path = str(image_path)
                    page.render_duration = render_time
                    page.ocr_duration = ocr_time
                    page.render_completed_at = datetime.utcnow()
                    page.ocr_completed_at = datetime.utcnow()
                    page.stage1_complete = True
                    page.status = PageStatus.OCR_PROCESSING
                    await session.commit()
            
            logger.debug(
                f"Stage1 completed | Job={task.job_id} | "
                f"Page={task.page_number} | "
                f"Engine={ocr_engine} | "
                f"Confidence={ocr_confidence:.3f} | "
                f"Time={total_time:.3f}s"
            )
            
            return {
                'job_id': task.job_id,
                'page_id': task.page_id,
                'page_number': task.page_number,
                'ocr_text': ocr_text,
                'ocr_confidence': ocr_confidence,
                'ocr_engine': ocr_engine,
                'render_time': render_time,
                'ocr_time': ocr_time
            }
            
        except Exception as e:
            logger.error(
                f"Stage1 failed | Job={task.job_id} | "
                f"Page={task.page_number} | Error={e}"
            )
            
            # Update page status in database
            async with AsyncSessionLocal() as session:
                page = await session.get(Page, task.page_id)
                if page:
                    page.error_message = str(e)
                    page.error_type = type(e).__name__
                    page.status = PageStatus.FAILED
                    await session.commit()
            
            return None
    
    async def _stage2_worker(self):
        """
        Worker for Stage 2: AI Classification
        I/O-bound, runs concurrently with semaphore
        """
        logger.info("Stage2 worker started")
        
        while not self._shutdown:
            try:
                # Get task from queue
                task: Stage2Task = await self._stage2_queue.get()
                
                if task is None:
                    break
                
                progress = self._progress.get(task.job_id)
                if progress:
                    progress.stage2_pending -= 1
                    progress.stage2_processing += 1
                    STAGE2_QUEUE_SIZE.set(self._stage2_queue.qsize())
                
                # Process the task with semaphore
                async with self._stage2_semaphore:
                    result = await self._process_stage2(task)
                
                if result is not None:
                    # Update progress (empty code is valid: page completed, just no resolution)
                    if progress:
                        code = result.get('resolution_code') or ""
                        if code and code not in progress.resolution_groups:
                            progress.resolution_groups[code] = []
                        if code:
                            progress.resolution_groups[code].append(task.page_number)
                        
                        progress.stage2_completed += 1
                        progress.stage2_processing -= 1
                        if result.get('ai_time'):
                            progress.ai_times.append(result['ai_time'])
                else:
                    if progress:
                        progress.stage2_failed += 1
                        progress.stage2_processing -= 1
                
                # Trigger Stage 3 once all pages have a result (completed or failed)
                if progress and progress.stage2_completed + progress.stage2_failed >= progress.total_pages:
                    if task.job_id not in self._stage3_enqueued:
                        self._stage3_enqueued.add(task.job_id)
                        await self._stage3_queue.put(task.job_id)
                
                self._stage2_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stage2 worker error: {e}")
        
        logger.info("Stage2 worker stopped")
    
    async def _process_stage2(self, task: Stage2Task) -> Optional[Dict]:
        """
        Process a Stage 2 task (AI Classification)
        
        Args:
            task: Stage2Task to process
            
        Returns:
            Dict with results or None on failure
        """
        import time
        
        try:
            start_time = time.time()
            
            # Classify the text
            resolution_code, response, ai_time = await classify_resolution(
                task.ocr_text,
                {'page_number': task.page_number, 'job_id': task.job_id}
            )
            
            total_time = time.time() - start_time
            
            # Save results to database
            async with AsyncSessionLocal() as session:
                page = await session.get(Page, task.page_id)
                if page:
                    page.resolution_code = resolution_code
                    page.ai_response = str(response)
                    page.ai_duration = ai_time
                    page.ai_completed_at = datetime.utcnow()
                    page.stage2_complete = True
                    page.status = PageStatus.COMPLETED
                    await session.commit()
            
            logger.debug(
                f"Stage2 completed | Job={task.job_id} | "
                f"Page={task.page_number} | "
                f"Code={resolution_code[:50] if resolution_code else 'None'} | "
                f"Time={total_time:.3f}s"
            )
            
            return {
                'job_id': task.job_id,
                'page_id': task.page_id,
                'page_number': task.page_number,
                'resolution_code': resolution_code,
                'ai_time': ai_time
            }
            
        except Exception as e:
            logger.error(
                f"Stage2 failed | Job={task.job_id} | "
                f"Page={task.page_number} | Error={e}"
            )
            
            # Update page status in database
            async with AsyncSessionLocal() as session:
                page = await session.get(Page, task.page_id)
                if page:
                    page.error_message = str(e)
                    page.error_type = type(e).__name__
                    page.status = PageStatus.FAILED
                    await session.commit()
            
            return None
    
    async def _stage3_worker(self):
        """
        Worker for Stage 3: Grouping + PDF Creation
        Light processing, creates output PDFs
        """
        logger.info("Stage3 worker started")
        
        while not self._shutdown:
            try:
                # Get job ID from queue
                job_id = await self._stage3_queue.get()
                
                if job_id is None:
                    break
                
                STAGE3_QUEUE_SIZE.set(self._stage3_queue.qsize())
                
                # Process the job
                await self._process_stage3(job_id)
                
                self._stage3_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stage3 worker error: {e}")
        
        logger.info("Stage3 worker stopped")
    
    async def _process_stage3(self, job_id: int):
        """
        Process Stage 3: Group pages and create PDFs
        
        Args:
            job_id: Job ID to process
        """
        import time
        
        start_time = time.time()
        progress = self._progress.get(job_id)
        
        try:
            # Get job and pages from database
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if not job:
                    logger.warning(f"Job {job_id} not found")
                    return
                
                pages = (await session.execute(
                    select(Page).where(Page.job_id == job_id)
                )).scalars().all()
            
            if not pages:
                logger.warning(f"No pages found for job {job_id}")
                return
            
            # Group pages by resolution code
            groups = defaultdict(list)
            for page in pages:
                if page.resolution_code:
                    groups[page.resolution_code].append(page.page_number)
                else:
                    logger.warning(f"Page {page.page_number} has no resolution code")
            
            # Create resolution groups in database
            resolution_groups = []
            output_dir = settings.OUTPUT_DIR / f"job_{job_id}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_files = []
            for code, page_numbers in groups.items():
                start_page = min(page_numbers)
                end_page = max(page_numbers)
                page_count = len(page_numbers)
                
                # Create resolution group
                group = ResolutionGroup(
                    job_id=job_id,
                    resolution_code=code,
                    start_page=start_page,
                    end_page=end_page,
                    page_count=page_count,
                    status="processing"
                )
                resolution_groups.append(group)
                
                # Create PDF for this resolution
                safe_code = code[:50].replace("/", "_").replace("\\", "_")
                output_path = output_dir / f"{safe_code}.pdf"
                
                pdf_path = await assembler.create_resolution_pdf(
                    Path(job.file_path),
                    output_path,
                    page_numbers,
                    code
                )
                
                group.output_pdf_path = str(pdf_path[0])
                group.file_size = pdf_path[2]
                group.completed_at = datetime.utcnow()
                group.status = "completed"
                
                pdf_files.append(output_path)
            
            # Save resolution groups to database
            async with AsyncSessionLocal() as session:
                for group in resolution_groups:
                    session.add(group)
                await session.commit()
            
            # Create ZIP archive
            zip_path = output_dir / f"{job.filename}.zip"
            await assembler.create_zip_archive(pdf_files, zip_path)
            
            # Update job status
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.output_zip_path = str(zip_path)
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    job.processed_pages = sum(len(pages) for pages in groups.values())
                    job.failed_pages = len([p for p in pages if p.status == PageStatus.FAILED])
                    await session.commit()
            
            # Notify connected clients that the job is complete
            try:
                from ..websocket.handler import ws_manager
                await ws_manager.notify_job_complete(job_id)
            except Exception as ws_err:
                logger.warning(f"Failed to notify job complete via WebSocket: {ws_err}")
            
            # Update progress
            if progress:
                progress.stage3_completed = len(resolution_groups)
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Stage3 completed | Job={job_id} | "
                f"Groups={len(resolution_groups)} | "
                f"Time={processing_time:.3f}s | "
                f"Output={output_dir}"
            )
            
        except Exception as e:
            logger.error(f"Stage3 failed for job {job_id}: {e}")
            
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    await session.commit()
    
    async def get_job_progress(self, job_id: int) -> Optional[Dict]:
        """
        Get progress information for a job
        
        Args:
            job_id: Job ID
            
        Returns:
            Dict with progress information or None
        """
        progress = self._progress.get(job_id)
        if not progress:
            return None
        
        return {
            'job_id': job_id,
            'total_pages': progress.total_pages,
            'stage1': {
                'pending': progress.stage1_pending,
                'processing': progress.stage1_processing,
                'completed': progress.stage1_completed,
                'failed': progress.stage1_failed
            },
            'stage2': {
                'pending': progress.stage2_pending,
                'processing': progress.stage2_processing,
                'completed': progress.stage2_completed,
                'failed': progress.stage2_failed
            },
            'stage3': {
                'completed': progress.stage3_completed
            },
            'overall_progress': progress.get_overall_progress(),
            'throughput': progress.get_throughput(),
            'eta_seconds': progress.get_eta(),
            'avg_latency': {
                'render': progress.get_avg_latency('render'),
                'ocr': progress.get_avg_latency('ocr'),
                'ai': progress.get_avg_latency('ai')
            },
            'error_rate': progress.get_error_rate(),
            'resolution_groups': list(progress.resolution_groups.keys())
        }
    
    async def get_system_stats(self) -> Dict:
        """
        Get system-level statistics
        
        Returns:
            Dict with system statistics
        """
        return {
            'stage1_queue_size': self._stage1_queue.qsize(),
            'stage2_queue_size': self._stage2_queue.qsize(),
            'stage3_queue_size': self._stage3_queue.qsize(),
            'active_workers': 0,  # TODO: track actual workers
            'active_ai_requests': 0,  # TODO: track from DeepSeek client
            'pages_per_minute': self._pages_per_minute,
            'ai_requests_per_minute': self._ai_requests_per_minute
        }


# Global orchestrator instance
orchestrator = PipelineOrchestrator()


# For imports
from sqlalchemy import select
