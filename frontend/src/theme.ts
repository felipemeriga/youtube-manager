import { createTheme, alpha } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#7c3aed", light: "#a78bfa", dark: "#5b21b6" },
    secondary: { main: "#3b82f6", light: "#93c5fd", dark: "#2563eb" },
    success: { main: "#10b981" },
    error: { main: "#ef4444" },
    warning: { main: "#f59e0b" },
    background: {
      default: "#0f0f14",
      paper: "rgba(23, 23, 32, 0.68)",
    },
    divider: "rgba(255, 255, 255, 0.06)",
  },
  typography: {
    fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
    h1: { fontWeight: 700, letterSpacing: "-0.025em" },
    h2: { fontWeight: 700, letterSpacing: "-0.025em" },
    h3: { fontWeight: 700, letterSpacing: "-0.025em" },
    h4: { fontWeight: 700, letterSpacing: "-0.025em" },
    h5: { fontWeight: 600, letterSpacing: "-0.025em" },
    h6: { fontWeight: 600, letterSpacing: "-0.025em" },
    body1: { letterSpacing: "-0.01em", lineHeight: 1.6 },
    body2: { letterSpacing: "-0.01em", lineHeight: 1.6 },
    button: { fontWeight: 500 },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: 10,
          transition: "all 0.2s ease",
        },
        contained: {
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          boxShadow: "0 2px 8px rgba(124, 58, 237, 0.25)",
          "&:hover": {
            background: "linear-gradient(135deg, #6d28d9, #2563eb)",
            boxShadow: "0 4px 12px rgba(124, 58, 237, 0.35)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backdropFilter: "blur(20px)",
          backgroundColor: "rgba(23, 23, 32, 0.68)",
          border: `1px solid ${alpha("#ffffff", 0.06)}`,
          borderRadius: 16,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 10,
            transition: "all 0.2s ease",
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8 },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundImage: "none",
          backdropFilter: "blur(20px)",
          backgroundColor: "rgba(18, 18, 25, 0.95)",
          border: `1px solid ${alpha("#ffffff", 0.08)}`,
          borderRadius: 16,
        },
      },
    },
  },
});

export default theme;
