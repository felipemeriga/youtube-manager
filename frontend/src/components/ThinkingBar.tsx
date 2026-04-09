import { Box, Typography } from "@mui/material";

const STAGE_LABELS: Record<string, string> = {
  analyzing: "Researching trends & creating creative brief...",
  generating: "Generating thumbnail...",
  finding_trends: "Searching for recent trends...",
  writing_script: "Researching & writing full script...",
  saving: "Saving script...",
  thinking: "Thinking...",
};

export default function ThinkingBar({ stage }: { stage: string }) {
  return (
    <Box
      sx={{
        px: 3,
        py: 1.5,
        "@keyframes fadeSlideIn": {
          from: { opacity: 0, transform: "translateY(4px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        animation: "fadeSlideIn 0.2s ease-out",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          p: 1.5,
          borderRadius: 2.5,
          backgroundColor: "rgba(124, 58, 237, 0.08)",
          border: "1px solid rgba(124, 58, 237, 0.15)",
          backdropFilter: "blur(10px)",
        }}
      >
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: "#7c3aed",
            "@keyframes pulse": {
              "0%, 100%": { opacity: 1 },
              "50%": { opacity: 0.4 },
            },
            animation: "pulse 1.5s ease-in-out infinite",
          }}
        />
        <Typography
          variant="caption"
          sx={{ color: "#a78bfa", fontWeight: 500, letterSpacing: "0.02em" }}
        >
          {STAGE_LABELS[stage] || stage}
        </Typography>
      </Box>
    </Box>
  );
}
