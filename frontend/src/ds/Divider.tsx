import { styled } from "@mui/material/styles";
import { palette } from "./tokens";

export const Divider = styled("hr")({
  border: 0,
  height: 1,
  background: palette.border.subtle,
  margin: 0,
});
