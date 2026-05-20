import type { ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, typography } from "./tokens";

const Wrap = styled("div")({
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  marginBottom: 12,
});
const Label = styled("div")({ ...typography.scale.micro, color: palette.text.tertiary });
const Title = styled("h2")({ ...typography.scale.heading, color: palette.text.primary, margin: 0 });

export function SectionHeader({
  label, title, meta,
}: { label?: string; title: string; meta?: ReactNode }) {
  return (
    <Wrap>
      <div>
        {label && <Label>{label}</Label>}
        <Title>{title}</Title>
      </div>
      {meta && <div>{meta}</div>}
    </Wrap>
  );
}
