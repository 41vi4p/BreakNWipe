"use client";

import {
  BookOpen,
  Trash2,
  FileSearch,
  ShieldCheck,
  HardDrive,
  FileCheck2,
  Layers,
  TerminalSquare,
  MessageCircleQuestion,
  AlertTriangle,
} from "lucide-react";
import { Badge, Card, CardHeader, DataValue, PageTitle } from "@/components/ui";
import { ALGORITHMS, CATEGORIES } from "@/lib/algorithms";

// ---- In-page navigation ----

const SECTIONS = [
  { id: "getting-started", label: "Getting started", icon: BookOpen },
  { id: "wipe", label: "Secure wipe", icon: Trash2 },
  { id: "recover", label: "File recovery", icon: FileSearch },
  { id: "verify", label: "Verify erasure", icon: ShieldCheck },
  { id: "utility", label: "Disk utility", icon: HardDrive },
  { id: "certificates", label: "Certificates & logs", icon: FileCheck2 },
  { id: "algorithms", label: "Algorithm reference", icon: Layers },
  { id: "cli", label: "CLI reference", icon: TerminalSquare },
  { id: "faq", label: "FAQ", icon: MessageCircleQuestion },
];

// ---- Small presentational helpers ----

function Section({ id, title, icon, children }: { id: string; title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 space-y-4">
      <h2 className="flex items-center gap-2 border-b border-border pb-2 text-base font-semibold text-fg">
        <span className="text-primary">{icon}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-border bg-surface-2/60 px-4 py-3 font-mono text-xs leading-relaxed text-fg">
      {children}
    </pre>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-sm leading-relaxed text-fg-muted">{children}</p>;
}

function Steps({ items }: { items: React.ReactNode[] }) {
  return (
    <ol className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 text-sm leading-relaxed text-fg-muted">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/12 text-[11px] font-semibold text-primary">
            {i + 1}
          </span>
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ol>
  );
}

function Callout({ tone = "warning", children }: { tone?: "warning" | "info"; children: React.ReactNode }) {
  const styles =
    tone === "warning"
      ? "border-warning/30 bg-warning/8 text-warning"
      : "border-info/30 bg-info/8 text-info";
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm leading-relaxed ${styles}`}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span className="text-fg-muted">{children}</span>
    </div>
  );
}

// ---- CLI reference data ----

interface CliOption {
  flag: string;
  description: string;
}

interface CliCommandDoc {
  name: string;
  synopsis: string;
  status?: "experimental";
  description: React.ReactNode;
  options?: CliOption[];
  examples?: { comment: string; command: string }[];
}

const CLI_COMMANDS: CliCommandDoc[] = [
  {
    name: "breaknwipe",
    synopsis: "sudo breaknwipe [OPTIONS] [COMMAND]",
    description: (
      <>
        The root command. Run with no subcommand to launch the guided <strong>interactive wizard</strong>. Every device
        operation needs root, so prefix with <DataValue>sudo</DataValue>. <DataValue>bwipe</DataValue> is a shorter alias
        for the same command.
      </>
    ),
    options: [
      { flag: "--interactive, -i", description: "Launch the guided interactive wizard (also the default with no subcommand)" },
      { flag: "--gui", description: "Launch this web GUI (FastAPI server serving the interface you are reading now)" },
      { flag: "--list-devices, -l", description: "List detected storage devices with model, capacity, and mount state" },
      { flag: "--host TEXT", description: "Web server bind address for --gui (default: 127.0.0.1)" },
      { flag: "--port INTEGER", description: "Web server port for --gui (default: 8000)" },
      { flag: "--browser", description: "Auto-open the browser when starting --gui (off by default)" },
      { flag: "--verbose, -v", description: "Increase log verbosity (-v for info, -vv for debug)" },
      { flag: "--version", description: "Show version and team information" },
    ],
    examples: [
      { comment: "Guided wizard — the easiest way to wipe a drive", command: "sudo breaknwipe --interactive" },
      { comment: "Launch this web GUI on http://127.0.0.1:8000", command: "sudo breaknwipe --gui" },
      { comment: "See what drives are connected", command: "sudo breaknwipe --list-devices" },
    ],
  },
  {
    name: "wipe",
    synopsis: "sudo breaknwipe wipe -d DEVICE [OPTIONS]",
    description: (
      <>
        Securely erase a whole device from the command line (the scriptable &ldquo;expert mode&rdquo; behind the GUI&rsquo;s
        Wipe pillar). Asks for confirmation unless <DataValue>--force</DataValue> is given. The REA crypto-erase family is
        currently offered through this web GUI; the CLI covers the standard algorithms below.
      </>
    ),
    options: [
      { flag: "--device, -d PATH", description: "Target device, e.g. /dev/sdb (required)" },
      {
        flag: "--algorithm, -a NAME",
        description:
          "One of: nist-clear (default), nist-purge, dod-3pass, dod-7pass, gutmann, random, zeros, custom — see the Algorithm reference above",
      },
      { flag: "--passes, -p INTEGER", description: "Pass count for the random/custom algorithms" },
      { flag: "--verify", description: "Read back samples of the device after wiping to confirm the wipe took effect" },
      { flag: "--certificate, -c", description: "Generate the signed PDF + JSON certificate of destruction" },
      { flag: "--output, -o DIR", description: "Directory for generated reports/certificates" },
      { flag: "--dry-run", description: "Simulate the whole flow without writing to the device" },
      { flag: "--force", description: "Skip safety confirmations — dangerous, for scripted use only" },
    ],
    examples: [
      { comment: "NIST Purge a USB drive, verify, and issue a certificate", command: "sudo breaknwipe wipe -d /dev/sdb -a nist-purge --verify -c" },
      { comment: "Five random passes, but only simulate", command: "sudo breaknwipe wipe -d /dev/sdb -a random -p 5 --dry-run" },
    ],
  },
  {
    name: "info",
    synopsis: "sudo breaknwipe info DEVICE [OPTIONS]",
    description: (
      <>
        Everything about one device: model, serial, vendor, firmware, WWN, capacity, interface, secure-erase support,
        system-disk and mount status — plus a SMART health summary (temperature, power-on hours, honest remaining-lifespan
        estimate where a reliable indicator exists) and a partition table.
      </>
    ),
    options: [
      { flag: "--no-health", description: "Skip the SMART health/lifespan lookup (faster)" },
      { flag: "--no-partitions", description: "Skip the partition/filesystem listing" },
    ],
    examples: [{ comment: "Full report for the first SATA disk", command: "sudo breaknwipe info /dev/sda" }],
  },
  {
    name: "fsck",
    synopsis: "sudo breaknwipe fsck PARTITION [OPTIONS]",
    description: (
      <>
        Check — and optionally repair — a filesystem&rsquo;s integrity. Operates on a <strong>partition</strong> (e.g.{" "}
        <DataValue>/dev/sdb1</DataValue>), not a whole disk. Check-only is the default and never modifies anything.
        Dispatches to the right tool per filesystem (e2fsck, fsck.fat, fsck.exfat, ntfsfix, xfs_repair, btrfs check).
        Repair is always refused on a mounted partition — BreakNWipe never force-unmounts; unmount it yourself first, or
        boot from a live USB to repair your root filesystem.
      </>
    ),
    options: [
      { flag: "--repair", description: "Actually fix problems (default is check-only)" },
      { flag: "--filesystem, -t TYPE", description: "Override the auto-detected filesystem type" },
      { flag: "--force", description: "Override the system-disk / btrfs repair safety gate (dangerous)" },
    ],
    examples: [
      { comment: "Safe read-only check", command: "sudo breaknwipe fsck /dev/sdb1" },
      { comment: "Repair (partition must be unmounted)", command: "sudo breaknwipe fsck /dev/sdb1 --repair" },
    ],
  },
  {
    name: "resize",
    synopsis: "sudo breaknwipe resize PARTITION [OPTIONS]",
    description: (
      <>
        Grow, shrink, or move a partition. <strong>Preview-first:</strong> by default it only prints the exact shell
        commands it would run; nothing touches the disk until you re-run with <DataValue>--apply</DataValue>. Grow works{" "}
        <strong>live</strong> (while mounted) for ext4/XFS/Btrfs — the one-step fix for &ldquo;my VM disk grew but the
        partition didn&rsquo;t&rdquo;. Shrink and move require the partition to be unmounted; XFS cannot be shrunk at all.
      </>
    ),
    options: [
      { flag: "--mode [grow|shrink|move]", description: "grow into adjacent free space (default), shrink offline, or move offline (experimental)" },
      { flag: "--size INTEGER", description: "Target size in bytes (required for --mode shrink)" },
      { flag: "--start INTEGER", description: "New start sector (required for --mode move)" },
      { flag: "--apply", description: "Execute the plan (default: preview only)" },
      { flag: "--force", description: "Confirm system-disk or experimental-move operations" },
    ],
    examples: [
      { comment: "Preview growing a root partition into new free space", command: "sudo breaknwipe resize /dev/sda2 --mode grow" },
      { comment: "Actually do it (live, no unmount needed for ext4/XFS/Btrfs)", command: "sudo breaknwipe resize /dev/sda2 --mode grow --apply" },
      { comment: "Shrink an unmounted partition to 60 GB", command: "sudo breaknwipe resize /dev/sdb1 --mode shrink --size 60000000000 --apply" },
    ],
  },
  {
    name: "recover",
    synopsis: "sudo breaknwipe recover PARTITION [OPTIONS]",
    description: (
      <>
        Find and restore deleted files. Scan-only by default — it just lists what&rsquo;s recoverable. Quick scan (The
        Sleuth Kit) recovers files <strong>with their names</strong> on NTFS/FAT/exFAT; <DataValue>--deep</DataValue>{" "}
        (PhotoRec) carves file contents by signature on any filesystem, without names. The output folder must be on a{" "}
        <strong>different drive</strong> — recovery refuses to write to the device it&rsquo;s reading, which would
        overwrite the very data being recovered.
      </>
    ),
    options: [
      { flag: "--output, -o DIR", description: "Folder to recover into (must be on a different drive)" },
      { flag: "--all", description: "Recover every found file (quick scan; default is scan-only)" },
      { flag: "--deep", description: "Signature-carve with PhotoRec — recovers content without filenames" },
      { flag: "--filesystem, -t TYPE", description: "Override the auto-detected filesystem type" },
    ],
    examples: [
      { comment: "Just list recoverable deleted files", command: "sudo breaknwipe recover /dev/sdb1" },
      { comment: "Restore everything found, to another drive", command: "sudo breaknwipe recover /dev/sdb1 --output /mnt/rescue --all" },
      { comment: "Deep carve when the filesystem is gone (quick format, ext4)", command: "sudo breaknwipe recover /dev/sdb1 --deep --output /mnt/rescue" },
    ],
  },
  {
    name: "verify",
    synopsis: "sudo breaknwipe verify DEVICE [OPTIONS]",
    description: (
      <>
        Check whether a device has actually been wiped — read-only, never writes. Samples the raw device for leftover data
        (Shannon entropy, repeated patterns, known file-format signatures) and, if any filesystem is still recognizable,
        cross-checks that nothing is recoverable by name. Shows a live progress bar with ETA.
      </>
    ),
    options: [
      {
        flag: "--depth [quick|comprehensive|paranoid]",
        description: "How thoroughly to sample the device (default: comprehensive)",
      },
    ],
    examples: [{ comment: "Thorough post-wipe audit", command: "sudo breaknwipe verify /dev/sdb --depth paranoid" }],
  },
  {
    name: "list-algorithms",
    synopsis: "breaknwipe list-algorithms",
    description: <>Print all wiping algorithms the CLI accepts, with a one-line description and category for each.</>,
  },
  {
    name: "verify-certificate",
    synopsis: "breaknwipe verify-certificate -f CERT_FILE",
    status: "experimental",
    description: (
      <>
        Check a wipe certificate file&rsquo;s authenticity. Still being built out on the CLI side — for a full
        signature + blockchain check today, use the QR code on the certificate with the companion verification webapp, or
        the server&rsquo;s <DataValue>POST /api/verify/certificate</DataValue> endpoint.
      </>
    ),
    options: [{ flag: "--cert-file, -f PATH", description: "Certificate file to verify (required)" }],
  },
  {
    name: "batch",
    synopsis: "sudo breaknwipe batch -c CONFIG [OPTIONS]",
    status: "experimental",
    description: (
      <>Wipe multiple devices from a JSON/YAML configuration file. Implementation in progress — not yet functional.</>
    ),
    options: [
      { flag: "--config, -c PATH", description: "Batch configuration file (required)" },
      { flag: "--output, -o DIR", description: "Output directory for reports" },
      { flag: "--parallel, -p INTEGER", description: "Number of parallel operations (default: 1)" },
    ],
  },
];

// ---- FAQ data ----

const FAQS: { q: string; a: React.ReactNode }[] = [
  {
    q: "Why does BreakNWipe need root (sudo)?",
    a: (
      <>
        Every real device operation — reading raw sectors, issuing secure-erase commands, overwriting a block device —
        requires direct access to <DataValue>/dev/…</DataValue>, which Linux only grants to root. The CLI checks this at
        startup and exits with a clear message if you forget <DataValue>sudo</DataValue>.
      </>
    ),
  },
  {
    q: "Which algorithm should I pick?",
    a: (
      <>
        For most cases: <strong>NIST SP 800-88 Clear</strong> (1 pass) if the drive stays within your organization, and{" "}
        <strong>NIST SP 800-88 Purge</strong> (3 passes) before it leaves your control — resale, donation, disposal. Both
        are modern, recognized standards. Reach for DoD/Gutmann only when a specific policy names them, and for the REA
        family when you want a crypto-erase layer on top of overwriting.
      </>
    ),
  },
  {
    q: "Do I need 35 passes (Gutmann) to be safe?",
    a: (
      <>
        No. Gutmann&rsquo;s 35 patterns target 1990s-era MFM/RLL magnetic encoding that no modern drive uses. On today&rsquo;s
        hardware a single verified overwrite already defeats software recovery, which is why NIST&rsquo;s current guidance
        (SP 800-88) needs only 1–3 passes. Multi-pass mainly costs time — and on SSDs it just burns write cycles.
      </>
    ),
  },
  {
    q: "Why do some algorithms say “avoid on SSD/NVMe”?",
    a: (
      <>
        SSDs remap writes internally (wear leveling), so repeated pattern passes don&rsquo;t hit the same physical cells the
        way they do on spinning disks — extra passes add wear without adding much assurance. The heavy multi-pass methods
        (DoD 7-pass, Gutmann, REA Extreme) were designed for magnetic drives. On SSD/NVMe, prefer NIST Clear/Purge or a
        crypto-erase style method.
      </>
    ),
  },
  {
    q: "Can files be recovered after a BreakNWipe wipe?",
    a: (
      <>
        No — that is the point. Once a real wipe algorithm has overwritten a device, there is nothing left for any software
        (including BreakNWipe&rsquo;s own Recover pillar) to find. The Recover feature exists for <em>accidents</em> —
        deleted files and quick formats that haven&rsquo;t been overwritten yet — not for undoing a wipe. Use the Verify
        pillar to prove a wipe worked.
      </>
    ),
  },
  {
    q: "What's the difference between Quick scan and Deep scan in Recover?",
    a: (
      <>
        <strong>Quick scan</strong> (The Sleuth Kit) reads leftover filesystem metadata, so it recovers files with their
        original names and paths — works on NTFS, FAT, and exFAT, the common USB-stick/SD-card case.{" "}
        <strong>Deep scan</strong> (PhotoRec) ignores the filesystem and carves file contents by their format signatures —
        it works even after a quick format or on ext4, but recovered files lose their original names.
      </>
    ),
  },
  {
    q: "Why does recovery refuse my output folder?",
    a: (
      <>
        The output folder must live on a <strong>different physical drive</strong> than the one being recovered. Writing
        recovered files back onto the same device would overwrite the exact deleted data you&rsquo;re trying to rescue.
        This is enforced in the recovery engine itself, not just the UI. Plug in a second drive or point at another disk.
      </>
    ),
  },
  {
    q: "Verify says “no recognizable filesystem” — is that bad?",
    a: (
      <>
        After a wipe, it&rsquo;s good news. A properly erased device should have no filesystem structures left at all, so
        the recovery cross-check finding nothing to even scan is treated as a positive signal, not a failure.
      </>
    ),
  },
  {
    q: "How does someone verify my wipe certificate?",
    a: (
      <>
        Every certificate carries an RSA digital signature and a QR code. Scanning the QR opens the companion verification
        webapp, which checks the report&rsquo;s hash against the record anchored on the Ethereum Sepolia blockchain — so a
        recycler, auditor, or buyer can confirm the wipe happened exactly as described, without trusting the machine that
        produced the PDF. The JSON report can also be checked via the server&rsquo;s certificate-verification API.
      </>
    ),
  },
  {
    q: "Why won't it let me wipe / repair / shrink my system disk?",
    a: (
      <>
        Deliberate safety gates. Destructive operations on the disk the OS is running from are refused (or demand an
        explicit force + typed confirmation), repair is always refused on mounted partitions, and BreakNWipe{" "}
        <strong>never auto-unmounts</strong> anything. To operate on your own system disk, boot from a live USB and run
        BreakNWipe there.
      </>
    ),
  },
  {
    q: "What is REA?",
    a: (
      <>
        The <strong>Randomized Encryption Algorithm</strong> is BreakNWipe&rsquo;s own crypto-erase family: it first
        scrambles the drive&rsquo;s contents with layered, key-rotating encryption passes, then finishes with a
        standards-style overwrite. Variants trade speed against layering — from REA Fast (one layer + zero pass) up to REA
        Extreme (seven layers + Gutmann-style overwrite).
      </>
    ),
  },
  {
    q: "Can I open the GUI from another computer?",
    a: (
      <>
        By default the server binds to <DataValue>127.0.0.1</DataValue> (this machine only). You can start it with{" "}
        <DataValue>sudo breaknwipe --gui --host 0.0.0.0</DataValue> to reach it over the network — but the GUI has no
        authentication and can destroy data, so only do this on a trusted, isolated network.
      </>
    ),
  },
  {
    q: "A wipe is running — can I close the browser tab?",
    a: (
      <>
        Yes. Wipes run on the server, not in your browser. Reopen the Wipe pillar (or click the &ldquo;wipe in progress&rdquo;
        banner on the device picker) and it reconnects to the live progress. You can also cancel a running wipe from the
        progress view — though whatever was already overwritten stays overwritten.
      </>
    ),
  },
  {
    q: "How do I update or uninstall BreakNWipe?",
    a: (
      <>
        Installed via APT: <DataValue>sudo apt update && sudo apt upgrade</DataValue> keeps it current, and{" "}
        <DataValue>sudo apt remove breaknwipe</DataValue> uninstalls. Installed via the install script:{" "}
        <DataValue>sudo make uninstall-system</DataValue> from a checkout, or download and run{" "}
        <DataValue>scripts/uninstall.sh</DataValue>.
      </>
    ),
  },
  {
    q: "Does BreakNWipe handle hidden disk areas (HPA/DCO)?",
    a: (
      <>
        Yes — device detection probes for Host Protected Areas and Device Configuration Overlays via{" "}
        <DataValue>hdparm</DataValue>, so the wipe covers the drive&rsquo;s real capacity, not just the part the OS
        normally sees. Hardware secure-erase (ATA Secure Erase, NVMe Sanitize) is used where the drive supports it.
      </>
    ),
  },
];

// ---- Page ----

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <PageTitle
        title="Help & documentation"
        description="How to use every part of BreakNWipe — the web GUI, the command line, and the answers to common questions."
      />

      <div className="flex gap-8">
        {/* Sticky section nav (desktop) */}
        <aside className="hidden w-48 shrink-0 lg:block">
          <nav className="sticky top-20 space-y-0.5">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <a
                key={id}
                href={`#${id}`}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
              >
                <Icon size={15} />
                {label}
              </a>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 flex-1 space-y-10 pb-10">
          {/* ---- Getting started ---- */}
          <Section id="getting-started" title="Getting started" icon={<BookOpen size={18} />}>
            <P>
              BreakNWipe is a complete disk toolkit for Linux: securely wipe drives with tamper-proof certificates, recover
              accidentally deleted files, verify erasure, inspect drive health, and manage or repair partitions. Everything
              is available both from this web GUI and from the <DataValue>breaknwipe</DataValue> command line (alias:{" "}
              <DataValue>bwipe</DataValue>).
            </P>
            <Card className="p-5">
              <h3 className="mb-2 text-sm font-semibold text-fg">Install (Ubuntu/Debian, via APT)</h3>
              <CodeBlock>{`curl -fsSL https://41vi4p.github.io/BreakNWipe/apt/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/breaknwipe.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/breaknwipe.gpg] https://41vi4p.github.io/BreakNWipe/apt stable main" | sudo tee /etc/apt/sources.list.d/breaknwipe.list
sudo apt update && sudo apt install breaknwipe`}</CodeBlock>
              <h3 className="mb-2 mt-4 text-sm font-semibold text-fg">Or one-line script install</h3>
              <CodeBlock>{`curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/quickstart.sh | sudo bash`}</CodeBlock>
              <h3 className="mb-2 mt-4 text-sm font-semibold text-fg">Launch</h3>
              <CodeBlock>{`sudo breaknwipe --gui           # this web interface, on http://127.0.0.1:8000
sudo breaknwipe --interactive   # guided terminal wizard
sudo breaknwipe --list-devices  # quick device overview`}</CodeBlock>
            </Card>
            <Callout>
              BreakNWipe needs <strong>root privileges</strong> for direct device access — always run it with{" "}
              <DataValue>sudo</DataValue>. And treat every wipe as final: a completed wipe cannot be undone by anyone,
              including BreakNWipe&rsquo;s own recovery tools.
            </Callout>
            <P>
              The GUI is organized around four pillars in the top bar — <strong className="text-danger">Wipe</strong>,{" "}
              <strong className="text-info">Recover</strong>, <strong className="text-success">Verify</strong>, and{" "}
              <strong className="text-primary">Disk Utility</strong> — each a self-contained flow that starts by picking a
              device. The Audit log, Certificates, About, and this Help page live behind the compact icons on the right of
              the bar.
            </P>
          </Section>

          {/* ---- Wipe ---- */}
          <Section id="wipe" title="Secure wipe" icon={<Trash2 size={18} />}>
            <P>
              Permanently destroys all data on a device using a standards-compliant algorithm, with optional read-back
              verification and a digitally signed, blockchain-anchored certificate of destruction.
            </P>
            <Steps
              items={[
                <>Open <strong>Wipe</strong> and pick the target device. Model, capacity, and mount state are shown on each card — double-check you have the right drive.</>,
                <>Pick an algorithm <strong>category</strong> — Standard (named standards like NIST/DoD), REA (BreakNWipe&rsquo;s crypto-erase family), or Custom (configurable passes/patterns) — then the specific algorithm. Each card explains what it does and flags methods to avoid on SSDs.</>,
                <>Choose options: <strong>Verify after wipe</strong> (read-back sampling to confirm the wipe took effect) and <strong>Generate signed certificate</strong> (PDF + JSON proof of destruction).</>,
                <>Click <strong>Wipe device…</strong> and type the device path to confirm. This typed confirmation is the last stop — after it, data destruction begins.</>,
                <>Watch live progress: current pass, speed, bytes processed, and ETA. You can leave the page and come back — the wipe runs on the server and the page reconnects. A Cancel button stops it early (already-overwritten data stays gone).</>,
                <>When it finishes, download the certificate, or jump into the <strong>hex viewer</strong> to see with your own eyes that the drive reads back clean.</>,
              ]}
            />
            <Callout>
              Wiping a <strong>mounted</strong> or <strong>system</strong> disk is blocked or requires explicit force. To
              wipe the disk your OS runs from, boot from a live USB and run BreakNWipe there.
            </Callout>
          </Section>

          {/* ---- Recover ---- */}
          <Section id="recover" title="File recovery" icon={<FileSearch size={18} />}>
            <P>
              Finds and restores files that were deleted or quick-formatted but not yet overwritten — the &ldquo;I deleted
              photos off my USB stick&rdquo; case. Scanning is completely read-only.
            </P>
            <Steps
              items={[
                <>Open <strong>Recover</strong> and pick the partition (e.g. <DataValue>/dev/sdb1</DataValue>) that held the files. If the partition table itself is gone, run a Deep scan on the whole device instead.</>,
                <><strong>Quick scan</strong> (NTFS/FAT/exFAT) lists deleted files with their original names and sizes. Tick the ones you want — or select all.</>,
                <><strong>Deep scan</strong> works on any filesystem, even after a quick format, by recognizing file contents (signature carving) — but recovered files lose their original names. It shows live progress, rate, a running found-count, and ETA, and can be cancelled.</>,
                <>Choose an output folder <strong>on a different drive</strong> and start recovery. Writing to the same device would overwrite the very data being recovered, so BreakNWipe refuses it.</>,
                <>Browse the results right in the GUI — click any recovered file to preview images, PDFs, and text inline, or download it.</>,
              ]}
            />
            <Callout tone="info">
              A drive that was securely <em>wiped</em> has nothing to recover — recovery is for accidents, not for undoing
              a wipe. Also: stop using the affected drive immediately; every new write risks overwriting deleted data.
            </Callout>
          </Section>

          {/* ---- Verify ---- */}
          <Section id="verify" title="Verify erasure" icon={<ShieldCheck size={18} />}>
            <P>
              Confirms a device has actually been wiped clean — useful as an independent audit after any wipe (by
              BreakNWipe or anything else). Strictly read-only; safe to run any time.
            </P>
            <Steps
              items={[
                <>Open <strong>Verify</strong> and pick the device.</>,
                <>Choose a depth: <strong>quick</strong> (spot check), <strong>comprehensive</strong> (recommended), or <strong>paranoid</strong> (dense sampling of the whole drive — slow but thorough).</>,
                <>The check samples raw sectors across the device, measuring Shannon entropy, hunting for repeated leftover patterns, and matching known file-format signatures (JPEG, PNG, ZIP, …). A progress bar with ETA tracks it; you can cancel.</>,
                <>If any filesystem is still recognizable, a recovery cross-check confirms nothing is recoverable by name. Finding <em>no</em> filesystem at all after a wipe is itself a good sign.</>,
                <>Read the verdict: pass/fail plus the full statistics — samples checked, average entropy, pattern detections, and any signature hits with their offsets.</>,
              ]}
            />
            <P>
              Note the distinction: this pillar verifies the <strong>device</strong>. Verifying a{" "}
              <strong>certificate&rsquo;s</strong> authenticity is done by scanning its QR code (see Certificates below).
            </P>
          </Section>

          {/* ---- Disk utility ---- */}
          <Section id="utility" title="Disk utility" icon={<HardDrive size={18} />}>
            <P>
              The maintenance toolbox: pick a device under <strong>Disk Utility</strong> to open its detail page with
              health, partitions, repair, and the raw sector viewer.
            </P>
            <div className="space-y-3">
              <Card className="p-5">
                <h3 className="mb-1.5 text-sm font-semibold text-fg">Drive health</h3>
                <P>
                  SMART overall status, temperature, power-on hours, and warnings. A remaining-lifespan percentage is shown
                  only when a reliable indicator exists (NVMe&rsquo;s spec-mandated wear counter, or a recognized SATA SSD
                  wear attribute) — no fabricated numbers for drives that don&rsquo;t report one.
                </P>
              </Card>
              <Card className="p-5">
                <h3 className="mb-1.5 text-sm font-semibold text-fg">Partition map & resize</h3>
                <P>
                  A proportional map of partitions and free space. Per-partition actions: <strong>Extend</strong> into
                  adjacent free space (live for ext4/XFS/Btrfs — no unmount, the classic root/VM-disk fix, LVM included),{" "}
                  <strong>Shrink</strong> (offline only; XFS honestly reported as un-shrinkable), and <strong>Move</strong>{" "}
                  (experimental, offline, non-overlapping only). Every operation previews the exact commands first and
                  requires typed confirmation. For anything beyond these — changing partition types, complex layouts —
                  there&rsquo;s an &ldquo;Open GParted&rdquo; escape hatch.
                </P>
              </Card>
              <Card className="p-5">
                <h3 className="mb-1.5 text-sm font-semibold text-fg">Filesystem check & repair</h3>
                <P>
                  Runs the right checker per filesystem (ext4, FAT, exFAT, NTFS, XFS, Btrfs). Check-only by default;
                  repair is refused on mounted partitions and never auto-unmounts. System-disk and Btrfs repairs sit behind
                  an extra force gate.
                </P>
              </Card>
              <Card className="p-5">
                <h3 className="mb-1.5 text-sm font-semibold text-fg">Hex / sector viewer</h3>
                <P>
                  A read-only raw view of the device: hex + ASCII columns, offset gutter, 512-byte sector boundaries, and
                  jump-to-offset (hex <DataValue>0x…</DataValue> or decimal). It scrolls the entire device smoothly — even
                  multi-TB drives — fetching only what&rsquo;s visible. Offered from the post-wipe screen so you can{" "}
                  <em>see</em> the drive is zeroed.
                </P>
              </Card>
            </div>
          </Section>

          {/* ---- Certificates ---- */}
          <Section id="certificates" title="Certificates, reports & audit log" icon={<FileCheck2 size={18} />}>
            <P>
              Every wipe with &ldquo;Generate signed certificate&rdquo; enabled produces a <strong>PDF certificate</strong>{" "}
              and a matching <strong>JSON report</strong>: device identity (model, serial), algorithm and pass-by-pass
              details, timestamps, verification results, an RSA digital signature, and a QR code.
            </P>
            <ul className="space-y-2 text-sm leading-relaxed text-fg-muted">
              <li className="flex gap-2">
                <span className="text-primary">•</span>
                <span>
                  <strong className="text-fg">Blockchain anchoring</strong> — the report&rsquo;s hash is registered on the
                  Ethereum Sepolia blockchain, making the certificate tamper-evident: any later edit to the report breaks
                  the match with the on-chain record.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary">•</span>
                <span>
                  <strong className="text-fg">QR verification</strong> — anyone can scan the certificate&rsquo;s QR code
                  with the companion verification webapp to independently confirm the wipe against the blockchain, without
                  trusting the machine that produced the PDF.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary">•</span>
                <span>
                  <strong className="text-fg">Certificates page</strong> — download past certificates and reports
                  generated on this machine.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary">•</span>
                <span>
                  <strong className="text-fg">Audit log</strong> — a local, persistent record of every wipe operation run
                  on this machine, independent of the blockchain anchor.
                </span>
              </li>
            </ul>
          </Section>

          {/* ---- Algorithms ---- */}
          <Section id="algorithms" title="Algorithm reference" icon={<Layers size={18} />}>
            <P>
              Thirteen algorithms in three families. As a rule of thumb: <strong>NIST Clear</strong> for drives staying
              in-house, <strong>NIST Purge</strong> before a drive leaves your control, and the heavy multi-pass methods
              only where a policy explicitly demands them.
            </P>
            {CATEGORIES.map((cat) => (
              <Card key={cat.id}>
                <CardHeader title={cat.title} />
                <div className="px-5 pt-3">
                  <P>{cat.description}</P>
                </div>
                <div className="divide-y divide-border">
                  {ALGORITHMS.filter((a) => a.group === cat.id).map((a) => (
                    <div key={a.value} className="px-5 py-3.5">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-fg">{a.label}</span>
                        <DataValue className="text-xs text-fg-subtle">{a.value}</DataValue>
                        <Badge tone="neutral">{a.passes}</Badge>
                        {!a.ssdSuitable && <Badge tone="warning">avoid on SSD/NVMe</Badge>}
                      </div>
                      <p className="text-xs leading-relaxed text-fg-muted">{a.description}</p>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </Section>

          {/* ---- CLI ---- */}
          <Section id="cli" title="CLI reference" icon={<TerminalSquare size={18} />}>
            <P>
              Everything the GUI does is also scriptable. Commands and options tab-complete in bash/zsh/fish (set up
              automatically by the APT package and system installer). Run any command with <DataValue>--help</DataValue>{" "}
              for its built-in usage text.
            </P>
            <div className="space-y-4">
              {CLI_COMMANDS.map((cmd) => (
                <Card key={cmd.name}>
                  <CardHeader
                    title={
                      <span className="flex items-center gap-2">
                        <DataValue>{cmd.name}</DataValue>
                        {cmd.status === "experimental" && <Badge tone="warning">in progress</Badge>}
                      </span>
                    }
                  />
                  <div className="space-y-3 p-5">
                    <CodeBlock>{cmd.synopsis}</CodeBlock>
                    <P>{cmd.description}</P>
                    {cmd.options && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-b border-border text-[11px] uppercase tracking-wider text-fg-subtle">
                              <th className="py-2 pr-4 font-medium">Option</th>
                              <th className="py-2 font-medium">Description</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {cmd.options.map((o) => (
                              <tr key={o.flag}>
                                <td className="whitespace-nowrap py-2 pr-4 align-top">
                                  <DataValue className="text-xs">{o.flag}</DataValue>
                                </td>
                                <td className="py-2 text-fg-muted">{o.description}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {cmd.examples && (
                      <CodeBlock>
                        {cmd.examples.map((e) => `# ${e.comment}\n${e.command}`).join("\n\n")}
                      </CodeBlock>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </Section>

          {/* ---- FAQ ---- */}
          <Section id="faq" title="Frequently asked questions" icon={<MessageCircleQuestion size={18} />}>
            <Card className="divide-y divide-border">
              {FAQS.map((f) => (
                <details key={f.q} className="group px-5 py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-fg [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <span className="shrink-0 text-fg-subtle transition-transform group-open:rotate-90">›</span>
                  </summary>
                  <div className="mt-2 text-sm leading-relaxed text-fg-muted">{f.a}</div>
                </details>
              ))}
            </Card>
          </Section>
        </div>
      </div>
    </div>
  );
}
