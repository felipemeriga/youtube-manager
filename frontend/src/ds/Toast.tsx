import { styled, keyframes } from "@mui/material/styles";
import { palette, radius } from "./tokens";
import type { ReactNode } from "react";

const slideIn = keyframes`
  from { transform: translateY(8px); opacity: 0; }
  to   { transform: translateY(0);   opacity: 1; }
`;

export type ToastTone = "info" | "success" | "warning" | "danger";

const ACCENT: Record<ToastTone, string> = {
  info: palette.accent[500],
  success: palette.status.success,
  warning: palette.status.warning,
  danger: palette.status.danger,
};

const Wrap = styled("div", { shouldForwardProp: (p) => p !== "tone" })<{ tone: ToastTone }>(
  ({ tone }) => ({
    display: "flex",
    gap: 10,
    padding: "10px 14px",
    minWidth: 280,
    background: palette.bg.elevated,
    border: `1px solid ${palette.border.default}`,
    borderLeft: `3px solid ${ACCENT[tone]}`,
    borderRadius: radius.md,
    color: palette.text.primary,
    fontSize: 13,
    boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
    animation: `${slideIn} 180ms cubic-bezier(0.2, 0.8, 0.2, 1)`,
    "@media (prefers-reduced-motion: reduce)": { animation: "none" },
  }),
);

export function Toast({ tone = "info", children }: { tone?: ToastTone; children: ReactNode }) {
  return (
    <Wrap tone={tone} role="status">
      {children}
    </Wrap>
  );
}
