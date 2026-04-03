# YouTube Thumbnail Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a chat-based YouTube thumbnail creator with AI-powered generation using Nano Banana (Gemini), deployed as a full-stack app at youtube.merigafy.com.

**Architecture:** React + MUI + Vite frontend, FastAPI + Python backend, Supabase (separate project) for auth/db/storage. Agent brain via server-guardian `/api/ask` (Claude, zero cost). Image generation via Gemini API Nano Banana. Simple sequential pipeline — conversation history is the state machine. Two-step approval with buttons.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, google-genai, httpx, pyjwt, supabase-py | React 18, TypeScript, MUI v5, Vite, @supabase/supabase-js, react-router-dom, react-markdown | Docker, Nginx, Traefik

**Spec:** `docs/superpowers/specs/2026-04-03-thumbnail-creator-design.md`

---

## File Structure

### Backend (`backend/`)

```
backend/
├── pyproject.toml              # Dependencies (uv)
├── main.py                     # FastAPI app, CORS, router registration, health endpoint
├── auth.py                     # JWT validation via Supabase JWKS
├── config.py                   # Environment variable loading (Pydantic Settings)
├── routes/
│   ├── conversations.py        # CRUD for conversations
│   ├── chat.py                 # SSE streaming chat endpoint
│   └── assets.py               # Asset upload/list/delete/download
├── services/
│   ├── guardian.py              # server-guardian /api/ask client
│   ├── nano_banana.py           # Gemini Nano Banana image generation
│   └── thumbnail_pipeline.py   # Orchestrates the full thumbnail workflow
├── db/
│   └── schema.sql              # PostgreSQL schema + RLS policies
├── Dockerfile                  # Multi-stage uv build
└── tests/
    ├── conftest.py             # Shared fixtures
    ├── test_auth.py            # Auth tests
    ├── test_conversations.py   # Conversation CRUD tests
    ├── test_assets.py          # Asset endpoint tests
    ├── test_guardian.py        # Guardian client tests
    ├── test_nano_banana.py     # Nano Banana client tests
    └── test_thumbnail_pipeline.py  # Pipeline orchestration tests
```

### Frontend (`frontend/`)

```
frontend/
├── package.json                # Dependencies
├── vite.config.ts              # Vite config with API proxy
├── tsconfig.json               # TypeScript config
├── nginx.conf                  # Nginx SPA routing + API proxy + SSE
├── Dockerfile                  # Multi-stage Node builder → Nginx
├── index.html                  # Vite entry
└── src/
    ├── main.tsx                # React entry
    ├── App.tsx                 # Router + AuthProvider + protected routes
    ├── theme.ts                # MUI dark theme with glassmorphism
    ├── lib/
    │   ├── supabase.ts         # Supabase client init
    │   └── api.ts              # Authenticated fetch + SSE streamChat()
    ├── components/
    │   ├── AuthProvider.tsx     # Auth session context
    │   ├── ProtectedRoute.tsx   # Auth guard redirect
    │   ├── AppLayout.tsx        # 3-column layout (icon rail + sidebar + main)
    │   ├── IconRail.tsx         # Left nav icons (Chat, Assets)
    │   ├── ContextPanel.tsx     # Conversations list or folder browser
    │   ├── ChatArea.tsx         # Message list + auto-scroll + empty state
    │   ├── ChatInput.tsx        # Text input, Enter to send
    │   ├── MessageBubble.tsx    # Renders text, plan, image messages
    │   ├── ApprovalButtons.tsx  # Approve/Reject, Save/Regenerate buttons
    │   ├── ThinkingBar.tsx      # Processing stage indicator
    │   ├── AssetGrid.tsx        # Grid view of images/fonts
    │   └── AssetUpload.tsx      # Drag-and-drop upload zone
    └── pages/
        ├── LoginPage.tsx        # Sign-in only (no sign-up)
        ├── ChatPage.tsx         # Chat state management + streaming
        └── AssetsPage.tsx       # Browse/upload 4 asset folders
```

### Root

```
youtube-manager/
├── docker-compose.yml          # Backend + Frontend services
├── .env.example                # Required env vars template
├── .gitignore                  # node_modules, .env, __pycache__, .superpowers
├── backend/                    # (above)
└── frontend/                   # (above)
```

---

## Task 1: Project Scaffolding — Backend

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/main.py`
- Create: `backend/config.py`
- Create: `.env.example`

- [ ] **Step 1: Create backend pyproject.toml**

```toml
[project]
name = "youtube-manager-backend"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi[standard]>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pyjwt[crypto]>=2.8.0",
    "python-dotenv>=1.0.0",
    "supabase>=2.0.0",
    "httpx>=0.27.0",
    "google-genai>=1.0.0",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str
    gemini_api_key: str
    guardian_url: str = "http://server-guardian:3000"
    guardian_api_key: str
    cors_origins: str = "http://localhost:5173"

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 3: Create main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

