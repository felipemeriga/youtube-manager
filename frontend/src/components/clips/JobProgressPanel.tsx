import { Box, Button, LinearProgress, Paper, Stack, Typography, alpha } from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import type { ClipJob, ClipJobStage } from "../../types/clips";

const STAGE_LABELS: Record<string, string> = {
  metadata: "Lendo metadados do vídeo…",
  download: "Baixando vídeo…",
  transcribe: "Transcrevendo áudio…",
  segment: "Avaliando momentos para clips…",
  preview_render: "Renderizando prévias…",
  final_render: "Renderizando clips finais…",
  download_source: "Carregando vídeo original…",
  extract_audio: "Extraindo áudio para legendas…",
  render_finals: "Renderizando clips em alta resolução…",
  done: "Concluído",
};

const STAGE_ORDER: ClipJobStage[] = [
  "download",
  "transcribe",
  "segment",
  "preview_render",
];

const STAGE_SHORT: Record<ClipJobStage, string> = {
  metadata: "Início",
  download: "Download",
  transcribe: "Transcrição",
  segment: "Análise",
  preview_render: "Renderização",
  await_selection: "Seleção",
  final_render: "Final",
  download_source: "Fonte",
  extract_audio: "Áudio",
  render_finals: "Render",
  done: "Concluído",
};

function stageIndex(stage: ClipJobStage | null | undefined): number {
  if (!stage) return -1;
  const idx = STAGE_ORDER.indexOf(stage);
  if (idx >= 0) return idx;
  if (stage === "metadata") return -1;
  // Stages past preview_render mean previous stages are done.
  return STAGE_ORDER.length;
}

export default function JobProgressPanel({
  job, onCancel,
}: { job: ClipJob; onCancel: () => void }) {
  const label = STAGE_LABELS[job.current_stage ?? ""] ?? "Processando…";
  const activeIdx = stageIndex(job.current_stage);

  return (
    <Box sx={{ p: 4, maxWidth: 640, mx: "auto" }}>
      <Paper sx={{ p: 4 }}>
        <Stack spacing={3}>
          <Box>
            <Typography variant="h6" sx={{ mb: 0.5 }}>
              {job.title || job.youtube_url}
            </Typography>
            <Typography variant="body2" color="text.secondary">{label}</Typography>
          </Box>

          {/* Stage breadcrumb */}
          <Stack direction="row" spacing={0} alignItems="center" sx={{ flexWrap: "wrap", rowGap: 1 }}>
            {STAGE_ORDER.map((s, i) => {
              const done = i < activeIdx;
              const active = i === activeIdx;
              return (
                <Stack
                  key={s}
                  direction="row"
                  alignItems="center"
                  spacing={0.75}
                  sx={{
                    color: done ? "success.main" : active ? "primary.light" : "text.disabled",
                    fontWeight: active ? 600 : 500,
                    mr: i < STAGE_ORDER.length - 1 ? 1.5 : 0,
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
                    {STAGE_SHORT[s]}
                  </Typography>
                  {i < STAGE_ORDER.length - 1 && (
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

          {/* Progress bar */}
          <Box>
            <LinearProgress
              variant="determinate"
              value={job.progress_pct}
              sx={{
                height: 8,
                borderRadius: 4,
                backgroundColor: alpha("#ffffff", 0.06),
                "& .MuiLinearProgress-bar": {
                  background: "linear-gradient(90deg, #7c3aed, #3b82f6)",
                  borderRadius: 4,
                },
              }}
            />
            <Typography
              variant="caption"
              sx={{ mt: 1, display: "block", color: "text.secondary", fontVariantNumeric: "tabular-nums" }}
            >
              {job.progress_pct}%
            </Typography>
          </Box>

          <Box>
            <Button onClick={onCancel} color="error" variant="outlined" size="small">
              Cancelar trabalho
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}
