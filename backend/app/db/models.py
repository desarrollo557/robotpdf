"""
Database Models for PDF Resolution Bot
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, ForeignKey,
    DateTime, Index, JSON, BigInteger, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func
from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum

from .base import BaseModel
from ..core.settings import settings


class JobStatus(str, PyEnum):
    """Job processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PageStatus(str, PyEnum):
    """Page processing status"""
    PENDING = "pending"
    RENDERING = "rendering"
    OCR_PROCESSING = "ocr_processing"
    AI_CLASSIFYING = "ai_classifying"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """
    Represents a PDF processing job
    """
    
    __tablename__ = "jobs"
    
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Original file information
    filename: Mapped[str] = Column(String(500), nullable=False)
    original_filename: Mapped[str] = Column(String(500), nullable=False)
    file_path: Mapped[str] = Column(String(1000), nullable=False)
    file_size: Mapped[int] = Column(BigInteger, nullable=False)  # in bytes
    
    # Processing information
    total_pages: Mapped[int] = Column(Integer, nullable=False)
    processed_pages: Mapped[int] = Column(Integer, default=0)
    failed_pages: Mapped[int] = Column(Integer, default=0)
    status: Mapped[JobStatus] = Column(
        SQLEnum(JobStatus), 
        default=JobStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    
    # Statistics
    total_render_time: Mapped[float] = Column(Float, default=0.0)
    total_ocr_time: Mapped[float] = Column(Float, default=0.0)
    total_ai_time: Mapped[float] = Column(Float, default=0.0)
    total_assembly_time: Mapped[float] = Column(Float, default=0.0)
    
    # Resolution groups
    resolution_groups: Mapped[List["ResolutionGroup"]] = relationship(
        "ResolutionGroup", 
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    # Pages
    pages: Mapped[List["Page"]] = relationship(
        "Page", 
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    # Output
    output_zip_path: Mapped[Optional[str]] = Column(String(1000))
    
    # Error information
    error_message: Mapped[Optional[str]] = Column(Text)
    
    # Indexes
    __table_args__ = (
        Index('idx_job_status', 'status'),
        Index('idx_job_created_at', 'created_at'),
        Index('idx_job_filename', 'filename'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, filename={self.filename}, status={self.status})>"


class Page(BaseModel):
    """
    Represents a single page in a PDF document
    """
    
    __tablename__ = "pages"
    
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Job relationship
    job_id: Mapped[int] = Column(
        Integer, 
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    job: Mapped[Job] = relationship("Job", back_populates="pages")
    
    # Page information
    page_number: Mapped[int] = Column(Integer, nullable=False)
    
    # File paths
    image_path: Mapped[Optional[str]] = Column(String(1000))
    
    # OCR results
    ocr_text: Mapped[Optional[str]] = Column(Text)
    ocr_confidence: Mapped[Optional[float]] = Column(Float)
    ocr_engine: Mapped[Optional[str]] = Column(String(50))
    
    # AI classification results
    resolution_code: Mapped[Optional[str]] = Column(String(200))
    ai_response: Mapped[Optional[str]] = Column(Text)
    
    # Processing status
    status: Mapped[PageStatus] = Column(
        SQLEnum(PageStatus),
        default=PageStatus.PENDING,
        nullable=False
    )
    
    # Error handling
    error_message: Mapped[Optional[str]] = Column(Text)
    error_type: Mapped[Optional[str]] = Column(String(100))
    retry_count: Mapped[int] = Column(Integer, default=0)
    
    # Timestamps for each stage
    render_started_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    render_completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    ocr_started_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    ocr_completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    ai_started_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    ai_completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    
    # Timing metrics
    render_duration: Mapped[Optional[float]] = Column(Float)  # seconds
    ocr_duration: Mapped[Optional[float]] = Column(Float)  # seconds
    ai_duration: Mapped[Optional[float]] = Column(Float)  # seconds
    
    # Stage tracking for pipeline
    stage1_complete: Mapped[bool] = Column(Boolean, default=False)
    stage2_complete: Mapped[bool] = Column(Boolean, default=False)
    stage3_complete: Mapped[bool] = Column(Boolean, default=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_page_job_id', 'job_id'),
        Index('idx_page_page_number', 'page_number'),
        Index('idx_page_status', 'status'),
        Index('idx_page_resolution_code', 'resolution_code'),
        Index('idx_page_stage1_complete', 'stage1_complete'),
        Index('idx_page_stage2_complete', 'stage2_complete'),
    )
    
    def __repr__(self):
        return f"<Page(id={self.id}, job_id={self.job_id}, page={self.page_number})>"


class ResolutionGroup(BaseModel):
    """
    Represents a group of pages belonging to the same resolution
    """
    
    __tablename__ = "resolution_groups"
    
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Job relationship
    job_id: Mapped[int] = Column(
        Integer,
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    job: Mapped[Job] = relationship("Job", back_populates="resolution_groups")
    
    # Resolution information
    resolution_code: Mapped[str] = Column(String(200), nullable=False)
    
    # Page range
    start_page: Mapped[int] = Column(Integer, nullable=False)
    end_page: Mapped[int] = Column(Integer, nullable=False)
    
    # Output file
    output_pdf_path: Mapped[Optional[str]] = Column(String(1000))
    file_size: Mapped[Optional[int]] = Column(BigInteger)
    
    # Page count
    page_count: Mapped[int] = Column(Integer, nullable=False)
    
    # Processing status
    status: Mapped[str] = Column(String(50), default="pending")
    
    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    
    # Indexes
    __table_args__ = (
        Index('idx_resolution_group_job_id', 'job_id'),
        Index('idx_resolution_group_code', 'resolution_code'),
        Index('idx_resolution_group_start_page', 'start_page'),
    )
    
    def __repr__(self):
        return (
            f"<ResolutionGroup(id={self.id}, job_id={self.job_id}, "
            f"code={self.resolution_code}, pages={self.start_page}-{self.end_page})>"
        )


class JobStats(BaseModel):
    """
    Aggregated statistics for a job, updated periodically for performance
    """
    
    __tablename__ = "job_stats"
    
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Job relationship
    job_id: Mapped[int] = Column(
        Integer,
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Throughput metrics (updated periodically)
    pages_per_minute: Mapped[float] = Column(Float, default=0.0)
    ai_requests_per_minute: Mapped[float] = Column(Float, default=0.0)
    
    # Latency metrics (average in seconds)
    avg_render_latency: Mapped[float] = Column(Float, default=0.0)
    avg_ocr_latency: Mapped[float] = Column(Float, default=0.0)
    avg_ai_latency: Mapped[float] = Column(Float, default=0.0)
    
    # Error metrics
    error_rate: Mapped[float] = Column(Float, default=0.0)
    total_errors: Mapped[int] = Column(Integer, default=0)
    
    # Throughput history (last N minutes)
    throughput_history: Mapped[Optional[str]] = Column(Text, default="{}")
    
    # Estimated completion
    eta_seconds: Mapped[Optional[float]] = Column(Float)
    
    # Last update timestamp
    last_updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    def __repr__(self):
        return f"<JobStats(job_id={self.job_id}, pages_per_minute={self.pages_per_minute})>"


class SystemStats(BaseModel):
    """
    System-level statistics for monitoring
    """
    
    __tablename__ = "system_stats"
    
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Queue sizes
    stage1_queue_size: Mapped[int] = Column(Integer, default=0)
    stage2_queue_size: Mapped[int] = Column(Integer, default=0)
    stage3_queue_size: Mapped[int] = Column(Integer, default=0)
    
    # Active processes
    active_workers: Mapped[int] = Column(Integer, default=0)
    active_ai_requests: Mapped[int] = Column(Integer, default=0)
    
    # System metrics
    cpu_usage: Mapped[Optional[float]] = Column(Float)
    memory_usage: Mapped[Optional[float]] = Column(Float)
    disk_usage: Mapped[Optional[float]] = Column(Float)
    
    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    def __repr__(self):
        return (
            f"<SystemStats(stage1={self.stage1_queue_size}, "
            f"stage2={self.stage2_queue_size}, stage3={self.stage3_queue_size})>"
        )
