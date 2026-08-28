"""
OCR Engine Interface and Implementations
Hybrid OCR with Tesseract (fast) and PaddleOCR (fallback for low confidence)
"""

import asyncio
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Any
from PIL import Image
import io

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import OCR_LATENCY, PAGE_PROCESSED, PAGE_ERRORS

logger = get_logger(__name__)


class OCREngine(ABC):
    """
    Abstract base class for OCR engines
    """
    
    @abstractmethod
    async def extract_text(
        self,
        image: Image.Image
    ) -> Tuple[str, float, float]:
        """
        Extract text from an image
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (extracted_text, confidence_score, processing_time)
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the engine name"""
        pass


class TesseractOCREngine(OCREngine):
    """
    Tesseract OCR Engine - Fast CPU-based OCR
    """
    
    def __init__(self):
        """Initialize Tesseract engine"""
        self.name = "tesseract"
        self._tesseract_path = settings.TESSERACT_PATH
        self._lang = settings.TESSERACT_LANG
        
        # Try to import pytesseract
        try:
            import pytesseract
            self._pytesseract = pytesseract
            
            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = str(self._tesseract_path)
            
            logger.info(
                f"TesseractOCREngine initialized | "
                f"Path={self._tesseract_path or 'default'} | "
                f"Language={self._lang}"
            )
        except ImportError as e:
            logger.error(f"Failed to import pytesseract: {e}")
            raise
    
    async def extract_text(
        self,
        image: Image.Image
    ) -> Tuple[str, float, float]:
        """
        Extract text using Tesseract
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (text, confidence, processing_time)
        """
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            
            # Run Tesseract in thread pool (it's CPU-bound)
            text, confidence = await loop.run_in_executor(
                None,
                self._extract_text_sync,
                image
            )
            
            processing_time = time.time() - start_time
            
            # Record metrics
            OCR_LATENCY.observe(processing_time)
            PAGE_PROCESSED.labels(stage="ocr", status="success").inc()
            
            logger.debug(
                f"Tesseract OCR | Confidence={confidence:.3f} | "
                f"Time={processing_time:.3f}s | "
                f"Chars={len(text)}"
            )
            
            return text, confidence, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            PAGE_PROCESSED.labels(stage="ocr", status="failed").inc()
            PAGE_ERRORS.labels(stage="ocr", error_type=type(e).__name__).inc()
            logger.error(f"Tesseract OCR error: {e}")
            raise
    
    def _extract_text_sync(self, image: Image.Image) -> Tuple[str, float]:
        """
        Synchronous Tesseract extraction
        
        Args:
            image: PIL Image
            
        Returns:
            Tuple of (text, confidence)
        """
        try:
            # Convert to grayscale if needed
            if image.mode != 'L':
                image = image.convert('L')
            
            # Extract text with confidence
            data = self._pytesseract.image_to_data(
                image,
                lang=self._lang,
                output_type=self._pytesseract.Output.DICT,
                config="--psm 6 --oem 1"
            )
            
            text = data.get('text', '')
            confidences = data.get('conf', [])
            
            # Calculate average confidence
            if confidences and len(confidences) > 0:
                valid_confidences = [c for c in confidences if c > 0]
                avg_confidence = sum(valid_confidences) / len(valid_confidences) / 100
            else:
                avg_confidence = 0.0
            
            # Clean up text
            text = self._clean_text(text)
            
            return text, avg_confidence
            
        except Exception as e:
            logger.error(f"Sync Tesseract error: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        import re
        
        # Replace multiple newlines with single
        text = re.sub(r'\n+', '\n', text)
        # Replace multiple spaces with single
        text = re.sub(r' +', ' ', text)
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def get_name(self) -> str:
        return self.name


class PaddleOCREngine(OCREngine):
    """
    PaddleOCR Engine - GPU/CPU OCR with high accuracy
    Used as fallback when Tesseract confidence is low
    """
    
    def __init__(self):
        """Initialize PaddleOCR engine"""
        self.name = "paddleocr"
        self._use_gpu = settings.PADDLEOCR_USE_GPU
        self._lang = settings.PADDLEOCR_LANG
        self._ocr = None
        
        self._initialize_paddleocr()
    
    def _initialize_paddleocr(self):
        """Initialize PaddleOCR model"""
        try:
            from paddleocr import PaddleOCR
            
            # Configure PaddleOCR
            config = {
                'use_angle_cls': True,
                'lang': self._lang,
                'use_gpu': self._use_gpu,
                'det_db_unclip_ratio': 2.0,
                'rec_model_dir': None,
                'det_model_dir': None,
                'cls_model_dir': None,
                'page_num': 0,
            }
            
            self._ocr = PaddleOCR(**config)
            
            logger.info(
                f"PaddleOCREngine initialized | GPU={self._use_gpu} | "
                f"Language={self._lang}"
            )
            
        except ImportError as e:
            logger.warning(f"PaddleOCR not available: {e}")
            self._ocr = None
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            self._ocr = None
    
    async def extract_text(
        self,
        image: Image.Image
    ) -> Tuple[str, float, float]:
        """
        Extract text using PaddleOCR
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (text, confidence, processing_time)
        """
        if self._ocr is None:
            raise RuntimeError("PaddleOCR is not available")
        
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            
            # Run PaddleOCR in thread pool
            text, confidence = await loop.run_in_executor(
                None,
                self._extract_text_sync,
                image
            )
            
            processing_time = time.time() - start_time
            
            # Record metrics
            OCR_LATENCY.observe(processing_time)
            PAGE_PROCESSED.labels(stage="ocr", status="success").inc()
            
            logger.debug(
                f"PaddleOCR | Confidence={confidence:.3f} | "
                f"Time={processing_time:.3f}s | "
                f"Chars={len(text)}"
            )
            
            return text, confidence, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            PAGE_PROCESSED.labels(stage="ocr", status="failed").inc()
            PAGE_ERRORS.labels(stage="ocr", error_type=type(e).__name__).inc()
            logger.error(f"PaddleOCR error: {e}")
            raise
    
    def _extract_text_sync(self, image: Image.Image) -> Tuple[str, float]:
        """
        Synchronous PaddleOCR extraction
        
        Args:
            image: PIL Image
            
        Returns:
            Tuple of (text, confidence)
        """
        try:
            # Convert PIL Image to numpy array
            img_array = self._image_to_array(image)
            
            # Run OCR
            result = self._ocr.ocr(img_array, cls=True)
            
            # Extract text and calculate confidence
            text_parts = []
            confidences = []
            
            if result and len(result) > 0:
                for detection in result[0]:  # result[0] contains the detection results
                    if detection and len(detection) > 1:
                        text = detection[1][0]
                        confidence = detection[1][1]
                        text_parts.append(text)
                        confidences.append(confidence)
            
            full_text = '\n'.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Clean up text
            full_text = self._clean_text(full_text)
            
            return full_text, avg_confidence
            
        except Exception as e:
            logger.error(f"Sync PaddleOCR error: {e}")
            raise
    
    def _image_to_array(self, image: Image.Image):
        """Convert PIL Image to numpy array for PaddleOCR"""
        import numpy as np
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return np.array(image)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        import re
        
        # Replace multiple newlines with single
        text = re.sub(r'\n+', '\n', text)
        # Replace multiple spaces with single
        text = re.sub(r' +', ' ', text)
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def get_name(self) -> str:
        return self.name


class HybridOCREngine(OCREngine):
    """
    Hybrid OCR Engine - Uses Tesseract first, falls back to PaddleOCR
    if confidence is below threshold
    """
    
    def __init__(self):
        """Initialize hybrid engine with both Tesseract and PaddleOCR"""
        self.name = "hybrid"
        self._tesseract = TesseractOCREngine()
        
        # Only initialize PaddleOCR if fallback is enabled
        if settings.OCR_FALLBACK_ENABLED:
            try:
                self._paddleocr = PaddleOCREngine()
            except Exception as e:
                logger.warning(f"PaddleOCR fallback disabled: {e}")
                self._paddleocr = None
        else:
            self._paddleocr = None
        
        self._confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        
        logger.info(
            f"HybridOCREngine initialized | "
            f"Threshold={self._confidence_threshold} | "
            f"Fallback={self._paddleocr is not None}"
        )
    
    async def extract_text(
        self,
        image: Image.Image
    ) -> Tuple[str, float, float, str]:
        """
        Extract text using hybrid approach
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (text, confidence, processing_time, engine_used)
        """
        start_time = time.time()
        
        try:
            # Try Tesseract first
            tesseract_text, tesseract_confidence, tesseract_time = await self._tesseract.extract_text(image)
            total_time = time.time() - start_time
            
            # Check if confidence is sufficient
            if tesseract_confidence >= self._confidence_threshold:
                logger.debug(
                    f"Tesseract confidence {tesseract_confidence:.3f} >= "
                    f"threshold {self._confidence_threshold:.3f} | Using Tesseract"
                )
                return tesseract_text, tesseract_confidence, total_time, "tesseract"
            
            # Confidence is low, try PaddleOCR if available
            paddle_ready = (
                self._paddleocr is not None
                and getattr(self._paddleocr, "_ocr", None) is not None
            )
            if paddle_ready:
                logger.debug(
                    f"Tesseract confidence {tesseract_confidence:.3f} < "
                    f"threshold {self._confidence_threshold:.3f} | Falling back to PaddleOCR"
                )
                
                try:
                    paddle_text, paddle_confidence, paddle_time = await self._paddleocr.extract_text(image)
                    total_time = time.time() - start_time
                    # Always use PaddleOCR result when Tesseract confidence is low
                    return paddle_text, paddle_confidence, total_time, "paddleocr"
                except Exception as paddle_err:
                    logger.warning(
                        f"PaddleOCR fallback failed ({paddle_err}); "
                        f"keeping Tesseract result"
                    )
                    return tesseract_text, tesseract_confidence, total_time, "tesseract"
            else:
                logger.warning(
                    f"Tesseract confidence {tesseract_confidence:.3f} < "
                    f"threshold {self._confidence_threshold:.3f} | "
                    f"PaddleOCR unavailable | Using Tesseract anyway"
                )
                return tesseract_text, tesseract_confidence, total_time, "tesseract"
            
            # No fallback available, return Tesseract result anyway
            logger.warning(
                f"Tesseract confidence {tesseract_confidence:.3f} < "
                f"threshold {self._confidence_threshold:.3f} | "
                f"No fallback available | Using Tesseract anyway"
            )
            return tesseract_text, tesseract_confidence, total_time, "tesseract"
            
        except Exception as e:
            processing_time = time.time() - start_time
            PAGE_PROCESSED.labels(stage="ocr", status="failed").inc()
            PAGE_ERRORS.labels(stage="ocr", error_type=type(e).__name__).inc()
            logger.error(f"Hybrid OCR error: {e}")
            raise
    
    def get_name(self) -> str:
        return self.name


# Engine factory
_engines = {}


def get_ocr_engine(engine_name: Optional[str] = None) -> OCREngine:
    """
    Get OCR engine by name
    
    Args:
        engine_name: Name of the engine (tesseract, paddleocr, hybrid, auto)
        
    Returns:
        OCR Engine instance
    """
    global _engines
    
    if engine_name is None:
        engine_name = settings.OCR_ENGINE.lower()
    
    if engine_name not in _engines:
        if engine_name == "tesseract":
            _engines[engine_name] = TesseractOCREngine()
        elif engine_name == "paddleocr":
            _engines[engine_name] = PaddleOCREngine()
        elif engine_name == "hybrid" or engine_name == "auto":
            _engines[engine_name] = HybridOCREngine()
        else:
            raise ValueError(f"Unknown OCR engine: {engine_name}")
    
    return _engines[engine_name]


async def extract_text_from_image(
    image: Image.Image,
    engine_name: Optional[str] = None
) -> Tuple[str, float, float, str]:
    """
    Convenience function to extract text from an image
    
    Args:
        image: PIL Image to process
        engine_name: Optional engine name
        
    Returns:
        Tuple of (text, confidence, processing_time, engine_used)
    """
    engine = get_ocr_engine(engine_name)
    
    if isinstance(engine, HybridOCREngine):
        return await engine.extract_text(image)
    else:
        text, confidence, processing_time = await engine.extract_text(image)
        return text, confidence, processing_time, engine.get_name()
