export type ClipJobStatus =
  | "pending"
  | "processing"
  | "ready"
  | "rendering"
  | "completed"
  | "failed"
  | "expired";

export type ClipJobStage =
  | "metadata"
  | "download"
  | "transcribe"
  | "segment"
  | "preview_render"
  | "await_selection"
  | "final_render"
  | "done";

export interface ClipJobSummary {
  id: string;
  youtube_url: string;
  title: string | null;
  duration_seconds: number | null;
  status: ClipJobStatus;
  progress_pct: number;
  created_at: string;
}

export interface ClipCandidate {
  id: string;
  job_id: string;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  hype_score: number;
  hype_reasoning: string | null;
  transcript_excerpt: string | null;
  preview_storage_key: string | null;
  preview_poster_key: string | null;
  final_storage_key: string | null;
  selected: boolean;
  render_failed: boolean;
}

export interface ClipJob extends ClipJobSummary {
  current_stage: ClipJobStage | null;
  error_message: string | null;
  candidates: ClipCandidate[];
}

export type JobEvent =
  | { type: "progress"; stage: ClipJobStage; pct: number }
  | { type: "ready"; candidates: ClipCandidate[] }
  | { type: "render_progress"; candidate_id: string; pct: number }
  | { type: "render_complete"; candidate_id: string; signed_url: string }
  | { type: "render_failed"; candidate_id: string; error: string }
  | { type: "render_complete_all" }
  | { type: "error"; message: string };

export interface PreflightResponse {
  youtube_video_id: string;
  title: string;
  duration_seconds: number;
}
