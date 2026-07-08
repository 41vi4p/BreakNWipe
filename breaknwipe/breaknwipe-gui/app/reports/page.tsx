"use client";

import { Download, FileCheck2, FileX2 } from "lucide-react";
import { api, downloadUrl, type WipeReportRecord } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { formatBytes, formatDate } from "@/lib/format";
import { Badge, Button, Card, DataValue, EmptyState, ErrorState, PageTitle, Spinner } from "@/components/ui";

export default function ReportsPage() {
  const { data, error, loading } = useAsync(() => api.reports(), []);
  const records: WipeReportRecord[] = Array.isArray(data) ? data : [];

  return (
    <div>
      <PageTitle title="Certificates" description="Signed, verifiable certificates of destruction and past wipe records." />

      {loading && <Spinner label="Loading records…" />}
      {error && <ErrorState message={error} />}

      {!loading && !error && records.length === 0 && (
        <EmptyState title="No wipe records yet" description="Completed wipes will appear here, with their certificates when one was generated." />
      )}

      {!loading && !error && records.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {records.map((r, i) => {
            const succeeded = Boolean(r.success);
            const pdf = r.certificate_pdf_path || null;
            const json = r.certificate_json_path || null;
            const qr = r.qr_code_image_path || null;
            return (
              <Card key={r.report_id ?? r.session_id ?? i} className="flex flex-col p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2 text-primary">
                    <FileCheck2 size={16} className="shrink-0" />
                    <span className="truncate text-sm font-medium text-fg">{r.device_model || r.device_path || "Wipe record"}</span>
                  </div>
                  <Badge tone={succeeded ? "success" : "danger"}>{succeeded ? "wiped" : "failed"}</Badge>
                </div>

                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <DataValue className="block truncate text-sm text-fg-muted">{r.device_path || "—"}</DataValue>
                    {r.device_serial && (
                      <div className="truncate text-xs text-fg-subtle">
                        S/N <DataValue>{r.device_serial}</DataValue>
                      </div>
                    )}
                    <div className="text-xs text-fg-subtle">
                      {r.algorithm_used || "—"} · {formatDate(r.created_at ?? r.end_time)}
                    </div>
                    <div className="text-xs text-fg-subtle">
                      {formatBytes(r.total_bytes_written)}
                      {r.average_speed_mbps ? ` · ${Number(r.average_speed_mbps).toFixed(1)} MB/s` : ""}
                    </div>
                    <div className="text-xs text-fg-subtle">
                      Report <DataValue>{r.report_id}</DataValue>
                    </div>
                  </div>
                  {qr && (
                    // eslint-disable-next-line @next/next/no-img-element -- static-export SPA, API-served image
                    <img
                      src={downloadUrl(qr)}
                      alt="Verification QR code"
                      className="h-16 w-16 shrink-0 rounded-md border border-border bg-white p-1"
                    />
                  )}
                </div>

                <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
                  {pdf && (
                    <a href={downloadUrl(pdf)} target="_blank" rel="noreferrer">
                      <Button variant="secondary" size="sm">
                        <Download size={14} /> PDF
                      </Button>
                    </a>
                  )}
                  {json && (
                    <a href={downloadUrl(json)} target="_blank" rel="noreferrer">
                      <Button variant="secondary" size="sm">
                        <Download size={14} /> JSON
                      </Button>
                    </a>
                  )}
                  {!pdf && !json && (
                    <span className="inline-flex items-center gap-1.5 text-xs text-fg-subtle">
                      <FileX2 size={14} /> No certificate was generated for this wipe
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
