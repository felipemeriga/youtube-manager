import { useEffect, useState } from "react";
import { Box, Typography, List, ListItem, ListItemButton, ListItemText, Chip } from "@mui/material";
import { useNavigate } from "react-router-dom";
import type { ClipJobSummary } from "../types/clips";
import { clipsApi } from "../api/clips";
import NewJobForm from "../components/clips/NewJobForm";

export default function ClipsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ClipJobSummary[]>([]);

  async function refresh() {
    setJobs(await clipsApi.listJobs());
  }
  useEffect(() => { refresh(); }, []);

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
