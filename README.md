# YouTube Manager

A YouTube channel manager platform built around an AI agent. The two production features are:

1. **Thumbnail creator** — describe a thumbnail in chat, the agent analyzes your reference thumbnails, selects personal photos, crafts a plan, and generates the final image via Nano Banana (Gemini).
2. **Script creator** — chat-driven research and script generation for video topics, with structured outline → script approval.

A third feature — **viral clip extraction** from long-form YouTube videos — is implemented end-to-end (segment scoring, face-tracked vertical reframe, burned-in punctuated captions, 1080×1920 final render) but the UI entry point is **currently disabled** while the upstream RapidAPI quota is sized for production usage. See "Clips feature (disabled)" below.

## Features

- **Chat-based agentic UI** — conversational interface for thumbnails and scripts
- **Two-step approval flow** — review the agent's plan before generation, then approve or regenerate
- **Asset buckets** — reference thumbnails, personal photos, fonts, logos, scripts, and generated outputs, all managed through the UI
- **SSE streaming** — real-time streaming of agent responses, generation status, and clip-job progress
- **Nano Banana image generation** — Gemini API generates thumbnails from reference images, photos, fonts, logos, and the agent's plan in a single call
- **server-guardian LLM brain** — Claude Opus via server-guardian analyzes assets and crafts plans at zero API cost
- **Clip extraction pipeline** (UI disabled) — yt-dlp-free YouTube ingestion via RapidAPI, hype-segment scoring, MediaPipe face tracking, ffmpeg cut/reframe/mux, Whisper transcription fallback, diff-aligned punctuation, and burned-in ASS captions

## Architecture

```
Browser (React + MUI)
    |
    | SSE + REST
    v
FastAPI Backend
    |--- server-guardian (POST /api/ask)        -- agent brain (Claude Opus, free)
    |--- Anthropic API (Claude Haiku)           -- punctuation, intent routing
    |--- OpenAI API (Whisper)                   -- transcription fallback
    |--- Gemini API (Nano Banana)               -- image generation
    |--- RapidAPI (youtube-media-downloader)    -- video/audio/caption fetch
    |                                              (replaces yt-dlp on datacenter IPs)
    |--- ffmpeg                                 -- clip cut/reframe/mux + caption burn-in
    |--- Supabase                               -- PostgreSQL, Storage, Auth
```

The thumbnail flow uses a **LangGraph** state graph (`backend/services/thumbnail_nodes.py`) with PostgresSaver checkpointing. The chat workflow is conversation-history-driven: the `/api/chat` SSE endpoint reads prior messages to determine the next step. The clip pipeline runs as a background asyncio task with stage progress published over SSE via an in-process broker.

**Tech stack:**

| Layer    | Technology                                                        |
|----------|-------------------------------------------------------------------|
| Frontend | React 18, TypeScript, Material-UI v6, Vite                        |
| Backend  | FastAPI, Python 3.12, uvicorn                                     |
| LLM      | server-guardian (Claude Opus), Anthropic (Haiku), OpenAI (Whisper) |
| Image    | Gemini Nano Banana; OpenAI gpt-image (alternate provider)         |
| Video    | RapidAPI youtube-media-downloader, ffmpeg, MediaPipe Tasks API    |
| Graphs   | LangGraph (thumbnail orchestration) + PostgresSaver                |
| Database | Supabase (PostgreSQL + Storage + Auth)                             |
| Deploy   | Docker Compose, Traefik, Nginx                                     |

## Prerequisites

