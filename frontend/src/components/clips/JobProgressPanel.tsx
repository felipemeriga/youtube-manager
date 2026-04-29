import { Box, LinearProgress, Typography, Button } from "@mui/material";
import type { ClipJob } from "../../types/clips";

const STAGE_LABELS: Record<string, string> = {
  metadata: "Reading video metadata…",
  download: "Downloading video…",
  transcribe: "Transcribing audio…",
  segment: "Scoring clip-worthy moments…",
  preview_render: "Rendering preview clips…",
  final_render: "Rendering final clips…",
};

export default function JobProgressPanel({
  job, onCancel,
}: { job: ClipJob; onCancel: () => void }) {
  const label = STAGE_LABELS[job.current_stage ?? ""] ?? "Working…";
  return (
    <Box sx={{ p: 4, maxWidth: 600, mx: "auto" }}>
      <Typography variant="h6" gutterBottom>{job.title || job.youtube_url}</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>{label}</Typography>
      <LinearProgress variant="determinate" value={job.progress_pct} sx={{ my: 2 }} />
      <Typography variant="caption">{job.progress_pct}%</Typography>
      <Box sx={{ mt: 2 }}>
        <Button onClick={onCancel} color="error" variant="outlined" size="small">
          Cancel
        </Button>
      </Box>
    </Box>
  );
}
