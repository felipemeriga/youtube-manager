import { useEffect, useState } from "react";
import { Box, Typography, List, ListItem, ListItemButton, ListItemText, Chip } from "@mui/material";
import { useNavigate } from "react-router-dom";
import type { ClipJobSummary } from "../types/clips";
import { clipsApi } from "../api/clips";
import NewJobForm from "../components/clips/NewJobForm";

export default function ClipsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ClipJobSummary[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    clipsApi.listJobs(ctrl.signal)
      .then((data) => { if (!ctrl.signal.aborted) setJobs(data); })
      .catch((err) => { if (err?.name !== "AbortError") throw err; });
    return () => ctrl.abort();
  }, []);

  return (
    <Box sx={{ p: 4, maxWidth: 800, mx: "auto" }}>
      <Typography variant="h5" gutterBottom>YouTube Clips</Typography>
      <NewJobForm onCreated={(id) => navigate(`/clips/${id}`)} />
      <Typography variant="subtitle2" sx={{ mt: 4, mb: 1 }}>Past jobs</Typography>
      <List>
        {jobs.map(j => (
          <ListItem key={j.id} disablePadding>
            <ListItemButton onClick={() => navigate(`/clips/${j.id}`)}>
              <ListItemText
                primary={j.title || j.youtube_url}
                secondary={`${j.duration_seconds ?? "?"}s · ${new Date(j.created_at).toLocaleString()}`}
              />
              <Chip label={j.status} size="small" />
            </ListItemButton>
          </ListItem>
        ))}
        {jobs.length === 0 && (
          <Typography variant="body2" color="text.secondary">No jobs yet.</Typography>
        )}
      </List>
    </Box>
  );
}
