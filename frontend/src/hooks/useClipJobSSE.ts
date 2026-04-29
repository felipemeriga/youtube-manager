import { useEffect, useRef } from "react";
import { JobEvent } from "../types/clips";
import { supabase } from "../lib/supabase";

export function useClipJobSSE(
  jobId: string | null,
  onEvent: (e: JobEvent) => void,
) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let abort: AbortController | null = null;

    (async () => {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? "";
      abort = new AbortController();
      try {
        const resp = await fetch(`/api/clips/jobs/${jobId}/events`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: abort.signal,
        });
        if (!resp.ok || !resp.body) return;
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const events = buf.split("\n\n");
          buf = events.pop() ?? "";
          for (const block of events) {
            const dataLine = block
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (!dataLine) continue;
            try {
              const parsed: JobEvent = JSON.parse(dataLine.slice(6));
              handlerRef.current(parsed);
            } catch {
              /* heartbeat or malformed; ignore */
            }
          }
        }
      } catch {
        /* aborted */
      }
    })();

    return () => {
      cancelled = true;
      abort?.abort();
    };
  }, [jobId]);
}
