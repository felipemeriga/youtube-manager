import { forwardRef } from "react";
import type { HTMLAttributes } from "react";
import { styled } from "@mui/material/styles";

export interface StackProps extends HTMLAttributes<HTMLDivElement> {
  gap?: number;
  align?: "start" | "center" | "end" | "stretch";
}

const Root = styled("div", { shouldForwardProp: (p) => p !== "gap" && p !== "align" })<{
  gap: number;
  align: NonNullable<StackProps["align"]>;
}>(({ gap, align }) => ({
  display: "flex",
  flexDirection: "column",
  gap: `${gap * 4}px`,
  alignItems:
    align === "stretch"
      ? "stretch"
      : align === "start"
        ? "flex-start"
        : align === "end"
          ? "flex-end"
          : "center",
}));

export const Stack = forwardRef<HTMLDivElement, StackProps>(function Stack(
  { gap = 2, align = "stretch", ...rest },
  ref,
) {
  return <Root ref={ref} gap={gap} align={align} {...rest} />;
});
