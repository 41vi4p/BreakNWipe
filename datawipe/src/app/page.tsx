"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Html5Qrcode } from "html5-qrcode";
import { processQRResult } from "../actions/ProcessQRResult";

interface DecryptedData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

export default function Home() {
  const router = useRouter();
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);
  const mountedRef = useRef(true);

  const [scanning, setScanning] = useState(false);
  const [isStartingCamera, setIsStartingCamera] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [decryptedData, setDecryptedData] = useState<DecryptedData | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [isDecrypting, setIsDecrypting] = useState(false); // TODO: rename to isProcessing

  // zoom state (if camera supports it)
  const [zoomRange, setZoomRange] = useState<{
    min: number;
    max: number;
    step: number;
    current: number;
  } | null>(null);

  // create Html5Qrcode once
  useEffect(() => {
    scannerRef.current = new Html5Qrcode("qr-video", { verbose: false });
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      // cleanup: stop scanner and stop track if present
      (async () => {
        try {
          if (scannerRef.current) {
            // stop only if running
            await scannerRef.current.stop().catch(() => {});
            scannerRef.current.clear();
          }
        } catch {
          /* ignore */
        }
        try {
          trackRef.current?.stop();
        } catch {
          /* ignore */
        }
      })();
    };
  }, []);

  // internal stop + cleanup helper
  const stopScannerInternal = async () => {
    if (scannerRef.current) {
      try {
        await scannerRef.current.stop();
      } catch {
        /* ignore */
      }
      try {
        scannerRef.current.clear();
      } catch {
        /* ignore */
      }
    }
    try {
      trackRef.current?.stop();
    } catch {
      /* ignore */
    }
    trackRef.current = null;
    setScanning(false);
    setZoomRange(null);
  };

  // start scanning: pick camera, detect zoom capability, then start html5-qrcode
  const startScan = async () => {
    setError(null);
    setResult(null);
    setDecryptedData(null);
    setIsDecrypting(false);
    setIsStartingCamera(true);

    if (!scannerRef.current) {
      setError("Scanner not initialized");
      setIsStartingCamera(false);
      return;
    }

    try {
      // 1) Grab a short stream to detect deviceId and capabilities
      const probeStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" }, // prefer back camera
      });
      const probeTrack = probeStream.getVideoTracks()[0];
      const probeSettings = probeTrack.getSettings();
      const probeCaps = (probeTrack as any).getCapabilities?.() ?? {};

      // prepare zoom state if available
      if ("zoom" in probeCaps) {
        const min = probeCaps.zoom?.min ?? 1;
        const max = probeCaps.zoom?.max ?? 3;
        const step = probeCaps.zoom?.step ?? 0.1;
        const current = probeSettings.zoom ?? min;
        setZoomRange({ min, max, step, current });
      } else {
        setZoomRange(null);
      }

      // capture deviceId if available, then stop probe stream
      const deviceId = probeSettings.deviceId;
      probeStream.getTracks().forEach((t) => t.stop());

      // 2) Start scanner using deviceId (preferred) or facingMode
      const cameraConstraints = deviceId
        ? { deviceId: { exact: deviceId } } // use same camera as probe
        : { facingMode: "environment" };

      setScanning(true);
      setIsStartingCamera(false);

      await scannerRef.current.start(
        cameraConstraints,
        { fps: 60 },

        async (decodedText) => {
          // success callback
          if (!mountedRef.current) return;
          setResult(decodedText);
          setScanning(false);

          // stop scanner (and capture track afterwards)
          await stopScannerInternal();

          // process QR result (handles both encrypted and JSON formats)
          setIsDecrypting(true);
          try {
            const processResult = await processQRResult(decodedText);
            if (processResult.success && processResult.data) {
              setDecryptedData(processResult.data);
              console.log(
                `✅ Successfully processed ${processResult.format} format QR data`
              );
            } else {
              setError(processResult.error || "Failed to process QR code data");
              console.log(`❌ Processing failed: ${processResult.error}`);
            }
          } catch (err) {
            setError(
              "Error during QR processing: " +
                (err instanceof Error ? err.message : String(err))
            );
          } finally {
            setIsDecrypting(false);
          }
        },
        (scanErr) => {
          // non-fatal scan error
          // ignore NotFound errors (common)
          // console.warn("scan error", scanErr);
        }
      );

      // 3) After start resolves, the library created a <video> inside our container.
      // get the real track from that video to allow applyConstraints (zoom)
      const videoEl = document.querySelector(
        "#qr-video video"
      ) as HTMLVideoElement | null;
      if (videoEl) {
        const src = videoEl.srcObject as MediaStream | null;
        const runningTrack = src?.getVideoTracks()[0] ?? null;
        if (runningTrack) {
          trackRef.current = runningTrack;
          const caps = (runningTrack as any).getCapabilities?.() ?? {};
          const settings = runningTrack.getSettings?.() ?? {};
          if ("zoom" in caps) {
            const min = caps.zoom?.min ?? 1;
            const max = caps.zoom?.max ?? 3;
            const step = caps.zoom?.step ?? 0.1;
            const current = settings.zoom ?? min;
            setZoomRange({ min, max, step, current });
          }
        }
      }
    } catch (err) {
      console.error("startScan error", err);
      setError(
        err instanceof Error ? err.message : "Could not start camera scanner"
      );
      setScanning(false);
      setIsStartingCamera(false);
      // ensure cleanup
      try {
        await stopScannerInternal();
      } catch {
        /* ignore */
      }
    }
  };

  // stop scanning (public)
  const stopScan = async () => {
    await stopScannerInternal();
  };

  // change zoom
  const handleZoomChange = async (value: number) => {
    if (!trackRef.current) {
      setError("No camera track available to apply zoom");
      return;
    }
    try {
      // applyConstraints may fail on some devices / browsers
      await trackRef.current.applyConstraints({
        advanced: [{ zoom: value }],
      } as any);
      setZoomRange((prev) => (prev ? { ...prev, current: value } : prev));
    } catch (err) {
      console.warn("applyConstraints(zoom) failed", err);
      setError("Zoom not supported by this device/browser");
    }
  };

  const handleScanAnother = async () => {
    setResult(null);
    setDecryptedData(null);
    setError(null);
    setIsDecrypting(false);
    setIsStartingCamera(false);
    setZoomRange(null);
    // ensure scanner is stopped
    try {
      await stopScannerInternal();
    } catch {
      /* ignore */
    }
  };

  const handleViewReport = () => {
    if (decryptedData) {
      const dataParam = encodeURIComponent(JSON.stringify(decryptedData));
      router.push(`/report?data=${dataParam}`);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-900 via-gray-800 to-black relative overflow-hidden px-2">
      <div className="relative bg-white/6 backdrop-blur-md shadow-2xl rounded-2xl p-4 max-w-xl w-full text-center border border-white/10">
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="w-9 h-9 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-md flex items-center justify-center">
            <div className="w-3 h-3 bg-white rounded-sm"></div>
          </div>
          <h1 className="text-2xl font-semibold text-white">BreakNWipe</h1>
        </div>

        {/* Camera preview */}
        <div className="w-full aspect-square bg-black rounded-lg flex items-center justify-center overflow-hidden border border-white">
          <div id="qr-video" className="w-full h-full" />
        </div>

        {/* Title & hint */}
        <h2 className="text-lg font-semibold text-white mt-4">Scan QR Code</h2>
        <p className="text-gray-400 text-sm mb-4">
          Line up the device&apos;s QR code within the frame to view
          verification reports.
        </p>

        {/* Zoom slider */}
        {zoomRange && (
          <div className="w-full px-4 mb-3">
            <input
              type="range"
              min={zoomRange.min}
              max={zoomRange.max}
              step={zoomRange.step}
              value={zoomRange.current}
              onChange={(e) => handleZoomChange(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-300 mt-1">
              <span>Zoom {zoomRange.current.toFixed(2)}x</span>
              <span>
                {zoomRange.min.toFixed(1)}x - {zoomRange.max.toFixed(1)}x
              </span>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center justify-center gap-3 mt-3">
          {!scanning && !isStartingCamera ? (
            <button
              onClick={startScan}
              className="px-5 py-2 bg-white text-gray-900 rounded-md shadow"
            >
              Start Scanning
            </button>
          ) : isStartingCamera ? (
            <button
              disabled
              className="px-5 py-2 bg-gray-400 text-gray-700 rounded-md shadow cursor-not-allowed flex items-center gap-2"
            >
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-700 border-t-transparent"></div>
              Starting Camera...
            </button>
          ) : (
            <button
              onClick={stopScan}
              className="px-5 py-2 bg-red-600 text-white rounded-md shadow"
            >
              Stop
            </button>
          )}

          {/* <button
            onClick={handleScanAnother}
            className="px-4 py-2 bg-white/5 text-white rounded-md border border-white/10"
          >
            Reset
          </button> */}
        </div>

        {/* Errors */}
        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

        {/* Scanned / Decrypted result UI */}
        {(isDecrypting || decryptedData || result) && (
          <div className="mt-5 text-left">
            {isDecrypting && (
              <div className="p-3 bg-blue-900/20 rounded text-white text-center">
                Processing QR data…
              </div>
            )}

            {!isDecrypting && decryptedData && (
              <div className="p-3 bg-green-900/20 rounded text-white">
                <h3 className="font-semibold mb-2">✅ Verification Complete</h3>
                <div className="text-sm space-y-1">
                  <div>
                    <strong>Date & Time:</strong> {decryptedData.DateTime}
                  </div>
                  <div>
                    <strong>Device:</strong> {decryptedData.Device}
                  </div>
                  <div>
                    <strong>Serial:</strong> {decryptedData.Serial}
                  </div>
                  <div>
                    <strong>Method:</strong> {decryptedData.SanitizationMethod}
                  </div>
                  <div>
                    <strong>Verification:</strong> {decryptedData.Verification}
                  </div>
                  <div>
                    <strong>Operator:</strong> {decryptedData.Operator}
                  </div>
                  <div>
                    <strong>Digital Key:</strong> {decryptedData.DigitalKey}
                  </div>
                </div>
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleViewReport}
                    className="px-3 py-2 bg-green-600 rounded text-white font-medium"
                  >
                    View Full Report
                  </button>
                  <button
                    onClick={handleScanAnother}
                    className="px-3 py-2 bg-blue-600 rounded text-white"
                  >
                    Scan Another
                  </button>
                </div>
              </div>
            )}

            {!isDecrypting && !decryptedData && result && (
              <div className="p-3 bg-yellow-900/20 rounded text-white">
                <h3 className="font-semibold mb-1">⚠️ Raw QR Data</h3>
                <pre className="text-xs break-all text-gray-200">{result}</pre>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={handleScanAnother}
                    className="px-3 py-2 bg-blue-600 rounded text-white"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Test Section - for development
        {process.env.NODE_ENV === "development" && (
          <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-600">
            <h3 className="text-white font-semibold mb-3">🧪 Test QR Processing</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                onClick={async () => {
                  const testJSON = `{"report_id":"BNW-4fd1921f-1758151679","session_id":"4fd1921f-7576-4815-a4de-abb72b273cc0","device_model":"ST3160215AS","algorithm":"nist-clear","completed_at":"2025-09-18T04:57:56.144457","verification_url":"http://127.0.0.1:8000/api/wipe/verify/4fd1921f-7576-4815-a4de-abb72b273cc0"}`;
                  setResult(testJSON);
                  setIsDecrypting(true);
                  try {
                    const processResult = await processQRResult(testJSON);
                    if (processResult.success && processResult.data) {
                      setDecryptedData(processResult.data);
                      console.log(`✅ Test: Successfully processed ${processResult.format} format`);
                    } else {
                      setError(processResult.error || "Test failed");
                    }
                  } catch (err) {
                    setError("Test error: " + (err instanceof Error ? err.message : String(err)));
                  } finally {
                    setIsDecrypting(false);
                  }
                }}
                disabled={isDecrypting}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-green-400 text-sm"
              >
                Test JSON Format
              </button>
              <button
                onClick={async () => {
                  const testEncrypted = "RGF0ZVRpbWU6IDIwMjUtMDktMThUMTg6MjM6MzIuMjkzWiB8IERldmljZTogU2FtcGxlIEhERApTZXJpYWw6IFNBTVBMRTEyMzQ1NgpTYW5pdGl6YXRpb24gTWV0aG9kOiBET0QgNTIyMC4yMi1NClZlcmlmaWNhdGlvbjogUGFzc2VkCk9wZXJhdG9yOiBKb2huIERvZQpEaWdpdGFsS2V5OiBTQU1QTEVfS0VZXzEyMzQ1";
                  setResult(testEncrypted);
                  setIsDecrypting(true);
                  try {
                    const processResult = await processQRResult(testEncrypted);
                    if (processResult.success && processResult.data) {
                      setDecryptedData(processResult.data);
                      console.log(`✅ Test: Successfully processed ${processResult.format} format`);
                    } else {
                      setError(processResult.error || "Test failed");
                    }
                  } catch (err) {
                    setError("Test error: " + (err instanceof Error ? err.message : String(err)));
                  } finally {
                    setIsDecrypting(false);
                  }
                }}
                disabled={isDecrypting}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-purple-400 text-sm"
              >
                Test Encrypted Format
              </button>
            </div>
            <p className="text-gray-400 text-xs mt-2">
              These buttons test both JSON and encrypted QR formats without scanning.
            </p>
          </div>
        )} */}
      </div>
    </div>
  );
}
