import { forwardRef } from "react";
import type { TextareaHTMLAttributes } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, typography, motion } from "./tokens";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

const Root = styled("textarea", { shouldForwardProp: (p) => p !== "invalid" })<{ invalid: boolean }>(
  ({ invalid }) => ({
    width: "100%",
    padding: "10px 12px",
    fontSize: "14px",
    fontFamily: typography.fontSans,
    color: palette.text.primary,
    background: palette.bg.inset,
    border: `1px solid ${invalid ? palette.status.danger : palette.border.default}`,
    borderRadius: radius.md,
    resize: "vertical",
    minHeight: 80,
    transition: `border-color ${motion.duration.base} ${motion.easing}`,
    "&:focus-visible": {
      outline: "none",
      borderColor: palette.accent[500],
      boxShadow: `0 0 0 1px ${palette.accent[500]}`,
    },
  }),
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid = false, ...rest }, ref,
) {
  return <Root ref={ref} invalid={invalid} {...rest} />;
});
