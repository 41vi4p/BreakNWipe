"use client";

import * as React from "react";
import * as RadixDialog from "@radix-ui/react-dialog";
import { X, AlertTriangle } from "lucide-react";
import { Button, DataValue } from "./ui";

const OVERLAY = "fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in";
const CONTENT =
  "fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-surface shadow-[var(--shadow)] focus:outline-none";

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content className={CONTENT}>
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <RadixDialog.Title className="text-sm font-semibold text-fg">{title}</RadixDialog.Title>
            <RadixDialog.Close className="rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg">
              <X size={16} />
            </RadixDialog.Close>
          </div>
          <div className="px-5 py-4">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

// A destructive-action confirmation. When `confirmWord` is set, the confirm
// button stays disabled until the user types that exact word/path — the same
// "type-to-confirm" gate the CLI/backend enforce for dangerous operations.
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  confirmWord,
  danger = true,
  loading,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  confirmWord?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = React.useState("");
  const ready = !confirmWord || typed === confirmWord;

  // Reset the typed confirmation whenever the dialog closes (via any path:
  // the X, overlay click, Escape, or Cancel), so a reopen starts empty —
  // without a setState-in-effect.
  function handleOpenChange(o: boolean) {
    if (!o) setTyped("");
    onOpenChange(o);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange} title={title}>
      <div className="space-y-4">
        <div className="flex gap-3">
          {danger && (
            <span className="mt-0.5 shrink-0 text-danger">
              <AlertTriangle size={18} />
            </span>
          )}
          <div className="text-sm leading-relaxed text-fg-muted">{description}</div>
        </div>

        {confirmWord && (
          <div>
            <label className="mb-1.5 block text-xs text-fg-muted">
              Type <DataValue className="text-fg">{confirmWord}</DataValue> to confirm
            </label>
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoFocus
              spellCheck={false}
              className="data w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            />
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            disabled={!ready}
            loading={loading}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
