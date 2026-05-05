import { Box, Button, LinearProgress, Paper, Stack, Typography, alpha } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import type { ClipCandidate, ClipJobStage } from "../../types/clips";
import { clipsApi } from "../../api/clips";

const RENDER_STAGE_LABELS: Record<string, string> = {
  download_source: "Carregando vídeo original…",
  extract_audio: "Extraindo áudio…",
  transcribe: "Transcrevendo legendas…",
  render_finals: "Renderizando clips em 1080p…",
  done: "Concluído",
};

const RENDER_STAGE_ORDER: ClipJobStage[] = [
  "download_source",
  "extract_audio",
  "transcribe",
  "render_finals",
];

const RENDER_STAGE_SHORT: Partial<Record<ClipJobStage, string>> = {
  download_source: "Fonte",
  extract_audio: "Áudio",
  transcribe: "Legendas",
  render_finals: "Render",
};

function renderStageIndex(stage: ClipJobStage | null | undefined): number {
  if (!stage) return -1;
  const idx = RENDER_STAGE_ORDER.indexOf(stage);
  if (idx >= 0) return idx;
  if (stage === "done") return RENDER_STAGE_ORDER.length;
  return -1;
}

export default function FinalRenderPanel({
  selected, progress, signedUrls, onBack, currentStage, allDone,
}: {
  selected: ClipCandidate[];
  progress: Record<string, number>;
  signedUrls: Record<string, string>;
  onBack: () => void;
  currentStage: ClipJobStage | null;
  allDone: boolean;
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
  const stageLabel = currentStage
    ? RENDER_STAGE_LABELS[currentStage] ?? "Processando…"
    : allDone ? "Concluído" : "Iniciando…";
  const activeStageIdx = renderStageIndex(currentStage);

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

      {!allDone && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Stack spacing={2} alignItems="center">
            <Typography variant="body2" color="text.secondary">{stageLabel}</Typography>

            {/* Stage breadcrumb — centered, the only global progress indicator. */}
            <Stack
              direction="row"
              spacing={0}
              alignItems="center"
              justifyContent="center"
              sx={{ flexWrap: "wrap", rowGap: 1 }}
            >
              {RENDER_STAGE_ORDER.map((s, i) => {
                const done = i < activeStageIdx;
                const active = i === activeStageIdx;
                return (
                  <Stack
                    key={s}
                    direction="row"
                    alignItems="center"
                    spacing={0.75}
                    sx={{
                      color: done ? "success.main" : active ? "primary.light" : "text.disabled",
                      fontWeight: active ? 600 : 500,
                      mr: i < RENDER_STAGE_ORDER.length - 1 ? 1.5 : 0,
                    }}
                  >
                    {done ? (
                      <CheckCircleRoundedIcon sx={{ fontSize: 16 }} />
                    ) : (
                      <RadioButtonUncheckedRoundedIcon sx={{
                        fontSize: 16,
                        animation: active ? "pulse 1.5s ease-in-out infinite" : "none",
                        "@keyframes pulse": {
                          "0%, 100%": { opacity: 1 },
                          "50%": { opacity: 0.4 },
                        },
                      }} />
                    )}
                    <Typography variant="caption" sx={{ fontWeight: "inherit" }}>
                      {RENDER_STAGE_SHORT[s]}
                    </Typography>
                    {i < RENDER_STAGE_ORDER.length - 1 && (
                      <Box sx={{
                        width: 16,
                        height: 1,
                        ml: 1,
                        backgroundColor: done ? "success.main" : alpha("#ffffff", 0.1),
                      }} />
                    )}
                  </Stack>
                );
              })}
            </Stack>
          </Stack>
        </Paper>
      )}

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
