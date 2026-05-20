import { useEffect, useRef } from "react";

export interface UseSSEOptions {
  url: string;
  enabled?: boolean;
  onEvent: (data: unknown, event?: string) => void;
  onError?: (err: unknown) => void;
  headers?: Record<string, string>;
}

/**
 * SSE reader hook with explicit cancellation. Consumers don't need to manage
 * the reader lifecycle — unmount cancels the underlying ReadableStream reader
 * and aborts the fetch.
 */
export function useSSE({ url, enabled = true, onEvent, onError, headers }: UseSSEOptions): void {
  const cancelledRef = useRef(false);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  useEffect(() => {
    if (!enabled) return;
    cancelledRef.current = false;
    const ctrl = new AbortController();

    (async () => {
      try {
        const res = await fetch(url, { headers, signal: ctrl.signal });
        if (!res.body) throw new Error("No SSE body");
        const reader = res.body.getReader();
        readerRef.current = reader;
        const decoder = new TextDecoder();
        let buf = "";
        while (!cancelledRef.current) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            const lines = block.split("\n");
            let event: string | undefined;
            let dataStr = "";
            for (const line of lines) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
            }
            if (dataStr) {
              try {
                onEvent(JSON.parse(dataStr), event);
              } catch {
                onEvent(dataStr, event);
              }
            }
          }
        }
      } catch (err) {
        if ((err as { name?: string }).name === "AbortError") return;
        onError?.(err);
      }
    })();

    return () => {
      cancelledRef.current = true;
      readerRef.current?.cancel().catch(() => {});
      ctrl.abort();
    };
  }, [url, enabled, onEvent, onError, headers]);
}
