import { Box, Button, CircularProgress, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";
import MovieCreationIcon from "@mui/icons-material/MovieCreation";
import type { CaptionStyle } from "../../types/clips";

const CAPTION_STYLE_OPTIONS: { value: CaptionStyle; label: string }[] = [
  { value: "classic", label: "Clássico (branco c/ contorno)" },
  { value: "tiktok", label: "TikTok (Impact gigante)" },
  { value: "bold_yellow", label: "Amarelo destaque" },
  { value: "minimal_box", label: "Caixa preta minimalista" },
  { value: "top_centered", label: "Topo centralizado" },
];

export default function SelectionBar({
  count, onRender, disabled, loading, captionStyle, onCaptionStyleChange,
}: {
  count: number;
  onRender: () => void;
  disabled?: boolean;
  loading?: boolean;
  captionStyle: CaptionStyle;
  onCaptionStyleChange: (style: CaptionStyle) => void;
}) {
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
        flexWrap: "wrap",
      }}
    >
      <Typography variant="body2" sx={{ color: "#a78bfa", fontWeight: 600, mr: 1 }}>
        {count} clip{count > 1 ? "s" : ""} selecionado{count > 1 ? "s" : ""}
      </Typography>
      <FormControl size="small" sx={{ minWidth: 220 }} disabled={loading}>
        <InputLabel id="caption-style-label">Estilo das legendas</InputLabel>
        <Select
          labelId="caption-style-label"
          label="Estilo das legendas"
          value={captionStyle}
          onChange={(e) => onCaptionStyleChange(e.target.value as CaptionStyle)}
        >
          {CAPTION_STYLE_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <Button
        variant="contained"
        onClick={onRender}
        disabled={disabled || loading}
        startIcon={loading
          ? <CircularProgress size={16} sx={{ color: "inherit" }} />
          : <MovieCreationIcon />}
        sx={{ px: 3 }}
      >
        {loading ? "Iniciando…" : "Renderizar clips selecionados"}
      </Button>
    </Box>
  );
}
