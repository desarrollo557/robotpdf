"""
PDF to Image Renderer using pypdfium2
Optimized for OCR processing with configurable DPI and color space
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from concurrent.futures import ThreadPoolExecutor

import pypdfium2 as pdfium
from PIL import Image
import numpy as np

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import RENDER_LATENCY, PAGE_PROCESSED

logger = get_logger(__name__)


class PDFRenderer:
    """
    High-performance PDF renderer using PDFium (pypdfium2)
    
    Features:
    - Stream-based rendering (one page at a time)
    - Configurable DPI and color space
    - Automatic cleanup of temporary resources
    - Thread-safe operations
    """
    
    def __init__(self):
        """Initialize the PDF renderer"""
        self._executor = ThreadPoolExecutor(
            max_workers=settings.WORKERS,
            thread_name_prefix="pdf_renderer"
        )
        self._dpi = settings.RENDER_DPI
        self._scale = settings.RENDER_SCALE
        self._color_space = settings.RENDER_COLOR_SPACE
        
        logger.info(
            f"PDFRenderer initialized | DPI={self._dpi} | "
            f"Scale={self._scale} | ColorSpace={self._color_space}"
        )
    
    async def get_page_count(self, pdf_path: Path) -> int:
        """
        Get the total number of pages in a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Total number of pages
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._get_page_count_sync,
            pdf_path
        )
    
    def _get_page_count_sync(self, pdf_path: Path) -> int:
        """Synchronous implementation for page count"""
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
            return len(pdf)
        except Exception as e:
            logger.error(f"Error getting page count for {pdf_path}: {e}")
            raise
    
    async def render_page(
        self,
        pdf_path: Path,
        page_number: int,
        output_path: Optional[Path] = None
    ) -> Tuple[Image.Image, float]:
        """
        Render a specific page from a PDF to an image
        
        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number to render
            output_path: Optional path to save the image (if None, returns in memory)
            
        Returns:
            Tuple of (PIL Image, render time in seconds)
        """
        import time
        
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(
                self._executor,
                self._render_page_sync,
                pdf_path,
                page_number
            )
            
            render_time = time.time() - start_time
            
            # Record metrics
            RENDER_LATENCY.observe(render_time)
            PAGE_PROCESSED.labels(stage="render", status="success").inc()
            
            # Save to file if output path provided
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(output_path))
                logger.debug(
                    f"Rendered page {page_number} from {pdf_path.name} "
                    f"to {output_path.name} in {render_time:.3f}s"
                )
            
            return image, render_time
            
        except Exception as e:
            render_time = time.time() - start_time
            PAGE_PROCESSED.labels(stage="render", status="failed").inc()
            logger.error(
                f"Error rendering page {page_number} from {pdf_path}: {e}"
            )
            raise
    
    def _render_page_sync(
        self,
        pdf_path: Path,
        page_number: int
    ) -> Image.Image:
        """
        Synchronous implementation for page rendering
        
        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number
            
        Returns:
            PIL Image object
        """
        try:
            # Open PDF document
            pdf = pdfium.PdfDocument(str(pdf_path))
            
            # Get page (0-based index)
            page_index = page_number - 1
            if page_index < 0 or page_index >= len(pdf):
                raise ValueError(
                    f"Page number {page_number} is out of range (1-{len(pdf)})"
                )
            
            page = pdf[page_index]
            
            # Calculate dimensions
            width = int(page.get_width() * self._dpi / 72 * self._scale)
            height = int(page.get_height() * self._dpi / 72 * self._scale)
            
            # Render page to bitmap
            bitmap = page.render(
                scale=self._dpi / 72 * self._scale,
                rotation=0,
                colour_space=self._get_color_space()
            )
            
            # Convert to PIL Image
            buffer = bitmap.to_pil()
            
            # Apply color space conversion if needed
            if self._color_space == "gray" and buffer.mode != "L":
                buffer = buffer.convert("L")
            elif self._color_space == "rgb" and buffer.mode != "RGB":
                buffer = buffer.convert("RGB")
            
            return buffer
            
        except Exception as e:
            logger.error(f"Sync render error for {pdf_path} page {page_number}: {e}")
            raise
    
    def _get_color_space(self):
        """Get the PDFium color space based on settings"""
        color_spaces = {
            "gray": pdfium.PDF_COLORSPACE_GRAY,
            "rgb": pdfium.PDF_COLORSPACE_RGB,
            "cmyk": pdfium.PDF_COLORSPACE_CMYK
        }
        return color_spaces.get(self._color_space, pdfium.PDF_COLORSPACE_RGB)
    
    async def render_pages_batch(
        self,
        pdf_path: Path,
        page_numbers: list,
        output_dir: Optional[Path] = None
    ) -> dict:
        """
        Render multiple pages concurrently
        
        Args:
            pdf_path: Path to the PDF file
            page_numbers: List of 1-based page numbers to render
            output_dir: Optional directory to save images
            
        Returns:
            Dict mapping page_number to (image, render_time)
        """
        tasks = []
        results = {}
        
        for page_num in page_numbers:
            output_path = None
            if output_dir:
                output_path = output_dir / f"page_{page_num:04d}.png"
            
            task = asyncio.create_task(
                self.render_page(pdf_path, page_num, output_path)
            )
            tasks.append((page_num, task))
        
        for page_num, task in tasks:
            try:
                image, render_time = await task
                results[page_num] = (image, render_time)
            except Exception as e:
                logger.error(f"Error in batch render for page {page_num}: {e}")
                results[page_num] = (None, None)
        
        return results
    
    def get_image_dimensions(self, pdf_path: Path, page_number: int) -> Tuple[int, int]:
        """
        Get the dimensions of a page without rendering it
        
        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number
            
        Returns:
            Tuple of (width, height) in pixels at current DPI/scale
        """
        pdf = pdfium.PdfDocument(str(pdf_path))
        page_index = page_number - 1
        page = pdf[page_index]
        
        width = int(page.get_width() * self._dpi / 72 * self._scale)
        height = int(page.get_height() * self._dpi / 72 * self._scale)
        
        return width, height
    
    async def close(self):
        """Clean up resources"""
        self._executor.shutdown(wait=True)
        logger.info("PDFRenderer closed")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self._executor.shutdown(wait=False)
        except:
            pass


# Global renderer instance
renderer = PDFRenderer()


async def render_page_to_image(
    pdf_path: Path,
    page_number: int,
    output_path: Optional[Path] = None
) -> Tuple[Image.Image, float]:
    """
    Convenience function to render a PDF page to image
    
    Args:
        pdf_path: Path to the PDF file
        page_number: 1-based page number
        output_path: Optional path to save the image
        
    Returns:
        Tuple of (PIL Image, render time in seconds)
    """
    return await renderer.render_page(pdf_path, page_number, output_path)
