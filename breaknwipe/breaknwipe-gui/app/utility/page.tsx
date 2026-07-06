"use client";

import { DevicePicker } from "@/components/device-picker";

export default function UtilityPage() {
  return (
    <DevicePicker
      title="Disk Utility"
      description="Inspect health, browse and resize partitions, repair filesystems, or view raw sectors — pick a device to start."
      primaryLabel="Open"
      primaryHref={(p) => `/device/?path=${p}`}
      secondaryLabel="Wipe"
      secondaryHref={(p) => `/wipe/?path=${p}`}
    />
  );
}
