"""
Prometheus Metrics Configuration
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
from .settings import settings
from .logging import get_logger

logger = get_logger(__name__)

# ===========================================================================
# Metrics Definitions
# ===========================================================================

# Job Metrics
JOB_CREATED = Counter(
    'pdf_bot_job_created_total',
    'Total number of jobs created',
    ['status']
)

JOB_COMPLETED = Counter(
    'pdf_bot_job_completed_total',
    'Total number of jobs completed',
    ['status']
)

JOB_DURATION = Histogram(
    'pdf_bot_job_duration_seconds',
    'Job processing duration in seconds',
    buckets=[10, 30, 60, 120, 300, 600, 1200, 3600]
)

# Page Metrics
PAGE_PROCESSED = Counter(
    'pdf_bot_page_processed_total',
    'Total number of pages processed',
    ['stage', 'status']
)

PAGE_ERRORS = Counter(
    'pdf_bot_page_errors_total',
    'Total number of page processing errors',
    ['stage', 'error_type']
)

# Stage Latency Metrics
RENDER_LATENCY = Histogram(
    'pdf_bot_render_latency_seconds',
    'Time spent rendering PDF pages to images',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

OCR_LATENCY = Histogram(
    'pdf_bot_ocr_latency_seconds',
    'Time spent performing OCR on pages',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

AI_LATENCY = Histogram(
    'pdf_bot_ai_latency_seconds',
    'Time spent on AI classification',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

PDF_ASSEMBLY_LATENCY = Histogram(
    'pdf_bot_pdf_assembly_latency_seconds',
    'Time spent assembling output PDFs',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Queue Metrics
STAGE1_QUEUE_SIZE = Gauge(
    'pdf_bot_stage1_queue_size',
    'Current size of Stage 1 (Render+OCR) queue'
)

STAGE2_QUEUE_SIZE = Gauge(
    'pdf_bot_stage2_queue_size',
    'Current size of Stage 2 (AI Classification) queue'
)

STAGE3_QUEUE_SIZE = Gauge(
    'pdf_bot_stage3_queue_size',
    'Current size of Stage 3 (Grouping+PDF) queue'
)

# Throughput Metrics
PAGES_PER_MINUTE = Gauge(
    'pdf_bot_pages_per_minute',
    'Current throughput in pages per minute'
)

AI_REQUESTS_PER_MINUTE = Gauge(
    'pdf_bot_ai_requests_per_minute',
    'Current AI API requests per minute'
)

# System Metrics
ACTIVE_WORKERS = Gauge(
    'pdf_bot_active_workers',
    'Number of active worker processes'
)

ACTIVE_AI_REQUESTS = Gauge(
    'pdf_bot_active_ai_requests',
    'Number of concurrent AI requests'
)

# Resolution Metrics
RESOLUTIONS_DETECTED = Counter(
    'pdf_bot_resolutions_detected_total',
    'Total number of unique resolutions detected'
)

PAGES_PER_RESOLUTION = Histogram(
    'pdf_bot_pages_per_resolution',
    'Number of pages per resolution group',
    buckets=[1, 2, 5, 10, 20, 50, 100, 200, 500]
)

# ===========================================================================
# Metrics Server
# ===========================================================================

class MetricsServer:
    """
    Wrapper for Prometheus metrics HTTP server
    """
    
    _server = None
    
    @classmethod
    def start(cls):
        """Start the metrics HTTP server"""
        if settings.PROMETHEUS_ENABLED and not cls._server:
            try:
                cls._server = start_http_server(
                    port=settings.PROMETHEUS_PORT,
                    addr=settings.HOST
                )
                logger.info(
                    f"Prometheus metrics server started on "
                    f"http://{settings.HOST}:{settings.PROMETHEUS_PORT}"
                )
            except Exception as e:
                logger.error(f"Failed to start Prometheus server: {e}")
                cls._server = None
    
    @classmethod
    def stop(cls):
        """Stop the metrics HTTP server"""
        if cls._server:
            try:
                server = cls._server
                # prometheus_client >= 0.21 returns a (httpd, thread) tuple
                if isinstance(server, tuple):
                    httpd, thread = server
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(timeout=5)
                elif hasattr(server, "close"):
                    server.close()
                cls._server = None
                logger.info("Prometheus metrics server stopped")
            except Exception as e:
                logger.error(f"Error stopping Prometheus server: {e}")


# Start metrics server on module import if enabled
# Note: This is now started in main.py lifespan to avoid import-time issues
# if settings.PROMETHEUS_ENABLED:
#     MetricsServer.start()
