import type { HTMLAttributes, ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius } from "./tokens";

const Root = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  fontSize: "10px",
  fontWeight: 600,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  padding: "1px 8px",
  border: `1px solid ${palette.border.default}`,
  borderRadius: radius.sm,
  color: palette.text.secondary,
});

export interface PillProps extends HTMLAttributes<HTMLSpanElement> { children: ReactNode; }
export function Pill({ children, ...rest }: PillProps) { return <Root {...rest}>{children}</Root>; }
