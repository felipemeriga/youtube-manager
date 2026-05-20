import { Dialog, IconButton, Box, Typography, Chip, Stack, alpha } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useEffect, useState } from "react";
import type { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function ClipPreviewModal({
  candidate, open, onClose,
}: { candidate: ClipCandidate | null; open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate) { setUrl(null); return; }
    const ctrl = new AbortController();
    clipsApi.previewUrl(candidate.id, ctrl.signal)
      .then((r) => { if (!ctrl.signal.aborted) setUrl(r.url); })
      .catch(() => {});
    return () => ctrl.abort();
  }, [candidate]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { overflow: "hidden" } }}
    >
      <Box sx={{ position: "relative", bgcolor: "black" }}>
        <IconButton
          onClick={onClose}
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            color: "white",
            zIndex: 2,
            backgroundColor: "rgba(15,15,20,0.6)",
            backdropFilter: "blur(8px)",
            "&:hover": { backgroundColor: "rgba(15,15,20,0.85)" },
          }}
        >
          <CloseIcon />
        </IconButton>

        {/* Score chip top-left */}
        {candidate && (
          <Chip
            label={`★ ${candidate.hype_score.toFixed(1)}`}
            size="small"
            sx={{
              position: "absolute",
              top: 12,
              left: 12,
              zIndex: 2,
              fontWeight: 700,
              color: "white",
              backgroundColor: "#5b8def",
              boxShadow: "0 2px 8px rgba(91, 141, 239, 0.4)",
            }}
          />
        )}

        {url ? (
          <video
            src={url}
            controls
            autoPlay
            style={{
              width: "100%",
              maxHeight: "80vh",
              display: "block",
              backgroundColor: "black",
            }}
          />
        ) : (
          <Box sx={{ aspectRatio: "9 / 16", maxHeight: "80vh", width: "100%" }} />
        )}
      </Box>

      {candidate && (
        <Box sx={{ p: 2.5, borderTop: `1px solid ${alpha("#ffffff", 0.06)}` }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: candidate.hype_reasoning ? 1 : 0 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", fontVariantNumeric: "tabular-nums" }}>
              {formatTime(candidate.start_seconds)} → {formatTime(candidate.end_seconds)}
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              · {Math.round(candidate.duration_seconds)}s
            </Typography>
          </Stack>
          {candidate.hype_reasoning && (
            <Typography variant="body2" sx={{ color: "text.primary" }}>
              {candidate.hype_reasoning}
            </Typography>
          )}
        </Box>
      )}
    </Dialog>
  );
}
