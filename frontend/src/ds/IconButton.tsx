import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, motion } from "./tokens";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  size?: "sm" | "md";
  "aria-label": string;
  children: ReactNode;
}

const Root = styled("button", { shouldForwardProp: (p) => p !== "size" })<{ size: "sm" | "md" }>(
  ({ size }) => ({
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: size === "sm" ? 28 : 32,
    height: size === "sm" ? 28 : 32,
    background: "transparent",
    color: palette.text.secondary,
    border: "1px solid transparent",
    borderRadius: radius.md,
    cursor: "pointer",
    transition: `background-color ${motion.duration.base} ${motion.easing}, color ${motion.duration.base} ${motion.easing}`,
    "&:hover:not(:disabled)": { backgroundColor: palette.accent[50], color: palette.text.primary },
    "&:focus-visible": {
      outline: "none",
      boxShadow: `0 0 0 2px ${palette.bg.canvas}, 0 0 0 4px ${palette.accent[500]}`,
    },
    "&:disabled": { opacity: 0.5, cursor: "not-allowed" },
  }),
);

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { size = "md", children, ...rest },
  ref,
) {
  return <Root ref={ref} size={size} {...rest}>{children}</Root>;
});
