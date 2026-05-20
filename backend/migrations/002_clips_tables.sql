-- Migration 002: YouTube Clips feature
-- Tables: clip_jobs, clip_candidates

CREATE TABLE clip_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    youtube_url         TEXT NOT NULL,
    youtube_video_id    TEXT,
    title               TEXT,
    duration_seconds    INTEGER,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','processing','ready','rendering','completed','failed','expired')),
    current_stage       TEXT
                        CHECK (current_stage IS NULL OR current_stage IN
                            ('metadata','download','transcribe','segment','preview_render',
                             'await_selection','final_render','done')),
    progress_pct        INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    error_message       TEXT,
    source_storage_key  TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days')
);

CREATE TRIGGER update_clip_jobs_updated_at
    BEFORE UPDATE ON clip_jobs
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_clip_jobs_user_created ON clip_jobs (user_id, created_at DESC);
CREATE INDEX idx_clip_jobs_expires ON clip_jobs (expires_at) WHERE status != 'failed';

ALTER TABLE clip_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY clip_jobs_select ON clip_jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY clip_jobs_insert ON clip_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY clip_jobs_update ON clip_jobs FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY clip_jobs_delete ON clip_jobs FOR DELETE USING (auth.uid() = user_id);


CREATE TABLE clip_candidates (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id               UUID NOT NULL REFERENCES clip_jobs(id) ON DELETE CASCADE,
    start_seconds        DOUBLE PRECISION NOT NULL,
    end_seconds          DOUBLE PRECISION NOT NULL,
    duration_seconds     DOUBLE PRECISION NOT NULL,
    hype_score           DOUBLE PRECISION NOT NULL,
    hype_reasoning       TEXT,
    transcript_excerpt   TEXT,
    preview_storage_key  TEXT,
    preview_poster_key   TEXT,
    final_storage_key    TEXT,
    selected             BOOLEAN NOT NULL DEFAULT false,
    render_failed        BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clip_candidates_job_score ON clip_candidates (job_id, hype_score DESC);

ALTER TABLE clip_candidates ENABLE ROW LEVEL SECURITY;

CREATE POLICY clip_candidates_select ON clip_candidates FOR SELECT USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_insert ON clip_candidates FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_update ON clip_candidates FOR UPDATE USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_delete ON clip_candidates FOR DELETE USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
