import { Box, Typography } from "@mui/material";

export default function App() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
      }}
    >
      <Typography
        variant="h4"
        sx={{
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        YouTube Manager
      </Typography>
    </Box>
  );
}
