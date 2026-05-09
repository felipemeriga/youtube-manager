import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, motion, typography } from "./tokens";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
}

const Root = styled("button", {
  shouldForwardProp: (p) => p !== "variant" && p !== "size",
})<{ variant: Variant; size: Size }>(({ variant, size }) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  fontFamily: typography.fontSans,
  fontWeight: 500,
  fontSize: size === "sm" ? "12px" : "13px",
  lineHeight: 1,
  padding: size === "sm" ? "6px 10px" : "8px 14px",
  borderRadius: radius.md,
  border: "1px solid transparent",
  cursor: "pointer",
  transition: `background-color ${motion.duration.base} ${motion.easing}, color ${motion.duration.base} ${motion.easing}, border-color ${motion.duration.base} ${motion.easing}`,
  ...(variant === "primary" && {
    backgroundColor: palette.accent[500],
    color: "#fff",
    "&:hover:not(:disabled)": { backgroundColor: palette.accent[600] },
  }),
  ...(variant === "secondary" && {
    backgroundColor: palette.bg.surface,
    color: palette.text.primary,
    borderColor: palette.border.default,
    "&:hover:not(:disabled)": { borderColor: palette.border.strong },
  }),
  ...(variant === "ghost" && {
    backgroundColor: "transparent",
    color: palette.text.secondary,
    "&:hover:not(:disabled)": { backgroundColor: palette.accent[50], color: palette.text.primary },
  }),
  ...(variant === "danger" && {
    backgroundColor: palette.status.danger,
    color: "#fff",
    "&:hover:not(:disabled)": { filter: "brightness(0.95)" },
  }),
  "&:disabled": { opacity: 0.5, cursor: "not-allowed" },
  "&:focus-visible": {
    outline: "none",
    boxShadow: `0 0 0 2px ${palette.bg.canvas}, 0 0 0 4px ${palette.accent[500]}`,
  },
}));

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", startIcon, endIcon, children, ...rest },
  ref,
) {
  return (
    <Root ref={ref} variant={variant} size={size} {...rest}>
      {startIcon}
      {children}
      {endIcon}
    </Root>
  );
});
