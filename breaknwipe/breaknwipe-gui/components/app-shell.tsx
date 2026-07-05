"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HardDrive, ScrollText, FileCheck2, Info, ShieldCheck } from "lucide-react";
import { ThemeToggle } from "./theme";

const NAV = [
  { href: "/", label: "Devices", icon: HardDrive, match: (p: string) => p === "/" || p.startsWith("/device") || p.startsWith("/wipe") },
  { href: "/logs/", label: "Logs", icon: ScrollText, match: (p: string) => p.startsWith("/logs") },
  { href: "/reports/", label: "Reports", icon: FileCheck2, match: (p: string) => p.startsWith("/reports") },
  { href: "/about/", label: "About", icon: Info, match: (p: string) => p.startsWith("/about") },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Sidebar (desktop) / top strip (mobile) */}
      <aside className="flex shrink-0 flex-col border-b border-border bg-surface md:w-60 md:border-b-0 md:border-r">
        <div className="flex items-center gap-2.5 px-5 py-4">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-fg">
            <ShieldCheck size={18} />
          </span>
          <div className="leading-tight">
            <div className="font-semibold tracking-tight">BreakNWipe</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-fg-subtle">Disk Toolkit</div>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible md:pb-4">
          {NAV.map(({ href, label, icon: Icon, match }) => {
            const active = match(pathname);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-surface-2 text-fg"
                    : "text-fg-muted hover:bg-surface-2 hover:text-fg"
                }`}
              >
                <Icon size={17} className={active ? "text-primary" : ""} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto hidden px-5 py-4 text-[11px] leading-relaxed text-fg-subtle md:block">
          Root required for device access. Handle every operation with care.
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-surface/80 px-5 py-3 backdrop-blur">
          <div className="text-sm text-fg-muted">
            Secure wipe · Health · Partitions · Repair
          </div>
          <ThemeToggle />
        </header>
        <main className="min-w-0 flex-1 px-5 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
