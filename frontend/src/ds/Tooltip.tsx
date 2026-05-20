import { Tooltip as MuiTooltip, type TooltipProps } from "@mui/material";
import { palette } from "./tokens";

export function Tooltip(props: TooltipProps) {
  return (
    <MuiTooltip
      {...props}
      arrow
      slotProps={{
        tooltip: {
          sx: {
            background: palette.bg.elevated,
            color: palette.text.primary,
            border: `1px solid ${palette.border.default}`,
            fontSize: 12,
          },
        },
        arrow: { sx: { color: palette.bg.elevated } },
      }}
    />
  );
}
