import { useSyncExternalStore } from "react";
import type { ReactElement } from "react";
import type { TokenStore } from "../lib/tokenStore";

/**
 * Subscribes to a TokenStore and re-renders only when tokens append, leaving
 * sibling components untouched. Use this to render the streaming tail of a
 * chat message while the static message list stays memoized.
 */
export function StreamingTail({
  store,
  render,
}: {
  store: TokenStore;
  render: (text: string) => ReactElement;
}) {
  const text = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  return render(text);
}
