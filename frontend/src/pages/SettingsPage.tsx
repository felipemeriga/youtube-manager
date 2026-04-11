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
  IconButton,
  List,
  ListItem,
  ListItemText,
  Divider,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import {
  getPersona,
  upsertPersona,
  listMemories,
  deleteMemory,
} from "../lib/api";
import type { Memory, ScriptSection } from "../lib/api";
import ScriptTemplateBuilder from "../components/ScriptTemplateBuilder";

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
  const [memories, setMemories] = useState<Memory[]>([]);
  const [scriptTemplate, setScriptTemplate] = useState<ScriptSection[]>([]);

  useEffect(() => {
    Promise.all([
      getPersona().catch(() => null),
      listMemories().catch(() => []),
    ])
      .then(([persona, mems]) => {
        if (persona) {
          setChannelName(persona.channel_name);
          setLanguage(persona.language);
          setPersonaText(persona.persona_text);
          setScriptTemplate(persona.script_template || []);
        }
        setMemories(mems);
      })
      .catch(() => {
        setSnackbar({
          open: true,
          message: "Falha ao carregar configurações",
          severity: "error",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!channelName.trim() || !language.trim() || !personaText.trim()) {
      setSnackbar({
        open: true,
        message: "Todos os campos são obrigatórios",
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
        script_template: scriptTemplate,
      });
      setSnackbar({
        open: true,
        message: "Persona salva com sucesso",
        severity: "success",
      });
    } catch {
      setSnackbar({
        open: true,
        message: "Falha ao salvar persona",
        severity: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      setSnackbar({
        open: true,
        message: "Falha ao excluir memória",
        severity: "error",
      });
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
          Persona do Canal
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
          Configure a identidade do seu canal. Esta persona é usada pelo gerador de roteiros para combinar com seu estilo.
        </Typography>

        <TextField
          label="Nome do Canal"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value)}
          fullWidth
          required
        />

        <TextField
          label="Idioma"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          fullWidth
          required
          placeholder="ex: Português Brasileiro, Inglês, Espanhol"
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
            "Exemplo:\n" +
            "- Tom: Descontraído e informativo\n" +
            "- Humor: Piadas de programação e referências de tech\n" +
            "- Abordagem: Começa com ganchos provocativos\n" +
            "- Estilo: Linguagem acessível\n" +
            "- Evita: Jargão excessivo"
          }
        />

        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving}
          sx={{ alignSelf: "flex-end", minWidth: 120 }}
        >
          {saving ? <CircularProgress size={20} /> : "Salvar"}
        </Button>
      </Paper>

      <ScriptTemplateBuilder
        sections={scriptTemplate}
        onChange={setScriptTemplate}
      />

      <Paper
        sx={{
          width: "100%",
          maxWidth: 640,
          p: 4,
          mt: 3,
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Preferências Aprendidas
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
          Extraídas automaticamente do feedback dos seus roteiros. Ajudam a IA a combinar com seu estilo ao longo do tempo.
        </Typography>

        {memories.length === 0 ? (
          <Typography
            variant="body2"
            sx={{ color: "rgba(255,255,255,0.3)", py: 2 }}
          >
            Nenhuma preferência aprendida ainda. Elas aparecerão aqui conforme você aprova e rejeita roteiros.
          </Typography>
        ) : (
          <List disablePadding>
            {memories.map((memory, index) => (
              <Box key={memory.id}>
                {index > 0 && (
                  <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />
                )}
                <ListItem
                  secondaryAction={
                    <IconButton
                      edge="end"
                      onClick={() => handleDeleteMemory(memory.id)}
                      sx={{
                        color: "rgba(255,255,255,0.3)",
                        "&:hover": { color: "#ef4444" },
                      }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  }
                  sx={{ px: 0, pr: 6 }}
                >
                  <ListItemText
                    primary={memory.content}
                    primaryTypographyProps={{ variant: "body2" }}
                  />
                </ListItem>
              </Box>
            ))}
          </List>
        )}
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
