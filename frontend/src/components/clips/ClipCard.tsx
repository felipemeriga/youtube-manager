import { useEffect, useRef, useState } from "react";
import { Box, Card, Checkbox, Chip, Typography } from "@mui/material";
import type { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function ClipCard({
  candidate, selected, onToggleSelect, onClick,
}: {
  candidate: ClipCandidate;
  selected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let mounted = true;
    clipsApi.previewUrl(candidate.id)
      .then(({ url }) => { if (mounted) setPreviewUrl(url); })
      .catch(() => {});
    return () => { mounted = false; };
  }, [candidate.id]);

  return (
    <Card
      onClick={onClick}
      sx={{ position: "relative", cursor: "pointer", overflow: "hidden", aspectRatio: "9 / 16" }}
      onMouseEnter={() => videoRef.current?.play().catch(() => {})}
      onMouseLeave={() => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime = 0; } }}
    >
      {previewUrl ? (
        <video
          ref={videoRef}
          src={previewUrl}
          muted
          loop
          playsInline
          preload="metadata"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <Box sx={{ width: "100%", height: "100%", bgcolor: "rgba(255,255,255,0.04)" }} />
      )}
      <Chip
        label={candidate.hype_score.toFixed(1)}
        size="small"
        color="primary"
        sx={{ position: "absolute", top: 8, left: 8, fontWeight: 600 }}
      />
      <Checkbox
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={onToggleSelect}
        sx={{ position: "absolute", top: 0, right: 0, color: "white",
          "&.Mui-checked": { color: "#a78bfa" } }}
      />
      <Box sx={{ position: "absolute", bottom: 0, left: 0, right: 0,
                 p: 1, bgcolor: "rgba(0,0,0,0.6)" }}>
        <Typography variant="caption" sx={{ color: "white" }}>
          {formatTime(candidate.start_seconds)} → {formatTime(candidate.end_seconds)} · {Math.round(candidate.duration_seconds)}s
        </Typography>
        {candidate.hype_reasoning && (
          <Typography variant="caption" sx={{ color: "rgba(255,255,255,0.7)", display: "block" }}>
            {candidate.hype_reasoning}
          </Typography>
        )}
      </Box>
    </Card>
  );
}
