"use client";

import { ArrowLeft, ArrowRight, ShieldCheck, KeyRound, SlidersHorizontal } from "lucide-react";
import { ALGORITHMS, CATEGORIES, type AlgorithmGroup } from "@/lib/algorithms";
import { Badge } from "@/components/ui";

const CATEGORY_ICONS: Record<AlgorithmGroup, typeof ShieldCheck> = {
  "Standard": ShieldCheck,
  "REA (crypto-erase)": KeyRound,
  "Custom": SlidersHorizontal,
};

// Category -> algorithm grid, extracted from the wipe page so the shred page
// can use the same picker instead of duplicating it.
export function AlgorithmPicker({
  category,
  setCategory,
  algorithm,
  setAlgorithm,
  passes,
  setPasses,
  configurable,
}: {
  category: AlgorithmGroup | null;
  setCategory: (c: AlgorithmGroup | null) => void;
  algorithm: string;
  setAlgorithm: (a: string) => void;
  passes: number;
  setPasses: (p: number) => void;
  configurable?: boolean;
}) {
  function chooseCategory(id: AlgorithmGroup) {
    setCategory(id);
    // Auto-select the category's first algorithm so the confirm step never
    // silently uses a stale selection left over from a different category.
    const first = ALGORITHMS.find((a) => a.group === id);
    if (first) setAlgorithm(first.value);
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="mb-2.5 block text-sm font-medium text-fg">Algorithm</label>

        {!category ? (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {CATEGORIES.map((c) => {
              const Icon = CATEGORY_ICONS[c.id];
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => chooseCategory(c.id)}
                  className="flex flex-col gap-2 rounded-lg border-2 border-border bg-surface-2 p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-3"
                >
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/12 text-primary">
                    <Icon size={18} />
                  </span>
                  <span className="flex items-center gap-1.5 font-medium text-fg">
                    {c.title}
                    <ArrowRight size={14} className="text-fg-subtle" />
                  </span>
                  <p className="text-xs leading-relaxed text-fg-muted">{c.description}</p>
                </button>
              );
            })}
          </div>
        ) : (
          <div>
            <button
              type="button"
              onClick={() => setCategory(null)}
              className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted hover:text-fg"
            >
              <ArrowLeft size={13} /> Change category
            </button>
            <div className="mb-3 text-[11px] font-medium uppercase tracking-wide text-fg-subtle">{category}</div>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {ALGORITHMS.filter((a) => a.group === category).map((a) => {
                const active = algorithm === a.value;
                return (
                  <button
                    key={a.value}
                    type="button"
                    onClick={() => setAlgorithm(a.value)}
                    className={`flex flex-col gap-1.5 rounded-lg border-2 p-3.5 text-left transition-colors ${
                      active
                        ? "border-primary bg-primary/8 shadow-[0_0_0_3px_var(--ring)]"
                        : "border-border bg-surface-2 hover:border-border-strong hover:bg-surface-3"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                      <span className="font-medium text-fg">{a.label}</span>
                      <Badge tone={active ? "success" : "neutral"}>{a.passes}</Badge>
                    </div>
                    <p className="text-xs leading-relaxed text-fg-muted">{a.description}</p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                      {a.note && <span className="text-[11px] text-fg-subtle">{a.note}</span>}
                      {!a.ssdSuitable && (
                        <span className="text-[11px] text-warning">· designed for HDDs, avoid on SSD/NVMe</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
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
    </div>
  );
}
