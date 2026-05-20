import { styled } from "@mui/material/styles";
import { palette } from "./tokens";

type Tone = "ok" | "warn" | "danger" | "neutral";
const TONE: Record<Tone, string> = {
  ok: palette.status.success,
  warn: palette.status.warning,
  danger: palette.status.danger,
  neutral: palette.status.neutral,
};

const Dot = styled("span", { shouldForwardProp: (p) => p !== "tone" })<{ tone: Tone }>(
  ({ tone }) => ({
    display: "inline-block",
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: TONE[tone],
    flexShrink: 0,
  }),
);

export function StatusDot({ tone = "neutral" }: { tone?: Tone }) {
  return <Dot tone={tone} aria-hidden="true" />;
}
