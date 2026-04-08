import { useEffect, useState } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  Snackbar,
  Alert,
  CircularProgress,
} from "@mui/material";
import { getPersona, upsertPersona } from "../lib/api";

export default function SettingsPage() {
  const [channelName, setChannelName] = useState("");
  const [language, setLanguage] = useState("");
  const [personaText, setPersonaText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  useEffect(() => {
    getPersona()
      .then((persona) => {
        if (persona) {
          setChannelName(persona.channel_name);
          setLanguage(persona.language);
          setPersonaText(persona.persona_text);
        }
      })
      .catch(() => {
        setSnackbar({
          open: true,
          message: "Failed to load persona",
          severity: "error",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!channelName.trim() || !language.trim() || !personaText.trim()) {
      setSnackbar({
        open: true,
        message: "All fields are required",
        severity: "error",
      });
      return;
    }

    setSaving(true);
    try {
      await upsertPersona({
        channel_name: channelName.trim(),
        language: language.trim(),
        persona_text: personaText.trim(),
      });
      setSnackbar({
        open: true,
        message: "Persona saved successfully",
        severity: "success",
      });
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to save persona",
        severity: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        p: 4,
        overflow: "auto",
      }}
    >
      <Paper
        sx={{
          width: "100%",
          maxWidth: 640,
          p: 4,
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Channel Persona
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
          Configure your channel identity. This persona is used by the script
          generator to match your style.
        </Typography>

        <TextField
          label="Channel Name"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value)}
          fullWidth
          required
        />

        <TextField
          label="Language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          fullWidth
          required
          placeholder="e.g. Brazilian Portuguese, English, Spanish"
        />

        <TextField
          label="Persona"
          value={personaText}
          onChange={(e) => setPersonaText(e.target.value)}
          fullWidth
          required
          multiline
          minRows={6}
          maxRows={16}
          placeholder={
            "Describe your channel's personality, tone, style, humor, what to avoid...\n\n" +
            "Example:\n" +
            "Tone: conversational, informal, provocative\n" +
            "Humor: uses humor naturally, not forced\n" +
            "Approach: takes a position, never neutral\n" +
            "Style: direct, uses real examples, challenges conventional wisdom\n" +
            "Avoid: sounding like a guru, generic advice, corporate tone"
          }
        />

        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving}
          sx={{ alignSelf: "flex-end", minWidth: 120 }}
        >
          {saving ? <CircularProgress size={20} /> : "Save"}
        </Button>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
