"use client";

import Link from "next/link";
import { ArrowLeft, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { Button, Card, CardHeader, DataValue, ErrorState, PageTitle, Spinner, Badge } from "@/components/ui";
import { HealthPanel } from "@/components/health-panel";
import { PartitionMap } from "@/components/partition-map";
import { FsckPanel } from "@/components/fsck-panel";

export default function DevicePage() {
  const path = useQueryParam("path");

  const devices = useAsync(() => api.devices(), []);
  const health = useAsync(() => (path ? api.deviceHealth(path) : Promise.resolve(null)), [path]);
  const partitions = useAsync(() => (path ? api.devicePartitions(path) : Promise.resolve([])), [path]);
  const layout = useAsync(() => (path ? api.partitionTable(path) : Promise.resolve(null)), [path]);

  if (!path) {
    return <ErrorState message="No device path given. Go back to Devices and open one." />;
  }

  const device = devices.data?.find((d) => d.path === path);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link href="/" className="mb-2 inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
            <ArrowLeft size={15} /> Devices
          </Link>
          <PageTitle title={device?.model || "Device"} />
          <DataValue className="-mt-4 block text-sm text-fg-muted">{path}</DataValue>
        </div>
        <Link href={`/wipe/?path=${encodeURIComponent(path)}`}>
          <Button variant="danger" size="sm">
            <Trash2 size={15} />
            Wipe device
          </Button>
        </Link>
      </div>

      {devices.loading && <Spinner label="Loading device…" />}

      {device && (
        <Card>
          <CardHeader title="Overview" />
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 p-5 text-sm sm:grid-cols-3 lg:grid-cols-4">
            <Field label="Model" value={device.model} />
            <Field label="Serial" value={device.serial} mono />
            <Field label="Capacity" value={device.capacity_human} mono />
            <Field label="Type" value={device.device_type} mono />
            <Field label="Interface" value={device.interface} mono />
            <Field label="Hardware erase" value={device.secure_erase_support ? "Yes" : "No"} />
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-fg-subtle">Status</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {device.is_system_disk && <Badge tone="warning">System</Badge>}
                {device.is_mounted ? <Badge tone="info">Mounted</Badge> : <Badge tone="neutral">Not mounted</Badge>}
              </dd>
            </div>
            {device.mount_points.length > 0 && (
              <Field label="Mount points" value={device.mount_points.join(", ")} mono />
            )}
          </dl>
        </Card>
      )}

      {health.loading ? (
        <Spinner label="Reading SMART health…" />
      ) : health.data ? (
        <HealthPanel health={health.data} />
      ) : health.error ? (
        <ErrorState message={`Health: ${health.error}`} />
      ) : null}

      {layout.loading ? (
        <Spinner label="Reading partition table…" />
      ) : layout.data ? (
        <PartitionMap layout={layout.data} onChanged={() => { layout.reload(); partitions.reload(); }} />
      ) : layout.error ? (
        <ErrorState message={`Partition table: ${layout.error}`} />
      ) : null}

      {partitions.loading ? (
        <Spinner label="Listing partitions…" />
      ) : partitions.error ? (
        <ErrorState message={`Partitions: ${partitions.error}`} />
      ) : (
        <FsckPanel partitions={partitions.data ?? []} />
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-fg-subtle">{label}</dt>
      <dd className={`mt-1 font-medium text-fg ${mono ? "data" : ""}`}>{value || "—"}</dd>
    </div>
  );
}
