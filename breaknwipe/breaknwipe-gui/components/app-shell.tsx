"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Tooltip from "@radix-ui/react-tooltip";
import { Trash2, FileSearch, ShieldCheck, HardDrive, ScrollText, FileCheck2, Info } from "lucide-react";
import { ThemeToggle } from "./theme";

type Tint = "danger" | "info" | "success" | "primary";

const PILLARS: { href: string; label: string; icon: typeof Trash2; tint: Tint; match: (p: string) => boolean }[] = [
  { href: "/wipe/", label: "Wipe", icon: Trash2, tint: "danger", match: (p) => p.startsWith("/wipe") },
  { href: "/recover/", label: "Recover", icon: FileSearch, tint: "info", match: (p) => p.startsWith("/recover") },
  { href: "/verify/", label: "Verify", icon: ShieldCheck, tint: "success", match: (p) => p.startsWith("/verify") },
  {
    href: "/utility/",
    label: "Disk Utility",
    icon: HardDrive,
    tint: "primary",
    match: (p) => p.startsWith("/utility") || p.startsWith("/device") || p.startsWith("/hex"),
  },
];

const TINT_ACTIVE: Record<Tint, string> = {
  danger: "bg-danger/12 text-danger",
  info: "bg-info/12 text-info",
  success: "bg-success/12 text-success",
  primary: "bg-primary/12 text-primary",
};

const SECONDARY = [
  { href: "/logs/", label: "Audit log", icon: ScrollText },
  { href: "/reports/", label: "Reports", icon: FileCheck2 },
  { href: "/about/", label: "About", icon: Info },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  return (
    <div className="flex min-h-screen flex-col">
      <Tooltip.Provider delayDuration={300}>
        <header className="sticky top-0 z-40 border-b border-border bg-surface/85 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3">
            <Link href="/" className="flex shrink-0 items-center gap-2.5">
              {/* eslint-disable-next-line @next/next/no-img-element -- static-export SPA, no image optimizer to benefit from next/image */}
              <img src="/breaknwipe_logo1.png" alt="" className="h-8 w-8 rounded-lg" />
              <span className="hidden font-semibold tracking-tight text-fg sm:inline">BreakNWipe</span>
            </Link>

            {!isLanding && (
              <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
                {PILLARS.map(({ href, label, icon: Icon, tint, match }) => {
                  const active = match(pathname);
                  return (
                    <Link
                      key={href}
                      href={href}
                      className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                        active ? TINT_ACTIVE[tint] : "text-fg-muted hover:bg-surface-2 hover:text-fg"
                      }`}
                    >
                      <Icon size={16} />
                      {label}
                    </Link>
                  );
                })}
              </nav>
            )}

            <div className={`flex shrink-0 items-center gap-1 ${isLanding ? "ml-auto" : ""}`}>
              {SECONDARY.map(({ href, label, icon: Icon }) => (
                <Tooltip.Root key={href}>
                  <Tooltip.Trigger asChild>
                    <Link
                      href={href}
                      aria-label={label}
                      className={`inline-flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                        pathname.startsWith(href) ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg"
                      }`}
                    >
                      <Icon size={16} />
                    </Link>
                  </Tooltip.Trigger>
                  <Tooltip.Portal>
                    <Tooltip.Content
                      sideOffset={6}
                      className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-fg shadow-[var(--shadow)]"
                    >
                      {label}
                    </Tooltip.Content>
                  </Tooltip.Portal>
                </Tooltip.Root>
              ))}
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className={isLanding ? "min-w-0 flex-1" : "mx-auto min-w-0 w-full max-w-6xl flex-1 px-5 py-6 md:px-8 md:py-8"}>
          {children}
        </main>
      </Tooltip.Provider>
    </div>
  );
}
