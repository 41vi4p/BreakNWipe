"""
FastAPI Web Server for BreakNWipe

Provides REST API endpoints and WebSocket support for the web GUI.
"""

import os
import asyncio
import threading
import webbrowser
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .models import (
    ApiResponse, DeviceInfo, WipeRequest, WipeSession, WipeProgress,
    WebSocketMessage, WipeSessionStatus, PartitionModel, DeviceHealthModel,
    FsckCheckRequest
)
from .session_manager import WipeSessionManager
from ..device.filesystem import list_partitions
from ..device.health import get_device_health
from ..device.fsck import FilesystemChecker
from ..device import DeviceDetector


class WebServer:
    """FastAPI web server for BreakNWipe GUI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False):
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

        @self.app.get("/index.html", response_class=HTMLResponse)
        async def index_page():
            """Serve the main interface via index.html."""
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

        @self.app.get("/logs.html", response_class=HTMLResponse)
        async def logs_page():
            """Serve the logs page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "logs.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>Logs Page Not Found</h1>", status_code=404)

        @self.app.get("/reports.html", response_class=HTMLResponse)
        async def reports_page():
            """Serve the reports page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "reports.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>Reports Page Not Found</h1>", status_code=404)

        @self.app.get("/device-detail.html", response_class=HTMLResponse)
        async def device_detail_page():
            """Serve the device details/health/fsck page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "device-detail.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>Device Detail Page Not Found</h1>", status_code=404)

        @self.app.get("/about.html", response_class=HTMLResponse)
        async def about_page():
            """Serve the about page."""
            frontend_path = Path(__file__).parent.parent.parent / "frontend_ui" / "about.html"
            if frontend_path.exists():
                return HTMLResponse(content=frontend_path.read_text(), status_code=200)
            return HTMLResponse(content="<h1>About Page Not Found</h1>", status_code=404)

        @self.app.get("/favicon.ico")
        async def favicon():
            """Return a simple favicon or 404."""
            # Check if a favicon exists in the frontend directory
            favicon_path = Path(__file__).parent.parent.parent / "frontend_ui" / "favicon.ico"
            if favicon_path.exists():
                from fastapi.responses import FileResponse
                return FileResponse(path=str(favicon_path), media_type="image/x-icon")

            # Return a 1x1 transparent gif as a simple favicon
            from fastapi.responses import Response
            transparent_gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x04\x01\x00\x3b'
            return Response(content=transparent_gif, media_type="image/gif")

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

        # Note: these three are defined as plain `def`, not `async def` --
        # FastAPI/Starlette runs sync route handlers in a thread pool
        # automatically, so the blocking subprocess calls inside
        # get_device_health/list_partitions/FilesystemChecker.check() (which
        # can take a while for a repair) don't block the event loop the way
        # they would if awaited directly inside an async handler.

        @self.app.get("/api/devices/{device_path:path}/health", response_model=DeviceHealthModel)
        def get_device_health_endpoint(device_path: str):
            """Get SMART health/lifespan snapshot for a device."""
            device_path = "/" + device_path if not device_path.startswith("/") else device_path
            try:
                detector = DeviceDetector()
                device = detector.get_device_info(device_path)
                if not device:
                    raise HTTPException(status_code=404, detail=f"Device not found: {device_path}")
                health = get_device_health(device)
                return DeviceHealthModel(**health.to_dict())
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Health lookup failed: {e}")

        @self.app.get("/api/devices/{device_path:path}/partitions", response_model=List[PartitionModel])
        def get_device_partitions_endpoint(device_path: str):
            """List partitions/filesystems on a device."""
            device_path = "/" + device_path if not device_path.startswith("/") else device_path
            try:
                partitions = list_partitions(device_path)
                return [PartitionModel(**p.to_dict()) for p in partitions]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Partition listing failed: {e}")

        @self.app.post("/api/fsck/check")
        def fsck_check_endpoint(request: FsckCheckRequest):
            """
            Check (or, with repair=True, repair) a filesystem. Safety gates
            (never auto-unmounts, refuses --repair on a mounted partition,
            requires force for system-disk/btrfs repair) live in
            FilesystemChecker itself, so they apply here exactly as they do
            for the CLI -- the web layer cannot bypass them by, say, omitting
            a check the client is supposed to have already done.
            """
            try:
                result = FilesystemChecker().check(
                    request.partition,
                    repair=request.repair,
                    force=request.force,
                    filesystem=request.filesystem,
                )
                return JSONResponse(content=result.to_dict())
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"fsck failed: {e}")

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

        @self.app.get("/api/wipe/report/{session_id}")
        async def get_wipe_report(session_id: str):
            """Get detailed wipe report data for completed session."""
            session = self.session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            if session.progress.status != WipeSessionStatus.COMPLETED:
                raise HTTPException(status_code=400, detail="Session not completed yet")

            # Calculate duration
            duration_seconds = 0
            if hasattr(session.progress, 'started_at') and session.progress.started_at:
                duration_seconds = (session.progress.last_updated - session.progress.started_at).total_seconds()

            report_data = {
                "session_id": session_id,
                "device": {
                    "path": session.device_info.path,
                    "model": session.device_info.model,
                    "serial": session.device_info.serial,
                    "capacity": session.device_info.capacity_human,
                    "capacity_bytes": session.device_info.capacity,
                    "interface": session.device_info.interface,
                    "device_type": session.device_info.device_type
                },
                "wipe_details": {
                    "algorithm": session.wipe_request.algorithm,
                    "total_passes": session.progress.total_passes,
                    "verification_enabled": session.wipe_request.verify,
                    "certificate_generated": session.wipe_request.generate_certificate
                },
                "results": {
                    "status": session.progress.status,
                    "progress_percent": session.progress.progress_percent,
                    "data_processed_bytes": session.progress.data_processed,
                    "average_speed_mbps": session.progress.speed_mbps,
                    "duration_seconds": duration_seconds,
                    "started_at": session.progress.started_at.isoformat() if session.progress.started_at else None,
                    "completed_at": session.progress.last_updated.isoformat()
                },
                "certificate_path": getattr(session, 'certificate_path', None),
                "qr_data": getattr(session, 'qr_data', None),
                "report_id": getattr(session, 'report_id', f"BNW-{session_id[:8]}-{int(time.time())}")
            }

            return report_data

        @self.app.get("/api/wipe/download/{session_id}")
        async def download_certificate(session_id: str):
            """Download the generated certificate PDF."""
            session = self.session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            if not hasattr(session, 'certificate_path') or not session.certificate_path:
                raise HTTPException(status_code=404, detail="Certificate not generated")

            cert_path = Path(session.certificate_path)
            if not cert_path.exists():
                raise HTTPException(status_code=404, detail="Certificate file not found")

            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(cert_path),
                filename=f"BreakNWipe_Certificate_{session_id[:8]}.pdf",
                media_type="application/pdf"
            )

        @self.app.get("/api/logs")
        async def get_logs(device_path: str = None, status: str = None,
                          limit: int = 100, offset: int = 0, search: str = None):
            """Get wipe operation logs with optional filtering."""
            try:
                if search:
                    logs = self.session_manager.logger.search_logs(search, limit)
                else:
                    logs = self.session_manager.logger.get_logs(device_path, status, limit, offset)

                return {
                    "success": True,
                    "data": logs,
                    "total": len(logs)
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/statistics")
        async def get_log_statistics():
            """Get logging statistics."""
            try:
                stats = self.session_manager.logger.get_statistics()
                return {
                    "success": True,
                    "data": stats
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/device/{device_path:path}")
        async def get_device_logs(device_path: str):
            """Get all logs for a specific device."""
            try:
                logs = self.session_manager.logger.get_device_logs(device_path)
                return {
                    "success": True,
                    "data": logs,
                    "total": len(logs)
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/device-history")
        async def get_device_history(device_path: str = None):
            """Get device history records."""
            try:
                history = self.session_manager.logger.get_device_history(device_path)
                return {
                    "success": True,
                    "data": history
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/audit/{session_id}")
        async def get_audit_trail(session_id: str):
            """Get audit trail for a specific session."""
            try:
                audit_events = self.session_manager.logger.get_audit_trail(session_id)
                return {
                    "success": True,
                    "data": audit_events
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/{session_id}")
        async def get_log_by_session(session_id: str):
            """Get a specific log by session ID."""
            try:
                log = self.session_manager.logger.get_log_by_session(session_id)
                if not log:
                    raise HTTPException(status_code=404, detail="Log not found")

                return {
                    "success": True,
                    "data": log
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # Log deletion endpoints
        @self.app.delete("/api/logs/{session_id}")
        async def delete_log(session_id: str):
            """Delete a specific log entry."""
            try:
                success = self.session_manager.logger.delete_log(session_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Log not found")
                return {
                    "success": True,
                    "message": "Log deleted successfully"
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/logs")
        async def delete_multiple_logs(request: Request):
            """Delete multiple log entries."""
            try:
                # Get session IDs from request body
                body = await request.json()
                session_ids = body if isinstance(body, list) else []

                if not session_ids:
                    raise HTTPException(status_code=400, detail="No session IDs provided")

                deleted_count = self.session_manager.logger.delete_multiple_logs(session_ids)
                return {
                    "success": True,
                    "message": f"Deleted {deleted_count} log entries",
                    "deleted_count": deleted_count,
                    "requested_count": len(session_ids)
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/logs/cleanup")
        async def cleanup_old_logs(days_old: int = 90):
            """Delete logs older than specified number of days."""
            try:
                if days_old < 1:
                    raise HTTPException(status_code=400, detail="days_old must be at least 1")

                deleted_count = self.session_manager.logger.delete_old_logs(days_old)
                return {
                    "success": True,
                    "message": f"Cleaned up {deleted_count} old log entries",
                    "deleted_count": deleted_count,
                    "criteria": f"Logs older than {days_old} days"
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # Reports API endpoints
        @self.app.get("/api/reports")
        async def get_reports(device_path: str = None, limit: int = 100, offset: int = 0):
            """Get wipe reports with optional filtering."""
            try:
                reports = self.session_manager.logger.get_reports(device_path, limit, offset)
                return reports
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/reports/{session_id}")
        async def get_report_by_session(session_id: str):
            """Get a specific report by session ID."""
            try:
                report = self.session_manager.logger.get_report_by_session(session_id)
                if not report:
                    raise HTTPException(status_code=404, detail="Report not found")
                return report
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/reports/device/{device_path:path}")
        async def get_device_reports(device_path: str):
            """Get all reports for a specific device."""
            try:
                reports = self.session_manager.logger.get_device_reports(device_path)
                return reports
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/download{file_path:path}")
        async def download_report_file(file_path: str):
            """Download a report file (PDF, JSON, or QR code image)."""
            try:
                import os
                from fastapi.responses import FileResponse

                # Security check - ensure file path is within allowed directories
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    raise HTTPException(status_code=404, detail="File not found")

                # Additional security: check if file is in a reports/certificates directory
                allowed_dirs = [
                    '/tmp',
                    '/var/tmp',
                    str(Path.home() / '.breaknwipe'),
                    '/root/breaknwipe_reports',  # Certificate storage directory
                    '/home',  # User home directories
                    str(Path.cwd())  # Current working directory
                ]
                if not any(file_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
                    raise HTTPException(status_code=403, detail="Access denied")

                return FileResponse(
                    path=file_path,
                    filename=os.path.basename(file_path),
                    media_type='application/octet-stream'
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

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

        @self.app.get("/api/system-info")
        async def system_info():
            """Get system information for the about page."""
            try:
                import platform

                # Basic system information without requiring psutil
                system_info = {
                    "Operating System": f"{platform.system()} {platform.release()}",
                    "Architecture": platform.machine(),
                    "Python Version": platform.python_version(),
                    "Platform": platform.platform(),
                    "Processor": platform.processor() or "Unknown",
                    "Hostname": os.getenv('HOSTNAME', 'Unknown'),
                    "Current User": os.getenv('USER', os.getenv('USERNAME', 'Unknown')),
                    "Server Port": "8000",
                    "Database": "SQLite",
                    "Web Framework": "FastAPI + Uvicorn",
                    "Server Status": "Running"
                }

                # Try to get additional info if psutil is available
                try:
                    import psutil
                    system_info["CPU Count"] = psutil.cpu_count()
                    system_info["Memory (Total)"] = f"{psutil.virtual_memory().total // (1024**3)} GB"
                    system_info["Memory (Available)"] = f"{psutil.virtual_memory().available // (1024**3)} GB"
                    system_info["CPU Usage"] = f"{psutil.cpu_percent(interval=1)}%"
                except ImportError:
                    pass

                return system_info
            except Exception as e:
                # Fallback system info
                return {
                    "Operating System": "Unknown",
                    "Python Version": "Unknown",
                    "Server Status": "Running",
                    "Error": f"System info unavailable: {str(e)}"
                }

    async def _broadcast_progress(self, session_id: str, progress: WipeProgress):
        """Broadcast progress updates to connected WebSocket clients."""
        if session_id not in self.websocket_connections:
            return

        # Get session to retrieve algorithm information
        session = self.session_manager.get_session(session_id)
        algorithm_description = "Unknown Algorithm"

        if session:
            # Get algorithm description using the same logic as the algorithms.py
            from ..wipe_engine.algorithms import create_algorithm, AlgorithmType

            # Map WipeAlgorithm enum to string for create_algorithm
            algorithm_mapping = {
                "nist-clear": "NIST SP 800-88 Clear (1 pass)",
                "nist-purge": "NIST SP 800-88 Purge (3 passes)",
                "dod-3pass": "DoD 5220.22-M Standard (3 passes)",
                "dod-7pass": "DoD 5220.22-M Enhanced (7 passes)",
                "gutmann": "Gutmann Method (35 passes)",
                "random": "Random Data (3 passes)",
                "zeros": "Zero Fill (1 pass)",
                "custom": "Custom Algorithm",
                "rea-basic": "REA Basic - Encryption + NIST Clear (5 passes)",
                "rea-multichain": "REA Multichain - Multi-layer Encryption + DoD (8 passes)",
                "rea-extreme": "REA Extreme - Maximum Encryption + Gutmann (32 passes)",
                "rea-custom": "REA Custom - Configurable Encryption (6 passes)"
            }

            algorithm_description = algorithm_mapping.get(session.wipe_request.algorithm.value, "Unknown Algorithm")

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
                "estimated_remaining": progress.estimated_remaining,
                "algorithm_description": algorithm_description
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