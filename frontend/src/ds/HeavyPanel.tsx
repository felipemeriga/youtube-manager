import { Suspense, type ReactNode } from "react";
import { Skeleton } from "./Skeleton";

export interface HeavyPanelProps {
  fallback?: ReactNode;
  children?: ReactNode;
}

/**
 * Suspense boundary with a Skeleton fallback. Wrap any `React.lazy` component
 * that should render a placeholder while its chunk loads.
 *
 *     const ScriptViewer = lazy(() => import("./ScriptViewer"));
 *     <HeavyPanel><ScriptViewer ... /></HeavyPanel>
 *
 * For prefetch-on-hover, see `useHeavyPrefetch`.
 */
export function HeavyPanel({ fallback, children }: HeavyPanelProps) {
  return <Suspense fallback={fallback ?? <Skeleton style={{ height: 240 }} />}>{children}</Suspense>;
}

/** Returns a callback that warms a `React.lazy` chunk on first invocation. */
export function useHeavyPrefetch(load: () => Promise<unknown>): () => void {
  let warmed = false;
  return () => {
    if (warmed) return;
    warmed = true;
    void load();
  };
}
