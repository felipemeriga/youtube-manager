import type { ReactNode } from "react";
import { styled } from "@mui/material/styles";
import { palette, typography } from "./tokens";

const Wrap = styled("header")({
  display: "flex",
  alignItems: "flex-end",
  justifyContent: "space-between",
  gap: 16,
  paddingBottom: 16,
  borderBottom: `1px solid ${palette.border.subtle}`,
  marginBottom: 20,
});

const Eyebrow = styled("div")({ ...typography.scale.micro, color: palette.text.tertiary, marginBottom: 4 });
const Title = styled("h1")({ ...typography.scale.title, color: palette.text.primary, margin: 0 });
const Subtitle = styled("div")({ ...typography.scale.small, color: palette.text.secondary, marginTop: 4 });
const Actions = styled("div")({ display: "flex", gap: 8 });

export interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, subtitle, actions }: PageHeaderProps) {
  return (
    <Wrap>
      <div>
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <Title>{title}</Title>
        {subtitle && <Subtitle>{subtitle}</Subtitle>}
      </div>
      {actions && <Actions>{actions}</Actions>}
    </Wrap>
  );
}
