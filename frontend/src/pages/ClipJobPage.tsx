import { useEffect, useMemo, useState } from "react";
import { Box, Alert } from "@mui/material";
import { useParams } from "react-router-dom";
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
  const [job, setJob] = useState<ClipJob | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewing, setPreviewing] = useState<ClipCandidate | null>(null);
  const [renderProgress, setRenderProgress] = useState<Record<string, number>>({});
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});

  async function refresh() {
    if (!jobId) return;
    setJob(await clipsApi.getJob(jobId));
  }
  useEffect(() => { refresh(); }, [jobId]);

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

  if (!job) return <Box sx={{ p: 4 }}>Loading…</Box>;

  if (job.status === "failed") {
    return (
      <Box sx={{ p: 4, maxWidth: 600, mx: "auto" }}>
        <Alert severity="error">{job.error_message || "Job failed"}</Alert>
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
    <Box sx={{ p: 4 }}>
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
        onRender={async () => {
          await clipsApi.render(job.id, Array.from(selected));
          refresh();
        }}
      />
    </Box>
  );
}
