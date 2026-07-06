"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  FileWarning,
  Gauge,
  Info,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  api,
  VERIFY_JOB_TERMINAL,
  type DeviceInfo,
  type ErasureCheckResult,
  type VerifyJobProgress,
} from "@/lib/api";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { useWebSocket } from "@/lib/use-websocket";
import { formatDuration } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataValue,
  ErrorState,
  PageTitle,
  ProgressBar,
  Spinner,
} from "@/components/ui";
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
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const { last } = useWebSocket<{ type: string; data: VerifyJobProgress }>(jobId ? `/ws/verify/${jobId}` : null);
  const job = last?.data ?? null;
  const done = job ? VERIFY_JOB_TERMINAL.includes(job.status) : false;

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
    try {
      const { job_id } = await api.verifyErasureStart({ device: path, depth });
      setJobId(job_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!jobId) return;
    try {
      await api.verifyErasureCancel(jobId);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function newCheck() {
    setJobId(null);
    setError(null);
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

      {!jobId && (
        <Card>
          <CardHeader title="Check depth" icon={<Gauge size={16} />} />
          <div className="space-y-4 p-5">
            <div className="flex flex-col gap-2 sm:flex-row">
              {DEPTHS.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => setDepth(d.value)}
                  className={`flex-1 rounded-lg border-2 p-3 text-left transition-colors ${
                    depth === d.value
                      ? "border-primary bg-primary/8 shadow-[0_0_0_3px_var(--ring)]"
                      : "border-border bg-surface-2 hover:border-border-strong hover:bg-surface-3"
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
      )}

      {jobId && !done && <VerifyProgressCard job={job} onCancel={cancel} />}

      {jobId && done && job?.status === "cancelled" && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/8 px-4 py-3 text-sm text-warning">
          <Ban size={16} /> Check cancelled.
        </div>
      )}
      {jobId && done && job?.status === "failed" && job.error && !job.result && <ErrorState message={job.error} />}
      {jobId && done && job?.result && <ResultView result={job.result} />}
      {jobId && done && (
        <div className="flex justify-end">
          <Button variant="secondary" size="sm" onClick={newCheck}>
            Run another check
          </Button>
        </div>
      )}

      {error && <ErrorState message={error} />}
    </div>
  );
}

function VerifyProgressCard({ job, onCancel }: { job: VerifyJobProgress | null; onCancel: () => void }) {
  const statusLabel =
    job?.status === "sampling" ? "Sampling…" : job?.status === "cross_checking" ? "Cross-checking recovery…" : job?.status;

  return (
    <Card>
      <CardHeader
        title="Erasure check"
        icon={<ShieldCheck size={16} />}
        action={job ? <Badge tone="info">{job.status}</Badge> : undefined}
      />
      <div className="space-y-4 p-5">
        {!job && <Spinner label="Starting…" />}

        {job && (
          <>
            <div className="flex items-center justify-between text-sm">
              <span className="text-fg-muted">{statusLabel}</span>
              {job.percent != null && <DataValue className="font-medium text-fg">{job.percent.toFixed(0)}%</DataValue>}
            </div>
            <ProgressBar percent={job.percent ?? 0} />
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <Stat label="Samples" value={`${job.samples_done} / ${job.total_samples || "—"}`} />
              <Stat label="ETA" value={formatDuration(job.eta_seconds)} />
            </div>
            <div className="flex justify-end border-t border-border pt-4">
              <Button variant="danger" size="sm" onClick={onCancel}>
                <Ban size={15} /> Cancel check
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
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
