import type { HTMLAttributes, ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius } from "./tokens";

type Tone = "ok" | "warn" | "danger" | "neutral";
type Style = "subtle" | "solid";

const TONE_FG: Record<Tone, string> = {
  ok: palette.status.success,
  warn: palette.status.warning,
  danger: palette.status.danger,
  neutral: palette.text.secondary,
};

const Root = styled("span", { shouldForwardProp: (p) => p !== "tone" && p !== "styleVariant" })<{
  tone: Tone; styleVariant: Style;
}>(({ tone, styleVariant }) => ({
  display: "inline-flex",
  alignItems: "center",
  fontSize: "11px",
  fontWeight: 600,
  letterSpacing: "0.04em",
  padding: "2px 8px",
  borderRadius: radius.pill,
  ...(styleVariant === "subtle"
    ? { background: `${TONE_FG[tone]}1f`, color: TONE_FG[tone] }
    : { background: TONE_FG[tone], color: "#fff" }),
}));

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone; variant?: Style; children: ReactNode;
}

export function Badge({ tone = "neutral", variant = "subtle", children, ...rest }: BadgeProps) {
  return <Root tone={tone} styleVariant={variant} {...rest}>{children}</Root>;
}
