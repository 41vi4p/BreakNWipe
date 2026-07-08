"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  ChevronRight,
  File as FileIcon,
  Folder,
  Search,
  ShieldAlert,
  X,
  XCircle,
} from "lucide-react";
import {
  api,
  SHRED_JOB_TERMINAL,
  type Partition,
  type DirEntry,
  type DirListing,
  type ShredReliability,
  type ShredJobProgress,
} from "@/lib/api";
import { useAsync, useQueryParam } from "@/lib/hooks";
import { useWebSocket } from "@/lib/use-websocket";
import { formatBytes, formatDate } from "@/lib/format";
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
import { ConfirmDialog } from "@/components/dialog";
import { DevicePicker } from "@/components/device-picker";
import { AlgorithmPicker } from "@/components/algorithm-picker";
import { ALGORITHMS, algorithmLabel, type AlgorithmGroup } from "@/lib/algorithms";

export default function ShredPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <ShredPageInner />
    </Suspense>
  );
}

function ShredPageInner() {
  const path = useQueryParam("path");
  const partitions = useAsync(() => (path ? api.devicePartitions(path) : Promise.resolve([])), [path]);

  if (!path) {
    return (
      <DevicePicker
        title="Shred"
        description="Securely overwrite and delete specific files from a device, leaving the rest untouched."
        primaryLabel="Browse files"
        primaryHref={(p) => `/shred/?path=${p}`}
        primaryVariant="danger"
      />
    );
  }

  const mounted = (partitions.data ?? []).filter((p) => p.is_mounted);

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
          title="File shredder"
          description="Browse this device's files, select what to destroy, and choose an overwrite algorithm — only the selected files are touched."
        />
        <DataValue className="-mt-4 block text-sm text-fg-muted">{path}</DataValue>
      </div>

      {partitions.loading ? (
        <Spinner label="Loading partitions…" />
      ) : partitions.error ? (
        <ErrorState message={partitions.error} />
      ) : mounted.length === 0 ? (
        <EmptyState
          title="No mounted partitions found"
          description="The file shredder needs a mounted filesystem to browse — mount a partition on this device first."
        />
      ) : (
        <ShredTool partitions={mounted} />
      )}
    </div>
  );
}

function relPath(absPath: string, mountPoint: string): string {
  if (absPath === mountPoint) return "";
  return absPath.startsWith(mountPoint + "/") ? absPath.slice(mountPoint.length + 1) : absPath;
}

