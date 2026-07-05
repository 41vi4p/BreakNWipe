"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";

// Opens a WebSocket to the given backend path (e.g. `/ws/<session_id>`) and
// returns the latest parsed JSON message plus connection state. Pass `null` to
// stay disconnected (e.g. before a session exists).
export function useWebSocket<T = unknown>(path: string | null) {
  const [last, setLast] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!path) return;
    const ws = new WebSocket(wsUrl(path));
    ref.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (ev) => {
      try {
        setLast(JSON.parse(ev.data));
      } catch {
        /* ignore non-JSON frames */
      }
    };
    return () => ws.close();
  }, [path]);

  return { last, connected };
}
