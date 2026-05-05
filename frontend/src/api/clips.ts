import { apiFetch } from "../lib/api";
import type {
  CaptionStyle,
  ClipJob,
  ClipJobSummary,
  PreflightResponse,
} from "../types/clips";

export const clipsApi = {
  preflight: (youtube_url: string, signal?: AbortSignal) =>
    apiFetch<PreflightResponse>("/api/clips/jobs/preflight", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
      signal,
    }),

  createJob: (youtube_url: string, signal?: AbortSignal) =>
    apiFetch<ClipJobSummary>("/api/clips/jobs", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
      signal,
    }),

  listJobs: (signal?: AbortSignal) =>
    apiFetch<ClipJobSummary[]>("/api/clips/jobs", { signal }),

  getJob: (id: string, signal?: AbortSignal) =>
    apiFetch<ClipJob>(`/api/clips/jobs/${id}`, { signal }),

  deleteJob: (id: string, signal?: AbortSignal) =>
    apiFetch<{ status: string; files_removed: number }>(
      `/api/clips/jobs/${id}`,
      { method: "DELETE", signal }
    ),

  cancel: (id: string, signal?: AbortSignal) =>
    apiFetch<{ status: string }>(`/api/clips/jobs/${id}/cancel`, {
      method: "POST",
      signal,
    }),

  render: (
    id: string,
    candidate_ids: string[],
    caption_style: CaptionStyle = "classic",
    signal?: AbortSignal
  ) =>
    apiFetch<{ status: string }>(`/api/clips/jobs/${id}/render`, {
      method: "POST",
      body: JSON.stringify({ candidate_ids, caption_style }),
      signal,
    }),

  previewUrl: (candidateId: string, signal?: AbortSignal) =>
    apiFetch<{ url: string; poster_url: string | null }>(
      `/api/clips/candidates/${candidateId}/preview-url`,
      { signal }
    ),

  finalUrl: (candidateId: string, signal?: AbortSignal) =>
    apiFetch<{ url: string }>(
      `/api/clips/candidates/${candidateId}/final-url`,
      { signal }
    ),
};
