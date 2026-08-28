"""
Main Application Entry Point
FastAPI server for PDF Resolution Segmentation Bot
"""

import os
import asyncio
import signal
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.core.logging import get_logger, setup_logging
from app.core.metrics import MetricsServer
from app.db.base import init_db, close_db
from app.pipeline.orchestrator import orchestrator
from app.websocket.handler import ws_manager

# Import routers
from app.api.upload import router as upload_router
from app.api.download import router as download_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown
    """
    # Startup
    logger.info("Application starting up...")
    
    # Initialize database
    await init_db()
    
    # Start pipeline orchestrator
    await orchestrator.start()
    
    # Start WebSocket manager
    await ws_manager.start()
    
    # Start metrics server if enabled
    if settings.PROMETHEUS_ENABLED:
        MetricsServer.start()
    
    logger.info(
        f"Application started | "
        f"Host={settings.HOST} | "
        f"Port={settings.PORT} | "
        f"Workers={settings.WORKERS}"
    )
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    
    # Stop WebSocket manager
    await ws_manager.stop()
    
    # Stop pipeline orchestrator
    await orchestrator.stop()
    
    # Close database connections
    await close_db()
    
    # Stop metrics server
    MetricsServer.stop()
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="PDF Resolution Segmentation Bot",
    description="""
    A high-performance system for segmenting PDF documents by resolution codes using OCR and AI.
    
    Features:
    - Upload PDF documents
    - Automatic page-by-page OCR processing
    - AI-based resolution code detection
    - Real-time progress tracking via WebSocket
    - Download segmented PDFs by resolution code
    - High-throughput processing with 3-stage pipeline
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)

# Include API routers
app.include_router(upload_router)
app.include_router(download_router)

# Serve favicon
@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    from fastapi.responses import FileResponse
    import os
    favicon_path = os.path.join("static", "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return FileResponse(os.path.join("static", "favicon.svg"), media_type="image/svg+xml")

# Serve frontend index.html at root
@app.get("/", include_in_schema=False)
async def serve_frontend():
    from fastapi.responses import HTMLResponse
    import os
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Welcome to PDF Resolution Bot</h1>", status_code=200)

# Mount static files (assets: CSS, JS, etc.)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")


# WebSocket endpoint
from fastapi import WebSocket
from app.websocket.handler import websocket_endpoint

@app.websocket("/ws/{job_id}")
async def websocket_job_endpoint(
    websocket: WebSocket,
    job_id: Optional[int] = None
):
    """
    WebSocket endpoint for job-specific updates
    
    Args:
        websocket: WebSocket connection
        job_id: ID of the job to subscribe to
    """
    await websocket_endpoint(websocket, job_id)


@app.websocket("/ws")
async def websocket_general_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for general updates
    """
    await websocket_endpoint(websocket, None)


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns the health status of the application
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "ws_connections": ws_manager.get_connection_count(),
        "pipeline_running": orchestrator._running
    }


# Metrics endpoint (if Prometheus is disabled)
@app.get("/metrics")
async def get_metrics():
    """
    Get Prometheus metrics (if enabled)
    """
    if settings.PROMETHEUS_ENABLED:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    return {"metrics": "disabled"}


# API info endpoint (moved from "/" to avoid clashing with the frontend route)
@app.get("/api")
async def api_info():
    """
    API information endpoint
    """
    return {
        "name": "PDF Resolution Segmentation Bot",
        "version": "1.0.0",
        "description": "High-performance PDF segmentation by resolution codes",
        "docs": "/docs",
        "health": "/health"
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={"message": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )


# Signal handling for graceful shutdown
async def handle_signals():
    """Handle termination signals for graceful shutdown"""
    import signal
    
    loop = asyncio.get_event_loop()
    
    def signal_handler(signame):
        logger.info(f"Received signal: {signame}")
        
        # Trigger shutdown
        async def shutdown():
            logger.info("Initiating graceful shutdown...")
            # TODO: Implement graceful shutdown
            pass
        
        loop.create_task(shutdown())
    
    # Windows doesn't support SIGTERM in the same way
    # We'll rely on the lifespan manager


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
