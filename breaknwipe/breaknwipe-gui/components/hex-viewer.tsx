"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CornerUpRight } from "lucide-react";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { Button, Card, CardHeader, DataValue, ErrorState } from "./ui";

const ROW = 16;          // bytes per row
const ROW_H = 22;        // px per row (must match the rendered row height)
const CHUNK = 8192;      // bytes fetched per request (backend clamps to 64 KiB)
const VIEW_H = 620;      // scroll-container height in px
const OVERSCAN = 12;     // extra rows above/below the viewport

function hex(n: number, width: number): string {
  return n.toString(16).toUpperCase().padStart(width, "0");
}

function decodeBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}

export function HexViewer({ devicePath }: { devicePath: string }) {
  const [deviceSize, setDeviceSize] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [jump, setJump] = useState("");
  // Loaded chunk bytes, kept in state so render reads state (not a ref).
  const [chunkMap, setChunkMap] = useState<Map<number, Uint8Array>>(new Map());

  const scrollRef = useRef<HTMLDivElement | null>(null);
  // Bookkeeping refs, only ever touched inside callbacks (not during render).
  const loaded = useRef<Set<number>>(new Set());
  const pending = useRef<Set<number>>(new Set());

  // Fetch a chunk (aligned to CHUNK) once; caches the bytes in state.
  const ensureChunk = useCallback(
    (chunkIndex: number) => {
      if (chunkIndex < 0) return;
      if (loaded.current.has(chunkIndex) || pending.current.has(chunkIndex)) return;
      pending.current.add(chunkIndex);
      api
        .sectors(devicePath, chunkIndex * CHUNK, CHUNK)
        .then((d) => {
          pending.current.delete(chunkIndex);
          if (d.error) {
            setError(d.error);
            return;
          }
          setDeviceSize((prev) => (d.device_size && d.device_size !== prev ? d.device_size : prev));
          loaded.current.add(chunkIndex);
          setChunkMap((prev) => new Map(prev).set(chunkIndex, decodeBase64(d.data_base64)));
        })
        .catch((e: Error) => {
          pending.current.delete(chunkIndex);
          setError(e.message);
        });
    },
    [devicePath],
  );

  // Seed the first chunk (also gives us device_size) on mount. The parent keys
  // this component by device path, so switching devices remounts it fresh —
  // no in-effect state resets needed.
  useEffect(() => {
    ensureChunk(0);
  }, [ensureChunk]);

  const totalRows = deviceSize > 0 ? Math.ceil(deviceSize / ROW) : Math.max(64, chunkMap.size * (CHUNK / ROW));
  const firstRow = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN);
  const lastRow = Math.min(totalRows, Math.ceil((scrollTop + VIEW_H) / ROW_H) + OVERSCAN);

  // Ensure the chunks covering the visible rows are loaded.
  useEffect(() => {
    const startByte = firstRow * ROW;
    const endByte = lastRow * ROW;
    for (let c = Math.floor(startByte / CHUNK); c <= Math.floor(endByte / CHUNK); c++) ensureChunk(c);
  }, [firstRow, lastRow, ensureChunk]);

  function byteAt(offset: number): number | null {
    const c = Math.floor(offset / CHUNK);
    const chunk = chunkMap.get(c);
    if (!chunk) return null;
    const idx = offset - c * CHUNK;
    return idx < chunk.length ? chunk[idx] : null;
  }

  function doJump() {
    const raw = jump.trim();
    if (!raw || !scrollRef.current) return;
    const n = raw.toLowerCase().startsWith("0x") ? parseInt(raw, 16) : parseInt(raw, 10);
    if (Number.isNaN(n)) return;
    const row = Math.floor(n / ROW);
    scrollRef.current.scrollTop = row * ROW_H;
    setScrollTop(row * ROW_H);
  }

  const rows: React.ReactElement[] = [];
  for (let r = firstRow; r < lastRow; r++) {
    const base = r * ROW;
    const isSector = base % 512 === 0;
    const hexParts: string[] = [];
    const asciiParts: string[] = [];
    for (let i = 0; i < ROW; i++) {
      const b = byteAt(base + i);
      hexParts.push(b === null ? "··" : hex(b, 2));
      asciiParts.push(b === null ? " " : b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : "·");
    }
    rows.push(
      <div
        key={r}
        className="absolute left-0 flex w-full gap-4 whitespace-pre px-5"
        style={{ top: r * ROW_H, height: ROW_H, lineHeight: `${ROW_H}px` }}
      >
        <span className={`w-24 shrink-0 ${isSector ? "text-primary" : "text-fg-subtle"}`}>{hex(base, 10)}</span>
        <span className="shrink-0 text-fg">
          {hexParts.slice(0, 8).join(" ")} {hexParts.slice(8).join(" ")}
        </span>
        <span className="shrink-0 text-fg-muted">{asciiParts.join("")}</span>
      </div>,
    );
  }

  const rootError = error && chunkMap.size === 0;

  return (
    <Card>
      <CardHeader
        title="Raw sectors (hex)"
        icon={undefined}
        action={
          <span className="text-xs text-fg-subtle">
            <DataValue>{formatBytes(deviceSize)}</DataValue> device
          </span>
        }
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
        <input
          value={jump}
          onChange={(e) => setJump(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doJump()}
          placeholder="jump to offset (0x… or decimal)"
          className="data w-56 rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs text-fg outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        />
        <Button variant="secondary" size="sm" onClick={doJump}>
          <CornerUpRight size={14} /> Jump
        </Button>
        {deviceSize > 0 && (
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (scrollRef.current) scrollRef.current.scrollTop = 0;
                setScrollTop(0);
              }}
            >
              Start
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const top = Math.max(0, totalRows * ROW_H - VIEW_H);
                if (scrollRef.current) scrollRef.current.scrollTop = top;
                setScrollTop(top);
              }}
            >
              End
            </Button>
          </>
        )}
        <span className="ml-auto text-xs text-fg-subtle">
          offset <DataValue>0x{hex(firstRow * ROW, 10)}</DataValue> · scroll to browse
        </span>
      </div>

      {rootError ? (
        <div className="p-5">
          <ErrorState
            message={
              error!.toLowerCase().includes("root")
                ? "Reading raw sectors requires root. Launch the GUI with sudo."
                : error!
            }
          />
        </div>
      ) : (
        <>
          {/* Column header */}
          <div className="data flex gap-4 border-b border-border px-5 py-1.5 text-xs text-fg-subtle whitespace-pre">
            <span className="w-24 shrink-0">Offset</span>
            <span className="shrink-0">
              {Array.from({ length: 8 }, (_, i) => hex(i, 2)).join(" ")}{" "}
              {Array.from({ length: 8 }, (_, i) => hex(i + 8, 2)).join(" ")}
            </span>
            <span className="shrink-0">ASCII</span>
          </div>

          {/* Virtualized scroll region */}
          <div
            ref={scrollRef}
            onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
            className="data overflow-auto text-xs"
            style={{ height: VIEW_H }}
          >
            <div style={{ height: totalRows * ROW_H, position: "relative" }}>{rows}</div>
          </div>
        </>
      )}

      <div className="border-t border-border px-5 py-2 text-xs text-fg-subtle">
        Scroll through the entire device; rows load as they come into view. 512-byte sector boundaries
        are highlighted in the offset column. <span className="text-fg-muted">··</span> means not yet loaded.
      </div>
    </Card>
  );
}
