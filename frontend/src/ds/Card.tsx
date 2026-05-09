import { forwardRef } from "react";
import type { HTMLAttributes } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius } from "./tokens";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean;
  flush?: boolean;
}

const Root = styled("div", {
  shouldForwardProp: (p) => p !== "padded" && p !== "flush",
})<{ padded: boolean; flush: boolean }>(({ padded, flush }) => ({
  background: palette.bg.surface,
  border: `1px solid ${palette.border.subtle}`,
  borderRadius: radius.lg,
  padding: flush ? 0 : padded ? "20px" : "16px",
}));

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { padded = false, flush = false, children, ...rest },
  ref,
) {
  return <Root ref={ref} padded={padded} flush={flush} {...rest}>{children}</Root>;
});
