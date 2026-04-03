# YouTube Thumbnail Creator — Design Spec

## Overview

A chat-based YouTube thumbnail creator that uses an AI agent to generate thumbnails from natural language descriptions. The agent analyzes reference thumbnails, selects appropriate personal photos, and generates images using Nano Banana (Gemini image generation). Built as the first feature of a broader YouTube channel manager platform.

## Architecture

### Approach: Simple Sequential Pipeline

Conversation history is the state machine. No LangGraph, no task queues. The `/api/chat` SSE endpoint handles the entire workflow — the agent reads prior messages to determine where it is in the flow and what to do next.

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (React + MUI)                  │
│                                                           │
│  ┌──────────┐  ┌───────────────────────────────────────┐ │
│  │ Sidebar   │  │  Chat Area                            │ │
│  │ Convos    │  │  Messages + Approval Buttons          │ │
│  │ Ref Thumbs│  │  Inline image display                 │ │
│  │ Photos    │  │  [Approve] [Reject]                   │ │
│  │ Fonts     │  │  [Save to Outputs] [Regenerate]       │ │
│  │ Outputs   │  │                                       │ │
│  └──────────┘  └───────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────┘
                             │ SSE + REST
                             ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                     │
│  Auth (JWT) · Routes (/api/*) · Thumbnail Pipeline       │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼───────────┐    ┌─────────────▼──────────────┐
│  server-guardian      │    │  Gemini API (Nano Banana)   │
│  POST /api/ask        │    │  Image generation           │
│  Claude LLM (zero $)  │    │  with vision input          │
└──────────────────────┘    └────────────────────────────┘
           │
┌──────────▼─────────────────────────────────────────────┐
│  Supabase (separate project from agentic-rag)           │
│  PostgreSQL: conversations, messages (RLS by user)      │
│  Storage: reference-thumbs/, personal-photos/,          │
│           fonts/, outputs/                              │
│  Auth: manual accounts only (no sign-up)                │
└────────────────────────────────────────────────────────┘
```

### External Service Integration

- **server-guardian** (`POST /api/ask`): Agent brain. Claude Opus via Max subscription, zero API cost. Reachable at `http://server-guardian:3000` on the Docker `proxy` network. Used for analyzing assets, crafting plans, and deciding which references/photos to use.
- **Gemini API (Nano Banana)**: Image generation. Receives all reference thumbs, personal photos, fonts, video title, and the agent's plan in a single call. Returns the generated thumbnail.
- **Supabase**: Own project instance (not shared with agentic-rag). PostgreSQL for conversations/messages, Storage for image/font assets, Auth for user management.

## Chat Workflow & Approval Flow

### Turn-by-Turn Flow

**Turn 1 — User describes the thumbnail:**
User types a description including the video title. Example: "Create a thumbnail for my Python tutorial about decorators. Title: 'Python Decorators Explained'"

**Turn 2 — Agent responds with plan:**
1. Backend fetches all files from reference-thumbs, personal-photos, and fonts buckets
2. Sends everything to server-guardian `/api/ask` with system prompt instructing it to analyze assets and propose a plan
3. Streams the plan text via SSE
4. Message rendered with `[Approve]` `[Reject]` buttons

**Turn 3 — User approves or rejects:**
- Approve button sends: `{ content: "APPROVED", type: "approval" }`
- Reject button opens text input for feedback, sends as regular message

**Turn 4 (if approved) — Generation:**
1. Backend reads conversation history, sees approval
2. Builds Nano Banana prompt from the plan + all assets (images + fonts + title)
3. Calls Gemini API
4. Streams status updates via SSE ("Generating thumbnail...")
5. Receives generated image, stores temporarily
6. Streams image inline in the message
7. Message rendered with `[Save to Outputs]` `[Regenerate]` buttons

**Turn 5 — Final approval:**
- Save button sends: `{ content: "SAVE_OUTPUT", type: "save" }` → backend saves to outputs bucket, confirms in chat
- Regenerate button sends: `{ content: "REGENERATE", type: "regenerate" }` with optional feedback → re-calls Nano Banana

### Message Types

| type | role | Description |
|------|------|-------------|
| `text` | user | Regular description or feedback |
| `plan` | assistant | Agent's proposed plan (shows Approve/Reject) |
| `approval` | user | User approved the plan |
| `image` | assistant | Generated thumbnail (shows Save/Regenerate) |
| `save` | user | User approved the image for saving |
| `regenerate` | user | User wants a new generation |

## Database Schema

### PostgreSQL (Supabase — separate project)

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- conversations
CREATE TABLE conversations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title       TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Auto-update updated_at
CREATE TRIGGER update_conversations_updated_at
  BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- messages
CREATE TABLE messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT NOT NULL,
  type            TEXT NOT NULL DEFAULT 'text' CHECK (type IN ('text', 'plan', 'approval', 'image', 'save', 'regenerate')),
  image_url       TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- RLS policies
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY conversations_user_policy ON conversations
  FOR ALL USING (auth.uid() = user_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY messages_user_policy ON messages
  FOR ALL USING (
    conversation_id IN (
      SELECT id FROM conversations WHERE user_id = auth.uid()
    )
  );
```

### Supabase Storage — 4 Buckets

| Bucket | Contents | Max file size |
|--------|----------|---------------|
| `reference-thumbs` | Example thumbnails (~5 files) | 10MB |
| `personal-photos` | User photos (~20 files) | 10MB |
| `fonts` | Font files (.ttf, .otf) | 5MB |
| `outputs` | Generated thumbnails | 10MB |

All buckets scoped by `user_id/` prefix path.

## API Endpoints

### Auth
JWT validation via Supabase. All routes protected with `Depends(get_current_user)`.

### Conversations
```
GET    /api/conversations          → list user's conversations
POST   /api/conversations          → create new conversation
GET    /api/conversations/{id}     → get conversation + messages
DELETE /api/conversations/{id}     → delete conversation
```

### Chat
```
POST   /api/chat                   → stream chat response (SSE)
       body: { conversation_id, content, type }
       type: "text" | "approval" | "save" | "regenerate"
```

The `/api/chat` endpoint handles the entire workflow. Based on `type` and conversation history:
- `text` → new request or feedback, calls server-guardian for plan
- `approval` → triggers Nano Banana generation
- `save` → saves generated image to outputs bucket
- `regenerate` → re-calls Nano Banana with optional feedback

### Assets
```
GET    /api/assets/{bucket}        → list files in bucket
POST   /api/assets/{bucket}/upload → upload file to bucket
DELETE /api/assets/{bucket}/{name} → delete file from bucket
GET    /api/assets/{bucket}/{name} → download file
```

### Health
```
GET    /api/health                 → { status: "ok" }
```

## Frontend Structure

### Tech Stack
- React 18 + TypeScript
- Material-UI v5 (dark theme with glassmorphism, matching agentic-rag aesthetic)
- Vite bundler
- Supabase JS client for auth

### Component Tree

```
src/
├── App.tsx                    # Router + protected routes
├── lib/
│   ├── supabase.ts           # Supabase client (own project)
│   └── api.ts                # API client + SSE streaming
├── components/
│   ├── AuthProvider.tsx       # Session context
│   ├── ProtectedRoute.tsx     # Auth guard
│   ├── AppLayout.tsx          # Sidebar + main area
│   ├── IconRail.tsx           # Left nav (Chat, Assets)
│   ├── ContextPanel.tsx       # Conversations list or folder browser
│   ├── ChatArea.tsx           # Messages + auto-scroll
│   ├── ChatInput.tsx          # Text input
│   ├── MessageBubble.tsx      # Text, plan, and image messages
│   ├── ApprovalButtons.tsx    # Approve/Reject + Save/Regenerate
│   ├── AssetGrid.tsx          # Grid view of images/fonts in a folder
│   └── AssetUpload.tsx        # Drag-and-drop upload for asset folders
├── pages/
│   ├── LoginPage.tsx          # Sign-in only (no sign-up)
│   ├── ChatPage.tsx           # Chat state management
│   └── AssetsPage.tsx         # Browse/upload assets (4 folders)
└── theme.ts                   # MUI dark theme (glassmorphism)
```

### Key UI Behaviors
- **ApprovalButtons** renders contextually based on message type: plan messages show Approve/Reject, image messages show Save/Regenerate
- **MessageBubble** renders inline images for type `image` with download link
- **LoginPage** has sign-in only — no sign-up tab (manual account creation)
- **ContextPanel** switches between conversation list (on ChatPage) and folder browser (on AssetsPage)

## Deployment

### Docker Compose

Two services following the HIVE pattern:

**Backend:**
- `uv`-based Python image (matching rag-backend)
- `uvicorn main:app --host 0.0.0.0 --port 8000`
- Joins `proxy` network (access to server-guardian)
- Health check: `GET /api/health`

**Frontend:**
- Node.js 22 builder → Nginx
- Vite build with env vars at build time
- SPA routing via nginx.conf
- Depends on backend

### Traefik Routing
- `youtube.merigafy.com/api/*` → backend (priority 100)
- `youtube.merigafy.com/*` → frontend (priority 50)
- HTTPS via Let's Encrypt

### Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `SUPABASE_URL` | backend | YouTube Manager Supabase project URL |
| `SUPABASE_SERVICE_KEY` | backend | Service role key |
| `SUPABASE_JWT_SECRET` | backend | JWT verification |
| `GEMINI_API_KEY` | backend | Nano Banana image generation |
| `GUARDIAN_URL` | backend | `http://server-guardian:3000` |
| `GUARDIAN_API_KEY` | backend | Bearer token for `/api/ask` |
| `VITE_SUPABASE_URL` | frontend | Supabase URL (build-time) |
| `VITE_SUPABASE_ANON_KEY` | frontend | Supabase anon key (build-time) |
| `VITE_API_URL` | frontend | Backend API URL (build-time) |

### Network
Joins the existing `proxy` bridge network shared by all HIVE services. Backend reaches server-guardian at `http://server-guardian:3000`.
