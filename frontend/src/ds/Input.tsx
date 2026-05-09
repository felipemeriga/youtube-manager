import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, typography, motion } from "./tokens";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

const Root = styled("input", { shouldForwardProp: (p) => p !== "invalid" })<{ invalid: boolean }>(
  ({ invalid }) => ({
    width: "100%",
    padding: "8px 12px",
    fontSize: "14px",
    fontFamily: typography.fontSans,
    color: palette.text.primary,
    background: palette.bg.inset,
    border: `1px solid ${invalid ? palette.status.danger : palette.border.default}`,
    borderRadius: radius.md,
    transition: `border-color ${motion.duration.base} ${motion.easing}`,
    "&::placeholder": { color: palette.text.tertiary },
    "&:hover:not(:disabled)": { borderColor: palette.border.strong },
    "&:focus-visible": {
      outline: "none",
      borderColor: palette.accent[500],
      boxShadow: `0 0 0 1px ${palette.accent[500]}`,
    },
    "&:disabled": { opacity: 0.5, cursor: "not-allowed" },
  }),
);

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid = false, ...rest }, ref,
) {
  return <Root ref={ref} invalid={invalid} {...rest} />;
});
