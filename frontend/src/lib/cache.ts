// Tiny stale-while-revalidate cache. No external deps.

import { useEffect, useRef, useState } from "react";

type Entry<T> = { data: T; ts: number };
const store = new Map<string, Entry<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();

export interface QueryOptions {
  ttl?: number;       // ms; below this age data is considered fresh
  swr?: number;       // ms; serve stale up to this age while revalidating
}

const DEFAULT_TTL = 30_000;
const DEFAULT_SWR = 5 * 60_000;

export function getCached<T>(key: string): T | undefined {
  return store.get(key)?.data as T | undefined;
}

export function setCached<T>(key: string, data: T): void {
  store.set(key, { data, ts: Date.now() });
}

export function invalidate(prefix: string): void {
  for (const k of Array.from(store.keys())) {
    if (k.startsWith(prefix)) store.delete(k);
  }
}

export function clearCache(): void {
  store.clear();
}

export function useCachedQuery<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  opts: QueryOptions = {},
): { data: T | undefined; isStale: boolean; error: unknown; refetch: () => void } {
  const { ttl = DEFAULT_TTL, swr = DEFAULT_SWR } = opts;
  const [data, setData] = useState<T | undefined>(() => getCached<T>(key));
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    const abort = new AbortController();

    const entry = store.get(key) as Entry<T> | undefined;
    const age = entry ? Date.now() - entry.ts : Infinity;
    const fresh = age < ttl;

    if (entry) setData(entry.data);

    if (!fresh) {
      // Deduplicate in-flight requests by key.
      let p = inFlight.get(key) as Promise<T> | undefined;
      if (!p) {
        p = fetcher(abort.signal)
          .then((v) => {
            setCached(key, v);
            return v;
          })
          .finally(() => inFlight.delete(key));
        inFlight.set(key, p);
      }
      p.then((v) => {
        if (!mounted.current) return;
        setData(v);
        setError(null);
      }).catch((e) => {
        if (!mounted.current) return;
        if ((e as { name?: string }).name === "AbortError") return;
        setError(e);
      });
    }

    return () => {
      mounted.current = false;
      abort.abort();
    };
    // swr is read once via closure; intentionally omitted from deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick, ttl, fetcher]);

  const isStale = (() => {
    const e = store.get(key);
    if (!e) return true;
    return Date.now() - e.ts > ttl;
  })();

  return {
    data,
    isStale,
    error,
    refetch: () => setTick((t) => t + 1),
  };
}
