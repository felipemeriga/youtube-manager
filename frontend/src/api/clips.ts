import { apiFetch } from "../lib/api";
import type {
  ClipJob,
  ClipJobSummary,
  PreflightResponse,
} from "../types/clips";

export const clipsApi = {
  preflight: (youtube_url: string) =>
    apiFetch<PreflightResponse>("/api/clips/jobs/preflight", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
    }),

  createJob: (youtube_url: string) =>
    apiFetch<ClipJobSummary>("/api/clips/jobs", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
    }),

  listJobs: (signal?: AbortSignal) =>
    apiFetch<ClipJobSummary[]>("/api/clips/jobs", { signal }),

  getJob: (id: string, signal?: AbortSignal) =>
    apiFetch<ClipJob>(`/api/clips/jobs/${id}`, { signal }),

  deleteJob: (id: string) =>
    apiFetch<{ status: string; files_removed: number }>(
      `/api/clips/jobs/${id}`,
      { method: "DELETE" }
    ),

  cancel: (id: string) =>
    apiFetch<{ status: string }>(`/api/clips/jobs/${id}/cancel`, {
      method: "POST",
    }),

  render: (id: string, candidate_ids: string[]) =>
    apiFetch<{ status: string }>(`/api/clips/jobs/${id}/render`, {
      method: "POST",
      body: JSON.stringify({ candidate_ids }),
    }),

  previewUrl: (candidateId: string, signal?: AbortSignal) =>
    apiFetch<{ url: string; poster_url: string | null }>(
      `/api/clips/candidates/${candidateId}/preview-url`,
      { signal }
    ),

  finalUrl: (candidateId: string) =>
    apiFetch<{ url: string }>(
      `/api/clips/candidates/${candidateId}/final-url`
    ),
};
