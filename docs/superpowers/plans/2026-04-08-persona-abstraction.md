# Per-User Channel Persona Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded channel persona with a per-user persona stored in Supabase, editable from a new Settings page, making the app channel-agnostic.

**Architecture:** New `channel_personas` table in Supabase with RLS. New `/api/personas` backend route for CRUD. New `/settings` frontend page with MUI form. Script pipeline fetches persona from DB instead of importing hardcoded module.

**Tech Stack:** Python/FastAPI, Supabase (Postgres + RLS), React 18, MUI 6, React Router 6, Vite 5

---

### Task 1: Database Schema — `channel_personas` Table

**Files:**
- Modify: `backend/db/schema.sql` (append after line 57)

- [ ] **Step 1: Add channel_personas table and RLS to schema.sql**

Append the following to the end of `backend/db/schema.sql`:

```sql
-- channel_personas
CREATE TABLE channel_personas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    channel_name TEXT NOT NULL,
    language    TEXT NOT NULL,
    persona_text TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER update_channel_personas_updated_at
    BEFORE UPDATE ON channel_personas
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_channel_personas_user_id ON channel_personas(user_id);

-- RLS
ALTER TABLE channel_personas ENABLE ROW LEVEL SECURITY;

CREATE POLICY channel_personas_select ON channel_personas
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY channel_personas_insert ON channel_personas
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY channel_personas_update ON channel_personas
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY channel_personas_delete ON channel_personas
    FOR DELETE USING (auth.uid() = user_id);
```

- [ ] **Step 2: Run the SQL in Supabase**

Execute the new SQL block against your Supabase project (via the SQL Editor in the Supabase dashboard or `psql`).

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.sql
git commit -m "feat: add channel_personas table with RLS"
```

---

### Task 2: Backend — Personas API Route

**Files:**
- Create: `backend/routes/personas.py`
- Modify: `backend/main.py:7-28` (add import + include router)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_personas_route.py`:

```python
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_auth():
    with patch("auth.get_current_user", return_value="test-user-id"):
        yield


def _mock_supabase(select_data=None):
    sb = MagicMock()
    chain = sb.table.return_value

    execute_result = MagicMock()
    execute_result.data = select_data if select_data is not None else []

    chain.select.return_value.eq.return_value.single.return_value.execute = MagicMock(
        return_value=execute_result
    )
    chain.select.return_value.eq.return_value.execute = MagicMock(
        return_value=execute_result
    )
    chain.upsert.return_value.execute = MagicMock(return_value=execute_result)
    chain.delete.return_value.eq.return_value.execute = MagicMock(
        return_value=execute_result
    )
    return sb


def test_get_persona_returns_404_when_none(client):
    sb = _mock_supabase(select_data=None)
    empty_result = MagicMock()
    empty_result.data = None
    sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute = MagicMock(
        return_value=empty_result
    )
    with patch("routes.personas.get_supabase", return_value=sb):
        response = client.get("/api/personas")
    assert response.status_code == 404


def test_get_persona_returns_data(client):
    persona = {
        "id": "abc",
        "user_id": "test-user-id",
        "channel_name": "My Channel",
        "language": "English",
        "persona_text": "Casual and fun",
    }
    sb = _mock_supabase(select_data=persona)
    with patch("routes.personas.get_supabase", return_value=sb):
        response = client.get("/api/personas")
    assert response.status_code == 200
    assert response.json()["channel_name"] == "My Channel"


def test_put_persona_upserts(client):
    upserted = {
        "id": "abc",
        "user_id": "test-user-id",
        "channel_name": "New Channel",
        "language": "Portuguese",
        "persona_text": "Direct and provocative",
    }
    sb = _mock_supabase()
    upsert_result = MagicMock()
    upsert_result.data = [upserted]
    sb.table.return_value.upsert.return_value.execute = MagicMock(
        return_value=upsert_result
    )
    with patch("routes.personas.get_supabase", return_value=sb):
        response = client.put(
            "/api/personas",
            json={
                "channel_name": "New Channel",
                "language": "Portuguese",
                "persona_text": "Direct and provocative",
            },
        )
    assert response.status_code == 200
    assert response.json()["channel_name"] == "New Channel"


def test_delete_persona(client):
    sb = _mock_supabase()
    delete_result = MagicMock()
    delete_result.data = [{"id": "abc"}]
    sb.table.return_value.delete.return_value.eq.return_value.execute = MagicMock(
        return_value=delete_result
    )
    with patch("routes.personas.get_supabase", return_value=sb):
        response = client.delete("/api/personas")
    assert response.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_personas_route.py -v`
Expected: FAIL — `routes.personas` does not exist yet.

- [ ] **Step 3: Create the personas route**

