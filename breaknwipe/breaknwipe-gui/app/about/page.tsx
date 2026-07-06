"use client";

import { ShieldCheck, HardDrive, HeartPulse, Wrench, Move, Trash2, FileCheck2, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Card, CardHeader, DataValue, PageTitle, Spinner } from "@/components/ui";

const CAPABILITIES = [
  { icon: Trash2, title: "Secure wipe", body: "NIST/DoD/Gutmann + REA crypto-erase, with read-back verification and signed, blockchain-anchored certificates of destruction." },
  { icon: HeartPulse, title: "Drive health", body: "SMART status, temperature, power-on hours, and an honest remaining-lifespan estimate where a reliable indicator exists." },
  { icon: HardDrive, title: "Partitions", body: "Browse partitions and free space on any disk, with filesystem types and mount state." },
  { icon: Wrench, title: "Filesystem repair", body: "Check and repair ext/FAT/exFAT/NTFS/XFS/Btrfs — never auto-unmounting, always safe by default." },
  { icon: Move, title: "Resize", body: "Grow (live for ext4/XFS/Btrfs), shrink, and move partitions — including the one-step 'extend my root/VM disk' fix." },
  { icon: FileCheck2, title: "Certificates", body: "Every wipe produces a tamper-proof PDF/JSON certificate with a QR code, verifiable by anyone." },
];

const TEAM = [
  { name: "Blaise Rodrigues", role: "Team Lead — Algorithms, Testing & Architecture" },
  { name: "David Porathur", role: "CLI Utility, Features Integration & Architecture" },
  { name: "Vanessa Rodrigues", role: "Next.js App, Research & Architecture" },
  { name: "Natasha Lewis", role: "UI & Research" },
  { name: "Chris Lopes", role: "Next.js App with digital-signature verification" },
  { name: "Anastasia Lopes", role: "UI, Frontend & Research" },
];

export default function AboutPage() {
  const { data: sys, loading } = useAsync(() => api.systemInfo(), []);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="About" />

      <Card className="p-6">
        <div className="flex items-start gap-4">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-fg">
            <ShieldCheck size={22} />
          </span>
          <div>
            <div className="text-xl font-semibold tracking-tight">BreakNWipe</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-fg-subtle">Complete Disk Toolkit</div>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              BreakNWipe is an open-source, one-stop disk toolkit for Linux: securely wipe drives,
              inspect their health, manage and resize partitions, and repair filesystems — from one
              clean interface, without the confusion of traditional tools. It began as a secure-data-
              wiping project for <strong>Smart India Hackathon 2025</strong> (Problem Statement
              SIH25070, &ldquo;Secure Data Wiping for Trustworthy IT Asset Recycling&rdquo;) and grew
              from there. Secure wipe with tamper-proof, blockchain-anchored certificates remains its
              flagship.
            </p>
            <a
              href="https://github.com/41vi4p/BreakNWipe"
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <ExternalLink size={15} /> github.com/41vi4p/BreakNWipe
            </a>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="What it does" />
        <div className="grid grid-cols-1 gap-px overflow-hidden rounded-b-xl bg-border sm:grid-cols-2">
          {CAPABILITIES.map((c) => (
            <div key={c.title} className="bg-surface p-5">
              <div className="mb-1.5 flex items-center gap-2 font-medium text-fg">
                <c.icon size={16} className="text-primary" />
                {c.title}
              </div>
              <p className="text-sm leading-relaxed text-fg-muted">{c.body}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Team CodeBreakers" />
        <ul className="divide-y divide-border">
          {TEAM.map((m) => (
            <li key={m.name} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
              <span className="font-medium text-fg">{m.name}</span>
              <span className="text-sm text-fg-muted">{m.role}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title="System" />
        {loading && (
          <div className="p-5">
            <Spinner />
          </div>
        )}
        {sys && (
          <dl className="divide-y divide-border">
            {Object.entries(sys).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-4 px-5 py-2.5 text-sm">
                <dt className="text-fg-muted">{k}</dt>
                <dd>
                  <DataValue className="text-fg">{String(v)}</DataValue>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </Card>

      <p className="pb-2 text-center text-xs text-fg-subtle">
        Licensed under GPL-3.0 · Made with care by Team CodeBreakers for Smart India Hackathon 2025
      </p>
    </div>
  );
}
