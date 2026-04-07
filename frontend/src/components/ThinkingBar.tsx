import { Box, Typography, LinearProgress } from "@mui/material";

const STAGE_LABELS: Record<string, string> = {
  analyzing: "Analyzing your assets...",
  generating: "Generating thumbnail...",
  finding_trends: "Searching for recent trends...",
  writing_script: "Researching & writing full script...",
  saving: "Saving script...",
};

export default function ThinkingBar({ stage }: { stage: string }) {
  return (
    <Box sx={{ px: 3, py: 1.5 }}>
      <Box
        sx={{
          p: 1.5,
          borderRadius: 2,
          backgroundColor: "rgba(124, 58, 237, 0.1)",
          border: "1px solid rgba(124, 58, 237, 0.2)",
        }}
      >
        <Typography
          variant="caption"
          color="primary"
          sx={{ mb: 0.5, display: "block" }}
        >
          {STAGE_LABELS[stage] || stage}
        </Typography>
        <LinearProgress
          sx={{
            borderRadius: 1,
            backgroundColor: "rgba(124, 58, 237, 0.1)",
            "& .MuiLinearProgress-bar": {
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            },
          }}
        />
      </Box>
    </Box>
  );
}
