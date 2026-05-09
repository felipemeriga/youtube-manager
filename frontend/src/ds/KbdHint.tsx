import { styled } from "@mui/material/styles";
import { palette, typography, radius } from "./tokens";
import type { ReactNode } from "react";

const Kbd = styled("kbd")({
  display: "inline-flex",
  alignItems: "center",
  fontFamily: typography.fontMono,
  fontSize: 11,
  padding: "1px 6px",
  border: `1px solid ${palette.border.default}`,
  borderBottomWidth: 2,
  borderRadius: radius.sm,
  background: palette.bg.inset,
  color: palette.text.secondary,
});

export function KbdHint({ children }: { children: ReactNode }) {
  return <Kbd>{children}</Kbd>;
}