app = FastAPI(title="YouTube Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Create .env.example at project root**

```env
# Supabase (YouTube Manager project — separate from agentic-rag)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_ANON_KEY=your-anon-key

# Gemini API (Nano Banana)
GEMINI_API_KEY=your-gemini-api-key

# Server Guardian (LLM brain)
GUARDIAN_URL=http://server-guardian:3000
GUARDIAN_API_KEY=your-guardian-api-key

# Frontend (build-time)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 5: Install dependencies and verify**

```bash
cd backend && uv sync
```

- [ ] **Step 6: Run health endpoint to verify**

```bash
cd backend && uv run uvicorn main:app --port 8000 &
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
kill %1
```

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/main.py backend/config.py .env.example
git commit -m "feat: scaffold backend with FastAPI, config, and health endpoint"
```

---

## Task 2: Database Schema

**Files:**
- Create: `backend/db/schema.sql`

- [ ] **Step 1: Create schema.sql**

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

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- messages
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'text'
                    CHECK (type IN ('text', 'plan', 'approval', 'image', 'save', 'regenerate')),
    image_url       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_select ON conversations
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY conversations_insert ON conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY conversations_update ON conversations
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY conversations_delete ON conversations
    FOR DELETE USING (auth.uid() = user_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_select ON messages
    FOR SELECT USING (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );
CREATE POLICY messages_insert ON messages
    FOR INSERT WITH CHECK (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );
CREATE POLICY messages_delete ON messages
    FOR DELETE USING (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );
```

- [ ] **Step 2: Apply schema to Supabase**

Run this SQL in the Supabase SQL Editor for the YouTube Manager project. Also create the 4 storage buckets via the Supabase dashboard:
- `reference-thumbs`
- `personal-photos`
- `fonts`
- `outputs`

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.sql
git commit -m "feat: add database schema with conversations, messages, and RLS policies"
```

---

## Task 3: Backend Auth

**Files:**
- Create: `backend/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/conftest.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings():
    with patch("config.settings") as mock:
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_service_key = "test-service-key"
        mock.supabase_jwt_secret = "test-jwt-secret"
        mock.gemini_api_key = "test-gemini-key"
        mock.guardian_url = "http://localhost:3000"
        mock.guardian_api_key = "test-guardian-key"
        mock.cors_origins = "http://localhost:5173"
        yield mock


@pytest.fixture
def client(mock_settings):
    from main import app
    return TestClient(app)


@pytest.fixture
def valid_user_id():
    return "550e8400-e29b-41d4-a716-446655440000"
```

Create `backend/tests/test_auth.py`:

```python
import jwt
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from auth import get_current_user


def create_test_token(user_id: str, secret: str, expired: bool = False) -> str:
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": int(time.time()) + (-3600 if expired else 3600),
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_token_returns_user_id(valid_user_id):
    secret = "test-jwt-secret"
    token = create_test_token(valid_user_id, secret)

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == valid_user_id


def test_missing_token_returns_401():
    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 401


def test_expired_token_returns_401(valid_user_id):
    secret = "test-jwt-secret"
    token = create_test_token(valid_user_id, secret, expired=True)

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_auth.py -v
# Expected: FAIL — auth module does not exist
```

- [ ] **Step 3: Implement auth.py**

```python
import jwt
from fastapi import Request, HTTPException

from config import settings


async def get_current_user(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no sub claim")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_auth.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat: add JWT authentication with Supabase token validation"
```

---

## Task 4: Backend Conversation CRUD

**Files:**
- Create: `backend/routes/conversations.py`
- Create: `backend/tests/test_conversations.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_conversations.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.conversations import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase():
    mock_sb = MagicMock()
    return mock_sb


def test_list_conversations():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "conv-1", "title": "Test", "created_at": "2026-04-03T00:00:00Z", "updated_at": "2026-04-03T00:00:00Z"}
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "conv-1"


def test_create_conversation():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "new-conv", "user_id": user_id, "title": None, "created_at": "2026-04-03T00:00:00Z", "updated_at": "2026-04-03T00:00:00Z"}
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    assert response.json()["id"] == "new-conv"


def test_get_conversation_with_messages():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    # First call: get conversation
    conv_query = MagicMock()
    conv_query.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "conv-1", "title": "Test", "user_id": user_id
    }
    # Second call: get messages
    msg_query = MagicMock()
    msg_query.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "msg-1", "role": "user", "content": "hello", "type": "text", "image_url": None}
    ]
    mock_sb.table.side_effect = lambda name: conv_query if name == "conversations" else msg_query

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1")

    assert response.status_code == 200
    assert response.json()["id"] == "conv-1"
    assert len(response.json()["messages"]) == 1


def test_delete_conversation():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "conv-1"}
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.delete("/api/conversations/conv-1")

    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_conversations.py -v
# Expected: FAIL — routes.conversations does not exist
```

- [ ] **Step 3: Implement conversations router**

Create `backend/routes/__init__.py` (empty file).

Create `backend/routes/conversations.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


@router.get("/api/conversations")
async def list_conversations(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return result.data


@router.post("/api/conversations")
async def create_conversation(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").insert({"user_id": user_id}).execute()
    return result.data[0]


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    conv = sb.table("conversations").select("*").eq("id", conversation_id).eq("user_id", user_id).single().execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = sb.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
    return {**conv.data, "messages": messages.data}


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").delete().eq("id", conversation_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/main.py` after the CORS middleware block:

```python
from routes.conversations import router as conversations_router

app.include_router(conversations_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_conversations.py -v
# Expected: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/routes/__init__.py backend/routes/conversations.py backend/tests/test_conversations.py backend/main.py
git commit -m "feat: add conversation CRUD endpoints"
```

---

## Task 5: Backend Assets Endpoints

**Files:**
- Create: `backend/routes/assets.py`
- Create: `backend/tests/test_assets.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_assets.py`:

```python
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.assets import router

VALID_BUCKETS = ["reference-thumbs", "personal-photos", "fonts", "outputs"]


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def test_list_assets():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [
        {"name": "thumb1.png", "metadata": {"size": 12345}}
    ]

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/reference-thumbs")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "thumb1.png"


def test_list_assets_invalid_bucket():
    client = create_app("test-user")
    response = client.get("/api/assets/invalid-bucket")
    assert response.status_code == 400


def test_upload_asset():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {"Key": "test-user/photo.jpg"}

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/personal-photos/upload",
            files={"file": ("photo.jpg", b"fake-image-data", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "photo.jpg"


def test_delete_asset():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.remove.return_value = [{"name": "photo.jpg"}]

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.delete("/api/assets/personal-photos/photo.jpg")

    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_assets.py -v
# Expected: FAIL — routes.assets does not exist
```

- [ ] **Step 3: Implement assets router**

Create `backend/routes/assets.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()

VALID_BUCKETS = {"reference-thumbs", "personal-photos", "fonts", "outputs"}
MAX_FILE_SIZES = {
    "reference-thumbs": 10 * 1024 * 1024,
    "personal-photos": 10 * 1024 * 1024,
    "fonts": 5 * 1024 * 1024,
    "outputs": 10 * 1024 * 1024,
}


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


def validate_bucket(bucket: str):
    if bucket not in VALID_BUCKETS:
        raise HTTPException(status_code=400, detail=f"Invalid bucket: {bucket}. Must be one of {VALID_BUCKETS}")


@router.get("/api/assets/{bucket}")
async def list_assets(bucket: str, user_id: str = Depends(get_current_user)):
    validate_bucket(bucket)
    sb = get_supabase()
    files = sb.storage.from_(bucket).list(path=user_id)
    return files


@router.post("/api/assets/{bucket}/upload")
async def upload_asset(bucket: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    validate_bucket(bucket)
    content = await file.read()
    max_size = MAX_FILE_SIZES[bucket]
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max {max_size // (1024*1024)}MB")

    sb = get_supabase()
    storage_path = f"{user_id}/{file.filename}"
    sb.storage.from_(bucket).upload(storage_path, content, {"content-type": file.content_type})
    return {"name": file.filename, "bucket": bucket, "path": storage_path}


@router.delete("/api/assets/{bucket}/{filename}")
async def delete_asset(bucket: str, filename: str, user_id: str = Depends(get_current_user)):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    sb.storage.from_(bucket).remove([storage_path])
    return {"status": "deleted", "name": filename}


@router.get("/api/assets/{bucket}/{filename}")
async def download_asset(bucket: str, filename: str, user_id: str = Depends(get_current_user)):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    data = sb.storage.from_(bucket).download(storage_path)
    from fastapi.responses import Response
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/main.py`:

```python
from routes.assets import router as assets_router

app.include_router(assets_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_assets.py -v
# Expected: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/routes/assets.py backend/tests/test_assets.py backend/main.py
git commit -m "feat: add asset upload/list/delete/download endpoints for 4 storage buckets"
```

---

## Task 6: Server-Guardian Client

**Files:**
- Create: `backend/services/guardian.py`
- Create: `backend/tests/test_guardian.py`

- [ ] **Step 1: Write the failing test**

Create `backend/services/__init__.py` (empty file).

Create `backend/tests/test_guardian.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from services.guardian import ask_guardian


@pytest.mark.asyncio
async def test_ask_guardian_returns_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Here is my plan for your thumbnail..."}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            result = await ask_guardian(
                prompt="Create a thumbnail plan for a Python tutorial",
                system="You are a YouTube thumbnail designer."
            )

    assert result == "Here is my plan for your thumbnail..."
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://localhost:3000/api/ask"
    body = call_args[1]["json"]
    assert "Create a thumbnail plan" in body["prompt"]
    assert body["system"] == "You are a YouTube thumbnail designer."


@pytest.mark.asyncio
async def test_ask_guardian_handles_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=MagicMock(status_code=500)
    ))

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            with pytest.raises(Exception, match="Guardian request failed"):
                await ask_guardian(prompt="test", system="test")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_guardian.py -v
# Expected: FAIL — services.guardian does not exist
```

- [ ] **Step 3: Implement guardian client**

Create `backend/services/guardian.py`:

```python
import httpx

from config import settings


async def ask_guardian(prompt: str, system: str, timeout: int = 120) -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.guardian_url}/api/ask",
                json={"prompt": prompt, "system": system, "timeout": timeout * 1000},
                headers={"Authorization": f"Bearer {settings.guardian_api_key}"},
                timeout=timeout + 10,
            )
            response.raise_for_status()
            return response.json()["response"]
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise Exception(f"Guardian request failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_guardian.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/services/__init__.py backend/services/guardian.py backend/tests/test_guardian.py
git commit -m "feat: add server-guardian HTTP client for LLM reasoning"
```

---

## Task 7: Nano Banana Client

**Files:**
- Create: `backend/services/nano_banana.py`
- Create: `backend/tests/test_nano_banana.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_nano_banana.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from services.nano_banana import generate_thumbnail


@pytest.mark.asyncio
async def test_generate_thumbnail_returns_image_bytes():
    # Mock the Gemini client and response
    mock_image = MagicMock()
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake-png-data"

    # Create a mock BytesIO-like object
    mock_buffer = BytesIO(mock_image_bytes)
    mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(mock_image_bytes))

    mock_part = MagicMock()
    mock_part.inline_data = True
    mock_part.as_image.return_value = mock_image

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            result = await generate_thumbnail(
                prompt="A tech-style YouTube thumbnail with Python code background",
                reference_images=[b"ref-image-1-bytes"],
                personal_photos=[b"photo-1-bytes"],
                font_files=[b"font-1-bytes"],
            )

    assert result is not None
    assert isinstance(result, bytes)
    mock_client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_thumbnail_no_image_in_response():
    mock_part = MagicMock()
    mock_part.inline_data = None

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            with pytest.raises(Exception, match="No image generated"):
                await generate_thumbnail(
                    prompt="test prompt",
                    reference_images=[],
                    personal_photos=[],
                    font_files=[],
                )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_nano_banana.py -v
# Expected: FAIL — services.nano_banana does not exist
```

- [ ] **Step 3: Implement Nano Banana client**

Create `backend/services/nano_banana.py`:

```python
from io import BytesIO

from google import genai
from google.genai import types

from config import settings


async def generate_thumbnail(
    prompt: str,
    reference_images: list[bytes],
    personal_photos: list[bytes],
    font_files: list[bytes],
) -> bytes:
    client = genai.Client(api_key=settings.gemini_api_key)

    contents = []

    # Add reference thumbnails
    if reference_images:
        contents.append("Here are my reference thumbnails for style inspiration:")
        for img_bytes in reference_images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

    # Add personal photos
    if personal_photos:
        contents.append("Here are my personal photos. Pick the best one for this thumbnail:")
        for img_bytes in personal_photos:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    # Add font files
    if font_files:
        contents.append("Here are available fonts for the text:")
        for font_bytes in font_files:
            contents.append(types.Part.from_bytes(data=font_bytes, mime_type="font/ttf"))

    # Add the generation prompt
    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-image-generation",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.parts:
        if part.inline_data is not None:
            image = part.as_image()
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

    raise Exception("No image generated by Nano Banana")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_nano_banana.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/services/nano_banana.py backend/tests/test_nano_banana.py
git commit -m "feat: add Nano Banana (Gemini) image generation client"
```

---

## Task 8: Thumbnail Pipeline

**Files:**
- Create: `backend/services/thumbnail_pipeline.py`
- Create: `backend/tests/test_thumbnail_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_thumbnail_pipeline.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.thumbnail_pipeline import handle_chat_message


@pytest.mark.asyncio
async def test_text_message_generates_plan():
    mock_sb = MagicMock()
    # Mock fetching conversation messages (empty history)
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    # Mock insert (save user message + assistant plan)
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    # Mock update conversation title
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    # Mock listing storage files
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch("services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock) as mock_guardian:
            mock_guardian.return_value = "I'll create a tech-style thumbnail using your studio portrait..."

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="Create a thumbnail for my Python tutorial. Title: Python Decorators",
                msg_type="text",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    stages = [e for e in events if "stage" in e]
    tokens = [e for e in events if "token" in e]
    done = [e for e in events if e.get("done")]
    plan_type = [e for e in events if e.get("message_type") == "plan"]

    assert any(s["stage"] == "analyzing" for s in stages)
    assert len(tokens) > 0
    assert len(done) == 1
    assert len(plan_type) == 1


@pytest.mark.asyncio
async def test_approval_triggers_generation():
    mock_sb = MagicMock()
    # Mock fetching conversation messages (has plan + approval)
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {"role": "assistant", "content": "I'll use your studio portrait...", "type": "plan"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-2"}]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"

    fake_image = b"\x89PNG\r\n\x1a\nfake-thumbnail"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch("services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    stages = [e for e in events if "stage" in e]
    image_events = [e for e in events if e.get("message_type") == "image"]

    assert any(s["stage"] == "generating" for s in stages)
    assert len(image_events) == 1
    assert "image_base64" in image_events[0]


@pytest.mark.asyncio
async def test_save_stores_to_outputs():
    mock_sb = MagicMock()
    # Mock fetching conversation messages (has image message with URL)
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "assistant", "content": "Generated thumbnail", "type": "image", "image_url": "temp/thumb.png"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-3"}]
    mock_sb.storage.from_.return_value.download.return_value = b"fake-image-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {"Key": "test-user/thumb.png"}

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert "saved" in done[0].get("content", "").lower() or done[0].get("saved")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_thumbnail_pipeline.py -v
# Expected: FAIL — services.thumbnail_pipeline does not exist
```

- [ ] **Step 3: Implement thumbnail pipeline**

Create `backend/services/thumbnail_pipeline.py`:

```python
import json
import base64
import uuid
from typing import AsyncGenerator

from supabase import create_client

from config import settings
from services.guardian import ask_guardian
from services.nano_banana import generate_thumbnail


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def fetch_all_assets(sb, user_id: str, bucket: str) -> list[bytes]:
    files = sb.storage.from_(bucket).list(path=user_id)
    result = []
    for f in files:
        if f.get("name"):
            data = sb.storage.from_(bucket).download(f"{user_id}/{f['name']}")
            result.append(data)
    return result


SYSTEM_PROMPT = """You are a professional YouTube thumbnail designer. The user will describe what thumbnail they want.

You will receive:
- Reference thumbnails for style inspiration
- The user's personal photos to choose from
- Available fonts for text

Analyze all provided assets and propose a detailed thumbnail plan including:
- Which reference thumbnail style to follow and why
- Which personal photo to use and why
- Text placement, font choice, and color scheme
- Overall composition and mood

Be specific and visual in your description. The plan will be used to generate the actual thumbnail."""


async def handle_text_message(
    sb, conversation_id: str, content: str, user_id: str
) -> AsyncGenerator[str, None]:
    # Save user message
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": content,
        "type": "text",
    }).execute()

    # Update conversation title from first message
    sb.table("conversations").update({"title": content[:50]}).eq("id", conversation_id).execute()

    yield sse_event({"stage": "analyzing"})

    # Fetch all assets
    ref_thumbs = fetch_all_assets(sb, user_id, "reference-thumbs")
    photos = fetch_all_assets(sb, user_id, "personal-photos")
    fonts = fetch_all_assets(sb, user_id, "fonts")

    # Build prompt for Guardian
    asset_summary = f"Reference thumbnails: {len(ref_thumbs)} images. Personal photos: {len(photos)} images. Fonts: {len(fonts)} files."
    full_prompt = f"{asset_summary}\n\nUser request: {content}"

    # Ask Guardian for a plan
    plan = await ask_guardian(prompt=full_prompt, system=SYSTEM_PROMPT)

    # Stream plan tokens
    for token in plan.split():
        yield sse_event({"token": token + " "})

    # Save plan message
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": plan,
        "type": "plan",
    }).execute()

    yield sse_event({"message_type": "plan"})
    yield sse_event({"done": True})


async def handle_approval(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    # Save approval message
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": "APPROVED",
        "type": "approval",
    }).execute()

    yield sse_event({"stage": "generating"})

    # Get conversation history to find the plan
    messages = sb.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute().data
    plan_message = next((m for m in reversed(messages) if m["type"] == "plan"), None)
    user_request = next((m for m in messages if m["type"] == "text"), None)

    prompt_parts = []
    if user_request:
        prompt_parts.append(f"User request: {user_request['content']}")
    if plan_message:
        prompt_parts.append(f"Approved plan: {plan_message['content']}")
    prompt_parts.append("Generate a professional YouTube thumbnail based on the above plan.")

    # Fetch assets
    ref_thumbs = fetch_all_assets(sb, user_id, "reference-thumbs")
    photos = fetch_all_assets(sb, user_id, "personal-photos")
    fonts = fetch_all_assets(sb, user_id, "fonts")

    # Generate thumbnail
    image_bytes = await generate_thumbnail(
        prompt="\n".join(prompt_parts),
        reference_images=ref_thumbs,
        personal_photos=photos,
        font_files=fonts,
    )

    # Store temporarily in outputs bucket
    temp_filename = f"temp_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_filename}"
    sb.storage.from_("outputs").upload(storage_path, image_bytes, {"content-type": "image/png"})

    # Save image message
    image_base64 = base64.b64encode(image_bytes).decode()
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": "Here's your generated thumbnail:",
        "type": "image",
        "image_url": storage_path,
    }).execute()

    yield sse_event({"message_type": "image", "image_base64": image_base64, "image_url": storage_path})
    yield sse_event({"done": True})


async def handle_save(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    # Save the save message
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": "SAVE_OUTPUT",
        "type": "save",
    }).execute()

    # Find the most recent image message
    messages = sb.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute().data
    image_message = next((m for m in reversed(messages) if m["type"] == "image"), None)

    if image_message and image_message.get("image_url"):
        # Image is already in outputs bucket from handle_approval
        # Rename from temp to final
        temp_path = image_message["image_url"]
        final_filename = f"thumbnail_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"

        # Download and re-upload with final name
        image_data = sb.storage.from_("outputs").download(temp_path)
        sb.storage.from_("outputs").upload(final_path, image_data, {"content-type": "image/png"})
        # Remove temp file
        sb.storage.from_("outputs").remove([temp_path])

        # Update the image message with final URL
        sb.table("messages").update({"image_url": final_path}).eq("id", image_message["id"]).execute()

        # Save confirmation message
        sb.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": f"Thumbnail saved to outputs as {final_filename}",
            "type": "text",
        }).execute()

        yield sse_event({"done": True, "saved": True, "content": f"Thumbnail saved as {final_filename}", "path": final_path})
    else:
        yield sse_event({"done": True, "error": "No image found to save"})


async def handle_regenerate(
    sb, conversation_id: str, content: str, user_id: str
) -> AsyncGenerator[str, None]:
    # Save regenerate message
    sb.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": content or "REGENERATE",
        "type": "regenerate",
    }).execute()

    # Re-run generation with optional feedback
    async for event in handle_approval(sb, conversation_id, user_id):
        yield event


async def handle_chat_message(
    conversation_id: str,
    content: str,
    msg_type: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    sb = get_supabase()

    if msg_type == "text":
        async for event in handle_text_message(sb, conversation_id, content, user_id):
            yield event
    elif msg_type == "approval":
        async for event in handle_approval(sb, conversation_id, user_id):
            yield event
    elif msg_type == "save":
        async for event in handle_save(sb, conversation_id, user_id):
            yield event
    elif msg_type == "regenerate":
        async for event in handle_regenerate(sb, conversation_id, content, user_id):
            yield event
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_thumbnail_pipeline.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/services/thumbnail_pipeline.py backend/tests/test_thumbnail_pipeline.py
git commit -m "feat: add thumbnail pipeline orchestrating Guardian + Nano Banana with approval flow"
```

---

## Task 9: Chat SSE Endpoint

**Files:**
- Create: `backend/routes/chat.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Implement chat route**

Create `backend/routes/chat.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from services.thumbnail_pipeline import handle_chat_message

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"


@router.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    return StreamingResponse(
        handle_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            msg_type=request.type,
            user_id=user_id,
        ),
        media_type="text/event-stream",
    )
```

- [ ] **Step 2: Register router in main.py**

Add to `backend/main.py`:

```python
from routes.chat import router as chat_router

app.include_router(chat_router)
```

- [ ] **Step 3: Run all backend tests**

```bash
cd backend && uv run pytest -v
# Expected: all tests pass
```

- [ ] **Step 4: Commit**

```bash
git add backend/routes/chat.py backend/main.py
git commit -m "feat: add chat SSE streaming endpoint"
```

---

## Task 10: Frontend Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/vite-env.d.ts`
- Create: `frontend/src/theme.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "youtube-manager-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@emotion/react": "^11.13.0",
    "@emotion/styled": "^11.13.0",
    "@mui/icons-material": "^6.0.0",
    "@mui/material": "^6.0.0",
    "@supabase/supabase-js": "^2.45.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-markdown": "^9.0.0",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>YouTube Manager</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: 'Inter', sans-serif; background: #0a0a0f; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create src/vite-env.d.ts**

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

- [ ] **Step 6: Create src/theme.ts**

```typescript
import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#7c3aed" },
    secondary: { main: "#3b82f6" },
    background: {
      default: "#0a0a0f",
      paper: "rgba(255,255,255,0.05)",
    },
  },
  typography: {
    fontFamily: "'Inter', sans-serif",
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backdropFilter: "blur(20px)",
          backgroundColor: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
        },
      },
    },
  },
});