- Python 3.12
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) package manager
- **ffmpeg** on PATH (required for clip cut/reframe/mux and thumbnail effects)
- A Supabase project (with the schema from `backend/db/schema.sql` applied)
- Gemini API key
- A running [server-guardian](https://github.com/your-org/server-guardian) instance
- (Optional, only if re-enabling the clips feature) A RapidAPI subscription to [youtube-media-downloader](https://rapidapi.com/DataFanatic/api/youtube-media-downloader)

## Setup

### Backend

```bash
cd backend
cp .env.example .env   # fill in values (see table below)
uv sync
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env   # fill in values (see table below)
npm install
npm run dev
```

### Environment Variables

**Backend (`backend/.env`):**

| Variable                | Required | Purpose                                                                |
|-------------------------|----------|------------------------------------------------------------------------|
| `SUPABASE_URL`          | yes      | Supabase project URL                                                   |
| `SUPABASE_SERVICE_KEY`  | yes      | Supabase service role key                                              |
| `GEMINI_API_KEY`        | yes      | Gemini API key for Nano Banana generation                              |
| `GUARDIAN_URL`          | optional | server-guardian URL (default: `http://localhost:3000`)                 |
| `GUARDIAN_API_KEY`      | optional | Bearer token for server-guardian `/api/ask`                            |
| `ANTHROPIC_API_KEY`     | optional | Direct Anthropic API key for Haiku (punctuation, intent routing)       |
| `ANTHROPIC_MODEL`       | optional | Override Haiku model (default: `claude-haiku-4-5-20251001`)            |
| `OPENAI_API_KEY`        | optional | Whisper transcription fallback + gpt-image alternate provider          |
| `VOYAGE_API_KEY`        | optional | Voyage embeddings (personal-photo semantic search)                     |
| `DATABASE_URL`          | optional | Postgres URL for LangGraph PostgresSaver (thumbnail checkpointing)     |
| `CORS_ORIGINS`          | optional | Allowed origins (default: `http://localhost:5173`)                     |
| `RAPIDAPI_KEY`          | clips    | RapidAPI key for youtube-media-downloader — only needed if clips on    |
| `CLIPS_BUCKET`          | clips    | Supabase storage bucket for clip artifacts (default: `clips`)          |
| `CLIPS_TMP_DIR`         | clips    | Scratch dir for clip jobs (default: `/tmp/clips`)                      |
| `CLIPS_CLEANUP_TOKEN`   | clips    | Service token for the `POST /api/clips/cleanup` TTL sweep              |

**Frontend (`frontend/.env`):**

| Variable                | Purpose                         |
|-------------------------|---------------------------------|
| `VITE_SUPABASE_URL`    | Supabase project URL            |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous key        |
| `VITE_API_URL`         | Backend API URL                 |

## Docker Deployment

The project deploys with Docker Compose behind a Traefik reverse proxy on the shared `proxy` network. Traefik routes `youtube.merigafy.com/api/*` to the backend (priority 100) and all other paths to the frontend (priority 50), with HTTPS via Let's Encrypt.

```bash
# Create a .env file in the project root with all variables listed above
docker compose up -d --build
```

The backend health check ensures the frontend only starts after the API is ready.

## Testing

### Backend

```bash
cd backend
uv sync --group dev
pytest
```

### Frontend

```bash
cd frontend
npm run build
```

## Project Structure

```
youtube-manager/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile                   # python:3.12-slim + ffmpeg + uv
│   ├── pyproject.toml
│   ├── main.py                      # FastAPI app, CORS, health, route mounts
│   ├── config.py                    # pydantic-settings — all env vars
│   ├── auth.py                      # JWT validation via Supabase
│   ├── db/schema.sql                # PostgreSQL schema (conversations, clips, RLS)
│   ├── routes/                      # chat, conversations, assets, personas,
│   │                                # memories, clips
│   ├── services/
│   │   ├── llm.py                   # Anthropic + guardian client
│   │   ├── intent_router.py         # Routes user messages by intent
│   │   ├── guardian.py              # server-guardian client
│   │   ├── nano_banana.py           # Gemini image generation
│   │   ├── openai_image.py          # OpenAI gpt-image alternate provider
│   │   ├── thumbnail_nodes.py       # LangGraph nodes (composite, etc.)
│   │   ├── thumbnail_state.py       # LangGraph state schema
│   │   ├── youtube_saas.py          # RapidAPI client (metadata, download, captions)
│   │   └── clips/                   # download, transcript, segment, render_*,
│   │                                # face_detection, job_runner, sse_broker
│   └── tests/                       # ~329 backend tests
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf                   # SPA routing
│   ├── package.json / vite.config.ts
│   └── src/
│       ├── App.tsx                  # Router + protected routes
│       ├── theme.ts                 # MUI dark theme (glassmorphism)
│       ├── lib/                     # supabase, api client, SSE
│       ├── components/              # AuthProvider, AppLayout, IconRail,
│       │                            # chat/, clips/ (UI disabled), assets/
│       ├── hooks/                   # useClipJobSSE, usePageAbort, etc.
│       └── pages/                   # LoginPage, ChatPage, AssetsPage,
│                                    # ClipsPage, ClipJobPage, SettingsPage
└── docs/
    └── superpowers/specs/           # Design specifications
```

## API Endpoints

All endpoints (except `/api/health` and `/api/clips/cleanup`) require a valid Supabase JWT in the `Authorization` header.

**Core**

| Method | Path                                  | Description                                |
|--------|---------------------------------------|--------------------------------------------|
| GET    | `/api/health`                         | Health check                               |
| GET    | `/api/conversations`                  | List user conversations                    |
| POST   | `/api/conversations`                  | Create a conversation (`mode`: thumbnail/script) |
| GET    | `/api/conversations/{id}`             | Get conversation with messages             |
| PATCH  | `/api/conversations/{id}`             | Rename a conversation                      |
| DELETE | `/api/conversations/{id}`             | Delete a conversation                      |
| GET    | `/api/conversations/{id}/status`      | Get conversation pipeline status           |
| POST   | `/api/chat`                           | Stream chat response (SSE)                 |

**Assets, personas, memories**

| Method | Path                                          | Description                              |
|--------|-----------------------------------------------|------------------------------------------|
| GET    | `/api/assets/{bucket}`                        | List files in a bucket                   |
| POST   | `/api/assets/{bucket}/upload`                 | Upload file to a bucket                  |
| GET    | `/api/assets/{bucket}/{filename}`             | Download a file                          |
| GET    | `/api/assets/{bucket}/signed/{filename}`      | Get a short-lived signed URL             |
| POST   | `/api/assets/batch-signed-urls`               | Batch-issue signed URLs                  |
| POST   | `/api/assets/batch-thumbnails`                | Batch-issue thumbnail URLs               |
| DELETE | `/api/assets/{bucket}/{filename}`             | Delete a file                            |
| POST   | `/api/assets/personal-photos/reindex`         | Re-embed personal photos for semantic search |
| GET    | `/api/personas`                               | List personas                            |
| PUT    | `/api/personas`                               | Upsert a persona                         |
| DELETE | `/api/personas`                               | Delete a persona                         |
| GET    | `/api/memories`                               | List Mem0 memories                       |
| DELETE | `/api/memories/{id}`                          | Delete a memory                          |

**Clips (UI currently disabled — endpoints remain for re-enable)**

| Method | Path                                              | Description                                  |
|--------|---------------------------------------------------|----------------------------------------------|
| POST   | `/api/clips/jobs/preflight`                       | Validate URL + return metadata before creating a job |
| POST   | `/api/clips/jobs`                                 | Create a clip job and kick off the pipeline  |
| GET    | `/api/clips/jobs`                                 | List the user's clip jobs                    |
| GET    | `/api/clips/jobs/{id}`                            | Get a job with candidates                    |
| GET    | `/api/clips/jobs/{id}/events`                     | SSE stream of pipeline progress              |
| POST   | `/api/clips/jobs/{id}/render`                     | Render finals for selected candidates        |
| POST   | `/api/clips/jobs/{id}/cancel`                     | Cancel an in-flight job                      |
| DELETE | `/api/clips/jobs/{id}`                            | Delete a job and its storage objects         |
| GET    | `/api/clips/candidates/{id}/preview-url`          | Signed URL for the candidate preview MP4     |
| GET    | `/api/clips/candidates/{id}/final-url`            | Signed URL for the candidate final MP4       |
| POST   | `/api/clips/cleanup`                              | TTL sweep (service token via `CLIPS_CLEANUP_TOKEN`) |

The `/api/chat` endpoint drives the chat workflow. Based on the `type` field in the request body (`text`, `approval`, `save`, `regenerate`) and conversation history, it determines the next action: generate a plan, produce a thumbnail or script, save to outputs, or regenerate with feedback.

## Clips feature (disabled)

The clip extraction pipeline is fully implemented and tested (329 backend tests pass) but the UI entry point is currently hidden:

- `frontend/src/App.tsx` — the `/clips` and `/clips/:jobId` `<Route>` lines and their `lazy()` imports are commented out
- `frontend/src/components/IconRail.tsx` — the Clips sidebar `<Tooltip>` / `<IconButton>` is removed

To **re-enable**, uncomment those four lines in `App.tsx` and restore the Tooltip block in `IconRail.tsx`. Everything backend-side stays live: `backend/services/youtube_saas.py`, `backend/services/clips/*`, `backend/routes/clips.py`, plus the DB tables `clip_jobs` and `clip_candidates`.

Why disabled: the SaaS replacement (RapidAPI youtube-media-downloader) was added after YouTube began bot-blocking yt-dlp on datacenter IPs. The free tier covers ~20–30 jobs/month; pushing it harder requires a paid plan. The feature is on ice until usage volume is known. When re-enabling, also consider the optimisation of caching `fetch_video_info` once per pipeline run instead of 3–5 times.
