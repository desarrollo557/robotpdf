"""
WebSocket Handler for Real-time Progress Updates
"""

import asyncio
import json
import time
from typing import Dict, Set, Any

from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from ..core.settings import settings
from ..core.logging import get_logger
from ..pipeline.orchestrator import orchestrator

logger = get_logger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts progress updates
    """
    
    def __init__(self):
        """Initialize WebSocket manager"""
        self._connections: Set[WebSocket] = set()
        self._job_connections: Dict[int, Set[WebSocket]] = {}
        self._update_interval = settings.PROGRESS_UPDATE_INTERVAL_MS / 1000
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"WebSocketManager initialized | "
            f"UpdateInterval={self._update_interval}s"
        )
    
    async def start(self):
        """Start the WebSocket manager"""
        self._running = True
        self._update_task = asyncio.create_task(self._broadcast_updates())
        logger.info("WebSocketManager started")
    
    async def stop(self):
        """Stop the WebSocket manager"""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connection in self._connections:
            try:
                await connection.close()
            except:
                pass
        
        self._connections.clear()
        self._job_connections.clear()
        
        logger.info("WebSocketManager stopped")
    
    async def connect(self, websocket: WebSocket, job_id: Optional[int] = None):
        """
        Add a new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            job_id: Optional job ID to subscribe to
        """
        await websocket.accept()
        self._connections.add(websocket)
        
        if job_id:
            if job_id not in self._job_connections:
                self._job_connections[job_id] = set()
            self._job_connections[job_id].add(websocket)
        
        logger.debug(
            f"WebSocket connected | Total={len(self._connections)} | "
            f"Job={job_id}"
        )
        
        # Send initial data
        try:
            if job_id:
                progress = await orchestrator.get_job_progress(job_id)
                if progress:
                    await websocket.send_json({
                        "type": "progress",
                        "job_id": job_id,
                        "data": progress
                    })
            
            system_stats = await orchestrator.get_system_stats()
            await websocket.send_json({
                "type": "system_stats",
                "data": system_stats
            })
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
    
    async def disconnect(self, websocket: WebSocket, job_id: Optional[int] = None):
        """
        Remove a WebSocket connection
        
        Args:
            websocket: WebSocket connection
            job_id: Optional job ID to unsubscribe from
        """
        self._connections.discard(websocket)
        
        if job_id and job_id in self._job_connections:
            self._job_connections[job_id].discard(websocket)
            if not self._job_connections[job_id]:
                del self._job_connections[job_id]
        
        logger.debug(
            f"WebSocket disconnected | Total={len(self._connections)} | "
            f"Job={job_id}"
        )
    
    async def _broadcast_updates(self):
        """
        Periodically broadcast updates to all connected clients
        """
        while self._running:
            try:
                await asyncio.sleep(self._update_interval)
                
                # Collect all updates
                updates = []
                
                # System stats
                system_stats = await orchestrator.get_system_stats()
                updates.append({
                    "type": "system_stats",
                    "data": system_stats
                })
                
                # Job progress for all jobs with active connections
                for job_id in self._job_connections:
                    progress = await orchestrator.get_job_progress(job_id)
                    if progress:
                        updates.append({
                            "type": "progress",
                            "job_id": job_id,
                            "data": progress
                        })
                
                # Broadcast all updates
                if updates:
                    await self._broadcast(updates)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
    
    async def _broadcast(self, messages: list):
        """
        Broadcast messages to all connected clients
        
        Args:
            messages: List of message dicts to send
        """
        disconnected = set()
        
        for connection in self._connections:
            try:
                for message in messages:
                    await connection.send_json(message)
            except (WebSocketDisconnect, ConnectionClosed, ConnectionError) as e:
                disconnected.add(connection)
                logger.debug(f"WebSocket disconnected during broadcast: {e}")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
        
        # Remove disconnected clients
        for connection in disconnected:
            self._connections.discard(connection)
    
    async def send_to_job(self, job_id: int, message: Dict[str, Any]):
        """
        Send a message to all clients subscribed to a job
        
        Args:
            job_id: Job ID
            message: Message to send
        """
        if job_id not in self._job_connections:
            return
        
        disconnected = set()
        for connection in self._job_connections[job_id]:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, ConnectionClosed, ConnectionError):
                disconnected.add(connection)
            except Exception as e:
                logger.error(f"Error sending job message: {e}")
        
        # Remove disconnected clients
        for connection in disconnected:
            self._job_connections[job_id].discard(connection)
            self._connections.discard(connection)
        
        if not self._job_connections[job_id]:
            del self._job_connections[job_id]
    
    async def notify_job_progress(self, job_id: int):
        """
        Notify all clients about progress for a specific job
        
        Args:
            job_id: Job ID
        """
        progress = await orchestrator.get_job_progress(job_id)
        if progress:
            await self.send_to_job(job_id, {
                "type": "progress",
                "job_id": job_id,
                "data": progress
            })
    
    async def notify_job_complete(self, job_id: int):
        """
        Notify all clients that a job is complete
        
        Args:
            job_id: Job ID
        """
        progress = await orchestrator.get_job_progress(job_id)
        if progress:
            await self.send_to_job(job_id, {
                "type": "job_complete",
                "job_id": job_id,
                "data": progress
            })
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self._connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


async def websocket_endpoint(
    websocket: WebSocket,
    job_id: Optional[int] = None
):
    """
    WebSocket endpoint for real-time updates
    
    Args:
        websocket: WebSocket connection
        job_id: Optional job ID to subscribe to
    """
    await ws_manager.connect(websocket, job_id)
    
    try:
        while True:
            # Keep connection alive
            try:
                data = await websocket.receive_text()
                
                # Handle incoming messages (if any)
                try:
                    message = json.loads(data)
                    if message.get("type") == "subscribe":
                        job_id = message.get("job_id")
                        if job_id:
                            if job_id not in ws_manager._job_connections:
                                ws_manager._job_connections[job_id] = set()
                            ws_manager._job_connections[job_id].add(websocket)
                except:
                    pass
                    
            except (WebSocketDisconnect, ConnectionClosed):
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket, job_id)
