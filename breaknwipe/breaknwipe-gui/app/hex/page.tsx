"use client";

import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useQueryParam } from "@/lib/hooks";
import { DataValue, ErrorState, PageTitle, Spinner } from "@/components/ui";
import { HexViewer } from "@/components/hex-viewer";

export default function HexPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <HexPageInner />
    </Suspense>
  );
}

function HexPageInner() {
  const path = useQueryParam("path");

  if (!path) {
    return <ErrorState message="No device path given. Open a device and choose View sectors." />;
  }

  return (
    <div className="space-y-5">
      <div>
        <Link
          href={`/device/?path=${encodeURIComponent(path)}`}
          className="mb-2 inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft size={15} /> Device
        </Link>
        <PageTitle title="Sector viewer" description="Inspect raw bytes on the device — e.g. to confirm a wipe zeroed it." />
        <DataValue className="-mt-4 block text-sm text-fg-muted">{path}</DataValue>
      </div>

      <HexViewer key={path} devicePath={path} />
    </div>
  );
}
