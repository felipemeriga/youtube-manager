import { Box, Button, CircularProgress, Typography } from "@mui/material";
import MovieCreationIcon from "@mui/icons-material/MovieCreation";

export default function SelectionBar({
  count, onRender, disabled, loading,
}: { count: number; onRender: () => void; disabled?: boolean; loading?: boolean }) {
  if (count === 0) return null;
  return (
    <Box
      sx={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1300,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        py: 1.5,
        px: 3,
        backgroundColor: "rgba(15,15,25,0.85)",
        backdropFilter: "blur(12px)",
        borderTop: "1px solid rgba(124,58,237,0.3)",
      }}
    >
      <Typography variant="body2" sx={{ color: "#a78bfa", fontWeight: 600, mr: 1 }}>
        {count} clip{count > 1 ? "s" : ""} selected
      </Typography>
      <Button
        variant="contained"
        onClick={onRender}
        disabled={disabled || loading}
        startIcon={loading
          ? <CircularProgress size={16} sx={{ color: "inherit" }} />
          : <MovieCreationIcon />}
        sx={{ px: 3 }}
      >
        {loading ? "Starting…" : "Render selected clips"}
      </Button>
    </Box>
  );
}
