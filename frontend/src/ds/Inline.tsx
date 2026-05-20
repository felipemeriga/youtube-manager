import { forwardRef } from "react";
import type { HTMLAttributes } from "react";
import { styled } from "@mui/material/styles";

export interface InlineProps extends HTMLAttributes<HTMLDivElement> {
  gap?: number;
  align?: "start" | "center" | "end" | "baseline";
  wrap?: boolean;
}

const Root = styled("div", {
  shouldForwardProp: (p) => p !== "gap" && p !== "align" && p !== "wrap",
})<{ gap: number; align: NonNullable<InlineProps["align"]>; wrap: boolean }>(
  ({ gap, align, wrap }) => ({
    display: "flex",
    flexDirection: "row",
    gap: `${gap * 4}px`,
    alignItems:
      align === "baseline"
        ? "baseline"
        : align === "start"
          ? "flex-start"
          : align === "end"
            ? "flex-end"
            : "center",
    flexWrap: wrap ? "wrap" : "nowrap",
  }),
);

export const Inline = forwardRef<HTMLDivElement, InlineProps>(function Inline(
  { gap = 2, align = "center", wrap = false, ...rest },
  ref,
) {
  return <Root ref={ref} gap={gap} align={align} wrap={wrap} {...rest} />;
});
