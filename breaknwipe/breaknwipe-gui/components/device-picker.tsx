"use client";

import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { DeviceCard } from "@/components/device-card";
import { Button, EmptyState, ErrorState, PageTitle, Spinner } from "@/components/ui";

// Shared "choose a device" entry step for the Wipe / Recover / Disk Utility
// pillars -- each pillar reaches its own flow through the same picker with a
// different primary action, instead of duplicating the devices list three times.
export function DevicePicker({
  title,
  description,
  primaryLabel,
  primaryHref,
  primaryVariant = "primary",
  secondaryLabel,
  secondaryHref,
  extra,
}: {
  title: string;
  description?: string;
  primaryLabel: string;
  primaryHref: (path: string) => string;
  primaryVariant?: "primary" | "danger" | "secondary";
  secondaryLabel?: string;
  secondaryHref?: (path: string) => string;
  extra?: React.ReactNode;
}) {
  const { data: devices, error, loading, reload } = useAsync(() => api.devices(), []);

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageTitle title={title} description={description} />
        <Button variant="secondary" size="sm" onClick={reload}>
          <RefreshCw size={15} />
          Refresh
        </Button>
      </div>

      {extra}

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
            <DeviceCard
              key={d.path}
              device={d}
              primaryLabel={primaryLabel}
              primaryHref={primaryHref}
              primaryVariant={primaryVariant}
              secondaryLabel={secondaryLabel}
              secondaryHref={secondaryHref}
            />
          ))}
        </div>
      )}
    </div>
  );
}
