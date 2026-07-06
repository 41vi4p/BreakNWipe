"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  FileWarning,
  Gauge,
  Info,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { api, type DeviceInfo, type ErasureCheckResult } from "@/lib/api";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { Badge, Button, Card, CardHeader, DataValue, ErrorState, PageTitle, Spinner } from "@/components/ui";
import { DevicePicker } from "@/components/device-picker";

type Depth = "quick" | "comprehensive" | "paranoid";

const DEPTHS: { value: Depth; label: string; desc: string }[] = [
  { value: "quick", label: "Quick", desc: "~10 samples. A fast sanity check." },
  { value: "comprehensive", label: "Comprehensive", desc: "~100 samples, random + sequential. Recommended." },
  { value: "paranoid", label: "Paranoid", desc: "Up to 100 MB read across the device. Slowest, most thorough." },
];

export default function VerifyPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <VerifyPageInner />
    </Suspense>
  );
}

function VerifyPageInner() {
  const path = useQueryParam("path");
  const { data: devices } = useAsync(() => api.devices().catch(() => []), []);
  const device = devices?.find((d) => d.path === path) as DeviceInfo | undefined;

  const [depth, setDepth] = useState<Depth>("comprehensive");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ErasureCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!path) {
    return (
      <DevicePicker
        title="Verify"
        description="Confirm a device has actually been wiped — no data should remain on it. Read-only, safe to run any time."
        primaryLabel="Verify"
        primaryHref={(p) => `/verify/?path=${p}`}
        primaryVariant="secondary"
      />
    );
  }

  async function run() {
    if (!path) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.verifyErasure({ device: path, depth });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <Link href="/verify/" className="mb-2 inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
          <ArrowLeft size={15} /> Devices
        </Link>
        <PageTitle
          title="Verify erasure"
          description="Reads the device to confirm no recoverable data remains. This never writes to the device."
        />
        <DataValue className="-mt-4 block text-sm text-fg-muted">
          {path} {device ? `· ${device.model}` : ""}
        </DataValue>
      </div>

      <Card>
        <CardHeader title="Check depth" icon={<Gauge size={16} />} />
        <div className="space-y-4 p-5">
          <div className="flex flex-col gap-2 sm:flex-row">
            {DEPTHS.map((d) => (
              <button
                key={d.value}
                type="button"
                onClick={() => setDepth(d.value)}
                className={`flex-1 rounded-lg border p-3 text-left transition-colors ${
                  depth === d.value ? "border-primary bg-primary/8" : "border-border bg-surface-2 hover:bg-surface-3"
                }`}
              >
                <div className="text-sm font-medium text-fg">{d.label}</div>
                <div className="mt-1 text-xs text-fg-muted">{d.desc}</div>
              </button>
            ))}
          </div>
          <Button onClick={run} loading={busy}>
            <ShieldCheck size={15} /> Run check
          </Button>
        </div>
      </Card>

      {error && <ErrorState message={error} />}
      {result && <ResultView result={result} />}
    </div>
  );
}

function ResultView({ result }: { result: ErasureCheckResult }) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/8 p-4 text-sm text-warning">
        <div className="mb-1 font-medium">Can&apos;t check this device</div>
        {result.refusal_reason}
      </div>
    );
  }
  if (result.error) {
    return <ErrorState message={result.error} />;
  }

  const ok = result.passed;

  return (
    <div className="space-y-4">
      <Card className={ok ? "border-success/30" : "border-danger/30"}>
        <div className="flex items-center gap-4 p-5">
          <span
            className={`inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${
              ok ? "bg-success/12 text-success" : "bg-danger/12 text-danger"
            }`}
          >
            {ok ? <CheckCircle2 size={24} /> : <XCircle size={24} />}
          </span>
          <div>
            <div className="text-lg font-semibold text-fg">
              {ok ? "No recoverable data found" : "This device does not appear fully erased"}
            </div>
            <div className="text-sm text-fg-muted">
              {result.samples_checked} sample{result.samples_checked === 1 ? "" : "s"} checked ({result.depth})
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Statistics" />
        <div className="grid grid-cols-2 gap-3 p-5 text-sm sm:grid-cols-3">
          <Stat label="Avg entropy" value={`${result.avg_entropy.toFixed(2)} / 8`} />
          <Stat label="Pattern hits" value={`${result.pattern_detection_percent.toFixed(1)}%`} />
          <Stat label="File signatures" value={String(result.signature_hits.length)} tone={result.signature_hits.length > 0 ? "danger" : undefined} />
        </div>
        {result.signature_hits.length > 0 && (
          <div className="border-t border-border p-5 text-sm">
            <div className="mb-2 flex items-center gap-1.5 font-medium text-danger">
              <FileWarning size={15} /> File signatures found
            </div>
            <div className="space-y-1">
              {result.signature_hits.map((h, i) => (
                <div key={i} className="data text-xs text-fg-muted">
                  offset <span className="text-fg">0x{h.offset.toString(16)}</span> — {h.signature}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {result.partition_checks.length > 0 && (
        <Card>
          <CardHeader title="Recovery cross-check" />
          <ul className="divide-y divide-border">
            {result.partition_checks.map((p) => (
              <li key={p.partition} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm">
                <div>
                  <DataValue className="text-fg">{p.partition}</DataValue>
                  {p.filesystem && <span className="ml-2 text-fg-muted">({p.filesystem})</span>}
                </div>
                <Badge tone={p.named_files_found > 0 ? "danger" : "success"}>{p.note}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {result.notes.length > 0 && (
        <div className="space-y-2">
          {result.notes.map((n, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-info/25 bg-info/8 px-4 py-2.5 text-sm text-fg-muted">
              <Info size={14} className="mt-0.5 shrink-0 text-info" />
              {n}
            </div>
          ))}
        </div>
      )}

      {!ok && (
        <div className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/8 px-4 py-3 text-sm text-danger">
          <ShieldAlert size={16} className="mt-0.5 shrink-0" />
          Consider running a full wipe on this device before disposing of or repurposing it.
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-fg-subtle">{label}</div>
      <DataValue className={`mt-0.5 block font-medium ${tone === "danger" ? "text-danger" : "text-fg"}`}>{value}</DataValue>
    </div>
  );
}
