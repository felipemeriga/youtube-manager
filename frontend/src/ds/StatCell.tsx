import type { ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, typography } from "./tokens";

const Wrap = styled("div")({ display: "flex", flexDirection: "column", gap: 4 });
const Label = styled("div")({ ...typography.scale.micro, color: palette.text.tertiary });
const Value = styled("div")({
  fontFamily: typography.fontMono,
  fontVariantNumeric: "tabular-nums",
  fontSize: "20px",
  fontWeight: 500,
  color: palette.text.primary,
});
const Delta = styled("div")({ ...typography.scale.caption, color: palette.status.success });

export function StatCell({
  label, value, delta,
}: { label: string; value: ReactNode; delta?: ReactNode }) {
  return (
    <Wrap>
      <Label>{label}</Label>
      <Value>{value}</Value>
      {delta && <Delta>{delta}</Delta>}
    </Wrap>
  );
}
