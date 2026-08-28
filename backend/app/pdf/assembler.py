"""
PDF Assembly Module using PyMuPDF
Creates output PDFs by extracting pages from source PDFs without recompression
"""

import asyncio
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import fitz  # PyMuPDF

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import PDF_ASSEMBLY_LATENCY, PAGE_PROCESSED, RESOLUTIONS_DETECTED, PAGES_PER_RESOLUTION
from ..db.models import Page, ResolutionGroup

logger = get_logger(__name__)


class PDFAssembler:
    """
    High-performance PDF assembler using PyMuPDF
    
    Features:
    - Extracts pages from source PDF without recompression
    - Creates new PDFs by inserting page ranges
    - Preserves original quality and metadata
    - Thread-safe operations for parallel processing
    """
    
    def __init__(self):
        """Initialize the PDF assembler"""
        self._executor = None
        logger.info("PDFAssembler initialized")
    
    def _get_executor(self):
        """Get or create thread pool executor"""
        if self._executor is None:
            self._executor = asyncio.get_event_loop().run_in_executor
        return self._executor
    
    async def create_resolution_pdf(
        self,
        source_pdf_path: Path,
        output_path: Path,
        page_numbers: List[int],
        resolution_code: str
    ) -> Tuple[Path, int, float]:
        """
        Create a new PDF containing specific pages from a source PDF
        
        Args:
            source_pdf_path: Path to the source PDF file
            output_path: Path to save the new PDF
            page_numbers: List of 1-based page numbers to include
            resolution_code: Resolution code for logging
            
        Returns:
            Tuple of (output_path, page_count, processing_time)
        """
        import time
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._create_resolution_pdf_sync,
                source_pdf_path,
                output_path,
                page_numbers,
                resolution_code
            )
            
            processing_time = time.time() - start_time
            
            # Record metrics
            PDF_ASSEMBLY_LATENCY.observe(processing_time)
            PAGE_PROCESSED.labels(stage="assembly", status="success").inc(len(page_numbers))
            PAGES_PER_RESOLUTION.observe(len(page_numbers))
            RESOLUTIONS_DETECTED.inc()
            
            logger.info(
                f"Created resolution PDF | Code={resolution_code[:50]} | "
                f"Pages={len(page_numbers)} | "
                f"Time={processing_time:.3f}s | "
                f"Output={output_path.name}"
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            PAGE_PROCESSED.labels(stage="assembly", status="failed").inc(len(page_numbers))
            logger.error(
                f"Error creating resolution PDF {resolution_code}: {e}"
            )
            raise
    
    def _create_resolution_pdf_sync(
        self,
        source_pdf_path: Path,
        output_path: Path,
        page_numbers: List[int],
        resolution_code: str
    ) -> Tuple[Path, int, float]:
        """
        Synchronous implementation for creating resolution PDF
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Open source PDF
            source_pdf = fitz.open(str(source_pdf_path))
            
            # Create new PDF
            new_pdf = fitz.open()
            
            # Insert pages (0-based index in PyMuPDF)
            for page_num in page_numbers:
                page_index = page_num - 1
                if page_index >= 0 and page_index < len(source_pdf):
                    new_pdf.insert_pdf(source_pdf, from_page=page_index, to_page=page_index)
            
            # Save new PDF
            new_pdf.save(str(output_path))
            new_pdf.close()
            source_pdf.close()
            
            # Get file size
            file_size = output_path.stat().st_size
            
            logger.debug(
                f"Saved resolution PDF | Code={resolution_code[:30]}... | "
                f"Pages={len(page_numbers)} | "
                f"Size={file_size / 1024:.1f}KB | "
                f"Path={output_path}"
            )
            
            return output_path, len(page_numbers), file_size
            
        except Exception as e:
            logger.error(f"Sync PDF assembly error: {e}")
            raise
    
    async def create_resolution_pdfs_for_job(
        self,
        source_pdf_path: Path,
        resolution_groups: List[Dict],
        output_dir: Path
    ) -> List[Dict]:
        """
        Create all resolution PDFs for a job
        
        Args:
            source_pdf_path: Path to the source PDF
            resolution_groups: List of resolution group dicts with:
                - resolution_code: The resolution code
                - start_page: First page number
                - end_page: Last page number
                - page_count: Number of pages
            output_dir: Directory to save output PDFs
            
        Returns:
            List of result dicts with file paths and metadata
        """
        tasks = []
        results = []
        
        for group in resolution_groups:
            resolution_code = group['resolution_code']
            page_numbers = list(range(group['start_page'], group['end_page'] + 1))
            
            # Sanitize filename
            safe_code = self._sanitize_filename(resolution_code or "unknown")
            output_path = output_dir / f"{safe_code}.pdf"
            
            task = asyncio.create_task(
                self.create_resolution_pdf(
                    source_pdf_path,
                    output_path,
                    page_numbers,
                    resolution_code
                )
            )
            tasks.append((group, task))
        
        for group, task in tasks:
            try:
                output_path, page_count, _ = await task
                results.append({
                    'resolution_code': group['resolution_code'],
                    'start_page': group['start_page'],
                    'end_page': group['end_page'],
                    'page_count': page_count,
                    'output_path': str(output_path),
                    'status': 'success'
                })
            except Exception as e:
                logger.error(
                    f"Error creating PDF for resolution {group.get('resolution_code')}: {e}"
                )
                results.append({
                    'resolution_code': group.get('resolution_code', 'unknown'),
                    'start_page': group.get('start_page', 0),
                    'end_page': group.get('end_page', 0),
                    'page_count': 0,
                    'output_path': None,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results
    
    async def create_zip_archive(
        self,
        pdf_files: List[Path],
        output_zip_path: Path
    ) -> Tuple[Path, int, float]:
        """
        Create a ZIP archive containing multiple PDF files
        
        Args:
            pdf_files: List of PDF file paths to include
            output_zip_path: Path to save the ZIP file
            
        Returns:
            Tuple of (output_path, file_count, processing_time)
        """
        import time
        import zipfile
        
        start_time = time.time()
        
        try:
            # Ensure output directory exists
            output_zip_path.parent.mkdir(parents=True, exist_ok=True)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._create_zip_sync,
                pdf_files,
                output_zip_path
            )
            
            processing_time = time.time() - start_time
            file_count = len(pdf_files)
            
            logger.info(
                f"Created ZIP archive | Files={file_count} | "
                f"Time={processing_time:.3f}s | "
                f"Output={output_zip_path.name}"
            )
            
            return output_zip_path, file_count, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error creating ZIP archive: {e}")
            raise
    
    def _create_zip_sync(
        self,
        pdf_files: List[Path],
        output_zip_path: Path
    ) -> None:
        """Synchronous ZIP creation"""
        with zipfile.ZipFile(str(output_zip_path), 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_file in pdf_files:
                arcname = pdf_file.name
                zipf.write(str(pdf_file), arcname)
                logger.debug(f"Added to ZIP: {arcname}")
    
    async def merge_pdfs(
        self,
        pdf_files: List[Path],
        output_path: Path
    ) -> Tuple[Path, int, float]:
        """
        Merge multiple PDF files into a single PDF
        
        Args:
            pdf_files: List of PDF file paths to merge
            output_path: Path to save the merged PDF
            
        Returns:
            Tuple of (output_path, total_pages, processing_time)
        """
        import time
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            total_pages = await loop.run_in_executor(
                None,
                self._merge_pdfs_sync,
                pdf_files,
                output_path
            )
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Merged PDFs | Count={len(pdf_files)} | "
                f"TotalPages={total_pages} | "
                f"Time={processing_time:.3f}s"
            )
            
            return output_path, total_pages, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error merging PDFs: {e}")
            raise
    
    def _merge_pdfs_sync(
        self,
        pdf_files: List[Path],
        output_path: Path
    ) -> int:
        """Synchronous PDF merging"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        merged_pdf = fitz.open()
        total_pages = 0
        
        for pdf_file in pdf_files:
            source_pdf = fitz.open(str(pdf_file))
            merged_pdf.insert_pdf(source_pdf)
            total_pages += len(source_pdf)
            source_pdf.close()
        
        merged_pdf.save(str(output_path))
        merged_pdf.close()
        
        return total_pages
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use as a filename
        
        Args:
            name: Input string
            
        Returns:
            Sanitized filename
        """
        import re
        
        # Remove or replace invalid characters
        name = str(name).strip()
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', '_', name)
        name = name[:100]  # Limit length
        
        if not name or name == '.':
            name = "resolution"
        
        return name
    
    async def get_pdf_page_count(self, pdf_path: Path) -> int:
        """
        Get the number of pages in a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Number of pages
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_pdf_page_count_sync,
            pdf_path
        )
    
    def _get_pdf_page_count_sync(self, pdf_path: Path) -> int:
        """Synchronous page count"""
        pdf = fitz.open(str(pdf_path))
        count = len(pdf)
        pdf.close()
        return count
    
    async def extract_pages_to_new_pdf(
        self,
        source_pdf_path: Path,
        output_pdf_path: Path,
        page_ranges: List[Tuple[int, int]]
    ) -> Path:
        """
        Extract specific page ranges to a new PDF
        
        Args:
            source_pdf_path: Source PDF path
            output_pdf_path: Output PDF path
            page_ranges: List of (start, end) tuples (1-based, inclusive)
            
        Returns:
            Output PDF path
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._extract_pages_sync,
            source_pdf_path,
            output_pdf_path,
            page_ranges
        )
        return output_pdf_path
    
    def _extract_pages_sync(
        self,
        source_pdf_path: Path,
        output_pdf_path: Path,
        page_ranges: List[Tuple[int, int]]
    ) -> None:
        """Synchronous page extraction"""
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        source_pdf = fitz.open(str(source_pdf_path))
        new_pdf = fitz.open()
        
        for start, end in page_ranges:
            # Convert to 0-based and inclusive
            for page_num in range(start - 1, end):
                if page_num < len(source_pdf):
                    new_pdf.insert_pdf(source_pdf, from_page=page_num, to_page=page_num)
        
        new_pdf.save(str(output_pdf_path))
        new_pdf.close()
        source_pdf.close()
    
    async def close(self):
        """Clean up resources"""
        if self._executor:
            pass  # Thread pool is managed by asyncio
        logger.info("PDFAssembler closed")


# Global assembler instance
assembler = PDFAssembler()


async def create_resolution_pdf(
    source_pdf_path: Path,
    output_path: Path,
    page_numbers: List[int],
    resolution_code: str
) -> Tuple[Path, int, float]:
    """
    Convenience function to create a resolution PDF
    """
    return await assembler.create_resolution_pdf(
        source_pdf_path, output_path, page_numbers, resolution_code
    )


async def create_zip_archive(
    pdf_files: List[Path],
    output_zip_path: Path
) -> Tuple[Path, int, float]:
    """
    Convenience function to create a ZIP archive
    """
    return await assembler.create_zip_archive(pdf_files, output_zip_path)
