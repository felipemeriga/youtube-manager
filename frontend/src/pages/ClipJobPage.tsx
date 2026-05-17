import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useNavigate, useParams } from "react-router-dom";
import type { CaptionStyle, ClipJob, ClipCandidate, JobEvent } from "../types/clips";
import { clipsApi } from "../api/clips";
import { useClipJobSSE } from "../hooks/useClipJobSSE";
import { usePageAbort } from "../hooks/usePageAbort";
import JobProgressPanel from "../components/clips/JobProgressPanel";
import ClipGrid from "../components/clips/ClipGrid";
import ClipPreviewModal from "../components/clips/ClipPreviewModal";
import SelectionBar from "../components/clips/SelectionBar";
import FinalRenderPanel from "../components/clips/FinalRenderPanel";
import { ensureNotificationPermission, notify } from "../lib/notify";

export default function ClipJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<ClipJob | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewing, setPreviewing] = useState<ClipCandidate | null>(null);
  const [renderProgress, setRenderProgress] = useState<Record<string, number>>({});
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});
  const [rendering, setRendering] = useState(false);
  const [renderTriggered, setRenderTriggered] = useState(false);
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>("classic");
  // Re-create the page-level abort whenever jobId changes so requests bound
  // to the previous job are cancelled the moment the route id changes.
  const { getSignal, isAbort } = usePageAbort(jobId);

  async function refresh() {
    if (!jobId) return;
    const signal = getSignal();
    try {
      const data = await clipsApi.getJob(jobId, signal);
      if (!signal.aborted) setJob(data);
    } catch (e) {
      if (isAbort(e)) return;
      throw e;
    }
  }
  useEffect(() => {
    if (!jobId) return;
    const signal = getSignal();
    clipsApi.getJob(jobId, signal)
      .then((data) => { if (!signal.aborted) setJob(data); })
      .catch((err) => { if (!isAbort(err)) throw err; });
  // jobId reset re-creates the abort controller via usePageAbort.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useClipJobSSE(jobId ?? null, (e: JobEvent) => {
    if (e.type === "progress") {
      setJob(j => j ? { ...j, current_stage: e.stage, progress_pct: e.pct } : j);
    } else if (e.type === "ready") {
      refresh();
      notify("Clips prontos", "Os candidatos a clip estão prontos para você revisar.");
    } else if (e.type === "render_progress") {
      setRenderProgress(p => ({ ...p, [e.candidate_id]: e.pct }));
    } else if (e.type === "render_complete") {
      setSignedUrls(u => ({ ...u, [e.candidate_id]: e.signed_url }));
    } else if (e.type === "render_complete_all") {
      refresh();
      notify("Renderização concluída", "Seus clips em alta resolução estão prontos para download.");
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
        onCancel={async () => {
          try {
            await clipsApi.cancel(job.id, getSignal());
            refresh();
          } catch (e) {
            if (isAbort(e)) return;
            throw e;
          }
        }}
      />
    );
  }

  if ((job.status === "rendering" || (job.status === "completed" && renderTriggered)) && selectedCandidates.length > 0) {
    const allDone = selectedCandidates.every(
      (c) => !!signedUrls[c.id] || !!c.final_storage_key,
    );
    return (
      <Box sx={{ p: 4, width: "100%", overflowY: "auto" }}>
        <FinalRenderPanel
          selected={selectedCandidates}
          progress={renderProgress}
          signedUrls={signedUrls}
          onBack={() => setSelected(new Set())}
          currentStage={job.current_stage}
          allDone={allDone}
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
        captionStyle={captionStyle}
        onCaptionStyleChange={setCaptionStyle}
        onRender={async () => {
          setRendering(true);
          setRenderTriggered(true);
          // Lazy permission request — must happen from a user gesture.
          ensureNotificationPermission();
          // Clear stale "done" signals for the candidates being re-rendered.
          // Without this, a previous render's final_storage_key / signedUrl
          // makes the FinalRenderPanel show "Baixar" pointing at the OLD
          // file while the new render is in progress. refresh() at the end
          // (and SSE render_complete) repopulates with the fresh values.
          const reRendering = new Set(selected);
          setJob((j) =>
            j
              ? {
                  ...j,
                  candidates: j.candidates.map((c) =>
                    reRendering.has(c.id)
                      ? { ...c, final_storage_key: null }
                      : c,
                  ),
                }
              : j,
          );
          setSignedUrls((u) => {
            const next = { ...u };
            for (const id of reRendering) delete next[id];
            return next;
          });
          setRenderProgress((p) => {
            const next = { ...p };
            for (const id of reRendering) delete next[id];
            return next;
          });
          const signal = getSignal();
          try {
            await clipsApi.render(job.id, Array.from(selected), captionStyle, signal);
            await refresh();
          } catch (e) {
            if (isAbort(e)) return;
            throw e;
          } finally {
            if (!signal.aborted) setRendering(false);
          }
        }}
      />
    </Box>
  );
}
