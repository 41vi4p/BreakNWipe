"use client";

import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { DeviceCard } from "@/components/device-card";
import { Button, EmptyState, ErrorState, PageTitle, Spinner } from "@/components/ui";

export default function DevicesPage() {
  const { data: devices, error, loading, reload } = useAsync(() => api.devices(), []);

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
