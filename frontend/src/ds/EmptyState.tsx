import type { ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, typography } from "./tokens";

const Wrap = styled("div")({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  textAlign: "center",
  padding: 48,
  border: `1px dashed ${palette.border.default}`,
  borderRadius: 14,
  color: palette.text.secondary,
});
const Icon = styled("div")({ marginBottom: 12, color: palette.text.tertiary });
const Title = styled("div")({ ...typography.scale.heading, color: palette.text.primary, marginBottom: 4 });
const Body = styled("div")({
  ...typography.scale.small,
  color: palette.text.secondary,
  maxWidth: 360,
  marginBottom: 16,
});

export function EmptyState({
  icon, title, body, cta,
}: { icon?: ReactNode; title: string; body?: ReactNode; cta?: ReactNode }) {
  return (
    <Wrap>
      {icon && <Icon>{icon}</Icon>}
      <Title>{title}</Title>
      {body && <Body>{body}</Body>}
      {cta}
    </Wrap>
  );
}
