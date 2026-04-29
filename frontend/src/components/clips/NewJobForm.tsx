import { useState } from "react";
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  TextField, Typography, Alert,
} from "@mui/material";
import { clipsApi } from "../../api/clips";

export default function NewJobForm({ onCreated }: { onCreated: (jobId: string) => void }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ duration: number; title: string } | null>(null);

  async function submit() {
    setError(null);
    setLoading(true);
    try {
      const meta = await clipsApi.preflight(url);
      if (meta.duration_seconds > 1800) {
        setConfirm({ duration: meta.duration_seconds, title: meta.title });
      } else {
        await create();
      }
    } catch (e: any) { setError(e.message || "Preflight failed"); }
    finally { setLoading(false); }
  }

  async function create() {
    setLoading(true);
    try {
      const job = await clipsApi.createJob(url);
      onCreated(job.id);
      setUrl("");
      setConfirm(null);
    } catch (e: any) { setError(e.message || "Failed to create job"); }
    finally { setLoading(false); }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField
          fullWidth size="small" placeholder="YouTube URL"
          value={url} onChange={e => setUrl(e.target.value)} disabled={loading}
        />
        <Button variant="contained" onClick={submit} disabled={loading || !url}>
          {loading ? "…" : "Generate clips"}
        </Button>
      </Box>
      <Typography variant="caption" color="text.secondary">
        ≤60 min videos. Processing takes ~2 min per minute of video.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Dialog open={!!confirm} onClose={() => setConfirm(null)}>
        <DialogTitle>Long video</DialogTitle>
        <DialogContent>
          {confirm && (
            <Typography>
              "{confirm.title}" is {Math.round(confirm.duration / 60)} min long. Processing will take ~{Math.round(confirm.duration / 30)} min and use significant compute. Continue?
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>Cancel</Button>
          <Button onClick={create} variant="contained">Continue</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
