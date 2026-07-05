"use client";

import { useState } from "react";
import { Wrench, CheckCircle2, XCircle, Info } from "lucide-react";
import { api, type FsckResult, type Partition } from "@/lib/api";
import { Button, Card, CardHeader, DataValue } from "./ui";
import { ConfirmDialog } from "./dialog";

export function FsckPanel({ partitions }: { partitions: Partition[] }) {
  const repairable = partitions.filter((p) => p.is_repairable_type);
  const [selected, setSelected] = useState<string>(repairable[0]?.path ?? "");
  const [force, setForce] = useState(false);
  const [result, setResult] = useState<FsckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function run(repair: boolean) {
    setBusy(true);
    setResult(null);
    try {
      const r = await api.fsckCheck({ partition: selected, repair, force });
      setResult(r);
    } catch (e) {
      setResult({
        partition_path: selected,
        tool_used: null,
        fstype: null,
        check_only: !repair,
        success: false,
        filesystem_clean: null,
        changes_made: false,
        needs_reboot: false,
        exit_code: null,
        duration_seconds: 0,
        error: (e as Error).message,
        raw_output: "",
        refused: false,
        refusal_reason: null,
        notes: [],
      });
    } finally {
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  if (repairable.length === 0) {
    return (
      <Card>
        <CardHeader title="Filesystem check & repair" icon={<Wrench size={16} />} />
        <div className="p-5 text-sm text-fg-muted">
          No repairable filesystems on this device.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Filesystem check & repair" icon={<Wrench size={16} />} />
      <div className="space-y-4 p-5">
        <p className="text-sm text-fg-muted">
          Check-only never modifies anything. Repair is refused on a mounted partition — unmount it
          first, or use a live medium for your system&apos;s root.
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex-1 min-w-[220px]">
            <span className="mb-1.5 block text-xs text-fg-muted">Partition</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              {repairable.map((p) => (
                <option key={p.path} value={p.path}>
                  {p.path}
                  {p.fstype ? ` (${p.fstype})` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 pb-2.5 text-sm text-fg-muted">
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            Force (system / btrfs)
          </label>
        </div>

        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => run(false)} loading={busy}>
            Check only
          </Button>
          <Button variant="danger" onClick={() => setConfirmOpen(true)} disabled={busy}>
            Repair…
          </Button>
        </div>

        {result && <FsckResultView result={result} />}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Repair filesystem"
        confirmLabel="Run repair"
        confirmWord={selected}
        loading={busy}
        onConfirm={() => run(true)}
        description={
          <>
            This will attempt to <strong>modify</strong> the filesystem on{" "}
            <DataValue className="text-fg">{selected}</DataValue> if problems are found. Make sure it
            is unmounted and that you have a backup of anything important.
          </>
        }
      />
    </Card>
  );
}

function FsckResultView({ result }: { result: FsckResult }) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/8 p-4 text-sm text-warning">
        <div className="mb-1 font-medium">Refused</div>
        {result.refusal_reason}
      </div>
    );
  }

  const ok = result.success && !result.error;
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-4 text-sm">
      <div className="mb-2 flex items-center gap-2 font-medium">
        {ok ? <CheckCircle2 size={16} className="text-success" /> : <XCircle size={16} className="text-danger" />}
        {result.error
          ? result.error
          : result.changes_made
            ? "Filesystem errors were found and corrected."
            : result.filesystem_clean
              ? "Filesystem is clean."
              : "Completed."}
      </div>
      <div className="text-fg-muted">
        Tool: <DataValue>{result.tool_used ?? "—"}</DataValue> · Filesystem:{" "}
        <DataValue>{result.fstype ?? "—"}</DataValue>
        {result.exit_code != null && (
          <>
            {" "}
            · Exit code: <DataValue>{result.exit_code}</DataValue>
          </>
        )}
      </div>
      {result.needs_reboot && (
        <div className="mt-2 text-warning">A reboot is recommended to complete the repair.</div>
      )}
      {result.notes.map((n, i) => (
        <div key={i} className="mt-2 flex items-start gap-2 text-fg-muted">
          <Info size={13} className="mt-0.5 shrink-0" />
          {n}
        </div>
      ))}
    </div>
  );
}
