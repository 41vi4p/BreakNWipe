"use client";

import { Activity, AlertTriangle, HeartPulse } from "lucide-react";
import type { DeviceHealth } from "@/lib/api";
import { Card, CardHeader, StatTile } from "./ui";

export function HealthPanel({ health }: { health: DeviceHealth }) {
  const smartTone =
    health.smart_overall === "PASSED" ? "success" : health.smart_overall === "FAILED" ? "danger" : undefined;

  const lifespanKnown = health.lifespan_remaining_percent !== null && health.lifespan_remaining_percent !== undefined;
  const lifespanTone =
    lifespanKnown && health.lifespan_remaining_percent! <= 15 ? "danger" : lifespanKnown && health.lifespan_remaining_percent! <= 30 ? "warning" : "success";

  return (
    <Card>
      <CardHeader title="Health" icon={<HeartPulse size={16} />} />
      <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
        <StatTile
          label="SMART"
          value={health.smart_overall ?? "Unknown"}
          tone={smartTone}
        />
        <StatTile
          label="Temperature"
          value={health.temperature_celsius != null ? `${health.temperature_celsius}°C` : "Unknown"}
        />
        <StatTile
          label="Power-on hours"
          value={health.power_on_hours != null ? health.power_on_hours.toLocaleString() : "Unknown"}
        />
        <StatTile
          label="Life remaining"
          value={lifespanKnown ? `${health.lifespan_remaining_percent}%` : "N/A"}
          tone={lifespanKnown ? (lifespanTone as "danger" | "warning" | "success") : undefined}
          hint={lifespanKnown ? undefined : "no standardized indicator"}
        />
      </div>

      <div className="border-t border-border px-5 py-3 text-xs text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          <Activity size={13} /> Lifespan source: {health.lifespan_source}
        </span>
      </div>

      {health.warnings.length > 0 && (
        <div className="space-y-1.5 border-t border-border px-5 py-3">
          {health.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-warning">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
