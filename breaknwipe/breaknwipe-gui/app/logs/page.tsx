"use client";

import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { formatDate } from "@/lib/format";
import { Badge, Card, DataValue, EmptyState, ErrorState, PageTitle, Spinner } from "@/components/ui";

type LogRecord = Record<string, unknown>;

function statusTone(status: string): "success" | "danger" | "warning" | "neutral" {
  const s = status.toLowerCase();
  if (s === "completed") return "success";
  if (s === "failed" || s === "cancelled") return "danger";
  if (s === "running" || s === "pending") return "warning";
  return "neutral";
}

export default function LogsPage() {
  const { data, error, loading } = useAsync(() => api.logs({ limit: 200 }), []);
  const records = (data?.data as LogRecord[] | undefined) ?? [];

  return (
    <div>
      <PageTitle title="Audit log" description="Every wipe operation recorded on this machine." />

      {loading && <Spinner label="Loading logs…" />}
      {error && <ErrorState message={error} />}

      {!loading && !error && records.length === 0 && (
        <EmptyState title="No log entries yet" description="Wipe operations will appear here." />
      )}

      {!loading && !error && records.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-fg-subtle">
                  <th className="px-5 py-2.5 font-medium">Device</th>
                  <th className="px-5 py-2.5 font-medium">Algorithm</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => {
                  const status = String(r.operation_status ?? r.status ?? "unknown");
                  return (
                    <tr key={(r.session_id as string) ?? i} className="border-b border-border last:border-0">
                      <td className="px-5 py-2.5">
                        <DataValue className="text-fg">{String(r.device_path ?? "—")}</DataValue>
                      </td>
                      <td className="px-5 py-2.5">
                        <DataValue className="text-fg-muted">{String(r.algorithm_used ?? r.algorithm ?? "—")}</DataValue>
                      </td>
                      <td className="px-5 py-2.5">
                        <Badge tone={statusTone(status)}>{status}</Badge>
                      </td>
                      <td className="px-5 py-2.5 text-fg-muted">
                        {formatDate((r.created_at ?? r.timestamp) as string)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
