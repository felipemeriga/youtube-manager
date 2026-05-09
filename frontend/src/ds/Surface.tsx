import { forwardRef } from "react";
import type { HTMLAttributes } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius } from "./tokens";

const Root = styled("div")({
  background: palette.bg.surface,
  border: `1px solid ${palette.border.subtle}`,
  borderRadius: radius.lg,
  backdropFilter: "blur(16px) saturate(140%)",
});

export const Surface = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function Surface(props, ref) { return <Root ref={ref} {...props} />; },
);