export default theme;
```

- [ ] **Step 7: Create src/main.tsx**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import theme from "./theme";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
```

- [ ] **Step 8: Create a placeholder App.tsx**

```tsx
import { Box, Typography } from "@mui/material";

export default function App() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
      }}
    >
      <Typography
        variant="h4"
        sx={{
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        YouTube Manager
      </Typography>
    </Box>
  );
}
```

- [ ] **Step 9: Install dependencies and verify dev server**

```bash
cd frontend && npm install && npm run dev &
# Open http://localhost:5173 — should show "YouTube Manager" gradient text
kill %1
```

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend with React, MUI, Vite, and dark theme"
```

---

## Task 11: Frontend Auth (Supabase + AuthProvider + LoginPage)

**Files:**
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/components/AuthProvider.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create lib/supabase.ts**

```typescript
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

- [ ] **Step 2: Create components/AuthProvider.tsx**

```tsx
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

interface AuthContextType {
  session: Session | null;
  user: User | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  user: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{ session, user: session?.user ?? null, loading, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}
```

- [ ] **Step 3: Create components/ProtectedRoute.tsx**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { Box, CircularProgress } from "@mui/material";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 4: Create pages/LoginPage.tsx**

```tsx
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Box, TextField, Button, Typography, Alert, Paper } from "@mui/material";
import { supabase } from "../lib/supabase";
import { useAuth } from "../components/AuthProvider";
import { useEffect } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { session } = useAuth();

  useEffect(() => {
    if (session) navigate("/", { replace: true });
  }, [session, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "linear-gradient(135deg, #0a0a0f 0%, #1a1025 100%)",
      }}
    >
      <Paper
        sx={{
          p: 4,
          width: 400,
          backdropFilter: "blur(20px)",
          backgroundColor: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 3,
        }}
      >
        <Typography
          variant="h4"
          sx={{
            mb: 3,
            textAlign: "center",
            background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          YouTube Manager
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 3 }}
          />
          <Button
            fullWidth
            type="submit"
            variant="contained"
            disabled={loading}
            sx={{
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              py: 1.5,
            }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}
```

