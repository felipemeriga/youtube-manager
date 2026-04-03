# YouTube Manager

A chat-based YouTube thumbnail creator powered by an AI agent. Describe a thumbnail in natural language and the agent analyzes your reference thumbnails, selects personal photos, crafts a plan, and generates the final image using Nano Banana (Gemini image generation). Built as the first feature of a broader YouTube channel manager platform.

## Features

- **Chat-based agentic UI** -- conversational interface for creating thumbnails through natural language
- **Two-step approval flow** -- review the agent's plan before generation, then approve or regenerate the result
- **4 asset buckets** -- reference thumbnails, personal photos, fonts, and generated outputs, all managed through the UI
- **SSE streaming** -- real-time streaming of agent responses and generation status
- **Nano Banana image generation** -- Gemini API generates thumbnails from reference images, photos, fonts, and the agent's plan in a single call
- **server-guardian LLM brain** -- Claude Opus via server-guardian analyzes assets and crafts thumbnail plans at zero API cost

## Architecture

```
Browser (React + MUI)
    |
    | SSE + REST
    v
FastAPI Backend
    |--- server-guardian (POST /api/ask) -- agent brain (Claude Opus)
    |--- Gemini API (Nano Banana)       -- image generation
    |--- Supabase                       -- PostgreSQL, Storage, Auth
```

Conversation history is the state machine. No LangGraph, no task queues. The `/api/chat` SSE endpoint handles the entire workflow -- the agent reads prior messages to determine where it is in the flow and what to do next.

**Tech stack:**

| Layer    | Technology                                       |
|----------|--------------------------------------------------|
| Frontend | React 18, TypeScript, Material-UI v6, Vite       |
| Backend  | FastAPI, Python 3.10+, uvicorn                   |
| LLM      | server-guardian (Claude Opus), Gemini API         |
| Database | Supabase (PostgreSQL + Storage + Auth)            |
| Deploy   | Docker Compose, Traefik, Nginx                   |

## Prerequisites

- Python 3.10+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) package manager
- A Supabase project (with the schema from `backend/db/schema.sql` applied)
- Gemini API key
- A running [server-guardian](https://github.com/your-org/server-guardian) instance

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

| Variable              | Purpose                                    |
|-----------------------|--------------------------------------------|
| `SUPABASE_URL`        | Supabase project URL                       |
| `SUPABASE_SERVICE_KEY` | Supabase service role key                 |
| `SUPABASE_JWT_SECRET` | JWT verification secret                    |
| `GEMINI_API_KEY`      | Gemini API key for Nano Banana generation  |
| `GUARDIAN_URL`        | server-guardian URL (default: `http://server-guardian:3000`) |
| `GUARDIAN_API_KEY`    | Bearer token for server-guardian `/api/ask` |
| `CORS_ORIGINS`       | Allowed origins (default: `http://localhost:5173`) |

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
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py                      # FastAPI app, CORS, health endpoint
│   ├── config.py                    # pydantic-settings configuration
│   ├── auth.py                      # JWT validation via Supabase
│   ├── db/
│   │   └── schema.sql               # PostgreSQL schema (conversations, messages, RLS)
│   ├── routes/
│   │   ├── conversations.py         # CRUD for conversations
│   │   ├── chat.py                  # SSE chat endpoint (workflow engine)
│   │   └── assets.py                # File upload/download for 4 buckets
│   ├── services/
│   │   ├── guardian.py              # server-guardian client
│   │   ├── nano_banana.py           # Gemini image generation client
│   │   └── thumbnail_pipeline.py    # Orchestrates plan + generation flow
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_conversations.py
│       ├── test_assets.py
│       ├── test_guardian.py
│       ├── test_nano_banana.py
│       └── test_thumbnail_pipeline.py
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf                   # SPA routing
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx                  # Router + protected routes
│       ├── main.tsx
│       ├── theme.ts                 # MUI dark theme (glassmorphism)
│       ├── lib/
│       │   ├── supabase.ts          # Supabase client
│       │   └── api.ts               # API client + SSE streaming
│       ├── components/
│       │   ├── AuthProvider.tsx      # Session context
│       │   ├── ProtectedRoute.tsx    # Auth guard
│       │   ├── AppLayout.tsx         # Sidebar + main area
│       │   ├── IconRail.tsx          # Left nav (Chat, Assets)
│       │   ├── ContextPanel.tsx      # Conversations list / folder browser
│       │   ├── ChatArea.tsx          # Messages + auto-scroll
│       │   ├── ChatInput.tsx         # Text input
│       │   ├── MessageBubble.tsx     # Text, plan, and image messages
│       │   ├── ApprovalButtons.tsx   # Approve/Reject + Save/Regenerate
│       │   ├── ThinkingBar.tsx       # Loading indicator
│       │   ├── AssetGrid.tsx         # Grid view of images/fonts
│       │   └── AssetUpload.tsx       # Drag-and-drop upload
│       └── pages/
│           ├── LoginPage.tsx         # Sign-in only (no sign-up)
│           ├── ChatPage.tsx          # Chat state management
│           └── AssetsPage.tsx        # Browse/upload assets (4 folders)
└── docs/
    └── superpowers/
        └── specs/                   # Design specifications
```

## API Endpoints

| Method | Path                            | Description                          |
|--------|---------------------------------|--------------------------------------|
| GET    | `/api/health`                   | Health check                         |
| GET    | `/api/conversations`            | List user conversations              |
| POST   | `/api/conversations`            | Create a new conversation            |
| GET    | `/api/conversations/{id}`       | Get conversation with messages       |
| DELETE | `/api/conversations/{id}`       | Delete a conversation                |
| POST   | `/api/chat`                     | Stream chat response (SSE)           |
| GET    | `/api/assets/{bucket}`          | List files in a bucket               |
| POST   | `/api/assets/{bucket}/upload`   | Upload file to a bucket              |
| GET    | `/api/assets/{bucket}/{name}`   | Download a file                      |
| DELETE | `/api/assets/{bucket}/{name}`   | Delete a file                        |

All endpoints (except health) require a valid Supabase JWT in the `Authorization` header.

The `/api/chat` endpoint drives the entire workflow. Based on the `type` field in the request body (`text`, `approval`, `save`, `regenerate`) and conversation history, it determines the next action: generate a plan, produce a thumbnail, save to outputs, or regenerate with feedback.