Create `backend/routes/personas.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


class PersonaRequest(BaseModel):
    channel_name: str
    language: str
    persona_text: str


@router.get("/api/personas")
async def get_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="No persona found")
    return result.data


@router.put("/api/personas")
async def upsert_persona(
    request: PersonaRequest, user_id: str = Depends(get_current_user)
):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .upsert(
            {
                "user_id": user_id,
                "channel_name": request.channel_name,
                "language": request.language,
                "persona_text": request.persona_text,
            },
            on_conflict="user_id",
        )
        .execute()
    )
    return result.data[0]


@router.delete("/api/personas")
async def delete_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="No persona found")
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in main.py**

In `backend/main.py`, add the import after line 9:

```python
from routes.personas import router as personas_router
```

Add the include after line 28:

```python
app.include_router(personas_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_personas_route.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Lint**

Run: `cd backend && uv run ruff check --fix && uv run ruff format`

- [ ] **Step 7: Commit**

```bash
git add backend/routes/personas.py backend/tests/test_personas_route.py backend/main.py
git commit -m "feat: add personas API route with CRUD endpoints"
```

---

### Task 3: Backend — Dynamic Persona in Script Pipeline

**Files:**
- Modify: `backend/services/script_pipeline.py:11,50-51,64-65,234,308`
- Delete: `backend/persona.py`
- Delete: `backend/tests/test_persona.py`
- Modify: `backend/tests/test_script_pipeline.py`

- [ ] **Step 1: Write the failing test for persona gate**

Add to `backend/tests/test_script_pipeline.py` after the existing imports (line 3):

```python
from unittest.mock import patch, MagicMock, AsyncMock
```

Already imported. Add this new test at the end of the file:

```python
@pytest.mark.asyncio
async def test_handle_ideation_errors_when_no_persona():
    sb = make_async_sb()

    # Mock persona lookup returning no data
    persona_result = MagicMock()
    persona_result.data = None
    persona_chain = MagicMock()
    persona_chain.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=persona_result
    )

    # Make table() return persona_chain for channel_personas, sb for others
    original_table = sb.table

    def table_router(name):
        if name == "channel_personas":
            return persona_chain
        return original_table(name)

    sb.table = MagicMock(side_effect=table_router)

    events = []
    mock_get_sb = AsyncMock(return_value=sb)
    with patch("services.script_pipeline.get_supabase", mock_get_sb):
        async for event in handle_script_chat_message(
            conversation_id="conv-1",
            content="Give me video ideas",
            msg_type="text",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    assert any(e.get("error") for e in events)
    assert any("persona" in e.get("error", "").lower() for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_script_pipeline.py::test_handle_ideation_errors_when_no_persona -v`
Expected: FAIL — pipeline doesn't check for persona yet.

- [ ] **Step 3: Update script_pipeline.py to use dynamic persona**

In `backend/services/script_pipeline.py`, make these changes:

**Remove line 11** (the `from persona import format_persona` import).

**Add a new helper function** after the `_extract_duration` function (after line 173):

```python
async def _get_user_persona(sb, user_id: str) -> dict | None:
    result = (
        await sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return result.data


def format_persona(persona: dict) -> str:
    return (
        f"# Channel Persona: {persona['channel_name']}\n\n"
        f"**Language:** {persona['language']}\n\n"
        f"{persona['persona_text']}\n"
    )
```

**Update `IDEATION_PROMPT_TEMPLATE`** — replace lines 50-51:

```python
    "Based on your research, suggest 5-10 specific video topics. The channel is "
    "{channel_name} ({language}).\n\n"
```

**Update `SCRIPT_PROMPT_TEMPLATE`** — replace lines 64-65:

```python
    "{persona}\n\n"
    "You are writing a complete YouTube video script in {language}.\n\n"
```

**Update `handle_ideation`** (around line 181) — add persona lookup after the supabase client line:

After `sb = await get_supabase()` (line 185), add:

```python
    persona_row = await _get_user_persona(sb, user_id)
    if not persona_row:
        yield sse_event({
            "error": "Please set up your channel persona in Settings before generating scripts.",
            "done": True,
        })
        return
```

Update the ideation prompt formatting (line 198) to:

```python
    ideation_prompt = IDEATION_PROMPT_TEMPLATE.format(
        user_input=user_message,
        channel_name=persona_row["channel_name"],
        language=persona_row["language"],
    )
```

**Update `handle_topic_selection`** (around line 207) — add persona lookup:

After `sb = await get_supabase()` (line 216), add:

```python
    persona_row = await _get_user_persona(sb, user_id)
    if not persona_row:
        yield sse_event({
            "error": "Please set up your channel persona in Settings before generating scripts.",
            "done": True,
        })
        return
```

Replace lines 234-236:

```python
    persona = format_persona(persona_row)
    script_prompt = SCRIPT_PROMPT_TEMPLATE.format(
        persona=persona,
        topic=topic_title,
        duration=duration,
        language=persona_row["language"],
    )
```

**Update `handle_script_approval`** (around line 245) — add persona lookup:

After `sb = await get_supabase()` (line 254), add:

```python
    persona_row = await _get_user_persona(sb, user_id)
    if not persona_row:
        yield sse_event({
            "error": "Please set up your channel persona in Settings before generating scripts.",
            "done": True,
        })
        return
```

Replace lines 308-311 (in the rejection branch):

```python
        persona = format_persona(persona_row)
        script_prompt = SCRIPT_PROMPT_TEMPLATE.format(
            persona=persona,
            topic=topic_title,
            duration=duration,
            language=persona_row["language"],
        )
```

- [ ] **Step 4: Update existing tests to mock persona**

In `backend/tests/test_script_pipeline.py`, update the `make_async_sb` function to include a persona lookup mock by default:

```python
def make_async_sb(**overrides):
    """Create a mock supabase client with async execute/storage methods."""
    sb = MagicMock()

    execute_result = MagicMock()
    execute_result.data = overrides.get("data", [])

    chain = sb.table.return_value
    chain.insert.return_value.execute = AsyncMock(return_value=execute_result)
    chain.update.return_value.eq.return_value.execute = AsyncMock(
        return_value=execute_result
    )
    chain.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    # Default persona mock
    persona_data = overrides.get(
        "persona",
        {
            "channel_name": "Test Channel",
            "language": "English",
            "persona_text": "Casual and direct",
        },
    )
    persona_result = MagicMock()
    persona_result.data = persona_data
    chain.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=persona_result
    )

    storage = sb.storage.from_.return_value
    storage.upload = AsyncMock(return_value={})

    return sb
```

- [ ] **Step 5: Delete hardcoded persona files**

```bash
rm backend/persona.py backend/tests/test_persona.py
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && uv run pytest tests/test_script_pipeline.py -v`
Expected: All tests PASS (including the new persona gate test).

- [ ] **Step 7: Lint**

Run: `cd backend && uv run ruff check --fix && uv run ruff format`

- [ ] **Step 8: Commit**

```bash
git add -A backend/persona.py backend/tests/test_persona.py backend/services/script_pipeline.py backend/tests/test_script_pipeline.py
git commit -m "feat: replace hardcoded persona with dynamic DB lookup in script pipeline"
```

---

### Task 4: Frontend — API Client Functions for Personas

**Files:**
- Modify: `frontend/src/lib/api.ts` (append exports)

- [ ] **Step 1: Add persona API functions**

Append the following to the end of `frontend/src/lib/api.ts`:

```typescript
export interface Persona {
  id: string;
  user_id: string;
  channel_name: string;
  language: string;
  persona_text: string;
  created_at: string;
  updated_at: string;
}

export const getPersona = () =>
  apiFetch<Persona>("/api/personas").catch((err) => {
    if (err.message.includes("404")) return null;
    throw err;
  });

export const upsertPersona = (data: {
  channel_name: string;
  language: string;
  persona_text: string;
}) =>
  apiFetch<Persona>("/api/personas", {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deletePersona = () =>
  apiFetch<void>("/api/personas", { method: "DELETE" });
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint --fix src/lib/api.ts && npx prettier --write src/lib/api.ts`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add persona CRUD functions to API client"
```

---

### Task 5: Frontend — Settings Page

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Create SettingsPage component**

Create `frontend/src/pages/SettingsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  Snackbar,
  Alert,
  CircularProgress,
} from "@mui/material";
import { getPersona, upsertPersona } from "../lib/api";

