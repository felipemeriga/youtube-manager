-- Cache the full transcript timeline on the job row so the finals pipeline
-- can reuse what run_pipeline already paid Whisper / yt-dlp to compute,
-- skipping extract_audio + transcribe on every render.
ALTER TABLE clip_jobs
    ADD COLUMN IF NOT EXISTS transcript_cues JSONB;
