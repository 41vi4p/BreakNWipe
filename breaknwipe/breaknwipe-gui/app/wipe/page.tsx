"use client";

import { Suspense, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ShieldAlert,
  Download,
  CheckCircle2,
  XCircle,
  Ban,
  Binary,
  Activity,
  FileCheck2,
  ExternalLink,
} from "lucide-react";
import { api, apiUrl, downloadUrl, WIPE_TERMINAL, type DeviceInfo, type WipeProgressState, type WipeReportDetails } from "@/lib/api";
import { ALGORITHMS, algorithmLabel, algorithmGroup, type AlgorithmGroup } from "@/lib/algorithms";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { useWebSocket } from "@/lib/use-websocket";
import { formatBytes, formatDate, formatDuration } from "@/lib/format";
import { Button, Card, CardHeader, DataValue, ErrorState, PageTitle, ProgressBar, Spinner, Badge, StatTile } from "@/components/ui";
import { ConfirmDialog } from "@/components/dialog";
import { DevicePicker } from "@/components/device-picker";
import { AlgorithmPicker } from "@/components/algorithm-picker";

type WipeProgress = WipeProgressState;

export default function WipePage() {
  return (
    <Suspense fallback={<Spinner />}>
      <WipePageInner />
    </Suspense>
  );
}

