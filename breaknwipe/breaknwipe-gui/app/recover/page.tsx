"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Ban,
  File as FileIcon,
  FileSearch,
  FolderInput,
  Info,
  RotateCcw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  api,
  RECOVERY_JOB_TERMINAL,
  type Partition,
  type RecoverableFile,
  type RecoveryScanResult,
  type RecoveryRestoreResult,
  type RecoveryJobProgress,
} from "@/lib/api";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { useWebSocket } from "@/lib/use-websocket";
import { formatBytes, formatDuration } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataValue,
  EmptyState,
  ErrorState,
  PageTitle,
  ProgressBar,
  Spinner,
} from "@/components/ui";
import { DevicePicker } from "@/components/device-picker";
import { RecoveredFileViewer } from "@/components/recovered-file-viewer";

export default function RecoverPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <RecoverPageInner />
    </Suspense>
  );
}

function RecoverPageInner() {
  const path = useQueryParam("path");
  const partitions = useAsync(() => (path ? api.devicePartitions(path) : Promise.resolve([])), [path]);
  const availability = useAsync(() => api.recoveryAvailable(), []);

  if (!path) {
    return (
      <DevicePicker
        title="Recover"
        description="Find and restore deleted or quick-formatted files from a device — pick one to start."
        primaryLabel="Recover"
        primaryHref={(p) => `/recover/?path=${p}`}
        primaryVariant="secondary"
      />
    );
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
        <PageTitle
          title="Recover deleted files"
          description="Find and restore files that were deleted or quick-formatted but not yet overwritten."
        />
        <DataValue className="-mt-4 block text-sm text-fg-muted">{path}</DataValue>
      </div>

      <HonestyNote />

      {partitions.loading || availability.loading ? (
        <Spinner label="Loading partitions…" />
      ) : partitions.error ? (
        <ErrorState message={`Partitions: ${partitions.error}`} />
      ) : (partitions.data ?? []).length === 0 ? (
        <EmptyState
          title="No partitions found on this device"
          description="Recovery works on a partition (e.g. /dev/sdb1), not the whole disk. If the partition table itself is gone, use Deep scan on the whole device."
        />
      ) : (
        <RecoverTool
          partitions={partitions.data ?? []}
          undeleteAvailable={availability.data?.undelete ?? false}
          deepScanAvailable={availability.data?.deep_scan ?? false}
        />
      )}
    </div>
  );
}

function HonestyNote() {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-info/25 bg-info/8 px-4 py-3 text-sm text-fg-muted">
      <Info size={16} className="mt-0.5 shrink-0 text-info" />
      <div>
        Recovery only works while the data is still physically on the drive. Files deleted or
        quick-formatted are usually recoverable; a drive that was securely wiped with BreakNWipe
        has <strong className="text-fg">nothing to recover</strong> — that&apos;s the point of a wipe.
        For the best results, stop using the drive and scan it before writing anything new to it.
      </div>
    </div>
  );
}

type Mode = "undelete" | "deep";

