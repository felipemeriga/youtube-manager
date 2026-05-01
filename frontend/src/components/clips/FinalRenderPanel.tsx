import { Box, Button, LinearProgress, Paper, Stack, Typography, alpha } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import type { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

export default function FinalRenderPanel({
  selected, progress, signedUrls, onBack,
}: {
  selected: ClipCandidate[];
  progress: Record<string, number>;
  signedUrls: Record<string, string>;
  onBack: () => void;
}) {
  async function download(id: string) {
    const url = signedUrls[id] ?? (await clipsApi.finalUrl(id)).url;
    const a = document.createElement("a");
    a.href = url;
    a.download = `clip-${id}.mp4`;
    a.click();
  }

  const isDone = (c: ClipCandidate) => !!signedUrls[c.id] || !!c.final_storage_key;
  const completedCount = selected.filter(isDone).length;

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 3 }}>
        <Button onClick={onBack} startIcon={<ArrowBackIcon />} size="small" color="inherit">
          Voltar à grade
        </Button>
        <Box sx={{ flex: 1 }} />
        <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600 }}>
          {completedCount} / {selected.length} prontos
        </Typography>
      </Stack>

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" },
        }}
      >
        {selected.map((c) => {
          const pct = progress[c.id] ?? (c.final_storage_key ? 100 : 0);
          const done = isDone(c);
          return (
            <Paper
              key={c.id}
              sx={{
                p: 2.5,
                display: "flex",
                flexDirection: "column",
                gap: 1.5,
                transition: "all 0.2s ease",
                border: done
                  ? `1px solid ${alpha("#10b981", 0.4)}`
                  : `1px solid ${alpha("#ffffff", 0.06)}`,
              }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" sx={{
                  fontWeight: 700,
                  color: "primary.light",
                  fontVariantNumeric: "tabular-nums",
                }}>
                  ★ {c.hype_score.toFixed(1)}
                </Typography>
                {done && (
                  <CheckCircleRoundedIcon sx={{ fontSize: 16, color: "success.main" }} />
                )}
              </Stack>

              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                  minHeight: "3.6em",
                  lineHeight: 1.5,
                }}
              >
                {c.hype_reasoning || `Clip · ${Math.round(c.duration_seconds)}s`}
              </Typography>

              {done ? (
                <Button
                  startIcon={<DownloadIcon />}
                  variant="contained"
                  onClick={() => download(c.id)}
                  fullWidth
                >
                  Baixar
                </Button>
              ) : (
                <Box>
                  <LinearProgress
                    variant="determinate"
                    value={pct}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      backgroundColor: alpha("#ffffff", 0.06),
                      "& .MuiLinearProgress-bar": {
                        background: "linear-gradient(90deg, #7c3aed, #3b82f6)",
                        borderRadius: 3,
                      },
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{
                      mt: 0.75,
                      display: "block",
                      color: "text.secondary",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    Renderizando… {pct}%
                  </Typography>
                </Box>
              )}
            </Paper>
          );
        })}
      </Box>
    </Box>
  );
}
