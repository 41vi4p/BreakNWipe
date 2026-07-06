"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert, Download, CheckCircle2, XCircle, Ban, Binary } from "lucide-react";
import { api, apiUrl, WIPE_TERMINAL, type DeviceInfo, type WipeProgressState } from "@/lib/api";
import { ALGORITHMS, algorithmLabel } from "@/lib/algorithms";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { useWebSocket } from "@/lib/use-websocket";
import { formatBytes, formatDuration } from "@/lib/format";
import { Button, Card, CardHeader, DataValue, ErrorState, PageTitle, ProgressBar, Spinner, Badge } from "@/components/ui";
import { ConfirmDialog } from "@/components/dialog";

type WipeProgress = WipeProgressState;

export default function WipePage() {
  const path = useQueryParam("path");
  const { data: devices, loading } = useAsync(() => api.devices(), []);
  const device = devices?.find((d) => d.path === path) as DeviceInfo | undefined;

  const [algorithm, setAlgorithm] = useState("nist-clear");
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
          setAlgorithm(resume.wipe_request?.algorithm ?? "nist-clear");
        }
      })
      .catch(() => {})
      .finally(() => alive && setResumeChecked(true));
    return () => {
      alive = false;
    };
  }, [path]);

  if (!path) return <ErrorState message="No device path given. Open a device from Devices first." />;

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
  }

  const done = progress && WIPE_TERMINAL.includes(progress.status);
  const succeeded = progress?.status === "completed";

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
            <div>
              <label className="mb-1.5 block text-sm font-medium text-fg">Algorithm</label>
              <select
                value={algorithm}
                onChange={(e) => setAlgorithm(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              >
                {["Standard", "REA (crypto-erase)"].map((group) => (
                  <optgroup key={group} label={group}>
                    {ALGORITHMS.filter((a) => a.group === group).map((a) => (
                      <option key={a.value} value={a.value}>
                        {a.label} — {a.passes}
                        {a.note ? ` (${a.note})` : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {configurable && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-fg">Passes</label>
                <input
                  type="number"
                  min={1}
                  max={35}
                  value={passes}
                  onChange={(e) => setPasses(Math.max(1, Math.min(35, Number(e.target.value) || 1)))}
                  className="data w-28 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                />
              </div>
            )}

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
                  {certificate && succeeded && (
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
                  <Link href="/">
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-fg-subtle">{label}</div>
      <DataValue className="mt-0.5 block font-medium text-fg">{value}</DataValue>
    </div>
  );
}
