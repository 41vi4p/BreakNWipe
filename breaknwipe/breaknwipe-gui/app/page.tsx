"use client";

import Link from "next/link";
import { ArrowRight, FileSearch, HardDrive, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { DataValue } from "@/components/ui";

type Tint = "danger" | "info" | "success" | "primary";

const PILLARS: {
  href: string;
  tint: Tint;
  icon: typeof Trash2;
  title: string;
  description: string;
}[] = [
  {
    href: "/wipe/",
    tint: "danger",
    icon: Trash2,
    title: "Wipe",
    description: "Erase a device with a standards-compliant algorithm and a signed, blockchain-anchored certificate.",
  },
  {
    href: "/recover/",
    tint: "info",
    icon: FileSearch,
    title: "Recover",
    description: "Find and restore files that were deleted or quick-formatted, before they're overwritten for good.",
  },
  {
    href: "/verify/",
    tint: "success",
    icon: ShieldCheck,
    title: "Verify",
    description: "Confirm a device has actually been wiped — no data should remain, checked read-only.",
  },
  {
    href: "/utility/",
    tint: "primary",
    icon: HardDrive,
    title: "Disk Utility",
    description: "Drive health, partitions, filesystem repair, and raw sector inspection — all in one place.",
  },
];

const TINT_STYLES: Record<Tint, { border: string; iconBg: string; iconFg: string }> = {
  danger: { border: "border-l-danger", iconBg: "bg-danger/12", iconFg: "text-danger" },
  info: { border: "border-l-info", iconBg: "bg-info/12", iconFg: "text-info" },
  success: { border: "border-l-success", iconBg: "bg-success/12", iconFg: "text-success" },
  primary: { border: "border-l-primary", iconBg: "bg-primary/12", iconFg: "text-primary" },
};

export default function HomePage() {
  const { data: devices } = useAsync(() => api.devices().catch(() => []), []);

  return (
    <div className="relative overflow-hidden">
      <HeroTexture />

      <div className="relative mx-auto max-w-5xl px-5 pb-16 pt-16 sm:pt-24">
        <div className="max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs font-medium text-fg-muted backdrop-blur">
            <span className="data text-primary">0F 9D 63</span>
            <span>· the color of a byte you can trust</span>
          </div>
          <h1 className="text-4xl font-semibold tracking-tight text-fg sm:text-5xl">
            Know exactly what happened to your data.
          </h1>
          <p className="mt-4 text-lg leading-relaxed text-fg-muted">
            BreakNWipe is a complete, open-source disk toolkit: securely erase drives with tamper-proof
            certificates, recover what was accidentally deleted, verify a drive was actually wiped clean,
            and manage disks — without the confusion of traditional tools.
          </p>

          {devices && (
            <Link
              href="/utility/"
              className="mt-6 inline-flex items-center gap-2 text-sm text-fg-muted transition-colors hover:text-fg"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
              </span>
              <DataValue className="text-fg">{devices.length}</DataValue> storage device
              {devices.length === 1 ? "" : "s"} detected on this machine
              <ArrowRight size={14} />
            </Link>
          )}
        </div>

        <div className="mt-12 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PILLARS.map((p) => {
            const t = TINT_STYLES[p.tint];
            return (
              <Link
                key={p.href}
                href={p.href}
                className={`group flex items-start gap-4 rounded-xl border border-l-4 border-border bg-surface p-5 shadow-[var(--shadow)] transition-transform hover:-translate-y-0.5 ${t.border}`}
              >
                <span className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${t.iconBg} ${t.iconFg}`}>
                  <p.icon size={20} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 font-semibold text-fg">
                    {p.title}
                    <ArrowRight size={15} className="text-fg-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-fg" />
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-fg-muted">{p.description}</p>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Deterministic (not Math.random) so the static-exported HTML and the client
// hydration render identical bytes -- a decorative hex dump, the product's own
// visual language, with the brand color's hex code (0f 9d 63) picked out in
// primary where a real "found it" highlight would land in the hex viewer.
function pseudoByte(i: number): string {
  const v = (i * 2654435761) >>> 24;
  return v.toString(16).padStart(2, "0");
}

function HeroTexture() {
  const cols = 18;
  const rows = 10;
  const highlightRow = 4;
  const highlightStart = 6;
  const highlightBytes = ["0f", "9d", "63"];

  const rowEls = Array.from({ length: rows }, (_, r) => {
    const cells = Array.from({ length: cols }, (_, c) => {
      const isHighlight = r === highlightRow && c >= highlightStart && c < highlightStart + highlightBytes.length;
      const value = isHighlight ? highlightBytes[c - highlightStart] : pseudoByte(r * cols + c);
      return (
        <span key={c} className={isHighlight ? "text-primary" : undefined}>
          {value}{" "}
        </span>
      );
    });
    return (
      <div key={r} className="whitespace-pre">
        {cells}
      </div>
    );
  });

  return (
    <div
      aria-hidden
      className="data pointer-events-none absolute inset-x-0 top-0 z-0 select-none text-[13px] leading-[1.9] text-fg-subtle/[0.12] [mask-image:linear-gradient(to_bottom,black,transparent)]"
    >
      {rowEls}
    </div>
  );
}
