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

export interface SectorData {
  device: string;
  offset: number;
  length: number;
  device_size: number;
  data_base64: string;
  error: string;
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

export interface WipeProgressState {
  status: string;
  progress_percent: number;
  current_pass: number;
  total_passes: number;
  speed_mbps: number;
  data_processed: number;
  estimated_remaining: number | null;
}

export interface WipeSessionSummary {
  session_id: string;
  device_info: { path: string; model: string; capacity_human: string };
  wipe_request: { algorithm: string };
  progress: WipeProgressState;
  error_message?: string | null;
}

export const WIPE_TERMINAL = ["completed", "failed", "cancelled"];

export interface DiskPartitionGeom {
  node: string;
  number: number;
  start_sector: number;
  size_sectors: number;
  size_bytes: number;
  fstype: string | null;
  mount_point: string | null;
  is_mounted: boolean;
  is_system: boolean;
  type_uuid: string | null;
  name: string | null;
  free_after_bytes: number;
}

export interface FreeSegment {
  start_sector: number;
  size_sectors: number;
  size_bytes: number;
}

export interface LogicalVolume {
  lv_name: string;
  vg_name: string;
  lv_path: string;
  lv_size_bytes: string;
  vg_free_bytes: string;
}

export interface DiskLayout {
  disk: string;
  table_type: string | null;
  sector_size: number;
  total_bytes: number;
  partitions: DiskPartitionGeom[];
  free_segments: FreeSegment[];
  has_lvm: boolean;
  error: string | null;
  logical_volumes?: LogicalVolume[];
}

export interface ResizePlan {
  partition: string;
  mode: string;
  fstype: string | null;
  current_bytes: number;
  target_bytes: number;
  commands: string[];
  warnings: string[];
  refused: boolean;
  refusal_reason: string | null;
  requires_force: boolean;
  experimental: boolean;
}

export interface ResizeResult {
  partition: string;
  mode: string;
  success: boolean;
  changes_made: boolean;
  commands_run: string[];
  output: string;
  error: string | null;
  refused: boolean;
  refusal_reason: string | null;
}

export interface ResizeRequest {
  partition: string;
  mode: "grow" | "shrink" | "move";
  target_bytes?: number | null;
  new_start_sector?: number | null;
  force?: boolean;
  dry_run?: boolean;
}

export interface RecoverableFile {
  inode: string;
  path: string;
  name: string;
  size: number;
  deleted_time: string;
  file_type: string;
}

export interface RecoveryScanResult {
  partition: string;
  filesystem: string | null;
  files: RecoverableFile[];
  note: string;
  error: string;
  refused: boolean;
  refusal_reason: string;
}

export interface RecoveryRestoreResult {
  partition: string;
  output_dir: string;
  requested: number;
  recovered: number;
  recovered_files: string[];
  error: string;
  refused: boolean;
  refusal_reason: string;
}

export interface RecoveryAvailability {
  tools: { fls: boolean; icat: boolean; photorec: boolean };
  undelete: boolean;
  deep_scan: boolean;
}

export interface RecoveryRestoreRequest {
  partition: string;
  output_dir: string;
  inodes?: string[];
  filesystem?: string | null;
}

export type RecoveryJobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface RecoveryJobProgress {
  job_id: string;
  partition: string;
  output_dir: string;
  status: RecoveryJobStatus;
  percent: number | null;
  bytes_processed: number;
  total_bytes: number;
  rate_bytes_per_sec: number;
  eta_seconds: number | null;
  recovered: number;
  recovered_files: string[];
  error: string | null;
}

export const RECOVERY_JOB_TERMINAL = ["completed", "failed", "cancelled"];

// ---- Endpoints ----

export const api = {
  devices: () => request<DeviceInfo[]>("/api/devices"),
  deviceHealth: (path: string) =>
    request<DeviceHealth>(`/api/devices/${encodeURIComponent(path)}/health`),
  devicePartitions: (path: string) =>
    request<Partition[]>(`/api/devices/${encodeURIComponent(path)}/partitions`),
  fsckCheck: (body: { partition: string; repair?: boolean; force?: boolean; filesystem?: string | null }) =>
    request<FsckResult>("/api/fsck/check", { method: "POST", body: JSON.stringify(body) }),
  partitionTable: (path: string) =>
    request<DiskLayout>(`/api/devices/${encodeURIComponent(path)}/partition-table`),
  sectors: (path: string, offset: number, length: number) =>
    request<SectorData>(`/api/devices/${encodeURIComponent(path)}/sectors?offset=${offset}&length=${length}`),
  partitionResizePlan: (body: ResizeRequest) =>
    request<ResizePlan>("/api/partition/resize", { method: "POST", body: JSON.stringify({ ...body, dry_run: true }) }),
  partitionResizeApply: (body: ResizeRequest) =>
    request<ResizeResult>("/api/partition/resize", { method: "POST", body: JSON.stringify({ ...body, dry_run: false }) }),
  wipeStart: (body: WipeStartRequest) =>
    request<ApiResponse>("/api/wipe/start", { method: "POST", body: JSON.stringify(body) }),
  wipeStatus: (sessionId: string) => request<WipeSessionSummary>(`/api/wipe/status/${sessionId}`),
  wipeSessions: () => request<WipeSessionSummary[]>("/api/wipe/sessions"),
  wipeCancel: (sessionId: string) =>
    request<ApiResponse>(`/api/wipe/cancel/${sessionId}`, { method: "POST" }),
  wipeReport: (sessionId: string) => request<Record<string, unknown>>(`/api/wipe/report/${sessionId}`),
  logs: (params?: Record<string, string | number>) => {
    const q = params ? "?" + new URLSearchParams(params as Record<string, string>).toString() : "";
    return request<Record<string, unknown>>(`/api/logs${q}`);
  },
  recoveryAvailable: () => request<RecoveryAvailability>("/api/recovery/available"),
  recoveryScan: (body: { partition: string; filesystem?: string | null }) =>
    request<RecoveryScanResult>("/api/recovery/scan", { method: "POST", body: JSON.stringify(body) }),
  recoveryRestore: (body: RecoveryRestoreRequest) =>
    request<RecoveryRestoreResult>("/api/recovery/restore", { method: "POST", body: JSON.stringify(body) }),
  recoveryDeepScanStart: (body: { partition: string; output_dir: string }) =>
    request<{ job_id: string }>("/api/recovery/deep-scan/start", { method: "POST", body: JSON.stringify(body) }),
  recoveryDeepScanStatus: (jobId: string) =>
    request<RecoveryJobProgress>(`/api/recovery/deep-scan/${jobId}`),
  recoveryDeepScanCancel: (jobId: string) =>
    request<{ success: boolean }>(`/api/recovery/deep-scan/${jobId}/cancel`, { method: "POST" }),
  reports: () => request<Record<string, unknown>>("/api/reports"),
  systemInfo: () => request<Record<string, string>>("/api/system-info"),
};
