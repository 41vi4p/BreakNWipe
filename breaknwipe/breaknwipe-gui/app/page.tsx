"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileSearch, FileX2, HardDrive, ShieldCheck, Trash2 } from "lucide-react";
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
    href: "/shred/",
    tint: "danger",
    icon: FileX2,
    title: "Shred",
    description: "Browse a device's files and securely destroy just the ones you pick, leaving the rest untouched.",
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
      <HeroGlow />
      <HeroTexture />

      <div className="relative mx-auto max-w-5xl px-5 pb-16 pt-16 sm:pt-24">
        <div className="flex flex-col items-center gap-10 lg:flex-row lg:justify-between">
          <div className="max-w-2xl">
            <h1 className="hero-in text-4xl font-semibold tracking-tight text-fg sm:text-5xl">
              Know exactly what happened to your data.
            </h1>
            <p className="hero-in mt-4 text-lg leading-relaxed text-fg-muted" style={{ animationDelay: "80ms" }}>
              BreakNWipe is a complete, open-source disk toolkit: securely erase drives with tamper-proof
              certificates, recover what was accidentally deleted, verify a drive was actually wiped clean,
              and manage disks — without the confusion of traditional tools.
            </p>

            {devices && (
              <Link
                href="/utility/"
                className="hero-in mt-6 inline-flex items-center gap-2 text-sm text-fg-muted transition-colors hover:text-fg"
                style={{ animationDelay: "160ms" }}
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

          <div className="hero-in hero-float shrink-0" style={{ animationDelay: "40ms" }}>
            {/* eslint-disable-next-line @next/next/no-img-element -- static-export SPA, no image optimizer to benefit from next/image */}
            <img
              src="/breaknwipe_logo1.png"
              alt="BreakNWipe"
              className="h-48 w-48 drop-shadow-[0_12px_32px_rgba(15,157,99,0.25)] sm:h-56 sm:w-56 lg:h-64 lg:w-64"
            />
          </div>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PILLARS.map((p, i) => {
            const t = TINT_STYLES[p.tint];
            return (
              <Link
                key={p.href}
                href={p.href}
                style={{ animationDelay: `${220 + i * 70}ms` }}
                className={`hero-in group flex items-start gap-4 rounded-xl border border-l-4 border-border bg-surface p-5 shadow-[var(--shadow)] transition-transform hover:-translate-y-0.5 ${t.border}`}
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

// A large, slow-drifting radial glow behind the hero -- pure CSS, gives the
// page some ambient depth at rest, independent of the hex texture below it.
function HeroGlow() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
      <div
        className="hero-glow absolute -left-1/4 -top-1/4 h-[560px] w-[560px] rounded-full opacity-[0.12] blur-3xl"
        style={{ background: "radial-gradient(circle, var(--primary), transparent 70%)" }}
      />
    </div>
  );
}

// Deterministic (not Math.random) so the static-exported HTML and the client
// hydration render identical bytes -- a decorative hex dump, the product's own
// visual language (this is what the hex viewer actually looks like scanning a
// drive). Two soft highlight bars sweep down through it on staggered loops,
// standing in for "actively being scanned"; a handful of bytes also flicker
// to a fresh value every so often, like live reads -- both purely ambient,
// no literal bytes called out. The flicker set is only ever populated from an
// effect (after mount), so the server-rendered/initial-hydration markup is
// identical either way -- no hydration mismatch from the randomness.
function pseudoByte(i: number): string {
  const v = (i * 2654435761) >>> 24;
  return v.toString(16).padStart(2, "0");
}

function HeroTexture() {
  const cols = 18;
  const rows = 10;
  const total = cols * rows;

  const [hot, setHot] = useState<Set<number>>(new Set());

  useEffect(() => {
    const id = setInterval(() => {
      const next = new Set<number>();
      const count = 2 + Math.floor(Math.random() * 3);
      for (let i = 0; i < count; i++) {
        next.add(Math.floor(Math.random() * total));
      }
      setHot(next);
    }, 1500);
    return () => clearInterval(id);
  }, [total]);

  const rowEls = Array.from({ length: rows }, (_, r) => {
    const cells = Array.from({ length: cols }, (_, c) => {
      const idx = r * cols + c;
      return (
        <span key={c} className={`transition-colors duration-700 ${hot.has(idx) ? "text-primary" : ""}`}>
          {pseudoByte(idx)}{" "}
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
      className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[260px] select-none overflow-hidden [mask-image:linear-gradient(to_bottom,black,transparent)]"
    >
      <div className="data text-[13px] leading-[1.9] text-fg-subtle/[0.14]">{rowEls}</div>
      <div className="hero-scan absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-primary/[0.09] to-transparent" />
      <div className="hero-scan-2 absolute inset-x-0 h-12 bg-gradient-to-b from-transparent via-info/[0.07] to-transparent" />
    </div>
  );
}