export default function SettingsPage() {
  const [channelName, setChannelName] = useState("");
  const [language, setLanguage] = useState("");
  const [personaText, setPersonaText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  useEffect(() => {
    getPersona()
      .then((persona) => {
        if (persona) {
          setChannelName(persona.channel_name);
          setLanguage(persona.language);
          setPersonaText(persona.persona_text);
        }
      })
      .catch(() => {
        setSnackbar({
          open: true,
          message: "Failed to load persona",
          severity: "error",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!channelName.trim() || !language.trim() || !personaText.trim()) {
      setSnackbar({
        open: true,
        message: "All fields are required",
        severity: "error",
      });
      return;
    }

    setSaving(true);
    try {
      await upsertPersona({
        channel_name: channelName.trim(),
        language: language.trim(),
        persona_text: personaText.trim(),
      });
      setSnackbar({
        open: true,
        message: "Persona saved successfully",
        severity: "success",
      });
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to save persona",
        severity: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        p: 4,
        overflow: "auto",
      }}
    >
      <Paper
        sx={{
          width: "100%",
          maxWidth: 640,
          p: 4,
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Channel Persona
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
          Configure your channel identity. This persona is used by the script
          generator to match your style.
        </Typography>

        <TextField
          label="Channel Name"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value)}
          fullWidth
          required
        />

        <TextField
          label="Language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          fullWidth
          required
          placeholder="e.g. Brazilian Portuguese, English, Spanish"
        />

        <TextField
          label="Persona"
          value={personaText}
          onChange={(e) => setPersonaText(e.target.value)}
          fullWidth
          required
          multiline
          minRows={6}
          maxRows={16}
          placeholder={
            "Describe your channel's personality, tone, style, humor, what to avoid...\n\n" +
            "Example:\n" +
            "Tone: conversational, informal, provocative\n" +
            "Humor: uses humor naturally, not forced\n" +
            "Approach: takes a position, never neutral\n" +
            "Style: direct, uses real examples, challenges conventional wisdom\n" +
            "Avoid: sounding like a guru, generic advice, corporate tone"
          }
        />

        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving}
          sx={{ alignSelf: "flex-end", minWidth: 120 }}
        >
          {saving ? <CircularProgress size={20} /> : "Save"}
        </Button>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint --fix src/pages/SettingsPage.tsx && npx prettier --write src/pages/SettingsPage.tsx`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add SettingsPage with persona form"
```

---

### Task 6: Frontend — Route + Sidebar Icon

**Files:**
- Modify: `frontend/src/App.tsx:1-24` (add route)
- Modify: `frontend/src/components/IconRail.tsx:1-60` (add gear icon)

- [ ] **Step 1: Add settings route in App.tsx**

In `frontend/src/App.tsx`, add the import after line 7:

```typescript
import SettingsPage from "./pages/SettingsPage";
```

Add the route after the `/assets` route (after line 23):

```typescript
            <Route path="/settings" element={<SettingsPage />} />
```

- [ ] **Step 2: Add gear icon to IconRail.tsx**

In `frontend/src/components/IconRail.tsx`, add the import after the existing icon imports (after line 4):

```typescript
import SettingsIcon from "@mui/icons-material/Settings";
```

Add the settings button before the flex spacer (`<Box sx={{ flex: 1 }} />`). Insert before line 56:

```tsx
      <Tooltip title="Settings" placement="right">
        <IconButton
          onClick={() => navigate("/settings")}
          sx={{
            color: isActive("/settings") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <SettingsIcon />
        </IconButton>
      </Tooltip>
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Lint**

Run: `cd frontend && npx eslint --fix src/App.tsx src/components/IconRail.tsx && npx prettier --write src/App.tsx src/components/IconRail.tsx`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/IconRail.tsx
git commit -m "feat: add settings route and gear icon to sidebar"
```

---

### Task 7: Frontend — Script Pipeline Error Handling for Missing Persona

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx` (add error handling for persona gate)

- [ ] **Step 1: Read ChatPage.tsx to find the error handling location**

Read `frontend/src/pages/ChatPage.tsx` and locate where `onError` or `callbacks.onError` is handled in the script chat flow. The `streamChat` function already supports `onError` in its callbacks.

- [ ] **Step 2: Add persona-specific error rendering**

In the `onError` callback handler within ChatPage.tsx, check if the error message contains "persona" and render it with a link to `/settings`. The exact implementation depends on how errors are currently rendered, but the pattern is:

In the `onError` callback passed to `streamChat`, update the handling to detect persona errors:

```typescript
onError: (error: string) => {
  if (error.toLowerCase().includes("persona")) {
    // Show error with link to settings
    addMessage({
      role: "assistant",
      content: error + " [Go to Settings](/settings)",
      type: "text",
    });
  } else {
    addMessage({ role: "assistant", content: error, type: "text" });
  }
  setLoading(false);
},
```

The exact function name (`addMessage` or similar) depends on the current ChatPage implementation — match the existing pattern.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 4: Lint**

Run: `cd frontend && npx eslint --fix src/pages/ChatPage.tsx && npx prettier --write src/pages/ChatPage.tsx`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "feat: show persona setup prompt when script pipeline has no persona"
```

---

### Task 8: Manual Smoke Test

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && uv run uvicorn main:app --reload --port 8000 &
cd frontend && npm run dev &
```

- [ ] **Step 2: Test the happy path**

1. Log in to the app
2. Navigate to Settings (gear icon)
3. Fill in channel name, language, and persona text
4. Click Save — verify success toast
5. Navigate to Chat, start a script conversation
6. Verify the pipeline uses the persona from Settings (check backend logs for the formatted prompt)

- [ ] **Step 3: Test the gate**

1. Delete your persona via the Supabase dashboard (or add a delete button test)
2. Start a new script conversation
3. Verify the error message appears with a link to Settings

- [ ] **Step 4: Test thumbnail mode is unaffected**

1. Start a thumbnail conversation
2. Verify it works without a persona
