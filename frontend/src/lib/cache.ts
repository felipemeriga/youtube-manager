// Tiny stale-while-revalidate cache. No external deps.

import { useEffect, useRef, useState } from "react";

type Entry<T> = { data: T; ts: number };
type FlightEntry = { promise: Promise<unknown>; ctrl: AbortController };
const store = new Map<string, Entry<unknown>>();
const inFlight = new Map<string, FlightEntry>();

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
  const { ttl = DEFAULT_TTL } = opts;
  // `swr` (stale-while-revalidate window) is reserved for future use; data is
  // always returned immediately when present and refetched in the background
  // when stale, regardless of the configured swr window.
  void DEFAULT_SWR;
  const [data, setData] = useState<T | undefined>(() => getCached<T>(key));
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);
  const mounted = useRef(true);
  const lastKeyRef = useRef(key);

  // Sync `data` to the cache for the *current* key whenever the key prop
  // changes — without this, `data` retains the previous key's value until
  // the effect runs (one render of stale data on every key switch).
  if (lastKeyRef.current !== key) {
    lastKeyRef.current = key;
    const cached = getCached<T>(key);
    if (data !== cached) setData(cached);
  }

  useEffect(() => {
    mounted.current = true;
    const abort = new AbortController();

    const entry = store.get(key) as Entry<T> | undefined;
    const age = entry ? Date.now() - entry.ts : Infinity;
    const fresh = age < ttl;

    if (entry) setData(entry.data);

    if (!fresh) {
      // Reuse an in-flight promise IF AND ONLY IF its abort signal is still
      // live. Under React StrictMode (and any other mount→unmount→remount
      // cycle), the first mount's controller aborts when its cleanup runs;
      // attaching to that already-rejected promise from the second mount used
      // to silently swallow the AbortError and leave `data` undefined forever.
      // Tracking the controller per inFlight entry lets us drop a dead promise
      // and issue a fresh fetch when the prior mount has aborted.
      type Flight = { promise: Promise<T>; ctrl: AbortController };
      let flight = inFlight.get(key) as Flight | undefined;
      if (flight && flight.ctrl.signal.aborted) {
        inFlight.delete(key);
        flight = undefined;
      }
      if (!flight) {
        const promise = fetcher(abort.signal)
          .then((v) => {
            setCached(key, v);
            return v;
          })
          .finally(() => {
            // Only clear if we're still the registered flight (a later mount
            // may have replaced us after an abort).
            if (inFlight.get(key) && (inFlight.get(key) as Flight).ctrl === abort) {
              inFlight.delete(key);
            }
          });
        flight = { promise, ctrl: abort };
        inFlight.set(key, flight);
      }
      flight.promise.then((v) => {
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
