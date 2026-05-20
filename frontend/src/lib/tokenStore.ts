// External-store pattern for streaming-token state — keeps reads cheap and
// re-renders scoped to subscribers via useSyncExternalStore.

type Listener = () => void;

export interface TokenStore {
  getSnapshot: () => string;
  subscribe: (l: Listener) => () => void;
  append: (chunk: string) => void;
  reset: () => void;
}

export function createTokenStore(): TokenStore {
  let value = "";
  const listeners = new Set<Listener>();
  return {
    getSnapshot: () => value,
    subscribe(l) {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    append(chunk) {
      value += chunk;
      listeners.forEach((l) => l());
    },
    reset() {
      value = "";
      listeners.forEach((l) => l());
    },
  };
}
