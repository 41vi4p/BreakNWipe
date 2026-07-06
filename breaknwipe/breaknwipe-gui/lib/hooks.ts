"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

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

// Reads a query param, reactively -- via Next's useSearchParams(), which
// re-renders on every client-side navigation (including a same-route change
// like /wipe/ -> /wipe/?path=X, e.g. picking a device from an in-page
// picker). A plain window.location.search read in a mount-only effect (the
// previous approach) misses exactly that case: App Router doesn't remount
// the page for a search-param-only navigation, so the effect never re-runs
// and the value gets stuck until a full page reload.
//
// useSearchParams() requires a Suspense boundary in a statically-exported
// app (Next can't know the query string at build time) -- every page that
// calls this hook wraps its content in <Suspense>.
export function useQueryParam(key: string): string | null {
  const params = useSearchParams();
  return params.get(key);
}
