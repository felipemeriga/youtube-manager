import { Box, Button, Card, LinearProgress, Typography } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
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

  return (
    <Box>
      <Button onClick={onBack} size="small" sx={{ mb: 2 }}>← Back to grid</Button>
      <Box sx={{
        display: "grid", gap: 2,
        gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" },
      }}>
        {selected.map(c => {
          const pct = progress[c.id] ?? 0;
          const done = !!signedUrls[c.id];
          return (
            <Card key={c.id} sx={{ p: 2 }}>
              <Typography variant="caption" sx={{ display: "block", mb: 1 }}>
                {c.hype_reasoning || `Score ${c.hype_score.toFixed(1)}`}
              </Typography>
              {done ? (
                <Button
                  startIcon={<DownloadIcon />}
                  variant="contained"
                  onClick={() => download(c.id)}
                  fullWidth
                >
                  Download
                </Button>
              ) : (
                <>
                  <LinearProgress variant="determinate" value={pct} />
                  <Typography variant="caption">{pct}%</Typography>
                </>
              )}
            </Card>
          );
        })}
      </Box>
    </Box>
  );
}
