"use client";

import { useState } from "react";
import { HardDrive, Maximize2, Minimize2, MoveHorizontal, ShieldAlert, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { api, type DiskLayout, type DiskPartitionGeom, type ResizePlan, type ResizeResult } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { Badge, Button, Card, CardHeader, DataValue, ErrorState } from "./ui";
import { Dialog } from "./dialog";

type Mode = "grow" | "shrink" | "move";

// Colors cycle across partitions so adjacent ones are distinguishable.
const PART_COLORS = ["bg-primary/70", "bg-info/70", "bg-warning/70", "bg-fg-subtle/60"];

export function PartitionMap({ layout, onChanged }: { layout: DiskLayout; onChanged: () => void }) {
  const [dialog, setDialog] = useState<{ mode: Mode; partition: DiskPartitionGeom } | null>(null);

  if (layout.error) return <ErrorState message={layout.error} />;

  const total = layout.total_bytes || 1;
  // Build an ordered list of blocks (partitions + free segments) by start sector.
  const blocks = [
    ...layout.partitions.map((p) => ({ kind: "part" as const, start: p.start_sector, bytes: p.size_bytes, part: p })),
    ...layout.free_segments.map((f) => ({ kind: "free" as const, start: f.start_sector, bytes: f.size_bytes, part: null })),
  ]
    .filter((b) => b.bytes > total * 0.001) // hide sub-0.1% slivers from the bar
    .sort((a, b) => a.start - b.start);

  let colorIdx = 0;

  return (
    <Card>
      <CardHeader
        title="Partitions & free space"
        icon={<HardDrive size={16} />}
        action={
          <span className="text-xs text-fg-subtle">
            {layout.table_type?.toUpperCase() ?? "—"} · <DataValue>{formatBytes(layout.total_bytes)}</DataValue>
          </span>
        }
      />

      <div className="p-5">
        {/* Proportional map */}
        <div className="flex h-12 w-full overflow-hidden rounded-lg border border-border">
          {blocks.map((b, i) => {
            const width = `${Math.max(2, (b.bytes / total) * 100)}%`;
            if (b.kind === "free") {
              return (
                <div
                  key={`free-${i}`}
                  style={{ width }}
                  className="flex items-center justify-center border-r border-border bg-[repeating-linear-gradient(45deg,transparent,transparent_5px,var(--surface-3)_5px,var(--surface-3)_10px)] text-[10px] text-fg-subtle last:border-r-0"
                  title={`Free: ${formatBytes(b.bytes)}`}
                >
                  {b.bytes > total * 0.06 ? "free" : ""}
                </div>
              );
            }
            const color = PART_COLORS[colorIdx++ % PART_COLORS.length];
            return (
              <div
                key={b.part!.node}
                style={{ width }}
                className={`flex items-center justify-center border-r border-border ${color} text-[10px] font-medium text-fg last:border-r-0`}
                title={`${b.part!.node} · ${formatBytes(b.bytes)}`}
              >
                {b.bytes > total * 0.06 ? b.part!.number : ""}
              </div>
            );
          })}
        </div>

        {/* Partition list with per-partition actions */}
        <div className="mt-4 divide-y divide-border">
          {layout.partitions.map((p, i) => (
            <div key={p.node} className="flex flex-wrap items-center gap-3 py-3">
              <span className={`h-3 w-3 shrink-0 rounded-sm ${PART_COLORS[i % PART_COLORS.length]}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <DataValue className="text-fg">{p.node}</DataValue>
                  {p.fstype && <Badge tone="neutral">{p.fstype}</Badge>}
                  {p.is_system && (
                    <Badge tone="warning">
                      <ShieldAlert size={11} /> system
                    </Badge>
                  )}
                  {p.is_mounted && <Badge tone="info">mounted</Badge>}
                </div>
                <div className="mt-0.5 text-xs text-fg-muted">
                  <DataValue>{formatBytes(p.size_bytes)}</DataValue>
                  {p.free_after_bytes > layout.sector_size && (
                    <> · <span className="text-success">{formatBytes(p.free_after_bytes)} free after</span></>
                  )}
                </div>
              </div>
              <div className="flex gap-1.5">
                {p.free_after_bytes > layout.sector_size && (
                  <Button variant="secondary" size="sm" onClick={() => setDialog({ mode: "grow", partition: p })}>
                    <Maximize2 size={14} /> Extend
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: "shrink", partition: p })}>
                  <Minimize2 size={14} /> Shrink
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: "move", partition: p })}>
                  <MoveHorizontal size={14} /> Move
                </Button>
              </div>
            </div>
          ))}
        </div>

        {layout.has_lvm && (
          <div className="mt-3 rounded-lg border border-info/30 bg-info/8 px-4 py-2.5 text-sm text-info">
            This disk uses LVM. After growing a physical-volume partition, extend the logical volume to use the space.
          </div>
        )}
      </div>

      {dialog && (
        <ResizeDialog
          mode={dialog.mode}
          partition={dialog.partition}
          layout={layout}
          onClose={() => setDialog(null)}
          onChanged={onChanged}
        />
      )}
    </Card>
  );
}

function ResizeDialog({
  mode,
  partition,
  layout,
  onClose,
  onChanged,
}: {
  mode: Mode;
  partition: DiskPartitionGeom;
  layout: DiskLayout;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [targetGb, setTargetGb] = useState<number>(Math.max(1, Math.floor(partition.size_bytes / 1e9)));
  const [newStartMib, setNewStartMib] = useState<number>(Math.floor((partition.start_sector * layout.sector_size) / 1048576));
  const [plan, setPlan] = useState<ResizePlan | null>(null);
  const [result, setResult] = useState<ResizeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState("");

  const title = { grow: "Extend partition", shrink: "Shrink partition", move: "Move partition (experimental)" }[mode];

  async function preview() {
    setBusy(true);
    setResult(null);
    try {
      const req = {
        partition: partition.node,
        mode,
        target_bytes: mode === "shrink" ? Math.round(targetGb * 1e9) : null,
        new_start_sector: mode === "move" ? Math.round((newStartMib * 1048576) / layout.sector_size) : null,
        force: true, // preview always allowed; apply re-gates
      };
      setPlan(await api.partitionResizePlan(req));
    } catch (e) {
      setPlan(null);
      setResult({
        partition: partition.node, mode, success: false, changes_made: false,
        commands_run: [], output: "", error: (e as Error).message, refused: false, refusal_reason: null,
      });
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setBusy(true);
    try {
      const req = {
        partition: partition.node,
        mode,
        target_bytes: mode === "shrink" ? Math.round(targetGb * 1e9) : null,
        new_start_sector: mode === "move" ? Math.round((newStartMib * 1048576) / layout.sector_size) : null,
        force: true,
      };
      const r = await api.partitionResizeApply(req);
      setResult(r);
      if (r.success) onChanged();
    } catch (e) {
      setResult({
        partition: partition.node, mode, success: false, changes_made: false,
        commands_run: [], output: "", error: (e as Error).message, refused: false, refusal_reason: null,
      });
    } finally {
      setBusy(false);
    }
  }

  const canApply = plan && !plan.refused && typed === partition.node;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={title}>
      <div className="space-y-4">
        <div className="text-sm text-fg-muted">
          <DataValue className="text-fg">{partition.node}</DataValue> · {partition.fstype ?? "no filesystem"} ·{" "}
          <DataValue>{formatBytes(partition.size_bytes)}</DataValue>
        </div>

        {mode === "grow" && (
          <p className="text-sm text-fg-muted">
            Extend into the <span className="text-success">{formatBytes(partition.free_after_bytes)}</span> of free space
            after this partition and grow its filesystem. This can be done live for ext4/XFS/Btrfs.
          </p>
        )}

        {mode === "shrink" && (
          <label className="block">
            <span className="mb-1.5 block text-sm text-fg">New size (GB)</span>
            <input
              type="number"
              min={1}
              step={1}
              value={targetGb}
              onChange={(e) => setTargetGb(Math.max(1, Number(e.target.value) || 1))}
              className="data w-32 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            />
            <span className="ml-2 text-xs text-fg-subtle">must be unmounted; back up first</span>
          </label>
        )}

        {mode === "move" && (
          <div className="rounded-lg border border-danger/30 bg-danger/8 p-3 text-sm text-danger">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle size={15} /> Experimental & high-risk
            </div>
            <p className="mt-1 text-danger/90">
              Moving block-copies the partition and rewrites the table. An interruption corrupts the filesystem.
              Must be unmounted; ensure stable power and a backup.
            </p>
            <label className="mt-3 block">
              <span className="mb-1 block text-xs">New start (MiB from disk start)</span>
              <input
                type="number"
                min={1}
                value={newStartMib}
                onChange={(e) => setNewStartMib(Math.max(1, Number(e.target.value) || 1))}
                className="data w-32 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-fg outline-none"
              />
            </label>
          </div>
        )}

        {!plan && !result && (
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={preview} loading={busy}>Preview</Button>
          </div>
        )}

        {plan && plan.refused && (
          <div className="rounded-lg border border-warning/30 bg-warning/8 p-3 text-sm text-warning">
            <div className="mb-1 font-medium">Refused</div>
            {plan.refusal_reason}
          </div>
        )}

        {plan && !plan.refused && !result && (
          <>
            <div className="rounded-lg border border-border bg-surface-2/50 p-3">
              <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-fg-subtle">
                Exact commands that will run
              </div>
              <div className="space-y-1">
                {plan.commands.map((c, i) => (
                  <DataValue key={i} className="block text-xs text-fg">$ {c}</DataValue>
                ))}
              </div>
              <div className="mt-2 text-xs text-fg-muted">
                {formatBytes(plan.current_bytes)} → <span className="text-fg">{formatBytes(plan.target_bytes)}</span>
              </div>
            </div>
            {plan.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-warning">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <span>{w}</span>
              </div>
            ))}
            <div>
              <label className="mb-1.5 block text-xs text-fg-muted">
                Type <DataValue className="text-fg">{partition.node}</DataValue> to confirm
              </label>
              <input
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                spellCheck={false}
                className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={onClose}>Cancel</Button>
              <Button variant="danger" disabled={!canApply} loading={busy} onClick={apply}>
                Apply {mode}
              </Button>
            </div>
          </>
        )}

        {result && (
          <>
            <div className="rounded-lg border border-border bg-surface-2/50 p-3 text-sm">
              <div className="mb-1 flex items-center gap-2 font-medium">
                {result.success ? (
                  <><CheckCircle2 size={16} className="text-success" /> {mode} completed.</>
                ) : result.refused ? (
                  <><AlertTriangle size={16} className="text-warning" /> Refused</>
                ) : (
                  <><XCircle size={16} className="text-danger" /> {mode} failed.</>
                )}
              </div>
              {result.refusal_reason && <div className="text-warning">{result.refusal_reason}</div>}
              {result.error && <div className="text-danger">{result.error}</div>}
              {result.commands_run.length > 0 && (
                <div className="mt-2 space-y-0.5">
                  {result.commands_run.map((c, i) => (
                    <DataValue key={i} className="block text-xs text-fg-muted">$ {c}</DataValue>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={onClose}>Close</Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}