- [ ] **Step 5: Update App.tsx with routing**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./components/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import { Box, Typography } from "@mui/material";

function ChatPagePlaceholder() {
  return (
    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
      <Typography variant="h5" color="text.secondary">Chat — coming soon</Typography>
    </Box>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <ChatPagePlaceholder />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Verify login page renders**

```bash
cd frontend && npm run dev &
# Open http://localhost:5173/login — should show sign-in form
kill %1
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: add Supabase auth, login page, and protected routes"
```

---

## Task 12: Frontend API Client + SSE Streaming

**Files:**
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create lib/api.ts**

```typescript
import { supabase } from "./supabase";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");
  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = await getAuthHeaders();
  const response = await fetch(path, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

export async function apiUpload(path: string, file: File): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(path, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.access_token}` },
    body: formData,
  });

  if (!response.ok) throw new Error(`Upload error: ${response.status}`);
  return response.json();
}

interface StreamCallbacks {
  onToken: (token: string) => void;
  onStage: (stage: string) => void;
  onImage: (base64: string, url: string) => void;
  onDone: (data: Record<string, unknown>) => void;
}

export async function streamChat(
  conversationId: string,
  content: string,
  type: string,
  callbacks: StreamCallbacks
): Promise<void> {
  const headers = await getAuthHeaders();

  const response = await fetch("/api/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({ conversation_id: conversationId, content, type }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const data = JSON.parse(jsonStr);

        if (data.token) callbacks.onToken(data.token);
        if (data.stage) callbacks.onStage(data.stage);
        if (data.image_base64) callbacks.onImage(data.image_base64, data.image_url || "");
        if (data.done) callbacks.onDone(data);
      } catch {
        // Incomplete JSON, will be handled in next chunk
      }
    }
  }
}

