import { Box, Button, Typography } from "@mui/material";

export default function SelectionBar({
  count, onRender, disabled,
}: { count: number; onRender: () => void; disabled?: boolean }) {
  if (count === 0) return null;
  return (
    <Box sx={{
      position: "sticky", bottom: 0, left: 0, right: 0,
      p: 2, bgcolor: "background.paper",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      zIndex: 2,
    }}>
      <Typography>{count} selected</Typography>
      <Button variant="contained" onClick={onRender} disabled={disabled}>
        Render selected clips
      </Button>
    </Box>
  );
}
