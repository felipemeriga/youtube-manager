import { Link, type LinkProps } from "react-router-dom";

const prefetchers: Record<string, () => Promise<unknown>> = {
  "/": () => import("../pages/ChatPage"),
  "/assets": () => import("../pages/AssetsPage"),
  "/clips": () => import("../pages/ClipsPage"),
  "/settings": () => import("../pages/SettingsPage"),
};

const warmed = new Set<string>();

/**
 * Warm the JS chunk for a route. First call kicks off the dynamic import;
 * subsequent calls for the same path are no-ops. Safe to call from anywhere
 * that has a hover/focus event for a navigation target — including
 * `<IconButton onMouseEnter={() => prefetchRoute("/assets")}>`.
 */
export function prefetchRoute(to: string): void {
  if (warmed.has(to)) return;
  warmed.add(to);
  const exact = prefetchers[to];
  if (exact) {
    void exact();
    return;
  }
  if (to.startsWith("/clips/")) void import("../pages/ClipJobPage");
}

export function PrefetchLink(props: LinkProps) {
  const to = typeof props.to === "string" ? props.to : "";
  return (
    <Link
      {...props}
      onMouseEnter={(e) => {
        prefetchRoute(to);
        props.onMouseEnter?.(e);
      }}
      onTouchStart={(e) => {
        prefetchRoute(to);
        props.onTouchStart?.(e);
      }}
      onFocus={(e) => {
        prefetchRoute(to);
        props.onFocus?.(e);
      }}
    />
  );
}
