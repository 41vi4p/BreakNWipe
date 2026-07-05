"use client";

import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Card, CardHeader, DataValue, PageTitle, Spinner } from "@/components/ui";

export default function AboutPage() {
  const { data, loading } = useAsync(() => api.systemInfo(), []);

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageTitle title="About" />

      <Card className="p-6">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-fg">
            <ShieldCheck size={20} />
          </span>
          <div>
            <div className="text-lg font-semibold tracking-tight">BreakNWipe</div>
            <p className="mt-1 text-sm leading-relaxed text-fg-muted">
              A complete, approachable disk toolkit — secure wipe with tamper-proof certificates,
              drive health, partition management, and filesystem repair. Built by Team CodeBreakers.
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="System" />
        {loading && (
          <div className="p-5">
            <Spinner />
          </div>
        )}
        {data && (
          <dl className="divide-y divide-border">
            {Object.entries(data).map(([k, v]) => (
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
    </div>
  );
}
