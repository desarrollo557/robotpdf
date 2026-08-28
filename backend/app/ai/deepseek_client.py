"""
DeepSeek API Client for Resolution Code Classification
Uses async httpx with semaphore-based rate limiting and exponential backoff
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

import httpx
from httpx import AsyncClient, Response, RequestError, HTTPStatusError

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.metrics import AI_LATENCY, AI_REQUESTS_PER_MINUTE, ACTIVE_AI_REQUESTS, PAGE_PROCESSED, PAGE_ERRORS

logger = get_logger(__name__)


class DeepSeekClient:
    """
    Async DeepSeek API client with:
    - Semaphore-based rate limiting
    - Exponential backoff for retries
    - Batch processing support
    - Structured response parsing
    """
    
    def __init__(self):
        """Initialize DeepSeek client"""
        self._api_key = settings.DEEPSEEK_API_KEY
        self._api_base = settings.DEEPSEEK_API_BASE
        self._model = settings.DEEPSEEK_MODEL
        self._max_concurrency = settings.AI_MAX_CONCURRENCY
        self._batch_size = settings.AI_BATCH_SIZE
        self._retry_count = settings.AI_RETRY_COUNT
        self._retry_backoff_base = settings.AI_RETRY_BACKOFF_BASE
        self._retry_backoff_max = settings.AI_RETRY_BACKOFF_MAX
        self._timeout = settings.AI_TIMEOUT
        
        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        
        # Track active requests for metrics
        self._active_requests = 0
        
        # HTTP client
        self._client = AsyncClient(
            base_url=self._api_base,
            timeout=self._timeout,
            headers=self._get_headers()
        )
        
        logger.info(
            f"DeepSeekClient initialized | Model={self._model} | "
            f"MaxConcurrency={self._max_concurrency} | "
            f"BatchSize={self._batch_size} | "
            f"Timeout={self._timeout}s"
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "PDF-Resolution-Bot/1.0"
        }
    
    async def classify_resolution(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any], float]:
        """
        Classify text to extract resolution code
        
        Args:
            text: Text to classify
            context: Optional context (page number, job info, etc.)
            
        Returns:
            Tuple of (resolution_code, full_response, processing_time)
        """
        start_time = time.time()
        
        async with self._semaphore:
            self._active_requests += 1
            ACTIVE_AI_REQUESTS.set(self._active_requests)
            
            try:
                resolution_code, response = await self._classify_with_retry(text, context)
                processing_time = time.time() - start_time
                
                # Record metrics
                AI_LATENCY.observe(processing_time)
                PAGE_PROCESSED.labels(stage="ai", status="success").inc()
                
                logger.debug(
                    f"AI Classification | Code={resolution_code[:50] if resolution_code else 'None'}... | "
                    f"Time={processing_time:.3f}s | "
                    f"Active={self._active_requests}"
                )
                
                return resolution_code, response, processing_time
                
            except Exception as e:
                processing_time = time.time() - start_time
                PAGE_PROCESSED.labels(stage="ai", status="failed").inc()
                PAGE_ERRORS.labels(stage="ai", error_type=type(e).__name__).inc()
                logger.error(f"AI classification error: {e}")
                raise
            finally:
                self._active_requests -= 1
                ACTIVE_AI_REQUESTS.set(self._active_requests)
    
    async def classify_batch(
        self,
        texts: List[str],
        contexts: Optional[List[Dict[str, Any]]] = None
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Classify multiple texts in a batch (single API call)
        
        Args:
            texts: List of texts to classify
            contexts: Optional list of contexts
            
        Returns:
            List of (resolution_code, response, processing_time) tuples
        """
        if not texts:
            return []
        
        # Group into batches if needed
        results = []
        for i in range(0, len(texts), self._batch_size):
            batch_texts = texts[i:i + self._batch_size]
            batch_contexts = contexts[i:i + self._batch_size] if contexts else None
            
            batch_results = await self._classify_batch_single_call(
                batch_texts, batch_contexts
            )
            results.extend(batch_results)
        
        return results
    
    async def _classify_batch_single_call(
        self,
        texts: List[str],
        contexts: Optional[List[Dict[str, Any]]]
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Classify a batch of texts in a single API call
        """
        start_time = time.time()
        
        async with self._semaphore:
            self._active_requests += 1
            ACTIVE_AI_REQUESTS.set(self._active_requests)
            
            try:
                batch_result = await self._classify_batch_with_retry(texts, contexts)
                processing_time = time.time() - start_time
                
                # Distribute processing time evenly across batch
                per_item_time = processing_time / len(texts)
                
                # Record metrics
                AI_LATENCY.observe(processing_time)
                AI_REQUESTS_PER_MINUTE.inc()
                PAGE_PROCESSED.labels(stage="ai", status="success").inc(len(texts))
                
                logger.debug(
                    f"Batch AI Classification | Items={len(texts)} | "
                    f"Time={processing_time:.3f}s | "
                    f"PerItem={per_item_time:.3f}s"
                )
                
                # Return results with per-item timing
                return [
                    (code, response, per_item_time) 
                    for code, response in batch_result
                ]
                
            except Exception as e:
                processing_time = time.time() - start_time
                PAGE_PROCESSED.labels(stage="ai", status="failed").inc(len(texts))
                PAGE_ERRORS.labels(stage="ai", error_type=type(e).__name__).inc(len(texts))
                logger.error(f"Batch AI classification error: {e}")
                raise
            finally:
                self._active_requests -= 1
                ACTIVE_AI_REQUESTS.set(self._active_requests)
    
    async def _classify_with_retry(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Classify with exponential backoff retry
        """
        last_exception = None
        
        for attempt in range(self._retry_count):
            try:
                return await self._classify_single(text, context)
            except (RequestError, HTTPStatusError) as e:
                last_exception = e
                
                # Check if it's a rate limit error
                if isinstance(e, HTTPStatusError) and e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After", self._retry_backoff_base)
                    sleep_time = min(float(retry_after), self._retry_backoff_max)
                else:
                    sleep_time = min(
                        self._retry_backoff_base * (2 ** attempt),
                        self._retry_backoff_max
                    )
                
                logger.warning(
                    f"AI request failed (attempt {attempt + 1}/{self._retry_count}) | "
                    f"Error={type(e).__name__} | "
                    f"Sleep={sleep_time:.2f}s"
                )
                
                await asyncio.sleep(sleep_time)
        
        raise last_exception or Exception("AI classification failed after retries")
    
    async def _classify_batch_with_retry(
        self,
        texts: List[str],
        contexts: Optional[List[Dict[str, Any]]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Classify batch with exponential backoff retry
        """
        last_exception = None
        
        for attempt in range(self._retry_count):
            try:
                return await self._classify_batch_single(texts, contexts)
            except (RequestError, HTTPStatusError) as e:
                last_exception = e
                
                if isinstance(e, HTTPStatusError) and e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After", self._retry_backoff_base)
                    sleep_time = min(float(retry_after), self._retry_backoff_max)
                else:
                    sleep_time = min(
                        self._retry_backoff_base * (2 ** attempt),
                        self._retry_backoff_max
                    )
                
                logger.warning(
                    f"Batch AI request failed (attempt {attempt + 1}/{self._retry_count}) | "
                    f"Error={type(e).__name__} | "
                    f"Sleep={sleep_time:.2f}s"
                )
                
                await asyncio.sleep(sleep_time)
        
        raise last_exception or Exception("Batch AI classification failed after retries")
    
    async def _classify_single(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Single classification request
        """
        # Build prompt
        prompt = self._build_prompt(text, context)
        
        # Prepare request
        request_data = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 100,
            "top_p": 1.0
        }
        
        # Send request
        response = await self._client.post(
            "/chat/completions",
            json=request_data
        )
        
        # Check for errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        return self._parse_response(data, text)
    
    async def _classify_batch_single(
        self,
        texts: List[str],
        contexts: Optional[List[Dict[str, Any]]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Single batch classification request
        """
        # Build batch prompt
        prompt = self._build_batch_prompt(texts, contexts)
        
        # Prepare request
        request_data = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 1000,
            "top_p": 1.0
        }
        
        # Send request
        response = await self._client.post(
            "/chat/completions",
            json=request_data
        )
        
        # Check for errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        return self._parse_batch_response(data, texts)
    
    def _build_prompt(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build the classification prompt
        
        Args:
            text: Text to classify
            context: Optional context information
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Eres un experto en procesamiento de documentos administrativos.",
            "Tu tarea es identificar el 'código de resolución' en el texto proporcionado.",
            "",
            "INSTRUCCIONES:",
            "1. Analiza cuidadosamente el texto a continuación.",
            "2. Identifica y extrae el 'código de resolución' o número de resolución.",
            "3. El código de resolución puede tener formatos variables: alfanumérico, numérico, con guiones, barras, etc.",
            "4. NO inventes un código si no lo encuentras claramente en el texto.",
            "5. Si no encuentras un código de resolución, devuelve una cadena vacía.",
            "",
            "TEXTO A ANALIZAR:",
            "---",
            text,
            "---",
            "",
            "RESPONDE EXACTAMENTE con este formato JSON (sin comentarios):",
            '{"codigo_resolucion": "<código encontrado o vacio>"}'
        ]
        
        return "\n".join(prompt_parts)
    
    def _build_batch_prompt(
        self,
        texts: List[str],
        contexts: Optional[List[Dict[str, Any]]]
    ) -> str:
        """
        Build a batch classification prompt
        
        Args:
            texts: List of texts to classify
            contexts: Optional list of contexts
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Eres un experto en procesamiento de documentos administrativos.",
            "Tu tarea es identificar el 'código de resolución' en cada uno de los textos proporcionados.",
            "",
            "INSTRUCCIONES:",
            "1. Analiza cuidadosamente CADA texto a continuación.",
            "2. Para CADA texto, identifica y extrae el 'código de resolución'.",
            "3. El código de resolución puede tener formatos variables.",
            "4. NO inventes códigos si no los encuentras claramente.",
            "5. Si no encuentras un código en un texto, devuelve cadena vacía para ese texto.",
            "",
            "TEXTOs A ANALIZAR:",
        ]
        
        for i, text in enumerate(texts):
            page_info = f" (Página {contexts[i].get('page_number', i + 1)})" if contexts and i < len(contexts) else ""
            prompt_parts.extend([
                f"TEXTO {i + 1}{page_info}:",
                "---",
                text,
                "---",
                ""
            ])
        
        prompt_parts.extend([
            "RESPONDE EXACTAMENTE con este formato JSON (sin comentarios):",
            '{"resultados": ['
            '  {"texto_numero": 1, "codigo_resolucion": "<código>"},'
            '  {"texto_numero": 2, "codigo_resolucion": "<código>"}'
            '  ...'
            ']}'
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_response(
        self,
        data: Dict[str, Any],
        original_text: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Parse the AI response
        
        Args:
            data: Response data from API
            original_text: Original text for context
            
        Returns:
            Tuple of (resolution_code, full_response)
        """
        try:
            # Extract the message content
            choices = data.get("choices", [])
            if not choices:
                logger.warning(f"No choices in response: {data}")
                return "", data
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            if not content:
                logger.warning(f"Empty content in response: {data}")
                return "", data
            
            # Parse JSON
            try:
                parsed = json.loads(content.strip())
                resolution_code = parsed.get("codigo_resolucion", "")
                
                # Clean up the code
                if isinstance(resolution_code, str):
                    resolution_code = resolution_code.strip()
                
                return resolution_code, data
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {content}")
                # Try to extract code from raw text
                return self._extract_code_from_text(content), data
                
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return "", data
    
    def _parse_batch_response(
        self,
        data: Dict[str, Any],
        texts: List[str]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Parse a batch AI response
        
        Args:
            data: Response data from API
            texts: Original texts for context
            
        Returns:
            List of (resolution_code, full_response) tuples
        """
        try:
            choices = data.get("choices", [])
            if not choices:
                logger.warning(f"No choices in batch response: {data}")
                return [("", data) for _ in texts]
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            if not content:
                logger.warning(f"Empty content in batch response: {data}")
                return [("", data) for _ in texts]
            
            # Parse JSON
            try:
                parsed = json.loads(content.strip())
                resultados = parsed.get("resultados", [])
                
                # Extract codes in order
                codes = []
                for resultado in resultados:
                    code = resultado.get("codigo_resolucion", "")
                    if isinstance(code, str):
                        code = code.strip()
                    codes.append(code)
                
                # Return codes with full response for each
                return [(code, data) for code in codes]
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON batch response: {content}")
                # Fallback: return empty codes
                return [("", data) for _ in texts]
                
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")
            return [("", data) for _ in texts]
    
    def _extract_code_from_text(self, text: str) -> str:
        """
        Try to extract resolution code from raw text (fallback)
        
        Args:
            text: Raw text to search for codes
            
        Returns:
            Extracted code or empty string
        """
        import re
        
        # Look for common resolution code patterns
        patterns = [
            # Alphanumeric with separators
            r'[A-Za-z]{2,4}-\d{4,8}-[A-Za-z0-9]{2,4}',
            r'[A-Za-z]{2,4}/\d{4,8}',
            r'RES\.?\s*\d{4,8}',
            r'RESOLUCION\s*[Nn]°?\s*\d{4,8}',
            # Just numbers
            r'\d{6,10}',
            # Simple alphanumeric
            r'[A-Za-z]{2,4}\d{4,8}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                code = match.group(0).strip()
                logger.info(f"Extracted code from fallback: {code}")
                return code
        
        return ""
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
        logger.info("DeepSeekClient closed")


# Global client instance
client = DeepSeekClient()


async def classify_resolution(
    text: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any], float]:
    """
    Convenience function to classify text and extract resolution code
    
    Args:
        text: Text to classify
        context: Optional context
        
    Returns:
        Tuple of (resolution_code, full_response, processing_time)
    """
    return await client.classify_resolution(text, context)


async def classify_batch(
    texts: List[str],
    contexts: Optional[List[Dict[str, Any]]] = None
) -> List[Tuple[str, Dict[str, Any], float]]:
    """
    Convenience function to classify multiple texts in a batch
    
    Args:
        texts: List of texts to classify
        contexts: Optional list of contexts
        
    Returns:
        List of (resolution_code, full_response, processing_time) tuples
    """
    return await client.classify_batch(texts, contexts)
