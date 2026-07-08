"""
FastAPI Web Server for BreakNWipe

Provides REST API endpoints and WebSocket support for the web GUI.
"""

import os
import asyncio
import logging
import threading
import webbrowser
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

from .models import (
    ApiResponse, DeviceInfo, WipeRequest, WipeSession, WipeProgress,
    WebSocketMessage, WipeSessionStatus, PartitionModel, DeviceHealthModel,
    FsckCheckRequest, PartitionResizeRequest, LvExtendRequest,
    RecoveryScanRequest, RecoveryRestoreRequest, RecoveryDeepScanStartRequest,
    ErasureCheckRequest
)
from .session_manager import WipeSessionManager
from .recovery_manager import RecoverySessionManager
from .verify_manager import VerifySessionManager
from ..device.filesystem import list_partitions
from ..device.health import get_device_health
from ..device.fsck import FilesystemChecker
from ..device import DeviceDetector
from .. import __version__


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
            version=__version__
        )
        self.session_manager = WipeSessionManager()
        self.recovery_manager = RecoverySessionManager()
        self.verify_manager = VerifySessionManager()
        self.websocket_connections: Dict[str, List[WebSocket]] = {}
        self.recovery_ws_connections: Dict[str, List[WebSocket]] = {}
        self.verify_ws_connections: Dict[str, List[WebSocket]] = {}
        # Folders a recovery operation has actually written to in this server's
        # lifetime -- the only directories /api/recovery/view is allowed to read
        # from, so browsing recovered files can't be turned into an arbitrary
        # local file-read (the client only ever supplies a path, never a root).
        self.recovered_roots: set = set()
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

        # Register the REST + WebSocket routes first so they take precedence over
        # the static-file mount below (Starlette matches routes in registration
        # order; a mount at "/" would otherwise swallow /api and /ws requests).
        self._setup_routes()

        # Serve the built Next.js GUI (a static export) as the site root. The GUI
        # lives inside this package at breaknwipe/breaknwipe-gui/out and is built
        # ahead of time (Node is a build-time-only dependency; see
        # scripts/build_packages.sh). `html=True` serves index.html for directory
        # requests and 404.html for misses. In dev the GUI runs separately on
        # :3000, so this mount is only exercised in a built/installed deployment.
        gui_out = Path(__file__).parent.parent / "breaknwipe-gui" / "out"
        legacy_frontend = Path(__file__).parent.parent.parent / "frontend_ui"
        if gui_out.exists():
            self.app.mount("/", StaticFiles(directory=str(gui_out), html=True), name="gui")
        elif legacy_frontend.exists():
            # Transitional fallback if the GUI hasn't been built yet.
            logger.warning(
                "Built GUI not found at %s; falling back to legacy frontend_ui. "
                "Build the GUI with `cd breaknwipe/breaknwipe-gui && npm ci && npm run build`.",
                gui_out,
            )
            self.app.mount("/", StaticFiles(directory=str(legacy_frontend), html=True), name="gui")
        else:
            logger.error("No GUI found to serve (looked for %s and %s).", gui_out, legacy_frontend)

        # Add startup event to capture event loop
        @self.app.on_event("startup")
        async def startup_event():
            self.event_loop = asyncio.get_running_loop()

    def _setup_routes(self):
        """Setup API routes. (The GUI itself is served as static files mounted at
        "/" in _setup_app; these are the REST + WebSocket endpoints it calls.)"""

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
            except Exception:
                logger.exception("Device detection failed")
                raise HTTPException(status_code=500, detail="Device detection failed. See server logs for details.")

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
                logger.exception(f"Health lookup failed for {device_path}")
                raise HTTPException(status_code=500, detail="Health lookup failed. See server logs for details.")

        @self.app.get("/api/devices/{device_path:path}/partitions", response_model=List[PartitionModel])
        def get_device_partitions_endpoint(device_path: str):
            """List partitions/filesystems on a device."""
            device_path = "/" + device_path if not device_path.startswith("/") else device_path
            try:
                partitions = list_partitions(device_path)
                return [PartitionModel(**p.to_dict()) for p in partitions]
            except Exception as e:
                logger.exception(f"Partition listing failed for {device_path}")
                raise HTTPException(status_code=500, detail="Partition listing failed. See server logs for details.")

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
                logger.exception(f"fsck failed for {request.partition}")
                raise HTTPException(status_code=500, detail="fsck failed. See server logs for details.")

        @self.app.post("/api/verify/erasure/start")
        def verify_erasure_start_endpoint(request: ErasureCheckRequest):
            """Start a read-only erasure check as a background job and return
            its job_id immediately -- a paranoid-depth check can read up to
            100MB and take a while. Progress streams over
            WS /ws/verify/{job_id}; GET /api/verify/erasure/{job_id} polls the
            same state for reconnects."""
            try:
                job_id = self.verify_manager.start_check(request.device, request.depth)

                def progress_callback(payload: Dict[str, Any]):
                    try:
                        if self.event_loop and not self.event_loop.is_closed():
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_verify_progress(job_id, payload), self.event_loop
                            )
                    except Exception as e:
                        logger.debug(f"Failed to broadcast verify progress: {e}")

                self.verify_manager.add_progress_callback(job_id, progress_callback)
                return JSONResponse(content={"job_id": job_id})
            except Exception:
                logger.exception(f"Failed to start erasure check for {request.device}")
                raise HTTPException(status_code=500, detail="Failed to start erasure check. See server logs for details.")

        @self.app.get("/api/verify/erasure/{job_id}")
        def verify_erasure_status_endpoint(job_id: str):
            """Current state of an erasure-check job -- used to reconnect
            after navigating away."""
            job = self.verify_manager.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Verify job not found.")
            return JSONResponse(content=job.to_dict())

        @self.app.post("/api/verify/erasure/{job_id}/cancel")
        def verify_erasure_cancel_endpoint(job_id: str):
            """Stop a running erasure check early."""
            ok = self.verify_manager.cancel_job(job_id)
            return JSONResponse(content={"success": ok})

        @self.app.get("/api/devices/{device_path:path}/sectors")
        def read_sectors_endpoint(device_path: str, offset: int = 0, length: int = 512):
            """Read raw bytes from a device (read-only) for the hex/sector viewer.
            Length is clamped server-side; reading raw devices requires root."""
            device_path = "/" + device_path if not device_path.startswith("/") else device_path
            try:
                from ..device.hexview import read_sectors
                return JSONResponse(content=read_sectors(device_path, offset, length).to_dict())
            except Exception:
                logger.exception(f"Sector read failed for {device_path}")
                raise HTTPException(status_code=500, detail="Sector read failed. See server logs for details.")

        # ---- Partition management (sync handlers -> thread pool; blocking subprocess) ----

        @self.app.get("/api/devices/{device_path:path}/partition-table")
        def get_partition_table_endpoint(device_path: str):
            """Full disk layout: partitions + free-space gaps + table type + LVM state."""
            device_path = "/" + device_path if not device_path.startswith("/") else device_path
            try:
                from ..device.partition import get_disk_layout, list_logical_volumes
                layout = get_disk_layout(device_path).to_dict()
                layout["logical_volumes"] = list_logical_volumes()
                return JSONResponse(content=layout)
            except Exception:
                logger.exception(f"Partition-table read failed for {device_path}")
                raise HTTPException(status_code=500, detail="Partition-table read failed. See server logs for details.")

        @self.app.post("/api/partition/resize")
        def partition_resize_endpoint(request: PartitionResizeRequest):
            """
            Plan (dry_run) or apply a partition resize. All safety gates live in
            PartitionResizer (validated paths, never auto-unmounts, refuses
            offline ops on mounted filesystems, system-disk/experimental-move
            force gates) and apply here identically to the CLI -- the client
            cannot bypass them.
            """
            try:
                from ..device.partition import PartitionResizer
                resizer = PartitionResizer()
                mode = request.mode

                if request.dry_run:
                    if mode == "grow":
                        plan = resizer.plan_grow(request.partition, force=request.force)
                    elif mode == "shrink":
                        plan = resizer.plan_shrink(request.partition, request.target_bytes or 0, force=request.force)
                    elif mode == "move":
                        plan = resizer.plan_move(request.partition, request.new_start_sector or 0, force=request.force)
                    else:
                        raise HTTPException(status_code=400, detail=f"Unknown resize mode '{mode}'.")
                    return JSONResponse(content=plan.to_dict())

                if mode == "grow":
                    result = resizer.grow(request.partition, force=request.force)
                elif mode == "shrink":
                    result = resizer.shrink(request.partition, request.target_bytes or 0, force=request.force)
                elif mode == "move":
                    result = resizer.move(request.partition, request.new_start_sector or 0, force=request.force)
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown resize mode '{mode}'.")
                return JSONResponse(content=result.to_dict())
            except HTTPException:
                raise
            except Exception:
                logger.exception(f"Partition resize failed for {request.partition}")
                raise HTTPException(status_code=500, detail="Partition resize failed. See server logs for details.")

        @self.app.post("/api/lvm/extend")
        def lvm_extend_endpoint(request: LvExtendRequest):
            """Extend an LVM logical volume (and its filesystem) to fill free VG space."""
            try:
                from ..device.partition import extend_lv
                return JSONResponse(content=extend_lv(request.lv_path).to_dict())
            except Exception:
                logger.exception(f"LV extend failed for {request.lv_path}")
                raise HTTPException(status_code=500, detail="LV extend failed. See server logs for details.")

        @self.app.get("/api/utility/gparted")
        def gparted_available_endpoint():
            """Whether GParted is installed -- drives whether the Disk Utility
            page offers it as an escape hatch for operations BreakNWipe's own
            partition tools don't cover (partition types, complex multi-disk
            layouts, etc.)."""
            import shutil
            return JSONResponse(content={"available": bool(shutil.which("gparted"))})

        @self.app.post("/api/utility/gparted/launch")
        def gparted_launch_endpoint():
            """Launch GParted as a separate desktop process. Fire-and-forget:
            BreakNWipe's own server keeps running regardless of what GParted
            does. Requires a graphical session -- this only works when
            `sudo breaknwipe --gui` was started from the user's own desktop
            (the usual way this app runs), since GParted needs the same
            DISPLAY/XAUTHORITY the server process inherited."""
            import shutil
            import subprocess

            gparted_path = shutil.which("gparted")
            if not gparted_path:
                raise HTTPException(status_code=404, detail="GParted is not installed (package: gparted).")

            try:
                subprocess.Popen(
                    [gparted_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                logger.exception("Failed to launch GParted")
                raise HTTPException(
                    status_code=500,
                    detail="Could not launch GParted. Try running 'sudo gparted' from a terminal instead.",
                )
            return JSONResponse(content={"success": True})

        # ---- File recovery (sync handlers -> thread pool; blocking subprocess) ----

        @self.app.get("/api/recovery/available")
        def recovery_available_endpoint():
            """Which recovery tools are installed (drives what the GUI offers)."""
            from ..device.recovery import recovery_tools
            tools = recovery_tools()
            return JSONResponse(content={
                "tools": tools,
                "undelete": tools["fls"] and tools["icat"],
                "deep_scan": tools["photorec"],
            })

        @self.app.post("/api/recovery/scan")
        def recovery_scan_endpoint(request: RecoveryScanRequest):
            """List recoverable deleted files on a partition. Read-only; all
            safety gates live in recovery.scan_deleted (validated paths)."""
            try:
                from ..device.recovery import scan_deleted
                return JSONResponse(content=scan_deleted(request.partition, request.filesystem).to_dict())
            except Exception:
                logger.exception(f"Recovery scan failed for {request.partition}")
                raise HTTPException(status_code=500, detail="Recovery scan failed. See server logs for details.")

        @self.app.post("/api/recovery/restore")
        def recovery_restore_endpoint(request: RecoveryRestoreRequest):
            """Recover selected files by inode (icat) to a folder on a DIFFERENT
            device -- enforced in recovery.recover_files so the client cannot
            overwrite the data it's recovering. This is synchronous because
            icat extraction of a handful of selected files is fast; a full
            deep scan is a background job (see /api/recovery/deep-scan/start)."""
            try:
                from ..device.recovery import recover_files
                result = recover_files(
                    request.partition, request.inodes, request.output_dir, request.filesystem
                )
                if not result.refused:
                    self.recovered_roots.add(os.path.realpath(request.output_dir))
                return JSONResponse(content=result.to_dict())
            except Exception:
                logger.exception(f"Recovery restore failed for {request.partition}")
                raise HTTPException(status_code=500, detail="Recovery restore failed. See server logs for details.")

        @self.app.post("/api/recovery/deep-scan/start")
        def recovery_deep_scan_start_endpoint(request: RecoveryDeepScanStartRequest):
            """Start a deep (PhotoRec) recovery scan as a background job and
            return its job_id immediately. Progress streams over
            WS /ws/recovery/{job_id}; GET /api/recovery/deep-scan/{job_id} polls
            the same state for reconnects."""
            try:
                self.recovered_roots.add(os.path.realpath(request.output_dir))
                job_id = self.recovery_manager.start_deep_scan(request.partition, request.output_dir)

                def progress_callback(payload: Dict[str, Any]):
                    try:
                        if self.event_loop and not self.event_loop.is_closed():
                            asyncio.run_coroutine_threadsafe(
                                self._broadcast_recovery_progress(job_id, payload), self.event_loop
                            )
                    except Exception as e:
                        logger.debug(f"Failed to broadcast recovery progress: {e}")

                self.recovery_manager.add_progress_callback(job_id, progress_callback)
                return JSONResponse(content={"job_id": job_id})
            except Exception:
                logger.exception(f"Failed to start deep scan for {request.partition}")
                raise HTTPException(status_code=500, detail="Failed to start deep scan. See server logs for details.")

        @self.app.get("/api/recovery/deep-scan/{job_id}")
        def recovery_deep_scan_status_endpoint(job_id: str):
            """Current state of a deep-scan job -- used to reconnect after
            navigating away, same pattern as GET /api/wipe/sessions."""
            job = self.recovery_manager.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Recovery job not found.")
            return JSONResponse(content=job.to_dict())

        @self.app.post("/api/recovery/deep-scan/{job_id}/cancel")
        def recovery_deep_scan_cancel_endpoint(job_id: str):
            """Stop a running deep scan early."""
            ok = self.recovery_manager.cancel_job(job_id)
            return JSONResponse(content={"success": ok})

        @self.app.get("/api/recovery/view")
        def recovery_view_endpoint(path: str):
            """Stream a recovered file's bytes (for the GUI's browse/preview
            panel) or offer it for download. Only readable if it lives inside a
            folder a recovery operation actually wrote to in this server's
            lifetime (self.recovered_roots) -- the client supplies a file path
            but never a root, so this can't become an arbitrary local file read."""
            try:
                resolved = os.path.realpath(path)
                if not os.path.exists(resolved) or not os.path.isfile(resolved):
                    raise HTTPException(status_code=404, detail="File not found")
                if not any(
                    resolved == root or resolved.startswith(root + os.sep)
                    for root in self.recovered_roots
                ):
                    raise HTTPException(status_code=403, detail="Access denied")

                import mimetypes
                media_type, _ = mimetypes.guess_type(resolved)
                return FileResponse(
                    path=resolved, filename=os.path.basename(resolved),
                    media_type=media_type or "application/octet-stream",
                )
            except HTTPException:
                raise
            except Exception:
                logger.exception(f"Recovery file view failed for {path}")
                raise HTTPException(status_code=500, detail="Could not read file. See server logs for details.")

        @self.app.post("/api/verify/certificate")
        async def verify_certificate_endpoint(file: UploadFile = File(...)):
            """Verify a wipe certificate's digital signature (and, if the
            certificate carries a hash, its blockchain anchor). Accepts the
            JSON report file directly -- the browser and this server aren't
            guaranteed to share a filesystem view, so upload is the only path
            that always works, unlike a server-side file path."""
            import json
            import tempfile

            try:
                raw = await file.read()
            except Exception:
                raise HTTPException(status_code=400, detail="Could not read the uploaded file.")

            try:
                cert_data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                return JSONResponse(content={
                    "valid": False, "signature_valid": False, "certificate_exists": True,
                    "error": "Not a valid JSON certificate. Upload the .json report, not the PDF.",
                    "report": None, "blockchain": None,
                })

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as tmp:
                    tmp.write(raw)
                    tmp_path = tmp.name

                cert_generator = self.session_manager.cert_generator
                result = cert_generator.verify_certificate(tmp_path)
            except Exception:
                logger.exception("Certificate verification failed")
                raise HTTPException(status_code=500, detail="Verification failed. See server logs for details.")
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            device_info = cert_data.get("device_info") or {}
            result["report"] = {
                "report_id": cert_data.get("report_id"),
                "generated_at": cert_data.get("generated_at"),
                "algorithm_used": cert_data.get("algorithm_used"),
                "success": cert_data.get("success"),
                "certificate_hash": cert_data.get("certificate_hash"),
                "device_model": device_info.get("model"),
                "device_path": device_info.get("path"),
                "device_serial": device_info.get("serial"),
            }

            result["blockchain"] = None
            cert_hash = cert_data.get("certificate_hash")
            if cert_hash:
                try:
                    result["blockchain"] = cert_generator.verify_certificate_blockchain(cert_hash)
                except Exception:
                    logger.exception("Blockchain verification failed")
                    result["blockchain"] = {"valid": False, "error": "Blockchain lookup failed. See server logs for details."}

            return JSONResponse(content=result)

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
            except ValueError as e:
                # start_wipe_session raises this deliberately (e.g. "Device
                # /dev/sdX not found") -- a clean, expected message, safe and
                # useful to echo back as-is.
                raise HTTPException(status_code=400, detail=str(e))
            except Exception:
                logger.exception("Failed to start wipe")
                raise HTTPException(status_code=500, detail="Failed to start wipe. See server logs for details.")

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

            # Verification outcome (None when verification wasn't requested)
            report_data["verification"] = {
                "enabled": session.wipe_request.verify,
                "passed": getattr(session, 'verification_passed', None)
            }

            # Certificate artifacts + blockchain anchor, when a certificate
            # was generated (session.certificate_files is stashed by
            # session_manager._execute_wipe)
            cert_files = getattr(session, 'certificate_files', None)
            if cert_files:
                report_data["certificate"] = {
                    "pdf_path": cert_files.get('pdf'),
                    "json_path": cert_files.get('json'),
                    "qr_png_path": cert_files.get('qr_png')
                }
                blockchain_result = cert_files.get('blockchain_result')
                if blockchain_result and blockchain_result.get('success'):
                    tx_hash = blockchain_result.get('transaction_hash')
                    report_data["blockchain"] = {
                        "tx_hash": tx_hash,
                        "report_hash": blockchain_result.get('report_hash'),
                        "explorer_url": f"https://sepolia.etherscan.io/tx/{tx_hash}" if tx_hash else None
                    }
                else:
                    report_data["blockchain"] = None
            else:
                report_data["certificate"] = None
                report_data["blockchain"] = None

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
            except Exception:
                logger.exception("Failed to fetch logs")
                raise HTTPException(status_code=500, detail="Failed to fetch logs. See server logs for details.")

        @self.app.get("/api/logs/statistics")
        async def get_log_statistics():
            """Get logging statistics."""
            try:
                stats = self.session_manager.logger.get_statistics()
                return {
                    "success": True,
                    "data": stats
                }
            except Exception:
                logger.exception("Failed to fetch log statistics")
                raise HTTPException(status_code=500, detail="Failed to fetch log statistics. See server logs for details.")

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
            except Exception:
                logger.exception(f"Failed to fetch logs for {device_path}")
                raise HTTPException(status_code=500, detail="Failed to fetch device logs. See server logs for details.")

        @self.app.get("/api/logs/device-history")
        async def get_device_history(device_path: str = None):
            """Get device history records."""
            try:
                history = self.session_manager.logger.get_device_history(device_path)
                return {
                    "success": True,
                    "data": history
                }
            except Exception:
                logger.exception(f"Failed to fetch device history for {device_path}")
                raise HTTPException(status_code=500, detail="Failed to fetch device history. See server logs for details.")

        @self.app.get("/api/logs/audit/{session_id}")
        async def get_audit_trail(session_id: str):
            """Get audit trail for a specific session."""
            try:
                audit_events = self.session_manager.logger.get_audit_trail(session_id)
                return {
                    "success": True,
                    "data": audit_events
                }
            except Exception:
                logger.exception(f"Failed to fetch audit trail for {session_id}")
                raise HTTPException(status_code=500, detail="Failed to fetch audit trail. See server logs for details.")

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
            except Exception:
                logger.exception(f"Failed to fetch log {session_id}")
                raise HTTPException(status_code=500, detail="Failed to fetch log. See server logs for details.")

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
            except Exception:
                logger.exception(f"Failed to delete log {session_id}")
                raise HTTPException(status_code=500, detail="Failed to delete log. See server logs for details.")

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
            except Exception:
                logger.exception("Failed to delete logs")
                raise HTTPException(status_code=500, detail="Failed to delete logs. See server logs for details.")

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
            except Exception:
                logger.exception("Failed to clean up old logs")
                raise HTTPException(status_code=500, detail="Failed to clean up old logs. See server logs for details.")

        # Reports API endpoints
        @self.app.get("/api/reports")
        async def get_reports(device_path: str = None, limit: int = 100, offset: int = 0):
            """Get wipe reports with optional filtering."""
            try:
                reports = self.session_manager.logger.get_reports(device_path, limit, offset)
                return reports
            except Exception:
                logger.exception("Failed to fetch reports")
                raise HTTPException(status_code=500, detail="Failed to fetch reports. See server logs for details.")

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
            except Exception:
                logger.exception(f"Failed to fetch report {session_id}")
                raise HTTPException(status_code=500, detail="Failed to fetch report. See server logs for details.")

        @self.app.get("/api/reports/device/{device_path:path}")
        async def get_device_reports(device_path: str):
            """Get all reports for a specific device."""
            try:
                reports = self.session_manager.logger.get_device_reports(device_path)
                return reports
            except Exception:
                logger.exception(f"Failed to fetch reports for {device_path}")
                raise HTTPException(status_code=500, detail="Failed to fetch device reports. See server logs for details.")

        @self.app.get("/api/download{file_path:path}")
        async def download_report_file(file_path: str):
            """Download a report file (PDF, JSON, or QR code image)."""
            try:
                import os
                from fastapi.responses import FileResponse

                # Resolve to a real, normalized absolute path *before* the
                # allowlist check -- comparing the raw string let a traversal
                # sequence (e.g. /home/../../etc/passwd) pass a naive
                # startswith('/home') check while actually pointing outside
                # every allowed directory.
                resolved_path = os.path.realpath(file_path)

                if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                    raise HTTPException(status_code=404, detail="File not found")

                # Additional security: check if file is in a reports/certificates directory.
                # Compare against os.sep-anchored prefixes (or an exact match), not a bare
                # startswith -- otherwise an allowed dir of "/home" would also match a
                # sibling directory like "/homefoo".
                allowed_dirs = [
                    os.path.realpath('/tmp'),
                    os.path.realpath('/var/tmp'),
                    os.path.realpath(str(Path.home() / '.breaknwipe')),
                    os.path.realpath('/root/breaknwipe_reports'),  # Certificate storage directory
                    os.path.realpath('/home'),  # User home directories
                    os.path.realpath(str(Path.cwd())),  # Current working directory
                ]
                if not any(
                    resolved_path == allowed_dir or resolved_path.startswith(allowed_dir + os.sep)
                    for allowed_dir in allowed_dirs
                ):
                    raise HTTPException(status_code=403, detail="Access denied")

                return FileResponse(
                    path=resolved_path,
                    filename=os.path.basename(resolved_path),
                    media_type='application/octet-stream'
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Download failed for {file_path}")
                raise HTTPException(status_code=500, detail="Download failed. See server logs for details.")

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

        @self.app.websocket("/ws/recovery/{job_id}")
        async def recovery_websocket_endpoint(websocket: WebSocket, job_id: str):
            """WebSocket endpoint for deep-scan recovery job progress."""
            await websocket.accept()

            if job_id not in self.recovery_ws_connections:
                self.recovery_ws_connections[job_id] = []
            self.recovery_ws_connections[job_id].append(websocket)

            try:
                # Send current status immediately (covers reconnects after
                # navigating away, same as the wipe WebSocket above).
                job = self.recovery_manager.get_job(job_id)
                if job:
                    message = WebSocketMessage(type="recovery_progress", session_id=job_id, data=job.to_dict())
                    await websocket.send_text(message.json())

                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break

            except WebSocketDisconnect:
                pass
            finally:
                if job_id in self.recovery_ws_connections:
                    try:
                        self.recovery_ws_connections[job_id].remove(websocket)
                        if not self.recovery_ws_connections[job_id]:
                            del self.recovery_ws_connections[job_id]
                    except ValueError:
                        pass

        @self.app.websocket("/ws/verify/{job_id}")
        async def verify_websocket_endpoint(websocket: WebSocket, job_id: str):
            """WebSocket endpoint for erasure-check job progress."""
            await websocket.accept()

            if job_id not in self.verify_ws_connections:
                self.verify_ws_connections[job_id] = []
            self.verify_ws_connections[job_id].append(websocket)

            try:
                job = self.verify_manager.get_job(job_id)
                if job:
                    message = WebSocketMessage(type="verify_progress", session_id=job_id, data=job.to_dict())
                    await websocket.send_text(message.json())

                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break

            except WebSocketDisconnect:
                pass
            finally:
                if job_id in self.verify_ws_connections:
                    try:
                        self.verify_ws_connections[job_id].remove(websocket)
                        if not self.verify_ws_connections[job_id]:
                            del self.verify_ws_connections[job_id]
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
                    "BreakNWipe Version": __version__,
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
                logger.exception("Failed to gather system info")
                return {
                    "Operating System": "Unknown",
                    "Python Version": "Unknown",
                    "Server Status": "Running",
                    "Error": "System info unavailable. See server logs for details."
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

    async def _broadcast_recovery_progress(self, job_id: str, data: Dict[str, Any]):
        """Broadcast a deep-scan recovery job's progress to connected WebSocket clients."""
        if job_id not in self.recovery_ws_connections:
            return

        message = WebSocketMessage(type="recovery_progress", session_id=job_id, data=data)

        disconnected_clients = []
        for websocket in self.recovery_ws_connections[job_id]:
            try:
                await websocket.send_text(message.json())
            except Exception:
                disconnected_clients.append(websocket)

        for client in disconnected_clients:
            try:
                self.recovery_ws_connections[job_id].remove(client)
            except ValueError:
                pass

    async def _broadcast_verify_progress(self, job_id: str, data: Dict[str, Any]):
        """Broadcast an erasure-check job's progress to connected WebSocket clients."""
        if job_id not in self.verify_ws_connections:
            return

        message = WebSocketMessage(type="verify_progress", session_id=job_id, data=data)

        disconnected_clients = []
        for websocket in self.verify_ws_connections[job_id]:
            try:
                await websocket.send_text(message.json())
            except Exception:
                disconnected_clients.append(websocket)

        for client in disconnected_clients:
            try:
                self.verify_ws_connections[job_id].remove(client)
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