function WipePageInner() {
  const path = useQueryParam("path");
  const { data: devices, loading } = useAsync(() => api.devices(), []);
  const device = devices?.find((d) => d.path === path) as DeviceInfo | undefined;
  const { data: allSessions } = useAsync(() => api.wipeSessions().catch(() => []), []);
  const activeWipes = (allSessions ?? []).filter((s) => !WIPE_TERMINAL.includes(s.progress.status));

  const [algorithm, setAlgorithm] = useState("nist-clear");
  const [category, setCategory] = useState<AlgorithmGroup | null>(null);
  const [passes, setPasses] = useState(3);
  const [verify, setVerify] = useState(true);
  const [certificate, setCertificate] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Seeds progress instantly when resuming an existing session, before the
  // WebSocket delivers its first live update.
  const [seed, setSeed] = useState<WipeProgress | null>(null);
  const [resumeChecked, setResumeChecked] = useState(false);

  const { last } = useWebSocket<{ type: string; data: WipeProgress }>(sessionId ? `/ws/${sessionId}` : null);
  const progress = last?.data ?? seed;
  const configurable = ALGORITHMS.find((a) => a.value === algorithm)?.configurablePasses;
  const succeeded = progress?.status === "completed";

  // Rich results (device details, certificate artifacts, QR, blockchain
  // anchor) — fetched once the wipe reports completed.
  const [report, setReport] = useState<WipeReportDetails | null>(null);
  useEffect(() => {
    if (!sessionId || !succeeded) return;
    let alive = true;
    api
      .wipeReport(sessionId)
      .then((r) => alive && setReport(r))
      .catch(() => {}); // fall back to the minimal completion row
    return () => {
      alive = false;
    };
  }, [sessionId, succeeded]);

  // On load, reconnect to an in-progress (or the latest) wipe for this device —
  // so navigating away and back doesn't lose the running wipe.
  useEffect(() => {
    if (!path) return;
    let alive = true;
    api
      .wipeSessions()
      .then((sessions) => {
        if (!alive) return;
        const mine = sessions.filter((s) => s.device_info?.path === path);
        const active = mine.find((s) => !WIPE_TERMINAL.includes(s.progress.status));
        const resume = active ?? mine[mine.length - 1];
        if (resume) {
          setSessionId(resume.session_id);
          setSeed(resume.progress);
          const resumedAlgorithm = resume.wipe_request?.algorithm ?? "nist-clear";
          setAlgorithm(resumedAlgorithm);
          setCategory(algorithmGroup(resumedAlgorithm) ?? null);
        }
      })
      .catch(() => {})
      .finally(() => alive && setResumeChecked(true));
    return () => {
      alive = false;
    };
  }, [path]);

  if (!path) {
    return (
      <DevicePicker
        title="Wipe"
        description="Securely erase a device with a standards-compliant algorithm and a tamper-proof certificate of destruction."
        primaryLabel="Wipe"
        primaryHref={(p) => `/wipe/?path=${p}`}
        primaryVariant="danger"
        extra={
          activeWipes.length > 0 ? (
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
          ) : undefined
        }
      />
    );
  }

  async function start() {
    if (!path) return;
    setStarting(true);
    setStartError(null);
    try {
      const res = await api.wipeStart({
        device_path: path,
        algorithm,
        verify,
        generate_certificate: certificate,
        passes: configurable ? passes : null,
      });
      const id = (res.data?.session_id as string) ?? null;
      setSeed(null);
      setSessionId(id);
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setStarting(false);
      setConfirmOpen(false);
    }
  }

  async function cancel() {
    if (!sessionId) return;
    setCancelling(true);
    try {
      await api.wipeCancel(sessionId);
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setCancelling(false);
    }
  }

  function newWipe() {
    setSessionId(null);
    setSeed(null);
    setStartError(null);
    setCategory(null);
    setReport(null);
  }

  const done = progress && WIPE_TERMINAL.includes(progress.status);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <Link href={`/device/?path=${encodeURIComponent(path)}`} className="mb-2 inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
          <ArrowLeft size={15} /> Device
        </Link>
        <PageTitle title="Secure wipe" />
        <DataValue className="-mt-4 block text-sm text-fg-muted">{path}</DataValue>
      </div>

      {(loading || !resumeChecked) && <Spinner label="Checking for an in-progress wipe…" />}

      {device && (
        <div className="rounded-lg border border-danger/30 bg-danger/8 px-4 py-3">
          <div className="flex items-start gap-2.5 text-sm text-danger">
            <ShieldAlert size={18} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">All data on this device will be permanently destroyed.</div>
              <div className="mt-1 text-danger/90">
                {device.model} · <DataValue>{device.capacity_human}</DataValue>
                {device.is_system_disk && " · this appears to be a SYSTEM disk"}
                {device.is_mounted && " · currently mounted (unmount before wiping)"}
              </div>
            </div>
          </div>
        </div>
      )}

      {resumeChecked && !sessionId && (
        <Card>
          <CardHeader title="Configure wipe" />
          <div className="space-y-5 p-5">
            <AlgorithmPicker
              category={category}
              setCategory={setCategory}
              algorithm={algorithm}
              setAlgorithm={setAlgorithm}
              passes={passes}
              setPasses={setPasses}
              configurable={configurable}
            />

            <div className="flex flex-wrap gap-5">
              <label className="flex items-center gap-2 text-sm text-fg">
                <input type="checkbox" checked={verify} onChange={(e) => setVerify(e.target.checked)} />
                Verify after wipe
              </label>
              <label className="flex items-center gap-2 text-sm text-fg">
                <input type="checkbox" checked={certificate} onChange={(e) => setCertificate(e.target.checked)} />
                Generate signed certificate
              </label>
            </div>

            {startError && <ErrorState message={startError} />}

            <div className="flex justify-end border-t border-border pt-4">
              <Button variant="danger" onClick={() => setConfirmOpen(true)}>
                <ShieldAlert size={16} />
                Wipe device…
              </Button>
            </div>
          </div>
        </Card>
      )}

      {sessionId && (
        <Card>
          <CardHeader
            title="Wipe in progress"
            action={
              progress ? (
                <Badge tone={succeeded ? "success" : progress.status === "failed" ? "danger" : "info"}>
                  {progress.status}
                </Badge>
              ) : undefined
            }
          />
          <div className="space-y-4 p-5">
            {!progress && <Spinner label="Starting…" />}
            {progress && (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-fg-muted">
                    Pass <DataValue className="text-fg">{progress.current_pass}</DataValue> /{" "}
                    <DataValue className="text-fg">{progress.total_passes}</DataValue> ·{" "}
                    {algorithmLabel(algorithm)}
                  </span>
                  <DataValue className="font-medium text-fg">{progress.progress_percent.toFixed(1)}%</DataValue>
                </div>
                <ProgressBar percent={progress.progress_percent} tone={progress.status === "failed" ? "danger" : "primary"} />
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <Stat label="Speed" value={`${progress.speed_mbps.toFixed(1)} MB/s`} />
                  <Stat label="Processed" value={formatBytes(progress.data_processed)} />
                  <Stat label="ETA" value={formatDuration(progress.estimated_remaining)} />
                </div>
                {!done && (
                  <div className="flex justify-end border-t border-border pt-4">
                    <Button variant="danger" size="sm" loading={cancelling} onClick={cancel}>
                      <Ban size={15} /> Cancel wipe
                    </Button>
                  </div>
                )}
              </>
            )}

            {done && (
              <div className="flex flex-col gap-3 border-t border-border pt-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {succeeded ? (
                    <>
                      <CheckCircle2 size={16} className="text-success" /> Wipe completed.
                    </>
                  ) : (
                    <>
                      <XCircle size={16} className="text-danger" /> Wipe {progress?.status}.
                    </>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {certificate && succeeded && !report && (
                    <a href={apiUrl(`/api/wipe/download/${sessionId}`)} target="_blank" rel="noreferrer">
                      <Button variant="secondary" size="sm">
                        <Download size={15} /> Download certificate
                      </Button>
                    </a>
                  )}
                  {succeeded && (
                    <Link href={`/hex/?path=${encodeURIComponent(path)}`}>
                      <Button variant="secondary" size="sm">
                        <Binary size={15} /> View sectors
                      </Button>
                    </Link>
                  )}
                  <Button variant="secondary" size="sm" onClick={newWipe}>
                    Start another wipe
                  </Button>
                  <Link href="/wipe/">
                    <Button variant="ghost" size="sm">
                      Back to devices
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {succeeded && report && (
        <>
          <Card>
            <CardHeader
              title="Wipe results"
              action={
                report.verification.enabled ? (
                  <Badge tone={report.verification.passed ? "success" : report.verification.passed === false ? "danger" : "neutral"}>
                    {report.verification.passed
                      ? "verification passed"
                      : report.verification.passed === false
                        ? "verification failed"
                        : "verification pending"}
                  </Badge>
                ) : (
                  <Badge tone="neutral">verification not run</Badge>
                )
              }
            />
            <div className="space-y-4 p-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatTile
                  label="Algorithm"
                  value={<span className="text-base">{algorithmLabel(report.wipe_details.algorithm)}</span>}
                  hint={`${report.wipe_details.total_passes} pass${report.wipe_details.total_passes === 1 ? "" : "es"}`}
                />
                <StatTile label="Duration" value={formatDuration(report.results.duration_seconds)} hint={`finished ${formatDate(report.results.completed_at)}`} />
                <StatTile label="Data wiped" value={formatBytes(report.results.data_processed_bytes)} hint={`avg ${report.results.average_speed_mbps.toFixed(1)} MB/s`} />
                <StatTile
                  label="Verification"
                  tone={report.verification.enabled ? (report.verification.passed ? "success" : "danger") : undefined}
                  value={
                    <span className="text-base">
                      {report.verification.enabled ? (report.verification.passed ? "Passed" : "Failed") : "Not run"}
                    </span>
                  }
                  hint="read-back sampling"
                />
              </div>
              <dl className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                <DetailRow label="Device" value={<DataValue>{report.device.path}</DataValue>} />
                <DetailRow label="Model" value={report.device.model || "—"} />
                <DetailRow label="Serial number" value={<DataValue>{report.device.serial || "—"}</DataValue>} />
                <DetailRow label="Capacity" value={<DataValue>{report.device.capacity}</DataValue>} />
                <DetailRow label="Interface / type" value={`${report.device.interface || "—"} · ${report.device.device_type || "—"}`} />
                <DetailRow label="Report ID" value={<DataValue>{report.report_id}</DataValue>} />
              </dl>
            </div>
          </Card>

          {report.certificate && (
            <Card>
              <CardHeader
                title="Certificate of destruction"
                action={report.blockchain ? <Badge tone="success">blockchain-anchored</Badge> : undefined}
              />
              <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start">
                {report.certificate.qr_png_path && (
                  <div className="flex shrink-0 flex-col items-center gap-2">
                    {/* eslint-disable-next-line @next/next/no-img-element -- static-export SPA, API-served image */}
                    <img
                      src={downloadUrl(report.certificate.qr_png_path)}
                      alt="Certificate verification QR code"
                      className="h-40 w-40 rounded-lg border border-border bg-white p-2"
                    />
                    <span className="text-xs text-fg-muted">Scan to verify</span>
                  </div>
                )}
                <div className="min-w-0 flex-1 space-y-4">
                  <p className="text-sm leading-relaxed text-fg-muted">
                    A digitally signed certificate was generated for this wipe. The QR code lets anyone
                    verify its authenticity{report.blockchain ? ", cross-checked against the Sepolia blockchain anchor" : ""}.
                  </p>
                  {report.blockchain?.tx_hash && (
                    <div className="rounded-lg border border-border bg-surface-2/50 px-4 py-3 text-sm">
                      <div className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Blockchain transaction</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <DataValue className="truncate text-fg">{report.blockchain.tx_hash}</DataValue>
                        {report.blockchain.explorer_url && (
                          <a
                            href={report.blockchain.explorer_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                          >
                            <ExternalLink size={13} /> Etherscan
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <a href={apiUrl(`/api/wipe/download/${sessionId}`)} target="_blank" rel="noreferrer">
                      <Button variant="secondary" size="sm">
                        <Download size={15} /> Certificate PDF
                      </Button>
                    </a>
                    {report.certificate.json_path && (
                      <a href={downloadUrl(report.certificate.json_path)} target="_blank" rel="noreferrer">
                        <Button variant="secondary" size="sm">
                          <FileCheck2 size={15} /> JSON report
                        </Button>
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Permanently wipe this device"
        confirmLabel="Wipe device"
        confirmWord={path}
        loading={starting}
        onConfirm={start}
        description={
          <>
            This will <strong>permanently destroy all data</strong> on{" "}
            <DataValue className="text-fg">{path}</DataValue> using {algorithmLabel(algorithm)}. This
            cannot be undone.
          </>
        }
      />
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 bg-surface px-4 py-2.5 text-sm">
      <dt className="shrink-0 text-fg-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-fg">{value}</dd>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-fg-subtle">{label}</div>
      <DataValue className="mt-0.5 block font-medium text-fg">{value}</DataValue>
    </div>
  );
}
