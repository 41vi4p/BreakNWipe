import * as React from "react";
import { Loader2 } from "lucide-react";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// ---- Button ----

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-fg hover:bg-primary-hover",
  secondary: "border border-border bg-surface text-fg hover:bg-surface-2",
  danger: "bg-danger text-danger-fg hover:bg-danger-hover",
  ghost: "text-fg-muted hover:bg-surface-2 hover:text-fg",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}) {
  return (
    <button
      className={cn(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], className)}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  );
}

// ---- Card ----

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-xl border border-border bg-surface", className)}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  action,
  icon,
}: {
  title: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-fg">
        {icon && <span className="text-primary">{icon}</span>}
        {title}
      </h3>
      {action}
    </div>
  );
}

// ---- Badge ----

type BadgeTone = "neutral" | "success" | "danger" | "warning" | "info";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-fg-muted",
  success: "bg-success/12 text-success",
  danger: "bg-danger/12 text-danger",
  warning: "bg-warning/15 text-warning",
  info: "bg-info/12 text-info",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// ---- Mono technical value ----

export function DataValue({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("data", className)}>{children}</span>;
}

// ---- Stat tile ----

export function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "danger" | "warning" | "success";
}) {
  const valueTone =
    tone === "danger" ? "text-danger" : tone === "warning" ? "text-warning" : tone === "success" ? "text-success" : "text-fg";
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold", valueTone)}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-fg-muted">{hint}</div>}
    </div>
  );
}

// ---- Progress bar ----

export function ProgressBar({ percent, tone = "primary" }: { percent: number; tone?: "primary" | "danger" }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
      <div
        className={cn("h-full rounded-full transition-[width] duration-300", tone === "danger" ? "bg-danger" : "bg-primary")}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

// ---- Spinner / states ----

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-fg-muted">
      <Loader2 size={16} className="animate-spin" />
      {label ?? "Loading…"}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface/40 px-6 py-14 text-center">
      <div className="text-sm font-medium text-fg">{title}</div>
      {description && <div className="mt-1 max-w-sm text-sm text-fg-muted">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/8 px-4 py-3 text-sm text-danger">
      {message}
    </div>
  );
}

export function PageTitle({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
      {description && <p className="mt-1 text-sm text-fg-muted">{description}</p>}
    </div>
  );
}
