// Design tokens — single source of truth for the DS.

export const palette = {
  bg: {
    canvas: "#0b0e14",
    surface: "#11151d",
    elevated: "#161b25",
    inset: "#0d1119",
  },
  border: {
    subtle: "rgba(255,255,255,0.06)",
    default: "rgba(255,255,255,0.10)",
    strong: "rgba(255,255,255,0.16)",
  },
  text: {
    primary: "#e6e8ee",
    secondary: "#9098a8",
    tertiary: "#5d6478",
    disabled: "#3a3f4d",
  },
  accent: {
    50: "rgba(91,141,239,0.10)",
    500: "#5b8def",
    600: "#4a7ad8",
  },
  status: {
    success: "#3ecf8e",
    warning: "#f5a524",
    danger: "#ef5a6f",
    neutral: "#6b7283",
  },
} as const;

export const typography = {
  fontSans: "'Inter', system-ui, -apple-system, sans-serif",
  fontMono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
  scale: {
    display: { fontSize: "28px", lineHeight: 1.2, fontWeight: 600, letterSpacing: "-0.03em" },
    title:   { fontSize: "20px", lineHeight: 1.3, fontWeight: 600, letterSpacing: "-0.02em" },
    heading: { fontSize: "16px", lineHeight: 1.4, fontWeight: 600, letterSpacing: "-0.015em" },
    body:    { fontSize: "14px", lineHeight: 1.55, fontWeight: 400, letterSpacing: "-0.005em" },
    small:   { fontSize: "13px", lineHeight: 1.5, fontWeight: 400, letterSpacing: "0" },
    caption: { fontSize: "12px", lineHeight: 1.4, fontWeight: 500, letterSpacing: "0.01em" },
    micro:   { fontSize: "11px", lineHeight: 1.3, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const },
    numeric: { fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontWeight: 500, fontVariantNumeric: "tabular-nums" as const },
  },
} as const;

// 4px base scale: spacing(2) = 8px, spacing(0.5) = 2px.
export const spacing = (n: number): string => `${n * 4}px`;

export const radius = {
  sm: "4px",
  md: "6px",
  lg: "10px",
  xl: "14px",
  pill: "999px",
} as const;

export const motion = {
  duration: { fast: "120ms", base: "180ms", slow: "280ms" },
  easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
} as const;

export const elevation = {
  glass: {
    background: palette.bg.surface,
    border: `1px solid ${palette.border.subtle}`,
    backdropFilter: "blur(16px) saturate(140%)",
  },
  modal: {
    background: palette.bg.elevated,
    border: `1px solid ${palette.border.default}`,
    boxShadow: "0 20px 48px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3)",
  },
} as const;

export const focusRing = {
  outline: "none",
  boxShadow: `0 0 0 2px ${palette.bg.canvas}, 0 0 0 4px ${palette.accent[500]}`,
} as const;

export type Palette = typeof palette;
export type Typography = typeof typography;
