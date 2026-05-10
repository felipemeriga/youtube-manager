import { useEffect, useState } from "react";
import {
  Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, LinearProgress, Paper, Stack, Tooltip, Typography,
} from "@mui/material";
import MovieFilterIcon from "@mui/icons-material/MovieFilter";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useNavigate } from "react-router-dom";
import type { ClipJobStatus, ClipJobSummary } from "../types/clips";
import { clipsApi } from "../api/clips";
import NewJobForm from "../components/clips/NewJobForm";
import { usePageAbort } from "../hooks/usePageAbort";

const STATUS_COLOR: Record<ClipJobStatus, "default" | "primary" | "secondary" | "success" | "error" | "warning"> = {
  pending: "warning",
  processing: "primary",
  ready: "secondary",
  rendering: "primary",
  completed: "success",
  failed: "error",
  expired: "default",
};

const STATUS_LABEL: Record<ClipJobStatus, string> = {
  pending: "Aguardando",
  processing: "Processando",
  ready: "Pronto",
  rendering: "Renderizando",
  completed: "Concluído",
  failed: "Falhou",
  expired: "Expirado",
};

const RUNNING: ClipJobStatus[] = ["pending", "processing", "rendering"];

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60_000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h} h`;
  const days = Math.floor(h / 24);
  if (days < 7) return `há ${days} d`;
  return d.toLocaleDateString("pt-BR");
}

function formatDuration(sec: number | null): string {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ClipsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ClipJobSummary[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<ClipJobSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { getSignal, isAbort } = usePageAbort();

  useEffect(() => {
    const signal = getSignal();
    let cancelled = false;

    const refresh = () => {
      clipsApi.listJobs(signal)
        .then((data) => { if (!cancelled && !signal.aborted) setJobs(data); })
        .catch((err) => { if (!isAbort(err)) throw err; });
    };
    refresh();

    return () => { cancelled = true; };
  // getSignal/isAbort are stable for the page lifetime.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Active-only polling: refresh the list every 5s while any job is in a
  // running state. Stops automatically when all jobs settle. Avoids hammering
  // the backend when nothing is in flight.
  useEffect(() => {
    const hasActive = jobs.some((j) => RUNNING.includes(j.status));
    if (!hasActive) return;
    const signal = getSignal();
    const id = window.setInterval(() => {
      clipsApi.listJobs(signal)
        .then((data) => { if (!signal.aborted) setJobs(data); })
        .catch((err) => { if (!isAbort(err)) throw err; });
    }, 5000);
    return () => window.clearInterval(id);
  // getSignal/isAbort stable.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  async function handleDelete() {
    if (!confirmDelete) return;
    setDeleting(true);
    const signal = getSignal();
    try {
      await clipsApi.deleteJob(confirmDelete.id, signal);
      setJobs((prev) => prev.filter((j) => j.id !== confirmDelete.id));
      setConfirmDelete(null);
    } catch (e) {
      if (isAbort(e)) return;
      throw e;
    } finally {
      if (!signal.aborted) setDeleting(false);
    }
  }

  return (
    <Box sx={{ px: 3, py: 3, maxWidth: 880, mx: "auto", width: "100%", overflowY: "auto" }}>
      <Typography variant="h4" sx={{ mb: 2, fontWeight: 700 }}>
        Clips do YouTube
      </Typography>

      <NewJobForm onCreated={(id) => navigate(`/clips/${id}`)} />

      <Typography
        variant="overline"
        sx={{ mt: 3, mb: 1, display: "block", color: "text.secondary", letterSpacing: "0.08em" }}
      >
        Trabalhos anteriores
      </Typography>

      {jobs.length === 0 ? (
        <Paper
          sx={{
            p: 6,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            gap: 1.5,
          }}
        >
          <MovieFilterIcon sx={{ fontSize: 48, color: "primary.light", opacity: 0.6 }} />
          <Typography variant="subtitle1">Nenhum trabalho ainda</Typography>
          <Typography variant="body2" color="text.secondary">
            Cole uma URL do YouTube acima para gerar seus primeiros clips.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.25}>
          {jobs.map((j) => {
            const isRunning = RUNNING.includes(j.status);
            return (
              <Paper
                key={j.id}
                onClick={() => navigate(`/clips/${j.id}`)}
                sx={{
                  px: 2.5,
                  py: 1.75,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  "&:hover": {
                    transform: "translateY(-1px)",
                    borderColor: "rgba(124, 58, 237, 0.4)",
                    boxShadow: "0 4px 16px rgba(124, 58, 237, 0.15)",
                  },
                }}
              >
                <Stack direction="row" alignItems="center" spacing={2}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="body1"
                      noWrap
                      sx={{ fontWeight: 500, mb: 0.25 }}
                      title={j.title || j.youtube_url}
                    >
                      {j.title || j.youtube_url}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDuration(j.duration_seconds)} · {formatRelative(j.created_at)}
                    </Typography>
                    {isRunning && (
                      <LinearProgress
                        variant="determinate"
                        value={j.progress_pct}
                        sx={{
                          mt: 1,
                          height: 4,
                          borderRadius: 2,
                          backgroundColor: "rgba(255,255,255,0.06)",
                          "& .MuiLinearProgress-bar": {
                            backgroundColor: "#5b8def",
                            borderRadius: 2,
                          },
                        }}
                      />
                    )}
                  </Box>
                  <Chip
                    label={STATUS_LABEL[j.status]}
                    size="small"
                    color={STATUS_COLOR[j.status]}
                    variant={j.status === "completed" || j.status === "failed" ? "filled" : "outlined"}
                    sx={{ fontWeight: 500 }}
                  />
                  <Tooltip title="Excluir trabalho" placement="left">
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDelete(j);
                      }}
                      sx={{
                        color: "text.disabled",
                        "&:hover": {
                          color: "error.main",
                          backgroundColor: "rgba(239,68,68,0.08)",
                        },
                      }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      )}

      <Dialog open={!!confirmDelete} onClose={() => !deleting && setConfirmDelete(null)}>
        <DialogTitle>Excluir este trabalho?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            "{confirmDelete?.title || confirmDelete?.youtube_url}" — todos os candidatos,
            clips de prévia e renderizações finais serão excluídos permanentemente.
            Esta ação não pode ser desfeita.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(null)} disabled={deleting}>
            Cancelar
          </Button>
          <Button
            onClick={handleDelete}
            disabled={deleting}
            color="error"
            variant="contained"
          >
            {deleting ? "Excluindo…" : "Excluir"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
