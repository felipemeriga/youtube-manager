// Lightweight wrapper around the Notifications API. Asking for permission must
// happen in response to a user gesture, so callers do that explicitly via
// `ensureNotificationPermission()` before relying on `notify()`.

export type NotifyPermissionState = "granted" | "denied" | "default" | "unsupported";

export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function notificationPermission(): NotifyPermissionState {
  if (!notificationsSupported()) return "unsupported";
  return Notification.permission;
}

/** Request permission. Must be called from a user gesture handler (click, etc). */
export async function ensureNotificationPermission(): Promise<NotifyPermissionState> {
  if (!notificationsSupported()) return "unsupported";
  if (Notification.permission === "granted" || Notification.permission === "denied") {
    return Notification.permission;
  }
  try {
    const result = await Notification.requestPermission();
    return result;
  } catch {
    return "default";
  }
}

/** Show a notification if permission has already been granted. Silent no-op otherwise. */
export function notify(title: string, body?: string): void {
  if (!notificationsSupported()) return;
  if (Notification.permission !== "granted") return;
  try {
    // Focus the originating tab if user clicks the notification.
    const n = new Notification(title, { body, silent: false });
    n.onclick = () => {
      try { window.focus(); } catch { /* noop */ }
      n.close();
    };
  } catch {
    // Ignore — some browsers throw inside iframes / restricted contexts.
  }
}
