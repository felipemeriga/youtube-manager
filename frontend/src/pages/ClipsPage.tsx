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
  pending: "Pending",
  processing: "Processing",
  ready: "Ready",
  rendering: "Rendering",
  completed: "Completed",
  failed: "Failed",
  expired: "Expired",
};

const RUNNING: ClipJobStatus[] = ["pending", "processing", "rendering"];

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
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

  useEffect(() => {
    const ctrl = new AbortController();
    clipsApi.listJobs(ctrl.signal)
      .then((data) => { if (!ctrl.signal.aborted) setJobs(data); })
      .catch((err) => { if (err?.name !== "AbortError") throw err; });
    return () => ctrl.abort();
  }, []);

  async function handleDelete() {
    if (!confirmDelete) return;
    setDeleting(true);
    try {
      await clipsApi.deleteJob(confirmDelete.id);
      setJobs((prev) => prev.filter((j) => j.id !== confirmDelete.id));
      setConfirmDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Box sx={{ p: 4, maxWidth: 880, mx: "auto" }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700 }}>
        YouTube Clips
      </Typography>

      <NewJobForm onCreated={(id) => navigate(`/clips/${id}`)} />

      <Typography
        variant="overline"
        sx={{ mt: 5, mb: 1.5, display: "block", color: "text.secondary", letterSpacing: "0.08em" }}
      >
        Past jobs
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
          <Typography variant="subtitle1">No jobs yet</Typography>
          <Typography variant="body2" color="text.secondary">
            Paste a YouTube URL above to generate your first clips.
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
                            background: "linear-gradient(90deg, #7c3aed, #3b82f6)",
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
                  <Tooltip title="Delete job" placement="left">
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
        <DialogTitle>Delete this job?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            "{confirmDelete?.title || confirmDelete?.youtube_url}" — all candidates,
            preview clips, and final renders will be permanently deleted. This cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(null)} disabled={deleting}>
            Cancel
          </Button>
          <Button
            onClick={handleDelete}
            disabled={deleting}
            color="error"
            variant="contained"
            sx={{
              background: "linear-gradient(135deg, #ef4444, #dc2626)",
              "&:hover": { background: "linear-gradient(135deg, #dc2626, #b91c1c)" },
            }}
          >
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