function RecoverTool({
  partitions,
  undeleteAvailable,
  deepScanAvailable,
}: {
  partitions: Partition[];
  undeleteAvailable: boolean;
  deepScanAvailable: boolean;
}) {
  const [partition, setPartition] = useState(partitions[0]?.path ?? "");
  const [mode, setMode] = useState<Mode>(undeleteAvailable ? "undelete" : "deep");
  const [outputDir, setOutputDir] = useState("");
  const [scan, setScan] = useState<RecoveryScanResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<"scan" | "restore" | "starting" | null>(null);
  const [result, setResult] = useState<RecoveryRestoreResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deepJobId, setDeepJobId] = useState<string | null>(null);
  const [viewerPath, setViewerPath] = useState<string | null>(null);

  const { last: deepLast } = useWebSocket<{ type: string; data: RecoveryJobProgress }>(
    deepJobId ? `/ws/recovery/${deepJobId}` : null,
  );
  const deepJob = deepLast?.data ?? null;

  const selectedPartition = partitions.find((p) => p.path === partition);

  async function runScan() {
    setBusy("scan");
    setError(null);
    setScan(null);
    setResult(null);
    setSelected(new Set());
    try {
      const r = await api.recoveryScan({ partition });
      setScan(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function runRestore() {
    if (!outputDir.trim()) {
      setError("Choose a folder to recover files into — it must be on a different drive.");
      return;
    }
    setBusy("restore");
    setError(null);
    setResult(null);
    try {
      const r = await api.recoveryRestore({
        partition,
        output_dir: outputDir.trim(),
        inodes: Array.from(selected),
      });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function startDeepScan() {
    if (!outputDir.trim()) {
      setError("Choose a folder to recover files into — it must be on a different drive.");
      return;
    }
    setBusy("starting");
    setError(null);
    try {
      const { job_id } = await api.recoveryDeepScanStart({ partition, output_dir: outputDir.trim() });
      setDeepJobId(job_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function cancelDeepScan() {
    if (!deepJobId) return;
    try {
      await api.recoveryDeepScanCancel(deepJobId);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function newDeepScan() {
    setDeepJobId(null);
    setError(null);
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="What to scan" icon={<FileSearch size={16} />} />
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[220px] flex-1">
              <span className="mb-1.5 block text-xs text-fg-muted">Partition</span>
              <select
                value={partition}
                onChange={(e) => {
                  setPartition(e.target.value);
                  setScan(null);
                  setResult(null);
                  setSelected(new Set());
                  setDeepJobId(null);
                }}
                className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              >
                {partitions.map((p) => (
                  <option key={p.path} value={p.path}>
                    {p.path}
                    {p.fstype ? ` (${p.fstype})` : ""}
                    {p.size_human ? ` — ${p.size_human}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {selectedPartition?.is_mounted && (
            <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/8 px-3 py-2 text-sm text-warning">
              <ShieldAlert size={15} className="mt-0.5 shrink-0" />
              This partition is mounted. Scanning is read-only and safe, but for the best recovery
              chance, unmount it and avoid writing to it.
            </div>
          )}

          <ModeToggle
            mode={mode}
            setMode={setMode}
            undeleteAvailable={undeleteAvailable}
            deepScanAvailable={deepScanAvailable}
          />

          {mode === "undelete" ? (
            <Button onClick={runScan} loading={busy === "scan"} disabled={!undeleteAvailable}>
              <FileSearch size={15} /> Scan for deleted files
            </Button>
          ) : (
            <p className="text-sm text-fg-muted">
              Deep scan reads the whole partition and rebuilds files by their content signatures. It
              finds files even when the filesystem is damaged or the names are gone, but it can&apos;t
              recover original filenames. Set an output folder below and start it.
            </p>
          )}
        </div>
      </Card>

      {mode === "undelete" && scan && <ScanResults scan={scan} selected={selected} setSelected={setSelected} />}

      {mode === "undelete" && scan && scan.files.length > 0 && !deepJobId && (
        <Card>
          <CardHeader title="Recover to" icon={<FolderInput size={16} />} />
          <div className="space-y-4 p-5">
            <label className="block">
              <span className="mb-1.5 block text-xs text-fg-muted">
                Output folder (must be on a different drive than the one you&apos;re recovering from)
              </span>
              <input
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="/home/you/recovered"
                className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              />
            </label>

            <Button onClick={runRestore} loading={busy === "restore"} disabled={selected.size === 0}>
              <RotateCcw size={15} /> Recover {selected.size > 0 ? `${selected.size} selected` : "selected"}
            </Button>
          </div>
        </Card>
      )}

      {mode === "deep" && !deepJobId && (
        <Card>
          <CardHeader title="Recover to" icon={<FolderInput size={16} />} />
          <div className="space-y-4 p-5">
            <p className="text-sm text-fg-muted">
              Deep scan reads the whole partition and rebuilds files by their content signatures. It
              finds files even when the filesystem is damaged or the names are gone, but it can&apos;t
              recover original filenames.
            </p>
            <label className="block">
              <span className="mb-1.5 block text-xs text-fg-muted">
                Output folder (must be on a different drive than the one you&apos;re recovering from)
              </span>
              <input
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="/home/you/recovered"
                className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              />
            </label>

            <Button onClick={startDeepScan} loading={busy === "starting"} disabled={!deepScanAvailable}>
              <Sparkles size={15} /> Start deep scan &amp; recover
            </Button>
          </div>
        </Card>
      )}

      {mode === "deep" && deepJobId && (
        <DeepScanProgress
          job={deepJob}
          onCancel={cancelDeepScan}
          onNewScan={newDeepScan}
          onView={setViewerPath}
        />
      )}

      {error && <ErrorState message={error} />}
      {result && <RestoreResultView result={result} onView={setViewerPath} />}

      <RecoveredFileViewer path={viewerPath} onOpenChange={(open) => !open && setViewerPath(null)} />
    </div>
  );
}

function RecoveredFileList({ files, onView }: { files: string[]; onView: (path: string) => void }) {
  return (
    <div className="max-h-64 overflow-auto rounded-lg border border-border bg-surface-2/50">
      {files.map((f, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onView(f)}
          className="flex w-full items-center gap-2 border-b border-border/60 px-3 py-2 text-left text-xs last:border-b-0 hover:bg-surface-3"
        >
          <FileIcon size={13} className="shrink-0 text-fg-subtle" />
          <span className="data truncate text-fg-muted">{f}</span>
        </button>
      ))}
    </div>
  );
}

function DeepScanProgress({
  job,
  onCancel,
  onNewScan,
  onView,
}: {
  job: RecoveryJobProgress | null;
  onCancel: () => void;
  onNewScan: () => void;
  onView: (path: string) => void;
}) {
  const succeeded = job?.status === "completed" && job.recovered > 0;
  const done = job ? RECOVERY_JOB_TERMINAL.includes(job.status) : false;

  return (
    <Card>
      <CardHeader
        title="Deep scan"
        icon={<Sparkles size={16} />}
        action={
          job ? (
            <Badge tone={succeeded ? "success" : job.status === "failed" ? "danger" : job.status === "cancelled" ? "warning" : "info"}>
              {job.status}
            </Badge>
          ) : undefined
        }
      />
      <div className="space-y-4 p-5">
        {!job && <Spinner label="Starting deep scan…" />}

        {job && (
          <>
            <div className="flex items-center justify-between text-sm">
              <span className="text-fg-muted">
                <DataValue className="text-fg">{formatBytes(job.bytes_processed)}</DataValue> /{" "}
                <DataValue className="text-fg">{formatBytes(job.total_bytes)}</DataValue> scanned
              </span>
              {job.percent != null && <DataValue className="font-medium text-fg">{job.percent.toFixed(1)}%</DataValue>}
            </div>
            <ProgressBar percent={job.percent ?? 0} tone={job.status === "failed" ? "danger" : "primary"} />
            <div className="grid grid-cols-3 gap-3 text-sm">
              <Stat label="Rate" value={`${formatBytes(job.rate_bytes_per_sec)}/s`} />
              <Stat label="Found so far" value={String(job.recovered)} />
              <Stat label="ETA" value={formatDuration(job.eta_seconds)} />
            </div>

            {!done && (
              <div className="flex justify-end border-t border-border pt-4">
                <Button variant="danger" size="sm" onClick={onCancel}>
                  <Ban size={15} /> Cancel deep scan
                </Button>
              </div>
            )}

            {done && (
              <div className="space-y-3 border-t border-border pt-4 text-sm">
                {job.error && <div className="text-danger">{job.error}</div>}
                {succeeded && (
                  <p className="text-fg-muted">
                    Recovered {job.recovered} file{job.recovered === 1 ? "" : "s"} to{" "}
                    <DataValue className="text-fg">{job.output_dir}</DataValue>. Open that folder to check
                    them.
                  </p>
                )}
                {job.recovered_files.length > 0 && (
                  <RecoveredFileList files={job.recovered_files} onView={onView} />
                )}
                <div className="flex justify-end">
                  <Button variant="secondary" size="sm" onClick={onNewScan}>
                    Start another scan
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
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

function ModeToggle({
  mode,
  setMode,
  undeleteAvailable,
  deepScanAvailable,
}: {
  mode: Mode;
  setMode: (m: Mode) => void;
  undeleteAvailable: boolean;
  deepScanAvailable: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <ModeCard
        active={mode === "undelete"}
        disabled={!undeleteAvailable}
        onClick={() => setMode("undelete")}
        title="Quick scan (by name)"
        desc="Lists deleted files with their names and sizes. Best for NTFS / FAT / exFAT drives and USB sticks."
        unavailableHint="Needs The Sleuth Kit (install the 'sleuthkit' package)."
      />
      <ModeCard
        active={mode === "deep"}
        disabled={!deepScanAvailable}
        onClick={() => setMode("deep")}
        title="Deep scan (by content)"
        desc="Carves files out of the raw disk by type. Recovers more, including from ext4 and damaged drives, but without original names."
        unavailableHint="Needs PhotoRec (install the 'testdisk' package)."
      />
    </div>
  );
}

function ModeCard({
  active,
  disabled,
  onClick,
  title,
  desc,
  unavailableHint,
}: {
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  title: string;
  desc: string;
  unavailableHint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex-1 rounded-lg border-2 p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        active ? "border-primary bg-primary/8 shadow-[0_0_0_3px_var(--ring)]" : "border-border bg-surface-2 hover:border-border-strong hover:bg-surface-3"
      }`}
    >
      <div className="text-sm font-medium text-fg">{title}</div>
      <div className="mt-1 text-xs text-fg-muted">{desc}</div>
      {disabled && <div className="mt-1.5 text-xs text-warning">{unavailableHint}</div>}
    </button>
  );
}

function ScanResults({
  scan,
  selected,
  setSelected,
}: {
  scan: RecoveryScanResult;
  selected: Set<string>;
  setSelected: (s: Set<string>) => void;
}) {
  const files = scan.files;
  const allSelected = files.length > 0 && files.every((f) => selected.has(f.inode));

  function toggle(inode: string) {
    const next = new Set(selected);
    if (next.has(inode)) next.delete(inode);
    else next.add(inode);
    setSelected(next);
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(files.map((f) => f.inode)));
  }

  if (scan.refused) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/8 p-4 text-sm text-warning">
        <div className="mb-1 font-medium">Can&apos;t scan this partition</div>
        {scan.refusal_reason}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader
        title={`Deleted files ${files.length > 0 ? `(${files.length})` : ""}`}
        action={
          files.length > 0 ? (
            <button onClick={toggleAll} className="text-xs text-primary hover:underline">
              {allSelected ? "Clear all" : "Select all"}
            </button>
          ) : undefined
        }
      />
      {scan.note && (
        <div className="flex items-start gap-2 border-b border-border px-5 py-3 text-sm text-fg-muted">
          <Info size={14} className="mt-0.5 shrink-0 text-info" />
          {scan.note}
        </div>
      )}
      {scan.error ? (
        <div className="p-5 text-sm text-danger">{scan.error}</div>
      ) : files.length === 0 ? (
        <div className="p-5 text-sm text-fg-muted">
          No named deleted files were found. Try a Deep scan — it recovers file contents by type,
          which is the only option on ext4 and heavily-used drives.
        </div>
      ) : (
        <FileTable files={files} selected={selected} toggle={toggle} />
      )}
    </Card>
  );
}

function FileTable({
  files,
  selected,
  toggle,
}: {
  files: RecoverableFile[];
  selected: Set<string>;
  toggle: (inode: string) => void;
}) {
  const sorted = useMemo(() => [...files].sort((a, b) => a.path.localeCompare(b.path)), [files]);
  return (
    <div className="max-h-[520px] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface text-left text-xs text-fg-subtle">
          <tr className="border-b border-border">
            <th className="w-10 px-5 py-2"></th>
            <th className="px-2 py-2 font-medium">Name</th>
            <th className="px-2 py-2 font-medium">Size</th>
            <th className="hidden px-2 py-2 font-medium sm:table-cell">Path</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((f) => (
            <tr
              key={f.inode}
              className="cursor-pointer border-b border-border/60 hover:bg-surface-2"
              onClick={() => toggle(f.inode)}
            >
              <td className="px-5 py-2">
                <input
                  type="checkbox"
                  checked={selected.has(f.inode)}
                  onChange={() => toggle(f.inode)}
                  onClick={(e) => e.stopPropagation()}
                />
              </td>
              <td className="px-2 py-2">
                <span className="font-medium text-fg">{f.name}</span>
              </td>
              <td className="px-2 py-2 text-fg-muted">
                <DataValue>{formatBytes(f.size)}</DataValue>
              </td>
              <td className="hidden px-2 py-2 text-fg-subtle sm:table-cell">
                <DataValue className="text-xs">{f.path}</DataValue>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RestoreResultView({
  result,
  onView,
}: {
  result: RecoveryRestoreResult;
  onView: (path: string) => void;
}) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/8 p-4 text-sm text-warning">
        <div className="mb-1 font-medium">Recovery refused</div>
        {result.refusal_reason}
      </div>
    );
  }

  const ok = result.recovered > 0;
  return (
    <Card>
      <CardHeader
        title="Recovery result"
        action={
          <Badge tone={ok ? "success" : "warning"}>
            {result.recovered} recovered{result.requested ? ` / ${result.requested} requested` : ""}
          </Badge>
        }
      />
      <div className="space-y-3 p-5 text-sm">
        {result.error && <div className="text-danger">{result.error}</div>}
        {ok && (
          <p className="text-fg-muted">
            Recovered {result.recovered} file{result.recovered === 1 ? "" : "s"} to{" "}
            <DataValue className="text-fg">{result.output_dir}</DataValue>. Open that folder to check
            them.
          </p>
        )}
        {result.recovered_files.length > 0 && (
          <RecoveredFileList files={result.recovered_files} onView={onView} />
        )}
      </div>
    </Card>
  );
}
