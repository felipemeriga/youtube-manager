import { useState } from "react";
import {
  Box, Button, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Stack, TextField, Typography, Alert,
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import { clipsApi } from "../../api/clips";
import { ensureNotificationPermission } from "../../lib/notify";

export default function NewJobForm({ onCreated }: { onCreated: (jobId: string) => void }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ duration: number; title: string } | null>(null);

  async function submit() {
    setError(null);
    setLoading(true);
    // Lazy permission request — must happen from a user gesture so the
    // "Clips prontos" notification can fire when the pipeline completes.
    ensureNotificationPermission();
    try {
      const meta = await clipsApi.preflight(url);
      if (meta.duration_seconds > 1800) {
        setConfirm({ duration: meta.duration_seconds, title: meta.title });
      } else {
        await create();
      }
    } catch (e: any) { setError(e.message || "Verificação prévia falhou"); }
    finally { setLoading(false); }
  }

  async function create() {
    setLoading(true);
    try {
      const job = await clipsApi.createJob(url);
      onCreated(job.id);
      setUrl("");
      setConfirm(null);
    } catch (e: any) { setError(e.message || "Falha ao criar trabalho"); }
    finally { setLoading(false); }
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="h6" sx={{ mb: 0.5 }}>
            Gerar clips a partir de um vídeo
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Cole qualquer URL do youtube.com ou youtu.be. Melhores resultados com vídeos de até 60 minutos.
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1.5 }}>
          <TextField
            fullWidth
            placeholder="https://youtube.com/watch?v=..."
            value={url}
            onChange={e => setUrl(e.target.value)}
            disabled={loading}
            onKeyDown={(e) => { if (e.key === "Enter" && url && !loading) submit(); }}
          />
          <Button
            variant="contained"
            onClick={submit}
            disabled={loading || !url}
            startIcon={loading
              ? <CircularProgress size={16} sx={{ color: "inherit" }} />
              : <AutoAwesomeIcon />}
            sx={{ px: 3, minWidth: 170, whiteSpace: "nowrap" }}
          >
            {loading ? "Processando…" : "Gerar clips"}
          </Button>
        </Box>
        <Typography variant="caption" color="text.secondary">
          O processamento leva ~2 min por minuto de vídeo.
        </Typography>
        {error && <Alert severity="error" sx={{ mt: 0 }}>{error}</Alert>}
      </Stack>
      <Dialog open={!!confirm} onClose={() => setConfirm(null)}>
        <DialogTitle>Vídeo longo</DialogTitle>
        <DialogContent>
          {confirm && (
            <Typography>
              "{confirm.title}" tem {Math.round(confirm.duration / 60)} min de duração.
              O processamento levará ~{Math.round(confirm.duration / 30)} min e usará
              recurso computacional significativo. Continuar?
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>Cancelar</Button>
          <Button onClick={create} variant="contained">Continuar</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
