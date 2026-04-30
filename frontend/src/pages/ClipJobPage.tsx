import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useNavigate, useParams } from "react-router-dom";
import type { ClipJob, ClipCandidate, JobEvent } from "../types/clips";
import { clipsApi } from "../api/clips";
import { useClipJobSSE } from "../hooks/useClipJobSSE";
import JobProgressPanel from "../components/clips/JobProgressPanel";
import ClipGrid from "../components/clips/ClipGrid";
import ClipPreviewModal from "../components/clips/ClipPreviewModal";
import SelectionBar from "../components/clips/SelectionBar";
import FinalRenderPanel from "../components/clips/FinalRenderPanel";

export default function ClipJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<ClipJob | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewing, setPreviewing] = useState<ClipCandidate | null>(null);
  const [renderProgress, setRenderProgress] = useState<Record<string, number>>({});
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});
  const [rendering, setRendering] = useState(false);

  async function refresh() {
    if (!jobId) return;
    setJob(await clipsApi.getJob(jobId));
  }
  useEffect(() => {
    if (!jobId) return;
    const ctrl = new AbortController();
    clipsApi.getJob(jobId, ctrl.signal)
      .then((data) => { if (!ctrl.signal.aborted) setJob(data); })
      .catch((err) => { if (err?.name !== "AbortError") throw err; });
    return () => ctrl.abort();
  }, [jobId]);

  useClipJobSSE(jobId ?? null, (e: JobEvent) => {
    if (e.type === "progress") {
      setJob(j => j ? { ...j, current_stage: e.stage, progress_pct: e.pct } : j);
    } else if (e.type === "ready") {
      refresh();
    } else if (e.type === "render_progress") {
      setRenderProgress(p => ({ ...p, [e.candidate_id]: e.pct }));
    } else if (e.type === "render_complete") {
      setSignedUrls(u => ({ ...u, [e.candidate_id]: e.signed_url }));
    } else if (e.type === "render_complete_all") {
      refresh();
    }
  });

  const selectedCandidates = useMemo(
    () => job?.candidates.filter(c => selected.has(c.id)) ?? [],
    [job, selected],
  );

  if (!job) {
    return (
      <Box sx={{ p: 8, display: "flex", justifyContent: "center" }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (job.status === "failed") {
    return (
      <Box sx={{ p: 4, maxWidth: 640, mx: "auto" }}>
        <Button onClick={() => navigate("/clips")} startIcon={<ArrowBackIcon />} sx={{ mb: 2 }} color="inherit">
          Voltar aos clips
        </Button>
        <Alert severity="error" variant="outlined">
          {job.error_message || "Trabalho falhou"}
        </Alert>
      </Box>
    );
  }

  if (["pending", "processing"].includes(job.status)) {
    return (
      <JobProgressPanel
        job={job}
        onCancel={async () => { await clipsApi.cancel(job.id); refresh(); }}
      />
    );
  }

  if (["rendering", "completed"].includes(job.status) && selectedCandidates.length > 0) {
    return (
      <Box sx={{ p: 4 }}>
        <FinalRenderPanel
          selected={selectedCandidates}
          progress={renderProgress}
          signedUrls={signedUrls}
          onBack={() => setSelected(new Set())}
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 1600, mx: "auto", pb: 12, width: "100%", overflowY: "auto" }}>
      <Stack direction="row" alignItems="flex-start" spacing={2} sx={{ mb: 3 }}>
        <Button
          onClick={() => navigate("/clips")}
          startIcon={<ArrowBackIcon />}
          color="inherit"
          size="small"
          sx={{ flexShrink: 0, mt: 0.5 }}
        >
          Todos os trabalhos
        </Button>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }} noWrap>
            {job.title || "Candidatos a clips"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {job.candidates.length} candidato{job.candidates.length === 1 ? "" : "s"} · escolha quais deseja renderizar em 1080p
          </Typography>
        </Box>
      </Stack>

      <ClipGrid
        candidates={job.candidates}
        selected={selected}
        onToggleSelect={(id) => setSelected(s => {
          const next = new Set(s);
          next.has(id) ? next.delete(id) : next.add(id);
          return next;
        })}
        onClickCard={setPreviewing}
      />
      <ClipPreviewModal
        candidate={previewing}
        open={!!previewing}
        onClose={() => setPreviewing(null)}
      />
      <SelectionBar
        count={selected.size}
        loading={rendering}
        onRender={async () => {
          setRendering(true);
          try {
            await clipsApi.render(job.id, Array.from(selected));
            await refresh();
          } finally {
            setRendering(false);
          }
        }}
      />
    </Box>
  );
}
