"use client";

import Link from "next/link";
import { RefreshCw, Activity } from "lucide-react";
import { api, WIPE_TERMINAL } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { DeviceCard } from "@/components/device-card";
import { Button, DataValue, EmptyState, ErrorState, PageTitle, Spinner } from "@/components/ui";

export default function DevicesPage() {
  const { data: devices, error, loading, reload } = useAsync(() => api.devices(), []);
  const { data: sessions } = useAsync(() => api.wipeSessions().catch(() => []), []);
  const activeWipes = (sessions ?? []).filter((s) => !WIPE_TERMINAL.includes(s.progress.status));

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageTitle
          title="Devices"
          description="Every storage device on this machine. Inspect health, manage partitions, repair filesystems, or securely wipe — from one place."
        />
        <Button variant="secondary" size="sm" onClick={reload}>
          <RefreshCw size={15} />
          Refresh
        </Button>
      </div>

      {activeWipes.length > 0 && (
        <div className="mb-5 space-y-2">
          {activeWipes.map((s) => (
            <Link
              key={s.session_id}
              href={`/wipe/?path=${encodeURIComponent(s.device_info.path)}`}
              className="flex items-center justify-between gap-3 rounded-lg border border-info/30 bg-info/8 px-4 py-3 text-sm transition-colors hover:bg-info/12"
            >
              <span className="flex items-center gap-2 text-info">
                <Activity size={16} className="animate-pulse" />
                Wipe in progress on <DataValue className="text-fg">{s.device_info.path}</DataValue> ·{" "}
                {s.progress.progress_percent.toFixed(0)}%
              </span>
              <span className="font-medium text-info">Resume →</span>
            </Link>
          ))}
        </div>
      )}

      {loading && <Spinner label="Detecting storage devices…" />}

      {error && (
        <ErrorState
          message={
            error.toLowerCase().includes("root")
              ? "Root privileges are required to detect devices. Launch the GUI with sudo."
              : error
          }
        />
      )}

      {!loading && !error && devices && devices.length === 0 && (
        <EmptyState
          title="No storage devices found"
          description="Connect a device and refresh. If devices are present, ensure the server is running with root privileges."
          action={
            <Button variant="secondary" size="sm" onClick={reload}>
              <RefreshCw size={15} />
              Refresh
            </Button>
          }
        />
      )}

      {!loading && !error && devices && devices.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {devices.map((d) => (
            <DeviceCard key={d.path} device={d} />
          ))}
        </div>
      )}
    </div>
  );
}
