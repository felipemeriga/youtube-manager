import { useEffect, useRef, useState } from "react";
import { Box, Card, Checkbox, Chip, Typography, alpha } from "@mui/material";
import type { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";
import { LazyImage } from "../../ds/LazyImage";

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
  const [posterUrl, setPosterUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    clipsApi.previewUrl(candidate.id, ctrl.signal)
      .then(({ url, poster_url }) => {
        if (ctrl.signal.aborted) return;
        setPreviewUrl(url);
        setPosterUrl(poster_url);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [candidate.id]);

  return (
    <Card
      onClick={onClick}
      sx={{
        position: "relative",
        cursor: "pointer",
        overflow: "hidden",
        aspectRatio: "9 / 16",
        border: selected
          ? "2px solid #5b8def"
          : `1px solid ${alpha("#ffffff", 0.08)}`,
        boxShadow: selected
          ? "0 0 0 4px rgba(91, 141, 239, 0.18), 0 8px 24px rgba(91, 141, 239, 0.25)"
          : "none",
        transition: "all 0.2s ease",
        "&:hover": {
          transform: "translateY(-3px)",
          borderColor: selected ? "#5b8def" : alpha("#5b8def", 0.5),
          boxShadow: selected
            ? "0 0 0 4px rgba(91, 141, 239, 0.22), 0 12px 28px rgba(91, 141, 239, 0.35)"
            : "0 8px 24px rgba(91, 141, 239, 0.2)",
        },
      }}
      onMouseEnter={() => videoRef.current?.play().catch(() => {})}
      onMouseLeave={() => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime = 0; } }}
    >
      {/* Poster image — shown immediately, sits behind the video so the video's
          first-frame transition is invisible. */}
      {posterUrl ? (
        <Box sx={{ position: "absolute", inset: 0 }}>
          <LazyImage src={posterUrl} alt="" />
        </Box>
      ) : (
        <Box sx={{
          position: "absolute", inset: 0,
          width: "100%", height: "100%",
          background: "rgba(91,141,239,0.08)",
        }} />
      )}
      {previewUrl && (
        <video
          ref={videoRef}
          src={previewUrl}
          poster={posterUrl ?? undefined}
          muted
          loop
          playsInline
          preload="metadata"
          style={{
            position: "absolute", inset: 0,
            width: "100%", height: "100%",
            objectFit: "cover", display: "block",
          }}
        />
      )}

      {/* Gradient overlay for legibility */}
      <Box sx={{
        position: "absolute", inset: 0,
        background: "linear-gradient(180deg, rgba(0,0,0,0.45) 0%, transparent 25%, transparent 55%, rgba(15,15,20,0.95) 100%)",
        pointerEvents: "none",
      }} />

      {/* Hype score (top-left) */}
      <Chip
        label={`★ ${candidate.hype_score.toFixed(1)}`}
        size="small"
        sx={{
          position: "absolute",
          top: 10,
          left: 10,
          fontWeight: 700,
          color: "white",
          backgroundColor: "#5b8def",
          boxShadow: "0 2px 8px rgba(91, 141, 239, 0.4)",
          border: "none",
        }}
      />

      {/* Selection checkbox (top-right) */}
      <Checkbox
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={onToggleSelect}
        sx={{
          position: "absolute",
          top: 4,
          right: 4,
          color: "white",
          backgroundColor: "rgba(0,0,0,0.35)",
          backdropFilter: "blur(8px)",
          borderRadius: 2,
          padding: "4px",
          "&:hover": { backgroundColor: "rgba(0,0,0,0.5)" },
          "&.Mui-checked": { color: "primary.light" },
        }}
      />

      {/* Duration chip (bottom-right, above caption) */}
      <Chip
        label={`${Math.round(candidate.duration_seconds)}s`}
        size="small"
        sx={{
          position: "absolute",
          bottom: candidate.hype_reasoning ? 78 : 56,
          right: 10,
          fontWeight: 600,
          color: "white",
          backgroundColor: "rgba(15,15,20,0.75)",
          backdropFilter: "blur(8px)",
          border: "1px solid rgba(255,255,255,0.1)",
        }}
      />

      {/* Caption */}
      <Box sx={{
        position: "absolute", bottom: 0, left: 0, right: 0,
        p: 1.25, pt: 2,
      }}>
        <Typography variant="caption" sx={{
          color: "rgba(255,255,255,0.95)",
          fontWeight: 600,
          fontVariantNumeric: "tabular-nums",
          textShadow: "0 1px 2px rgba(0,0,0,0.6)",
        }}>
          {formatTime(candidate.start_seconds)} → {formatTime(candidate.end_seconds)}
        </Typography>
        {candidate.hype_reasoning && (
          <Typography variant="caption" sx={{
            color: "rgba(255,255,255,0.78)",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            textShadow: "0 1px 2px rgba(0,0,0,0.6)",
            lineHeight: 1.35,
            mt: 0.25,
          }}>
            {candidate.hype_reasoning}
          </Typography>
        )}
      </Box>
    </Card>
  );
}
