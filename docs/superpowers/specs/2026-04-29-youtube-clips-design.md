# YouTube Clips Creator — Design

**Status:** Draft, pending user approval
**Date:** 2026-04-29
**Branch:** `feat/security-perf-ux-tier3` (continuation; ships in PR #8 as additional atomic commits)

## Goal

Let the user paste a YouTube URL of one of their own videos and get back a ranked grid of vertical 9:16 short-clip candidates with hype scores. The user clicks to preview, picks the ones they want, and the backend re-renders the selected clips at full quality with burned-in captions for download.

## Confirmed scope decisions

| Decision | Choice |
|---|---|
| Clip-boundary strategy | Hybrid: transcript-driven LLM segmentation, snapped to sentence boundaries, capped to Shorts-friendly buckets (15–60s, prefer 20–45s) |
| Hype scoring signal | Transcript-only LLM (no audio/visual signals in v1) |
| Vertical reframe | Face-aware crop via MediaPipe |
| App placement | Brand new top-level `/clips` page; not a conversation mode |
| Max input video duration | ≤60 min, with confirmation modal between 30–60 min |
| Transcript source | YouTube auto-captions via yt-dlp; Whisper fallback when missing or broken |
| Captions | Simple burned-in cue-level captions (one transcript cue at a time), **only on the user's selected final renders** (previews stay caption-free) |
| Candidate count per video | Adaptive: `min(20, ceil(duration_min / 2))` |
| Job execution model | DB-backed `clip_jobs` row + asyncio task in FastAPI process + SSE progress (matches existing thumbnail/script SSE pattern) |
| Storage retention | Source MP4 and previews auto-delete 7 days after job creation; finals persist until manually deleted |

## Architecture overview

```
┌────────────────────┐         ┌──────────────────────────────────────┐
│  Frontend (/clips) │         │  Backend (FastAPI, in-process)       │
│                    │         │                                      │
│  1. Submit URL ───────POST──▶│  POST /api/clips/jobs                │
│                    │         │   └─▶ insert clip_jobs row           │
│  2. Job ID + SSE ◀──SSE──────│   └─▶ asyncio.create_task(run_job)   │
│                    │         │                                      │
│  3. Progress bar   │         │  run_job pipeline:                   │
│                    │         │   ① yt-dlp metadata + duration check │
│                    │         │   ② yt-dlp download mp4 + captions   │
│                    │         │   ③ Whisper fallback if needed       │
│  4. Ranked grid  ◀──SSE──────│   ④ LLM segment + score              │
│                    │         │   ⑤ ffmpeg cut + face-aware reframe  │
│                    │         │       + low-bitrate preview          │
│  5. User selects   │         │   ⑥ upload previews → Supabase       │
│                    │         │   ⑦ insert clip_candidates rows      │
│  6. POST selections─────────▶│  POST /api/clips/jobs/:id/render     │
│                    │         │       full-quality + burn captions   │
│  7. Download finals◀──SSE────│       upload + signed URLs           │
└────────────────────┘         └──────────────────────────────────────┘
```

**Key properties:**
- **Two-phase execution** — phase 1 generates all preview candidates upfront; phase 2 renders only what the user picked. This is what makes "all clips upfront, ranked" affordable.
- **In-process worker** — no Redis/Celery. The `clip_jobs` row is the source of truth. Crash recovery: on app startup, any `processing`/`rendering` row gets marked `failed` (user re-submits).
- **Reused patterns** — SSE plumbing from thumbnail/script modes; signed-URL/storage patterns from `routes/assets.py`; Supabase 502 retry from commit `97678f5`.

## Data model

### Table: `clip_jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | primary key |
| `user_id` | uuid | fk `auth.users`, indexed, RLS pivot |
| `youtube_url` | text | as submitted |
| `youtube_video_id` | text | extracted from URL |
| `title` | text | from yt-dlp metadata |
| `duration_seconds` | integer | from yt-dlp metadata |
| `status` | text | `pending` \| `processing` \| `ready` \| `rendering` \| `completed` \| `failed` \| `expired` |
| `current_stage` | text | `metadata` \| `download` \| `transcribe` \| `segment` \| `preview_render` \| `await_selection` \| `final_render` \| `done` \| null |
| `progress_pct` | integer | 0–100 |
| `error_message` | text | null unless `status='failed'` |
| `source_storage_key` | text | `clips/{user_id}/{job_id}/source.mp4` |
| `created_at` | timestamptz | default now() |
| `updated_at` | timestamptz | default now() |
| `expires_at` | timestamptz | `created_at + 7 days` — drives cleanup |

### Table: `clip_candidates`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | primary key |
| `job_id` | uuid | fk `clip_jobs`, indexed |
| `start_seconds` | float | cut start in source |
| `end_seconds` | float | cut end in source |
| `duration_seconds` | float | denormalized for sort |
| `hype_score` | float | 0–10 from LLM |
| `hype_reasoning` | text | LLM's one-line rationale |
| `transcript_excerpt` | text | dialogue inside this clip window |
| `preview_storage_key` | text | `clips/{user_id}/{job_id}/previews/{candidate_id}.mp4` |
| `preview_poster_key` | text | `clips/{user_id}/{job_id}/previews/{candidate_id}.jpg` |
| `final_storage_key` | text | null until selected and rendered |
| `selected` | boolean | default false; set true on selection |
| `render_failed` | boolean | default false; set true if ffmpeg crashed on this candidate |
| `created_at` | timestamptz | default now() |

### Indexes
- `clip_jobs (user_id, created_at desc)` — job history list
- `clip_candidates (job_id, hype_score desc)` — ranked grid
- `clip_jobs (expires_at) WHERE status != 'failed'` — cleanup query

### RLS
- `clip_jobs`: `user_id = auth.uid()` for select/insert/update/delete
- `clip_candidates`: same user via `EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())`

## Backend pipeline

New module `backend/services/clips/` with one file per stage. Every stage updates `clip_jobs.current_stage` and `progress_pct`, and emits an SSE `progress` event.

### Stage 1 — Metadata & validation (`metadata.py`)
- `yt-dlp --dump-json --no-download <url>` → parse JSON
- Validate `duration ≤ 3600s`. If over, fail with `error_message="Video exceeds 60 min limit"`
- Persist `title`, `duration_seconds`, `youtube_video_id`
- **progress: 0 → 5%**

### Stage 2 — Source download (`download.py`)
- `yt-dlp -f "bv*[height<=1080]+ba/b" --merge-output-format mp4 -o <tmp>/source.mp4 <url>`
- 1080p cap — face detection doesn't need 4K
- Stream-upload to Supabase at `source_storage_key`; keep local copy in `tmp/` for downstream stages
- **progress: 5 → 25%**

### Stage 3 — Transcript (`transcript.py`)
- Try `yt-dlp --write-auto-subs --sub-format vtt --skip-download` (English)
- Detect "broken" captions: empty file, fewer than 5 cues, or cue text dominated by `[Music]`/`[Applause]`
- If missing/broken → OpenAI Whisper API (`whisper-1`) on the audio track with word-level timestamps
- Normalize both sources into `[(start, end, text)]`
- **progress: 25 → 45%**

### Stage 4 — Segmentation + scoring (`segment.py`)
- Single LLM call: "Given this transcript with timestamps, find the most viral clip-able moments. For each: `start_time`, `end_time`, `hype_score` (0–10), `reasoning` (one line). Constraints: duration 15–60s, prefer 20–45s, must end at sentence boundary."
- Use existing LLM provider (already configured for thumbnail/script modes)
- Parse JSON response; on parse failure, retry up to 2x with `temperature=0`
- Cap to `min(20, ceil(duration_min / 2))` highest-scoring candidates
- **progress: 45 → 55%**

### Stage 5 — Preview render (`render_preview.py`)
For each candidate, parallelized with `asyncio.Semaphore(3)`:
1. `ffmpeg -ss <start> -to <end> -i source.mp4 -c copy <tmp>/clip.mp4` — fast cut, no re-encode
2. Face detection (MediaPipe) on ~1 frame/sec → smoothed center-of-face X track
3. `ffmpeg -i clip.mp4 -vf "crop=ih*9/16:ih:<x_track>:0,scale=720:1280" -c:v libx264 -crf 30 -preset fast -b:a 96k preview.mp4`
4. Extract a single poster frame at the midpoint as `<candidate_id>.jpg`
5. Upload preview + poster to Supabase
6. Insert `clip_candidates` row
- **progress: 55 → 95%** (pro-rata across candidates)

### Stage 6 — Mark ready
- `status='ready'`, `current_stage='await_selection'`, `progress_pct=100`
- SSE pushes `{type: 'ready', candidates: [...]}`
- Local `tmp/` cleaned; **source.mp4 stays in Supabase** for re-render selection

### Stage 7 — Final render (`POST /api/clips/jobs/:id/render`)
For each candidate the user marked `selected=true`:
1. Download source from Supabase to tmp (or keep if same session)
2. Re-cut with re-encode at high quality: `-crf 18 -preset slow`, vertical reframe again
3. Generate `.ass` subtitles from cues overlapping the clip window (white bottom-center with black stroke)
4. Burn captions: `-vf "...crop...,scale=720:1280,subtitles=clip.ass"`
5. Upload to `final_storage_key`, return signed URL
- Status transitions: `ready → rendering → completed`

### Concurrency, cancellation, recovery
- One `asyncio.Task` per job in a module-level `_active_jobs: dict[str, asyncio.Task]`
- Cancel endpoint cancels the task and marks `status='failed'` with `error_message="Cancelled by user"`
- On app startup, mark any `processing` or `rendering` row → `failed`
- Each stage wrapped in try/except that updates `error_message` and stops the pipeline

## Frontend UI

Brand new top-level page at `/clips`. Sidebar gains a "Clips" entry alongside thumbnail/script entries.

### Routes
```
/clips                   ClipsPage      (job list + new job form)
/clips/:jobId            ClipJobPage    (job detail: progress / grid / final)
```

### Component structure
```
frontend/src/pages/ClipsPage.tsx
frontend/src/pages/ClipJobPage.tsx
frontend/src/components/clips/
  ├─ NewJobForm.tsx          URL input + submit + 30/60-min warning modal
  ├─ JobProgressPanel.tsx    SSE-driven progress bar + stage label
  ├─ ClipGrid.tsx            ranked grid of preview cards
  ├─ ClipCard.tsx            single preview: poster, hover-play, score chip, select toggle
  ├─ ClipPreviewModal.tsx    fullscreen player on click
  ├─ SelectionBar.tsx        sticky bottom: "N selected · [Render finals]"
  └─ FinalRenderPanel.tsx    progress + per-clip download links
frontend/src/api/clips.ts
frontend/src/hooks/useClipJobSSE.ts
```

### `ClipsPage` (job list)
- Top: `<NewJobForm />` — single text input + Submit. Note below: "≤60 min videos. ~2 min processing per minute of video."
- Below: list of past jobs (title, duration, created_at, status pill, "Open" link)

### `NewJobForm` — duration warning flow
1. On submit, call `POST /api/clips/jobs/preflight` (yt-dlp metadata only) → `{title, duration_seconds, video_id}`
2. If `duration > 60min`: block with error
3. If `duration > 30min`: confirmation modal "This is a long video — processing will take ~X minutes and use significant compute. Continue?"
4. Otherwise: directly `POST /api/clips/jobs`

### `ClipJobPage` — three states based on `status`

**(a) `pending` / `processing`** — full-page progress panel
- Big progress bar with stage label ("Transcribing audio…", "Scoring clips…", "Rendering 7/14…")
- SSE updates `progress_pct` and `current_stage`
- Cancel button

**(b) `ready`** — the ranked grid
- `<ClipGrid />` sorted by `hype_score desc`
- Each `<ClipCard />`:
  - `<video preload="metadata">` with poster from extracted JPG
  - On hover: silent autoplay loop of preview
  - On click: opens `<ClipPreviewModal />` with audio
  - Top-left chip: hype score (e.g. "8.7")
  - Top-right: select checkbox
  - Bottom: `Mm:ss → Mm:ss · 32s` and the LLM's reasoning
- Sticky `<SelectionBar />`: "3 selected — [Render selected clips]"
- On render click → `POST /api/clips/jobs/:id/render` with selected candidate IDs → page transitions to (c)

**(c) `rendering` / `completed`** — `<FinalRenderPanel />`
- For each selected candidate: progress bar → when done, replace with poster + Download button
- Downloads use signed URLs (existing pattern from `routes/assets.py`)
- "Back to grid" link returns to (b) so user can render more

### SSE event shape
```typescript
type JobEvent =
  | { type: 'progress'; stage: string; pct: number }
  | { type: 'ready'; candidates: ClipCandidate[] }
  | { type: 'render_progress'; candidate_id: string; pct: number }
  | { type: 'render_complete'; candidate_id: string; signed_url: string }
  | { type: 'error'; message: string }
```

### Mobile
Responsive grid: 1 col mobile, 2 col tablet, 3–4 col desktop. Tap-to-preview on touch (no hover autoplay).

## Storage layout

Supabase Storage bucket `clips` (private), all access via signed URLs from FastAPI:

```
clips/
  {user_id}/
    {job_id}/
      source.mp4                          (≤7 days)
      previews/
        {candidate_id}.mp4                (≤7 days)
        {candidate_id}.jpg                (≤7 days, poster frame)
      finals/
        {candidate_id}.mp4                (persistent — manual delete only)
```

## Retention / cleanup

- `clip_jobs.expires_at` = `created_at + 7 days` set on insert
- New endpoint `POST /api/clips/cleanup` — protected by a service-token header (not user auth). Intended to be triggered daily by an external scheduler (e.g., a cron-style task hitting the endpoint with the service token). Removes:
  - `source.mp4` for any job with `expires_at < now()`
  - all `previews/*.mp4` and `previews/*.jpg` for those jobs
  - `clip_candidates` rows whose `final_storage_key IS NULL`
- Job rows stay (history visible); status flipped to `expired`
- Finals are **never auto-deleted**

## Error handling

| Failure | Behavior |
|---|---|
| Invalid URL / age-gated / private video | yt-dlp fails fast → `failed` |
| Duration > 60 min | rejected at preflight, never creates a job |
| YT captions missing AND Whisper fails | retry once, then `failed` with "Transcription failed" |
| LLM JSON parse failure | retry up to 2x with `temperature=0`, then `failed` |
| ffmpeg crash on one candidate | mark `render_failed=true`, continue. If >50% fail, fail whole job |
| Supabase 502 on upload | reuse existing retry pattern (commit `97678f5`) |
| Server restart mid-job | startup hook marks `processing`/`rendering` → `failed` |
| User cancels | task cancelled, status `failed`, `error_message="Cancelled by user"`, partial files cleaned |

## Testing

**Unit tests (mock external boundaries):**
- `test_clips_metadata.py` — yt-dlp output parsing, duration validation
- `test_clips_transcript.py` — captions-or-Whisper decision, broken-caption detection
- `test_clips_segment.py` — LLM response parsing, candidate cap math
- `test_clips_render_preview.py` — ffmpeg command construction, face-track smoothing
- `test_clips_routes.py` — endpoint auth, RLS, status transitions, SSE event shape

**Integration test (one happy path, no real YouTube):**
- Small fixture MP4 + fake captions; assert full pipeline produces N candidates and a render-ready job. yt-dlp shimmed via dependency injection; OpenAI/LLM clients mocked.

**Frontend tests:**
- `NewJobForm` (preflight + warning modal logic)
- `ClipCard` (hover/click/select states)
- `useClipJobSSE` (event handling)

**No real YouTube calls in CI.**

## Dependencies

**Backend (new):**
- `yt-dlp` (PyPI)
- `mediapipe` (face detection)
- `openai` (Whisper) — likely already a dep

**System:** `ffmpeg` must be installed in the deployment environment.

**Frontend:** none new.

## Out of scope (deferred)

- Audio-energy or visual scoring signals (currently transcript-only)
- Speaker tracking for multi-face shots (face-aware crop only in v1)
- Animated/highlighted captions (simple burn-in only)
- Caption styling customization
- Alternate aspect ratios (9:16 only)
- Multi-language UI for captions
- Batch URL submission
- Re-running a job from history without re-submitting URL
