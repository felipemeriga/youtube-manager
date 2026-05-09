import { createTheme, alpha } from "@mui/material/styles";
import { palette, typography, radius, motion } from "./tokens";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: palette.accent[500], light: palette.accent[500], dark: palette.accent[600] },
    secondary: { main: palette.text.secondary },
    success: { main: palette.status.success },
    error: { main: palette.status.danger },
    warning: { main: palette.status.warning },
    background: {
      default: palette.bg.canvas,
      paper: palette.bg.surface,
    },
    divider: palette.border.subtle,
    text: {
      primary: palette.text.primary,
      secondary: palette.text.secondary,
      disabled: palette.text.disabled,
    },
  },
  typography: {
    fontFamily: typography.fontSans,
    h1: { ...typography.scale.display },
    h2: { ...typography.scale.title },
    h3: { ...typography.scale.heading },
    body1: { ...typography.scale.body },
    body2: { ...typography.scale.small },
    button: { fontWeight: 500, textTransform: "none" },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: radius.lg,
          transition: `background-color ${motion.duration.base} ${motion.easing}, color ${motion.duration.base} ${motion.easing}`,
          fontWeight: 500,
        },
        contained: {
          backgroundColor: palette.accent[500],
          color: "#fff",
          boxShadow: "none",
          "&:hover": { backgroundColor: palette.accent[600], boxShadow: "none" },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: palette.bg.surface,
          border: `1px solid ${palette.border.subtle}`,
          borderRadius: radius.lg,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: radius.md,
            backgroundColor: palette.bg.inset,
          },
        },
      },
    },
    MuiChip: { styleOverrides: { root: { borderRadius: radius.md } } },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundImage: "none",
          backgroundColor: palette.bg.elevated,
          border: `1px solid ${palette.border.default}`,
          borderRadius: radius.lg,
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: palette.bg.canvas,
          color: palette.text.primary,
          fontFeatureSettings: '"cv11", "ss01"',
        },
        "*:focus-visible": {
          outline: "none",
          boxShadow: `0 0 0 2px ${palette.bg.canvas}, 0 0 0 4px ${alpha(palette.accent[500], 0.9)}`,
        },
        "@media (prefers-reduced-motion: reduce)": {
          "*": {
            animation: "none !important",
            transition: "none !important",
          },
        },
      },
    },
  },
});

export default theme;
