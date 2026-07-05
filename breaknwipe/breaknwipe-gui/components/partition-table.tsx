"use client";

import { HardDrive, ShieldAlert } from "lucide-react";
import type { Partition } from "@/lib/api";
import { Badge, Card, CardHeader, DataValue, EmptyState } from "./ui";

export function PartitionTable({ partitions }: { partitions: Partition[] }) {
  return (
    <Card>
      <CardHeader title="Partitions" icon={<HardDrive size={16} />} />
      {partitions.length === 0 ? (
        <div className="p-5">
          <EmptyState title="No partitions detected" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-fg-subtle">
                <th className="px-5 py-2.5 font-medium">Path</th>
                <th className="px-5 py-2.5 font-medium">Size</th>
                <th className="px-5 py-2.5 font-medium">Filesystem</th>
                <th className="px-5 py-2.5 font-medium">Mount point</th>
              </tr>
            </thead>
            <tbody>
              {partitions.map((p) => (
                <tr key={p.path} className="border-b border-border last:border-0">
                  <td className="px-5 py-2.5">
                    <DataValue className="text-fg">{p.path}</DataValue>
                    {p.label && <span className="ml-2 text-xs text-fg-subtle">{p.label}</span>}
                  </td>
                  <td className="px-5 py-2.5">
                    <DataValue className="text-fg-muted">{p.size_human}</DataValue>
                  </td>
                  <td className="px-5 py-2.5">
                    {p.fstype ? <DataValue className="text-fg-muted">{p.fstype}</DataValue> : <span className="text-fg-subtle">—</span>}
                  </td>
                  <td className="px-5 py-2.5">
                    {p.mount_point ? (
                      <span className="inline-flex items-center gap-2">
                        <DataValue className="text-fg-muted">{p.mount_point}</DataValue>
                        {p.is_system && (
                          <Badge tone="warning">
                            <ShieldAlert size={11} /> system
                          </Badge>
                        )}
                      </span>
                    ) : (
                      <span className="text-fg-subtle">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
