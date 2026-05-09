import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";
import { Snackbar } from "@mui/material";
import { Toast, type ToastTone } from "../ds/Toast";

type Severity = "error" | "warning" | "info" | "success";

const SEVERITY_TO_TONE: Record<Severity, ToastTone> = {
  error: "danger",
  warning: "warning",
  info: "info",
  success: "success",
};

interface ToastState {
  message: string;
  severity: Severity;
}

interface ToastContextValue {
  showToast: (message: string, severity?: Severity) => void;
  showError: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);

  const showToast = useCallback((message: string, severity: Severity = "info") => {
    setToast({ message, severity });
  }, []);

  const showError = useCallback((message: string) => {
    setToast({ message, severity: "error" });
  }, []);

  // Auto-dismiss after 5s.
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const value = useMemo(() => ({ showToast, showError }), [showToast, showError]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Snackbar
        open={Boolean(toast)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        {toast ? (
          <div onClick={() => setToast(null)} style={{ cursor: "pointer" }}>
            <Toast tone={SEVERITY_TO_TONE[toast.severity]}>{toast.message}</Toast>
          </div>
        ) : undefined}
      </Snackbar>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