function ShredTool({ partitions }: { partitions: Partition[] }) {
  const [partition, setPartition] = useState(partitions[0]?.path ?? "");
  const [cwd, setCwd] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [category, setCategory] = useState<AlgorithmGroup | null>(null);
  const [algorithm, setAlgorithm] = useState("nist-clear");
  const [passes, setPasses] = useState(3);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const reliability = useAsync<ShredReliability | null>(
    () => (partition ? api.shredReliability(partition) : Promise.resolve(null)),
    [partition],
  );
  const listing = useAsync<DirListing | null>(
    () => (partition ? api.shredBrowse(partition, cwd) : Promise.resolve(null)),
    [partition, cwd],
  );

  const { last } = useWebSocket<{ type: string; data: ShredJobProgress }>(jobId ? `/ws/shred/${jobId}` : null);
  const job = last?.data ?? null;
  const done = job ? SHRED_JOB_TERMINAL.includes(job.status) : false;
  const configurable = ALGORITHMS.find((a) => a.value === algorithm)?.configurablePasses;

  const entries = useMemo(() => listing.data?.entries ?? [], [listing.data]);
  const filtered = useMemo(
    () => entries.filter((e) => e.name.toLowerCase().includes(search.trim().toLowerCase())),
    [entries, search],
  );
  const fileEntries = filtered.filter((e) => !e.is_dir);
  const allSelected = fileEntries.length > 0 && fileEntries.every((e) => selected.has(e.path));

  function toggle(filePath: string) {
    const next = new Set(selected);
    if (next.has(filePath)) next.delete(filePath);
    else next.add(filePath);
    setSelected(next);
  }

  function toggleAll() {
    const next = new Set(selected);
    if (allSelected) {
      fileEntries.forEach((e) => next.delete(e.path));
    } else {
      fileEntries.forEach((e) => next.add(e.path));
    }
    setSelected(next);
  }

  function navigate(entry: DirEntry) {
    if (!entry.is_dir || !listing.data) return;
    setCwd(relPath(entry.path, listing.data.mount_point));
  }

  function navigateUp() {
    if (!listing.data?.parent) return;
    setCwd(relPath(listing.data.parent, listing.data.mount_point));
  }

  function changePartition(next: string) {
    setPartition(next);
    setCwd("");
    setSearch("");
    setSelected(new Set());
    setJobId(null);
  }

  const selectedTotalBytes = useMemo(() => {
    let total = 0;
    for (const e of entries) if (selected.has(e.path)) total += e.size_bytes;
    return total;
  }, [entries, selected]);

  async function start() {
    setStarting(true);
    setStartError(null);
    try {
      const res = await api.shredStart({
        partition,
        paths: Array.from(selected),
        algorithm,
        passes: configurable ? passes : null,
      });
      setJobId(res.job_id);
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setStarting(false);
      setConfirmOpen(false);
    }
  }

  async function cancel() {
    if (!jobId) return;
    setCancelling(true);
    try {
      await api.shredCancel(jobId);
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setCancelling(false);
    }
  }

  function reset() {
    setJobId(null);
    setSelected(new Set());
    setStartError(null);
  }

  const breadcrumbSegments = cwd ? cwd.split("/").filter(Boolean) : [];

  if (jobId) {
    return (
      <ShredProgress
        job={job}
        done={done}
        cancelling={cancelling}
        onCancel={cancel}
        onReset={reset}
      />
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Choose a partition" />
        <div className="space-y-4 p-5">
          <label className="block">
            <span className="mb-1.5 block text-xs text-fg-muted">Partition</span>
            <select
              value={partition}
              onChange={(e) => changePartition(e.target.value)}
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

          {reliability.data && !reliability.data.reliable && (
            <div className="rounded-lg border border-warning/30 bg-warning/8 px-4 py-3 text-sm text-warning">
              <div className="mb-1 flex items-center gap-1.5 font-medium">
                <ShieldAlert size={15} /> This shred may not fully destroy the data
              </div>
              <ul className="ml-5 list-disc space-y-1">
                {reliability.data.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Browse files"
          action={
            fileEntries.length > 0 ? (
              <button onClick={toggleAll} className="text-xs text-primary hover:underline">
                {allSelected ? "Clear all" : "Select all"}
              </button>
            ) : undefined
          }
        />
        <div className="space-y-3 p-5">
          <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <button type="button" onClick={() => setCwd("")} className="hover:text-fg hover:underline">
              Home
            </button>
            {breadcrumbSegments.map((seg, i) => (
              <span key={i} className="flex items-center gap-2">
                <ChevronRight size={13} className="text-fg-subtle" />
                <button
                  type="button"
                  onClick={() => setCwd(breadcrumbSegments.slice(0, i + 1).join("/"))}
                  className="hover:text-fg hover:underline"
                >
                  {seg}
                </button>
              </span>
            ))}
          </div>

          <label className="relative block">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search this folder…"
              className="data w-full rounded-lg border border-border bg-surface-2 py-2 pl-9 pr-3 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            />
          </label>

          {listing.loading && <Spinner label="Loading…" />}
          {listing.error && <ErrorState message={listing.error} />}
          {!listing.loading && !listing.error && filtered.length === 0 && (
            <div className="p-2 text-sm text-fg-muted">This folder is empty{search ? " (or nothing matches your search)" : ""}.</div>
          )}
          {!listing.loading && !listing.error && filtered.length > 0 && (
            <div className="max-h-[420px] overflow-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface text-left text-xs text-fg-subtle">
                  <tr className="border-b border-border">
                    <th className="w-10 px-4 py-2"></th>
                    <th className="px-2 py-2 font-medium">Name</th>
                    <th className="px-2 py-2 font-medium">Size</th>
                    <th className="hidden px-2 py-2 font-medium sm:table-cell">Modified</th>
                  </tr>
                </thead>
                <tbody>
                  {listing.data?.parent !== null && listing.data?.parent !== undefined && (
                    <tr className="cursor-pointer border-b border-border/60 hover:bg-surface-2" onClick={navigateUp}>
                      <td className="px-4 py-2" />
                      <td className="px-2 py-2 text-fg-muted" colSpan={3}>
                        <span className="inline-flex items-center gap-2">
                          <Folder size={14} /> ..
                        </span>
                      </td>
                    </tr>
                  )}
                  {filtered.map((e) => (
                    <tr
                      key={e.path}
                      className={`border-b border-border/60 hover:bg-surface-2 ${e.is_dir ? "cursor-pointer" : ""}`}
                      onClick={() => (e.is_dir ? navigate(e) : toggle(e.path))}
                    >
                      <td className="px-4 py-2">
                        {!e.is_dir && (
                          <input
                            type="checkbox"
                            checked={selected.has(e.path)}
                            onChange={() => toggle(e.path)}
                            onClick={(ev) => ev.stopPropagation()}
                          />
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <span className="inline-flex items-center gap-2 font-medium text-fg">
                          {e.is_dir ? <Folder size={14} className="text-fg-subtle" /> : <FileIcon size={14} className="text-fg-subtle" />}
                          {e.name}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-fg-muted">
                        <DataValue>{e.is_dir ? "—" : formatBytes(e.size_bytes)}</DataValue>
                      </td>
                      <td className="hidden px-2 py-2 text-fg-subtle sm:table-cell">
                        {e.mtime ? formatDate(e.mtime) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {selected.size > 0 && (
        <Card>
          <CardHeader
            title={`Selected (${selected.size})`}
            action={
              <button onClick={() => setSelected(new Set())} className="text-xs text-fg-muted hover:text-fg hover:underline">
                Clear selection
              </button>
            }
          />
          <div className="max-h-40 space-y-1 overflow-auto p-4">
            {Array.from(selected).map((p) => (
              <div key={p} className="flex items-center justify-between gap-2 text-xs">
                <DataValue className="truncate text-fg-muted">{p}</DataValue>
                <button
                  onClick={() => {
                    const next = new Set(selected);
                    next.delete(p);
                    setSelected(next);
                  }}
                  className="shrink-0 text-fg-subtle hover:text-danger"
                >
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Overwrite algorithm" />
        <div className="p-5">
          <AlgorithmPicker
            category={category}
            setCategory={setCategory}
            algorithm={algorithm}
            setAlgorithm={setAlgorithm}
            passes={passes}
            setPasses={setPasses}
            configurable={configurable}
          />
        </div>
      </Card>

      {startError && <ErrorState message={startError} />}

      <div className="flex justify-end">
        <Button variant="danger" disabled={selected.size === 0} onClick={() => setConfirmOpen(true)}>
          <ShieldAlert size={16} />
          Shred {selected.size > 0 ? `${selected.size} file${selected.size === 1 ? "" : "s"}` : "files"}…
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Permanently shred these files"
        confirmLabel="Shred files"
        confirmWord="shred"
        loading={starting}
        onConfirm={start}
        description={
          <>
            This will <strong>permanently destroy</strong> {selected.size} file
            {selected.size === 1 ? "" : "s"} ({formatBytes(selectedTotalBytes)}) using{" "}
            {algorithmLabel(algorithm)}. The rest of the drive is untouched. This cannot be undone.
            {reliability.data && !reliability.data.reliable && (
              <div className="mt-2 text-warning">
                {reliability.data.warnings.join(" ")}
              </div>
            )}
          </>
        }
      />
    </div>
  );
}

function ShredProgress({
  job,
  done,
  cancelling,
  onCancel,
  onReset,
}: {
  job: ShredJobProgress | null;
  done: boolean;
  cancelling: boolean;
  onCancel: () => void;
  onReset: () => void;
}) {
  const succeeded = job?.status === "completed";

  return (
    <Card>
      <CardHeader
        title="Shredding files"
        action={
          job ? (
            <Badge tone={succeeded ? "success" : job.status === "failed" ? "danger" : job.status === "cancelled" ? "warning" : "info"}>
              {job.status}
            </Badge>
          ) : undefined
        }
      />
      <div className="space-y-4 p-5">
        {!job && <Spinner label="Starting…" />}
        {job && (
          <>
            <div className="flex items-center justify-between text-sm">
              <span className="truncate text-fg-muted">
                File <DataValue className="text-fg">{job.files_done}</DataValue> /{" "}
                <DataValue className="text-fg">{job.total_files}</DataValue>
                {job.current_file && !done && (
                  <>
                    {" "}
                    · <DataValue className="text-fg">{job.current_file.split("/").pop()}</DataValue> (pass{" "}
                    {job.current_pass}/{job.total_passes})
                  </>
                )}
              </span>
              {job.percent != null && <DataValue className="font-medium text-fg">{job.percent.toFixed(1)}%</DataValue>}
            </div>
            <ProgressBar percent={job.percent ?? 0} tone={job.status === "failed" ? "danger" : "primary"} />

            {!done && (
              <div className="flex justify-end border-t border-border pt-4">
                <Button variant="danger" size="sm" loading={cancelling} onClick={onCancel}>
                  <Ban size={15} /> Cancel
                </Button>
              </div>
            )}

            {done && job.result && (
              <div className="space-y-3 border-t border-border pt-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {job.result.shredded > 0 && job.result.failed === 0 ? (
                    <>
                      <CheckCircle2 size={16} className="text-success" /> Shredded {job.result.shredded}/{job.result.requested} file(s).
                    </>
                  ) : (
                    <>
                      <XCircle size={16} className="text-danger" /> {job.result.shredded}/{job.result.requested} shredded
                      {job.result.failed ? `, ${job.result.failed} failed` : ""}.
                    </>
                  )}
                </div>
                {job.result.refused && <div className="text-sm text-danger">{job.result.refusal_reason}</div>}
                <div className="max-h-72 space-y-1 overflow-auto rounded-lg border border-border bg-surface-2/50 p-2">
                  {job.result.files.map((f, i) => (
                    <div key={i} className="border-b border-border/40 px-2 py-1.5 text-xs last:border-b-0">
                      <div className="flex items-center gap-1.5">
                        {f.success ? (
                          <CheckCircle2 size={12} className="shrink-0 text-success" />
                        ) : (
                          <XCircle size={12} className="shrink-0 text-danger" />
                        )}
                        <DataValue className="truncate text-fg-muted">{f.path}</DataValue>
                      </div>
                      {f.error && <div className="ml-[18px] text-danger">{f.error}</div>}
                      {f.warnings.map((w, wi) => (
                        <div key={wi} className="ml-[18px] text-warning">
                          {w}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" size="sm" onClick={onReset}>
                    Shred more files
                  </Button>
                  <Link href="/shred/">
                    <Button variant="ghost" size="sm">
                      Back to devices
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