// Conversation helpers
export const listConversations = () => apiFetch<Array<Record<string, unknown>>>("/api/conversations");
export const createConversation = () => apiFetch<Record<string, unknown>>("/api/conversations", { method: "POST" });
export const getConversation = (id: string) => apiFetch<Record<string, unknown>>(`/api/conversations/${id}`);
export const deleteConversation = (id: string) => apiFetch<void>(`/api/conversations/${id}`, { method: "DELETE" });

// Asset helpers
export const listAssets = (bucket: string) => apiFetch<Array<Record<string, unknown>>>(`/api/assets/${bucket}`);
export const deleteAsset = (bucket: string, name: string) =>
  apiFetch<void>(`/api/assets/${bucket}/${name}`, { method: "DELETE" });
export const uploadAsset = (bucket: string, file: File) => apiUpload(`/api/assets/${bucket}/upload`, file);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add API client with SSE streaming and auth header injection"
```

---

## Task 13: Frontend Layout (AppLayout + IconRail + ContextPanel)

**Files:**
- Create: `frontend/src/components/AppLayout.tsx`
- Create: `frontend/src/components/IconRail.tsx`
- Create: `frontend/src/components/ContextPanel.tsx`

- [ ] **Step 1: Create components/IconRail.tsx**

```tsx
import { Box, IconButton, Tooltip, Avatar } from "@mui/material";
import ChatIcon from "@mui/icons-material/Chat";
import PhotoLibraryIcon from "@mui/icons-material/PhotoLibrary";
import LogoutIcon from "@mui/icons-material/Logout";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function IconRail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, signOut } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  return (
    <Box
      sx={{
        width: 56,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 2,
        gap: 1,
        borderRight: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.3)",
      }}
    >
      <Avatar
        sx={{
          width: 32,
          height: 32,
          mb: 2,
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          fontSize: 14,
        }}
      >
        {user?.email?.[0]?.toUpperCase() || "Y"}
      </Avatar>

      <Tooltip title="Chat" placement="right">
        <IconButton
          onClick={() => navigate("/")}
          sx={{
            color: isActive("/") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <ChatIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title="Assets" placement="right">
        <IconButton
          onClick={() => navigate("/assets")}
          sx={{
            color: isActive("/assets") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <PhotoLibraryIcon />
        </IconButton>
      </Tooltip>

      <Box sx={{ flex: 1 }} />

      <Tooltip title="Sign out" placement="right">
        <IconButton
          onClick={signOut}
          sx={{ color: "rgba(255,255,255,0.5)", "&:hover": { color: "#ef4444" } }}
        >
          <LogoutIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
```

- [ ] **Step 2: Create components/ContextPanel.tsx**

```tsx
import { Box, Typography, IconButton, List, ListItemButton, ListItemText } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useState } from "react";

interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
}

interface ContextPanelProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export default function ContextPanel({
  conversations,
  selectedId,
  onSelect,
  onCreate,
  onDelete,
}: ContextPanelProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <Box
      sx={{
        width: 220,
        borderRight: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.2)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", p: 1.5 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Conversations
        </Typography>
        <IconButton size="small" onClick={onCreate} sx={{ color: "rgba(255,255,255,0.5)" }}>
          <AddIcon fontSize="small" />
        </IconButton>
      </Box>

      <List sx={{ flex: 1, overflow: "auto", px: 0.5 }}>
        {conversations.map((conv) => (
          <ListItemButton
            key={conv.id}
            selected={conv.id === selectedId}
            onClick={() => onSelect(conv.id)}
            onMouseEnter={() => setHoveredId(conv.id)}
            onMouseLeave={() => setHoveredId(null)}
            sx={{
              borderRadius: 1,
              mb: 0.5,
              py: 0.75,
              "&.Mui-selected": {
                backgroundColor: "rgba(124, 58, 237, 0.15)",
              },
            }}
          >
            <ListItemText
              primary={conv.title || "New conversation"}
              primaryTypographyProps={{
                noWrap: true,
                fontSize: 13,
                color: "text.primary",
              }}
            />
            {hoveredId === conv.id && (
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
                sx={{ color: "rgba(255,255,255,0.3)", "&:hover": { color: "#ef4444" } }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            )}
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}
```

- [ ] **Step 3: Create components/AppLayout.tsx**

```tsx
import { Box } from "@mui/material";
import { Outlet } from "react-router-dom";
import IconRail from "./IconRail";

export default function AppLayout() {
  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <IconRail />
      <Box sx={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <Outlet />
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppLayout.tsx frontend/src/components/IconRail.tsx frontend/src/components/ContextPanel.tsx
git commit -m "feat: add app layout with icon rail and conversation sidebar"
```

---

## Task 14: Frontend Chat Components

**Files:**
- Create: `frontend/src/components/ChatArea.tsx`
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/MessageBubble.tsx`
- Create: `frontend/src/components/ApprovalButtons.tsx`
- Create: `frontend/src/components/ThinkingBar.tsx`

- [ ] **Step 1: Create components/ThinkingBar.tsx**

```tsx
import { Box, Typography, LinearProgress } from "@mui/material";

const STAGE_LABELS: Record<string, string> = {
  analyzing: "Analyzing your assets...",
  generating: "Generating thumbnail...",
};

export default function ThinkingBar({ stage }: { stage: string }) {
  return (
    <Box sx={{ px: 3, py: 1.5 }}>
      <Box
        sx={{
          p: 1.5,
          borderRadius: 2,
          backgroundColor: "rgba(124, 58, 237, 0.1)",
          border: "1px solid rgba(124, 58, 237, 0.2)",
        }}
      >
        <Typography variant="caption" color="primary" sx={{ mb: 0.5, display: "block" }}>
          {STAGE_LABELS[stage] || stage}
        </Typography>
        <LinearProgress
          sx={{
            borderRadius: 1,
            backgroundColor: "rgba(124, 58, 237, 0.1)",
            "& .MuiLinearProgress-bar": {
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            },
          }}
        />
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Create components/ApprovalButtons.tsx**

```tsx
import { Box, Button } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import SaveIcon from "@mui/icons-material/Save";
import RefreshIcon from "@mui/icons-material/Refresh";

interface ApprovalButtonsProps {
  type: "plan" | "image";
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}

export default function ApprovalButtons({ type, onApprove, onReject, disabled }: ApprovalButtonsProps) {
  if (type === "plan") {
    return (
      <Box sx={{ display: "flex", gap: 1, mt: 1.5 }}>
        <Button
          variant="contained"
          startIcon={<CheckIcon />}
          onClick={onApprove}
          disabled={disabled}
          sx={{ background: "linear-gradient(135deg, #059669, #10b981)" }}
        >
          Approve
        </Button>
        <Button
          variant="outlined"
          startIcon={<CloseIcon />}
          onClick={onReject}
          disabled={disabled}
          sx={{ borderColor: "rgba(239,68,68,0.5)", color: "#ef4444" }}
        >
          Reject
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", gap: 1, mt: 1.5 }}>
      <Button
        variant="contained"
        startIcon={<SaveIcon />}
        onClick={onApprove}
        disabled={disabled}
        sx={{ background: "linear-gradient(135deg, #059669, #10b981)" }}
      >
        Save to Outputs
      </Button>
      <Button
        variant="outlined"
        startIcon={<RefreshIcon />}
        onClick={onReject}
        disabled={disabled}
        sx={{ borderColor: "rgba(124,58,237,0.5)", color: "#7c3aed" }}
      >
        Regenerate
      </Button>
    </Box>
  );
}
```

- [ ] **Step 3: Create components/MessageBubble.tsx**

```tsx
import { Box, Typography } from "@mui/material";
import ReactMarkdown from "react-markdown";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ApprovalButtons from "./ApprovalButtons";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface MessageBubbleProps {
  message: Message;
  onApprove?: () => void;
  onReject?: () => void;
  isLatest?: boolean;
  isStreaming?: boolean;
}

export default function MessageBubble({
  message,
  onApprove,
  onReject,
  isLatest,
  isStreaming,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showButtons = isLatest && !isStreaming && onApprove && onReject;

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        px: 3,
        py: 0.75,
      }}
    >
      {!isUser && (
        <Box
          sx={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            mr: 1,
            mt: 0.5,
            flexShrink: 0,
          }}
        >
          <AutoAwesomeIcon sx={{ fontSize: 14, color: "#fff" }} />
        </Box>
      )}

      <Box
        sx={{
          maxWidth: "70%",
          p: 2,
          borderRadius: 2,
          backgroundColor: isUser
            ? "rgba(124, 58, 237, 0.15)"
            : "rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(10px)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        {/* Image display */}
        {message.image_base64 && (
          <Box
            component="img"
            src={`data:image/png;base64,${message.image_base64}`}
            alt="Generated thumbnail"
            sx={{
              width: "100%",
              maxWidth: 512,
              borderRadius: 1,
              mb: 1,
              display: "block",
            }}
          />
        )}

        {/* Text content */}
        <Box sx={{ "& p": { m: 0 }, "& p + p": { mt: 1 }, fontSize: 14, lineHeight: 1.6 }}>
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </Box>

        {/* Approval buttons */}
        {showButtons && message.type === "plan" && (
          <ApprovalButtons type="plan" onApprove={onApprove} onReject={onReject} />
        )}
        {showButtons && message.type === "image" && (
          <ApprovalButtons type="image" onApprove={onApprove} onReject={onReject} />
        )}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Create components/ChatInput.tsx**

```tsx
import { useState, KeyboardEvent } from "react";
import { Box, TextField, IconButton } from "@mui/material";
import SendIcon from "@mui/icons-material/Send";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box
      sx={{
        p: 2,
        borderTop: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.2)",
      }}
    >
      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Describe the thumbnail you want..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              backgroundColor: "rgba(255,255,255,0.05)",
            },
          }}
        />
        <IconButton
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          sx={{
            color: "#7c3aed",
            "&:disabled": { color: "rgba(255,255,255,0.2)" },
          }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
```

- [ ] **Step 5: Create components/ChatArea.tsx**

```tsx
import { useRef, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import ThinkingBar from "./ThinkingBar";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface ChatAreaProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  currentStage: string | null;
  onSend: (content: string) => void;
  onApprove: () => void;
  onReject: () => void;
}

export default function ChatArea({
  messages,
  streamingContent,
  isStreaming,
  currentStage,
  onSend,
  onApprove,
  onReject,
}: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingContent]);

  const isEmpty = messages.length === 0 && !isStreaming;

  return (
    <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Box ref={scrollRef} sx={{ flex: 1, overflow: "auto", py: 2 }}>
        {isEmpty && (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              gap: 2,
            }}
          >
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <AutoAwesomeIcon sx={{ color: "#fff", fontSize: 28 }} />
            </Box>
            <Typography variant="h6" color="text.secondary">
              Describe the thumbnail you want
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400, textAlign: "center" }}>
              Include the video title and any style preferences. The agent will analyze your references and create a plan.
            </Typography>
          </Box>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id || i}
            message={msg}
            isLatest={i === messages.length - 1 && !isStreaming}
            isStreaming={false}
            onApprove={onApprove}
            onReject={onReject}
          />
        ))}

        {isStreaming && streamingContent && (
          <MessageBubble
            message={{ role: "assistant", content: streamingContent, type: "text" }}
            isStreaming={true}
          />
        )}
      </Box>

      {currentStage && <ThinkingBar stage={currentStage} />}

      <ChatInput onSend={onSend} disabled={isStreaming} />
    </Box>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ThinkingBar.tsx frontend/src/components/ApprovalButtons.tsx frontend/src/components/MessageBubble.tsx frontend/src/components/ChatInput.tsx frontend/src/components/ChatArea.tsx
git commit -m "feat: add chat UI components with approval buttons and SSE streaming display"
```

---

## Task 15: Frontend ChatPage (State Management + Wiring)

**Files:**
- Create: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create pages/ChatPage.tsx**

```tsx
import { useState, useEffect, useRef, useCallback } from "react";
import { Box } from "@mui/material";
import ContextPanel from "../components/ContextPanel";
import ChatArea from "../components/ChatArea";
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  streamChat,
} from "../lib/api";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const streamingRef = useRef("");
  const imageRef = useRef<{ base64: string; url: string } | null>(null);

  const loadConversations = useCallback(async () => {
    const data = await listConversations();
    setConversations(data as Conversation[]);
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSelectConversation = async (id: string) => {
    setSelectedId(id);
    const data = await getConversation(id);
    setMessages((data as { messages: Message[] }).messages || []);
  };

  const handleCreateConversation = async () => {
    const conv = await createConversation();
    const newConv = conv as Conversation;
    setConversations((prev) => [newConv, ...prev]);
    setSelectedId(newConv.id);
    setMessages([]);
  };

  const handleDeleteConversation = async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (selectedId === id) {
      setSelectedId(null);
      setMessages([]);
    }
  };

  const sendMessage = async (content: string, type: string = "text") => {
    if (!selectedId) {
      // Auto-create conversation
      const conv = await createConversation();
      const newConv = conv as Conversation;
      setConversations((prev) => [newConv, ...prev]);
      setSelectedId(newConv.id);
      await doStream(newConv.id, content, type);
    } else {
      await doStream(selectedId, content, type);
    }
  };

  const doStream = async (conversationId: string, content: string, type: string) => {
    // Add user message to UI immediately
    if (type === "text") {
      setMessages((prev) => [...prev, { role: "user", content, type: "text" }]);
    }

    setIsStreaming(true);
    setStreamingContent("");
    setCurrentStage(null);
    streamingRef.current = "";
    imageRef.current = null;

    await streamChat(conversationId, content, type, {
      onToken: (token) => {
        streamingRef.current += token;
        setStreamingContent(streamingRef.current);
      },
      onStage: (stage) => {
        setCurrentStage(stage);
      },
      onImage: (base64, url) => {
        imageRef.current = { base64, url };
      },
      onDone: (data) => {
        const messageType = (data.message_type as string) || "text";
        const newMessage: Message = {
          role: "assistant",
          content: streamingRef.current || (data.content as string) || "",
          type: messageType,
        };
        if (imageRef.current) {
          newMessage.image_base64 = imageRef.current.base64;
          newMessage.image_url = imageRef.current.url;
        }
        if (data.saved) {
          newMessage.content = data.content as string || "Thumbnail saved!";
          newMessage.type = "text";
        }
        setMessages((prev) => [...prev, newMessage]);
        setStreamingContent("");
        setIsStreaming(false);
        setCurrentStage(null);
        loadConversations();
      },
    });
  };

  const handleSend = (content: string) => sendMessage(content, "text");

  const handleApprove = () => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "plan") {
      sendMessage("APPROVED", "approval");
    } else if (lastMsg?.type === "image") {
      sendMessage("SAVE_OUTPUT", "save");
    }
  };

  const handleReject = () => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "plan") {
      // Let user type feedback — just focus the input
    } else if (lastMsg?.type === "image") {
      sendMessage("REGENERATE", "regenerate");
    }
  };

  return (
    <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
      <ContextPanel
        conversations={conversations}
        selectedId={selectedId}
        onSelect={handleSelectConversation}
        onCreate={handleCreateConversation}
        onDelete={handleDeleteConversation}
      />
      <ChatArea
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        currentStage={currentStage}
        onSend={handleSend}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </Box>
  );
}
```

- [ ] **Step 2: Update App.tsx with full routing**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./components/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./components/AppLayout";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<ChatPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd frontend && npm run build
# Expected: build succeeds with no type errors
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx frontend/src/App.tsx
git commit -m "feat: add ChatPage with conversation management and SSE streaming"
```

---

## Task 16: Frontend Assets Page

**Files:**
- Create: `frontend/src/components/AssetGrid.tsx`
- Create: `frontend/src/components/AssetUpload.tsx`
- Create: `frontend/src/pages/AssetsPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create components/AssetUpload.tsx**

```tsx
import { useCallback } from "react";
import { Box, Typography } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";

interface AssetUploadProps {
  onUpload: (files: FileList) => void;
  accept?: string;
}

export default function AssetUpload({ onUpload, accept }: AssetUploadProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer.files.length > 0) {
        onUpload(e.dataTransfer.files);
      }
    },
    [onUpload]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onUpload(e.target.files);
      }
    },
    [onUpload]
  );

  return (
    <Box
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      sx={{
        border: "2px dashed rgba(124,58,237,0.3)",
        borderRadius: 2,
        p: 3,
        textAlign: "center",
        cursor: "pointer",
        transition: "border-color 0.2s",
        "&:hover": { borderColor: "#7c3aed" },
      }}
      onClick={() => document.getElementById("asset-upload-input")?.click()}
    >
      <input
        id="asset-upload-input"
        type="file"
        multiple
        hidden
        accept={accept}
        onChange={handleChange}
      />
      <CloudUploadIcon sx={{ fontSize: 40, color: "rgba(124,58,237,0.5)", mb: 1 }} />
      <Typography variant="body2" color="text.secondary">
        Drag & drop files here, or click to browse
      </Typography>
    </Box>
  );
}
```

- [ ] **Step 2: Create components/AssetGrid.tsx**

```tsx
import { Box, ImageList, ImageListItem, IconButton, Typography } from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";

interface AssetFile {
  name: string;
  metadata?: { size?: number };
}

interface AssetGridProps {
  files: AssetFile[];
  bucket: string;
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
}

function isImage(name: string) {
  return /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(name);
}

export default function AssetGrid({ files, bucket, onDelete, onDownload }: AssetGridProps) {
  if (files.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography color="text.secondary">No files yet</Typography>
      </Box>
    );
  }

  return (
    <ImageList cols={4} gap={12}>
      {files.map((file) => (
        <ImageListItem
          key={file.name}
          sx={{
            borderRadius: 2,
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.08)",
            backgroundColor: "rgba(255,255,255,0.03)",
            position: "relative",
            "&:hover .actions": { opacity: 1 },
          }}
        >
          {isImage(file.name) ? (
            <Box
              component="img"
              src={`/api/assets/${bucket}/${file.name}`}
              alt={file.name}
              sx={{ width: "100%", height: 150, objectFit: "cover" }}
            />
          ) : (
            <Box
              sx={{
                width: "100%",
                height: 150,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <InsertDriveFileIcon sx={{ fontSize: 48, color: "rgba(255,255,255,0.2)" }} />
            </Box>
          )}

          <Box sx={{ p: 1 }}>
            <Typography variant="caption" noWrap color="text.secondary">
              {file.name}
            </Typography>
          </Box>

          <Box
            className="actions"
            sx={{
              position: "absolute",
              top: 4,
              right: 4,
              display: "flex",
              gap: 0.5,
              opacity: 0,
              transition: "opacity 0.2s",
            }}
          >
            <IconButton
              size="small"
              onClick={() => onDownload(file.name)}
              sx={{ backgroundColor: "rgba(0,0,0,0.6)", color: "#fff" }}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => onDelete(file.name)}
              sx={{ backgroundColor: "rgba(0,0,0,0.6)", color: "#ef4444" }}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Box>
        </ImageListItem>
      ))}
    </ImageList>
  );
}
```

- [ ] **Step 3: Create pages/AssetsPage.tsx**

```tsx
import { useState, useEffect, useCallback } from "react";
import { Box, Typography, Tabs, Tab } from "@mui/material";
import AssetGrid from "../components/AssetGrid";
import AssetUpload from "../components/AssetUpload";
import { listAssets, uploadAsset, deleteAsset } from "../lib/api";

const BUCKETS = [
  { key: "reference-thumbs", label: "Reference Thumbnails", accept: "image/*" },
  { key: "personal-photos", label: "Personal Photos", accept: "image/*" },
  { key: "fonts", label: "Fonts", accept: ".ttf,.otf,.woff,.woff2" },
  { key: "outputs", label: "Generated Outputs", accept: "image/*" },
];

interface AssetFile {
  name: string;
  metadata?: { size?: number };
}

export default function AssetsPage() {
  const [activeTab, setActiveTab] = useState(0);
  const [files, setFiles] = useState<AssetFile[]>([]);
  const [loading, setLoading] = useState(false);

  const currentBucket = BUCKETS[activeTab];

  const loadFiles = useCallback(async () => {
    setLoading(true);
    const data = await listAssets(currentBucket.key);
    setFiles(data as AssetFile[]);
    setLoading(false);
  }, [currentBucket.key]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async (fileList: FileList) => {
    for (let i = 0; i < fileList.length; i++) {
      await uploadAsset(currentBucket.key, fileList[i]);
    }
    loadFiles();
  };

  const handleDelete = async (name: string) => {
    await deleteAsset(currentBucket.key, name);
    loadFiles();
  };

  const handleDownload = (name: string) => {
    window.open(`/api/assets/${currentBucket.key}/${name}`, "_blank");
  };

  return (
    <Box sx={{ flex: 1, display: "flex", flexDirection: "column", p: 3, overflow: "auto" }}>
      <Typography
        variant="h5"
        sx={{
          mb: 2,
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        Assets
      </Typography>

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{
          mb: 3,
          "& .MuiTab-root": { textTransform: "none" },
          "& .Mui-selected": { color: "#7c3aed" },
          "& .MuiTabs-indicator": { backgroundColor: "#7c3aed" },
        }}
      >
        {BUCKETS.map((b) => (
          <Tab key={b.key} label={b.label} />
        ))}
      </Tabs>

      {currentBucket.key !== "outputs" && (
        <Box sx={{ mb: 3 }}>
          <AssetUpload onUpload={handleUpload} accept={currentBucket.accept} />
        </Box>
      )}

      {loading ? (
        <Typography color="text.secondary">Loading...</Typography>
      ) : (
        <AssetGrid
          files={files}
          bucket={currentBucket.key}
          onDelete={handleDelete}
          onDownload={handleDownload}
        />
      )}
    </Box>
  );
}
```

- [ ] **Step 4: Update App.tsx to add assets route**

Add to the route group inside the `<ProtectedRoute>` layout route, after the ChatPage route:

```tsx
import AssetsPage from "./pages/AssetsPage";

// Inside the layout Route element, add:
<Route path="/assets" element={<AssetsPage />} />
```

- [ ] **Step 5: Verify frontend compiles**

```bash
cd frontend && npm run build
# Expected: build succeeds
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AssetUpload.tsx frontend/src/components/AssetGrid.tsx frontend/src/pages/AssetsPage.tsx frontend/src/App.tsx
git commit -m "feat: add assets page with 4-bucket upload, grid view, and management"
```

---

## Task 17: Docker & Deployment

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create backend/Dockerfile**

```dockerfile
# Build stage
FROM ghcr.io/astral-sh/uv:0.9-python3.10-bookworm-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .

# Runtime stage
FROM python:3.10-slim-bookworm

WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend/nginx.conf**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Create frontend/Dockerfile**

```dockerfile
# Build stage
FROM node:22-slim AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_URL

COPY . .
RUN npm run build

# Runtime stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GUARDIAN_URL=${GUARDIAN_URL}
      - GUARDIAN_API_KEY=${GUARDIAN_API_KEY}
      - CORS_ORIGINS=https://youtube.merigafy.com
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.yt-backend.rule=Host(`youtube.merigafy.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.yt-backend.entrypoints=websecure"
      - "traefik.http.routers.yt-backend.tls.certresolver=letsencrypt"
      - "traefik.http.routers.yt-backend.priority=100"
      - "traefik.http.services.yt-backend.loadbalancer.server.port=8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
        - VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
        - VITE_API_URL=https://youtube.merigafy.com
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.yt-frontend.rule=Host(`youtube.merigafy.com`)"
      - "traefik.http.routers.yt-frontend.entrypoints=websecure"
      - "traefik.http.routers.yt-frontend.tls.certresolver=letsencrypt"
      - "traefik.http.routers.yt-frontend.priority=50"
      - "traefik.http.services.yt-frontend.loadbalancer.server.port=80"

networks:
  proxy:
    external: true
    name: proxy
```

- [ ] **Step 5: Verify docker-compose config parses**

```bash
docker compose config --quiet
# Expected: no errors
```

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf docker-compose.yml
git commit -m "feat: add Docker deployment with Traefik routing at youtube.merigafy.com"
```

---

## Task 18: Integration Smoke Test

- [ ] **Step 1: Create a .env file from .env.example with your real values**

```bash
cp .env.example .env
# Edit .env with your Supabase, Gemini, and Guardian credentials
```

- [ ] **Step 2: Run backend locally and test health**

```bash
cd backend && uv run uvicorn main:app --port 8000 --reload &
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
```

- [ ] **Step 3: Run frontend locally and test login page**

```bash
cd frontend && npm run dev &
# Open http://localhost:5173/login — sign-in form should render
# Open http://localhost:5173 — should redirect to /login (not authenticated)
```

- [ ] **Step 4: Run all backend tests**

```bash
cd backend && uv run pytest -v
# Expected: all tests pass
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd frontend && npm run build
# Expected: build succeeds
```

- [ ] **Step 6: Stop local servers and commit any fixes**

```bash
kill %1 %2 2>/dev/null
git add -A && git status
# If there are fixes, commit them
```
