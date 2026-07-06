"use client";

import Link from "next/link";
import { HardDrive, Usb, MemoryStick, Server, ChevronRight, ShieldAlert } from "lucide-react";
import type { DeviceInfo } from "@/lib/api";
import { Badge, Button, DataValue } from "./ui";

function DeviceIcon({ type, iface, size }: { type: string; iface: string; size: number }) {
  const t = type.toLowerCase();
  const i = iface.toLowerCase();
  if (i === "usb" || t.includes("usb")) return <Usb size={size} />;
  if (i === "nvme" || t.includes("nvme") || t.includes("ssd")) return <MemoryStick size={size} />;
  if (t.includes("server")) return <Server size={size} />;
  return <HardDrive size={size} />;
}

export function DeviceCard({
  device,
  primaryLabel = "Wipe",
  primaryHref,
  primaryVariant = "primary",
  secondaryLabel = "Details",
  secondaryHref,
}: {
  device: DeviceInfo;
  primaryLabel?: string;
  primaryHref?: (path: string) => string;
  primaryVariant?: "primary" | "danger" | "secondary";
  secondaryLabel?: string;
  secondaryHref?: (path: string) => string;
}) {
  const encoded = encodeURIComponent(device.path);
  const primary = (primaryHref ?? ((p: string) => `/wipe/?path=${p}`))(encoded);
  const secondary = (secondaryHref ?? ((p: string) => `/device/?path=${p}`))(encoded);

  return (
    <div className="group flex flex-col rounded-xl border border-border bg-surface p-5 transition-colors hover:border-border-strong">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-fg-muted">
          <DeviceIcon type={device.device_type} iface={device.interface} size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-fg">{device.model || "Unknown device"}</div>
          <DataValue className="mt-0.5 block truncate text-sm text-fg-muted">{device.path}</DataValue>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <dt className="text-[11px] uppercase tracking-wide text-fg-subtle">Capacity</dt>
          <dd className="data mt-0.5 font-medium text-fg">{device.capacity_human}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wide text-fg-subtle">Interface</dt>
          <dd className="data mt-0.5 font-medium text-fg">{device.interface || "—"}</dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {device.is_system_disk && (
          <Badge tone="warning">
            <ShieldAlert size={12} /> System disk
          </Badge>
        )}
        {device.is_mounted ? <Badge tone="info">Mounted</Badge> : <Badge tone="neutral">Not mounted</Badge>}
        {device.secure_erase_support && <Badge tone="success">HW erase</Badge>}
      </div>

      <div className="mt-4 flex items-center gap-2 border-t border-border pt-4">
        <Link href={secondary} className="flex-1">
          <Button variant="secondary" size="sm" className="w-full">
            {secondaryLabel}
            <ChevronRight size={15} />
          </Button>
        </Link>
        <Link href={primary}>
          <Button variant={primaryVariant} size="sm">
            {primaryLabel}
          </Button>
        </Link>
      </div>
    </div>
  );
}
