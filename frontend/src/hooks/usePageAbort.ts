import { useEffect, useRef } from "react";

/**
 * Page-scoped AbortController. Returns helpers to:
 *  - get the current signal (to pass to fetch / api functions)
 *  - check whether a thrown error came from the abort (so we can swallow it)
 *
 * On unmount or when `key` changes (e.g. route id), the previous controller is
 * aborted, killing every in-flight request that received its signal. This is
 * the correct fix for stale requests piling up when a user navigates between
 * pages on a slow connection.
 */
export function usePageAbort(key?: string | null) {
  const ctrlRef = useRef<AbortController>(new AbortController());

  // Re-create on key change (e.g. switching jobs/conversations) so requests
  // tied to the previous key are cancelled immediately.
  useEffect(() => {
    ctrlRef.current = new AbortController();
    return () => {
      ctrlRef.current.abort();
    };
  }, [key]);

  return {
    /** Stable getter — always returns the current controller's signal. */
    getSignal: () => ctrlRef.current.signal,
    /** True if the error is from a fetch abort (DOMException name === "AbortError"). */
    isAbort: (err: unknown): boolean =>
      err instanceof DOMException
        ? err.name === "AbortError"
        : (err as { name?: string } | null)?.name === "AbortError",
  };
}
