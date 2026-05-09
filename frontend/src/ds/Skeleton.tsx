import { styled, keyframes } from "@mui/material/styles";
import { palette, radius } from "./tokens";

const shimmer = keyframes`
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
`;

export const Skeleton = styled("div", { shouldForwardProp: (p) => p !== "rounded" })<{
  rounded?: boolean;
}>(({ rounded }) => ({
  background: `linear-gradient(90deg, ${palette.bg.inset} 0%, ${palette.bg.surface} 50%, ${palette.bg.inset} 100%)`,
  backgroundSize: "200% 100%",
  animation: `${shimmer} 1.4s linear infinite`,
  borderRadius: rounded ? radius.pill : radius.md,
  "@media (prefers-reduced-motion: reduce)": { animation: "none" },
}));
