import { Link, type LinkProps } from "react-router-dom";

const prefetchers: Record<string, () => Promise<unknown>> = {
  "/": () => import("../pages/ChatPage"),
  "/assets": () => import("../pages/AssetsPage"),
  "/clips": () => import("../pages/ClipsPage"),
  "/settings": () => import("../pages/SettingsPage"),
};

const warmed = new Set<string>();

function prefetch(to: string) {
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
        prefetch(to);
        props.onMouseEnter?.(e);
      }}
      onTouchStart={(e) => {
        prefetch(to);
        props.onTouchStart?.(e);
      }}
      onFocus={(e) => {
        prefetch(to);
        props.onFocus?.(e);
      }}
    />
  );
}
