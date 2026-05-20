-- Migration 003: extend clip_jobs.current_stage CHECK constraint to cover the
-- finals pipeline stages emitted by run_finals_pipeline. The original
-- migration 002 only listed the clipping-pipeline stages, so updates such as
-- {"current_stage": "download_source"} fail with constraint
-- "clip_jobs_current_stage_check".

ALTER TABLE clip_jobs DROP CONSTRAINT IF EXISTS clip_jobs_current_stage_check;

ALTER TABLE clip_jobs
    ADD CONSTRAINT clip_jobs_current_stage_check
    CHECK (current_stage IS NULL OR current_stage IN (
        -- clipping pipeline stages
        'metadata','download','transcribe','segment','preview_render',
        'await_selection','final_render',
        -- finals pipeline stages (run_finals_pipeline)
        'download_source','extract_audio','render_finals',
        -- terminal
        'done'
    ));
