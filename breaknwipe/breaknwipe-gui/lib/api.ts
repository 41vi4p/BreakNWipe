// Typed client for the BreakNWipe FastAPI backend.
//
// In production the GUI is a static export served by the same FastAPI server
// that hosts the API, so requests are same-origin (empty base). In dev the
// Next dev server runs on :3000 while FastAPI runs on :8000 — auto-detected
// here so no env file is needed. NEXT_PUBLIC_API_BASE overrides both.

function apiBase(): string {
  const explicit = process.env.NEXT_PUBLIC_API_BASE;
  if (explicit) return explicit.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "";
}

// Absolute URL for a backend path — used for <a href> downloads (certificates)
// where a relative path wouldn't hit the backend during dev.
export function apiUrl(path: string): string {
  return apiBase() + path;
}

export function wsUrl(path: string): string {
  const base = apiBase();
  if (base) return base.replace(/^http/, "ws") + path;
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }
  return path;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiBase() + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Types (mirror the backend pydantic/dataclass shapes) ----

export interface DeviceInfo {
  path: string;
  model: string;
  serial: string;
  capacity: number;
  capacity_human: string;
  device_type: string;
  interface: string;
  is_mounted: boolean;
  secure_erase_support: boolean;
  mount_points: string[];
  is_system_disk: boolean;
}

export interface DeviceHealth {
  smart_overall: string | null;
  temperature_celsius: number | null;
  power_on_hours: number | null;
  power_cycles: number | null;
  reallocated_sectors: number | null;
  pending_sectors: number | null;
  lifespan_remaining_percent: number | null;
  lifespan_source: string;
  warnings: string[];
}

export interface Partition {
  path: string;
  parent_disk: string;
  size_bytes: number;
  size_human: string;
  fstype: string | null;
  label: string | null;
  uuid: string | null;
  mount_point: string | null;
  is_mounted: boolean;
  is_system: boolean;
  is_repairable_type: boolean;
}

export interface FsckResult {
  partition_path: string;
  tool_used: string | null;
  fstype: string | null;
  check_only: boolean;
  success: boolean;
  filesystem_clean: boolean | null;
  changes_made: boolean;
  needs_reboot: boolean;
  exit_code: number | null;
  duration_seconds: number;
  error: string | null;
  raw_output: string;
  refused: boolean;
  refusal_reason: string | null;
  notes: string[];
}

export interface WipeStartRequest {
  device_path: string;
  algorithm: string;
  verify?: boolean;
  generate_certificate?: boolean;
  passes?: number | null;
}

export interface ApiResponse {
  success: boolean;
  message: string;
  data?: Record<string, unknown> | null;
}

// ---- Endpoints ----

export const api = {
  devices: () => request<DeviceInfo[]>("/api/devices"),
  deviceHealth: (path: string) =>
    request<DeviceHealth>(`/api/devices/${encodeURIComponent(path)}/health`),
  devicePartitions: (path: string) =>
    request<Partition[]>(`/api/devices/${encodeURIComponent(path)}/partitions`),
  fsckCheck: (body: { partition: string; repair?: boolean; force?: boolean; filesystem?: string | null }) =>
    request<FsckResult>("/api/fsck/check", { method: "POST", body: JSON.stringify(body) }),
  wipeStart: (body: WipeStartRequest) =>
    request<ApiResponse>("/api/wipe/start", { method: "POST", body: JSON.stringify(body) }),
  wipeStatus: (sessionId: string) => request<Record<string, unknown>>(`/api/wipe/status/${sessionId}`),
  wipeReport: (sessionId: string) => request<Record<string, unknown>>(`/api/wipe/report/${sessionId}`),
  logs: (params?: Record<string, string | number>) => {
    const q = params ? "?" + new URLSearchParams(params as Record<string, string>).toString() : "";
    return request<Record<string, unknown>>(`/api/logs${q}`);
  },
  reports: () => request<Record<string, unknown>>("/api/reports"),
  systemInfo: () => request<Record<string, string>>("/api/system-info"),
};
