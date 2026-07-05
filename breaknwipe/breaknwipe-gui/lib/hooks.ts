"use client";

import { useCallback, useEffect, useState } from "react";

// Minimal async-data hook: runs `fn`, tracks loading/error, and exposes a
// `reload`. `deps` controls re-fetching.
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    // Enter loading state, then resolve asynchronously — a standard data-fetch
    // hook; the initial setState is intentional here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    fn()
      .then((d) => alive && (setData(d), setLoading(false)))
      .catch((e: Error) => alive && (setError(e.message), setLoading(false)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, reload };
}

// Reads a query param from window.location — avoids the Suspense boundary that
// `useSearchParams` requires under static export, and matches how the old GUI
// passed the device path.
export function useQueryParam(key: string): string | null {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    // Read the query string on mount (client-only). Intentional mount sync.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setValue(new URLSearchParams(window.location.search).get(key));
  }, [key]);
  return value;
}
