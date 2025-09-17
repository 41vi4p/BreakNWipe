"""
FastAPI Web Server for BreakNWipe

Provides REST API endpoints and WebSocket support for the web GUI.
"""

import os
import asyncio
import threading
import webbrowser
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .models import (
    ApiResponse, DeviceInfo, WipeRequest, WipeSession, WipeProgress,
    WebSocketMessage, WipeSessionStatus
)
from .session_manager import WipeSessionManager


class WebServer:
    """FastAPI web server for BreakNWipe GUI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
        """Initialize the web server."""
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self.app = FastAPI(
            title="BreakNWipe Web Interface",
            description="Secure data wiping with web GUI",
            version="1.0.0"
        )
        self.session_manager = WipeSessionManager()
        self.websocket_connections: Dict[str, List[WebSocket]] = {}
        self.event_loop = None
        self._setup_app()

    def _setup_app(self):
        """Setup FastAPI app with routes and middleware."""

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount static files (frontend_ui)
        frontend_path = Path(__file__).parent.parent.parent / "frontend_ui"
        if frontend_path.exists():
            self.app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

        # Setup routes
        self._setup_routes()

        # Add startup event to capture event loop
        @self.app.on_event("startup")
        async def startup_event():
            self.event_loop = asyncio.get_running_loop()

    def _setup_routes(self):
        """Setup API routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Serve the main interface."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "index.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>BreakNWipe Web Interface</h1><p>Frontend not found</p>")

        @self.app.get("/progress.html", response_class=HTMLResponse)
        async def progress_page():
            """Serve the progress page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "progress.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>Progress Page Not Found</h1>", status_code=404)

        @self.app.get("/qr-report.html", response_class=HTMLResponse)
        async def qr_report_page():
            """Serve the QR report page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "qr-report.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>Report Page Not Found</h1>", status_code=404)

        @self.app.get("/api/devices", response_model=List[DeviceInfo])
        async def get_devices():
            """Get list of available storage devices."""
            try:
                devices = self.session_manager.get_available_devices()
                if not devices:
                    # Check if running with root privileges
                    import os
                    if os.geteuid() != 0:
                        raise HTTPException(
                            status_code=403,
                            detail="Root privileges required for device detection. Please run the web server with sudo."
                        )
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail="No storage devices found. This could be due to system restrictions or no suitable devices connected."
                        )
                return devices
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                error_detail = f"Device detection failed: {str(e)}\nTraceback: {traceback.format_exc()}"
                raise HTTPException(status_code=500, detail=error_detail)

        @self.app.post("/api/wipe/start", response_model=ApiResponse)
        async def start_wipe(wipe_request: WipeRequest, background_tasks: BackgroundTasks):
            """Start a new wipe operation."""
            try:
                session_id = self.session_manager.start_wipe_session(wipe_request)

                # Setup WebSocket progress notifications
                def progress_callback(progress: WipeProgress):
                    try:
                        if self.event_loop and not self.event_loop.is_closed():
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_progress(session_id, progress), self.event_loop
                            )
                    except Exception as e:
                        print(f"Failed to broadcast progress: {e}")

                self.session_manager.add_progress_callback(session_id, progress_callback)

                return ApiResponse(
                    success=True,
                    message="Wipe operation started successfully",
                    data={"session_id": session_id}
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/api/wipe/status/{session_id}", response_model=WipeSession)
        async def get_wipe_status(session_id: str):
            """Get status of a specific wipe session."""
            session = self.session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session

        @self.app.get("/api/wipe/sessions", response_model=List[WipeSession])
        async def get_all_sessions():
            """Get all active wipe sessions."""
            return self.session_manager.get_all_sessions()

        @self.app.post("/api/wipe/cancel/{session_id}", response_model=ApiResponse)
        async def cancel_wipe(session_id: str):
            """Cancel a running wipe operation."""
            success = self.session_manager.cancel_session(session_id)
            if not success:
                raise HTTPException(status_code=400, detail="Cannot cancel session")

            return ApiResponse(
                success=True,
                message="Wipe operation cancelled successfully"
            )

        @self.app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            """WebSocket endpoint for real-time progress updates."""
            await websocket.accept()

            # Add to connections
            if session_id not in self.websocket_connections:
                self.websocket_connections[session_id] = []
            self.websocket_connections[session_id].append(websocket)

            try:
                # Send current status immediately
                session = self.session_manager.get_session(session_id)
                if session:
                    message = WebSocketMessage(
                        type="progress_update",
                        session_id=session_id,
                        data={
                            "status": session.progress.status,
                            "progress_percent": session.progress.progress_percent,
                            "current_pass": session.progress.current_pass,
                            "total_passes": session.progress.total_passes,
                            "speed_mbps": session.progress.speed_mbps,
                            "data_processed": session.progress.data_processed,
                            "estimated_remaining": session.progress.estimated_remaining
                        }
                    )
                    await websocket.send_text(message.json())

                # Keep connection alive
                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break

            except WebSocketDisconnect:
                pass
            finally:
                # Remove from connections
                if session_id in self.websocket_connections:
                    try:
                        self.websocket_connections[session_id].remove(websocket)
                        if not self.websocket_connections[session_id]:
                            del self.websocket_connections[session_id]
                    except ValueError:
                        pass

        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    async def _broadcast_progress(self, session_id: str, progress: WipeProgress):
        """Broadcast progress updates to connected WebSocket clients."""
        if session_id not in self.websocket_connections:
            return

        message = WebSocketMessage(
            type="progress_update",
            session_id=session_id,
            data={
                "status": progress.status,
                "progress_percent": progress.progress_percent,
                "current_pass": progress.current_pass,
                "total_passes": progress.total_passes,
                "speed_mbps": progress.speed_mbps,
                "data_processed": progress.data_processed,
                "estimated_remaining": progress.estimated_remaining
            }
        )

        # Send to all connected clients for this session
        disconnected_clients = []
        for websocket in self.websocket_connections[session_id]:
            try:
                await websocket.send_text(message.json())
            except Exception:
                disconnected_clients.append(websocket)

        # Remove disconnected clients
        for client in disconnected_clients:
            try:
                self.websocket_connections[session_id].remove(client)
            except ValueError:
                pass

    def start(self):
        """Start the web server."""
        if self.open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                import time
                time.sleep(2)  # Wait for server to start
                webbrowser.open(f"http://{self.host}:{self.port}")

            browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
            browser_thread.start()

        # Start the server
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )

    def start_in_thread(self):
        """Start the web server in a separate thread (non-blocking)."""
        def run_server():
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        if self.open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                import time
                time.sleep(3)  # Wait for server to start
                webbrowser.open(f"http://{self.host}:{self.port}")

            browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
            browser_thread.start()

        return server_thread