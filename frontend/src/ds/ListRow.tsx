import { forwardRef } from "react";
import type { HTMLAttributes, ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius, motion } from "./tokens";

export interface ListRowProps extends HTMLAttributes<HTMLDivElement> {
  leading?: ReactNode;
  meta?: ReactNode;
  trailing?: ReactNode;
  active?: boolean;
  interactive?: boolean;
}

const Root = styled("div", {
  shouldForwardProp: (p) => p !== "active" && p !== "interactive",
})<{ active: boolean; interactive: boolean }>(({ active, interactive }) => ({
  display: "grid",
  gridTemplateColumns: "auto 1fr auto auto",
  alignItems: "center",
  gap: 12,
  padding: "10px 12px",
  borderRadius: radius.md,
  cursor: interactive ? "pointer" : "default",
  background: active ? palette.accent[50] : "transparent",
  borderBottom: `1px solid ${palette.border.subtle}`,
  transition: `background-color ${motion.duration.base} ${motion.easing}`,
  "&:hover": interactive ? { background: palette.accent[50] } : undefined,
  "&:focus-visible": interactive
    ? { outline: "none", boxShadow: `0 0 0 2px ${palette.bg.canvas}, 0 0 0 4px ${palette.accent[500]}` }
    : undefined,
}));

const Content = styled("div")({ minWidth: 0 });

export const ListRow = forwardRef<HTMLDivElement, ListRowProps>(function ListRow(
  { leading, children, meta, trailing, active = false, interactive = false, ...rest },
  ref,
) {
  return (
    <Root
      ref={ref}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      active={active}
      interactive={interactive}
      {...rest}
    >
      <div>{leading}</div>
      <Content>{children}</Content>
      <div>{meta}</div>
      <div>{trailing}</div>
    </Root>
  );
});
