import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, typography } from "./tokens";

const Root = styled("select")({
  width: "100%",
  padding: "8px 12px",
  fontSize: "14px",
  fontFamily: typography.fontSans,
  color: palette.text.primary,
  background: palette.bg.inset,
  border: `1px solid ${palette.border.default}`,
  borderRadius: radius.md,
  cursor: "pointer",
  "&:focus-visible": {
    outline: "none",
    borderColor: palette.accent[500],
    boxShadow: `0 0 0 1px ${palette.accent[500]}`,
  },
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select(props, ref) { return <Root ref={ref} {...props} />; },
);
