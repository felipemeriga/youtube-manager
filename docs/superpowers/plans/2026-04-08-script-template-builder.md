# Script Template Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users customize script structure via a section-based builder on the Settings page, stored per-user and injected into the LLM system prompt.

**Architecture:** Add `script_template` JSONB column to `channel_personas`. Backend defines `DEFAULT_SCRIPT_SECTIONS` and injects enabled sections into the system prompt. Frontend adds a section builder UI with toggle, reorder, add, and delete capabilities.

**Tech Stack:** Python/FastAPI, Supabase (JSONB), React 18, MUI 6

---

### Task 1: Database — Add `script_template` Column

**Files:**
- Modify: `backend/db/schema.sql`

- [ ] **Step 1: Add column to schema.sql**

Append after the `channel_personas` table definition (after the `updated_at` column, before the closing `);`). Actually, since the table already exists, add a migration comment at the end of `backend/db/schema.sql`:

```sql
-- Migration: add script_template to channel_personas
-- ALTER TABLE channel_personas ADD COLUMN script_template JSONB DEFAULT NULL;
```

- [ ] **Step 2: Run migration in Supabase**

Execute in Supabase SQL Editor:

```sql
ALTER TABLE channel_personas ADD COLUMN script_template JSONB DEFAULT NULL;
```

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.sql
git commit -m "feat: add script_template JSONB column to channel_personas"
```

---

### Task 2: Backend — Default Sections + Persona Route Update

**Files:**
- Modify: `backend/routes/personas.py`
- Modify: `backend/tests/test_personas_route.py`

- [ ] **Step 1: Write tests for script_template in persona route**

Add these tests to the end of `backend/tests/test_personas_route.py`:

```python
def test_get_persona_includes_default_template_when_null():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": user_id,
        "channel_name": "My Channel",
        "language": "en",
        "persona_text": "Friendly",
        "script_template": None,
    }

    with patch("routes.personas.get_supabase", return_value=mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 200
    data = response.json()
    assert data["script_template"] is not None
    assert isinstance(data["script_template"], list)
    assert len(data["script_template"]) == 6
    assert data["script_template"][0]["name"] == "Hook / Opening"


def test_get_persona_returns_custom_template():
    user_id = "test-user-id"
    client = create_app(user_id)

    custom_template = [
        {"name": "Intro", "description": "Quick intro", "enabled": True, "order": 0},
    ]
    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": user_id,
        "channel_name": "My Channel",
        "language": "en",
        "persona_text": "Friendly",
        "script_template": custom_template,
    }

    with patch("routes.personas.get_supabase", return_value=mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 200
    assert response.json()["script_template"] == custom_template


def test_put_persona_with_script_template():
    user_id = "test-user-id"
    client = create_app(user_id)

    template = [
        {"name": "Hook", "description": "Opening hook", "enabled": True, "order": 0},
        {"name": "Script", "description": "Full script", "enabled": True, "order": 1},
    ]

    mock_sb = mock_supabase()
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
        {
            "user_id": user_id,
            "channel_name": "Ch",
            "language": "en",
            "persona_text": "Fun",
            "script_template": template,
        }
    ]

    with patch("routes.personas.get_supabase", return_value=mock_sb):
        response = client.put(
            "/api/personas",
            json={
                "channel_name": "Ch",
                "language": "en",
                "persona_text": "Fun",
                "script_template": template,
            },
        )

    assert response.status_code == 200
    mock_sb.table.return_value.upsert.assert_called_once()
    upsert_data = mock_sb.table.return_value.upsert.call_args[0][0]
    assert upsert_data["script_template"] == template
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_personas_route.py -v`
Expected: FAIL — `PersonaRequest` doesn't have `script_template`.

- [ ] **Step 3: Update `backend/routes/personas.py`**

Add the default sections constant and update the route:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from supabase import create_client

from auth import get_current_user
from config import settings

DEFAULT_SCRIPT_SECTIONS = [
    {"name": "Hook / Opening", "description": "Provocative hook in the first 30 seconds", "enabled": True, "order": 0},
    {"name": "Timing Table", "description": "Markdown table with Section, Time, Duration", "enabled": True, "order": 1},
    {"name": "Stats & Data", "description": "6-10 verified statistics with real source URLs", "enabled": True, "order": 2},
    {"name": "Talking Points", "description": "5-8 punchy one-liner quotes ready to say on camera", "enabled": True, "order": 3},
    {"name": "Full Script", "description": "Word-for-word dialogue organized by section with timing", "enabled": True, "order": 4},
    {"name": "Verified Sources", "description": "Numbered list of all sources with real URLs", "enabled": True, "order": 5},
]


class PersonaRequest(BaseModel):
    channel_name: str
    language: str
    persona_text: str
    script_template: Optional[list[dict]] = None


router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


@router.get("/api/personas")
async def get_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Persona not found")
    data = result.data
    if data.get("script_template") is None:
        data["script_template"] = DEFAULT_SCRIPT_SECTIONS
    return data


@router.put("/api/personas")
async def upsert_persona(
    request: PersonaRequest,
    user_id: str = Depends(get_current_user),
):
    sb = get_supabase()
    payload = {
        "user_id": user_id,
        "channel_name": request.channel_name,
        "language": request.language,
        "persona_text": request.persona_text,
    }
    if request.script_template is not None:
        payload["script_template"] = request.script_template
    result = (
        sb.table("channel_personas")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    return result.data[0]


@router.delete("/api/personas", status_code=204)
async def delete_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("channel_personas").delete().eq("user_id", user_id).execute()
    return Response(status_code=204)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_personas_route.py -v`
Expected: All pass (including the 3 new tests).

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/routes/personas.py backend/tests/test_personas_route.py
git commit -m "feat: add script_template to persona route with default sections"
```

---

### Task 3: Backend — Inject Template into System Prompt

**Files:**
- Modify: `backend/services/script_pipeline.py`
- Modify: `backend/tests/test_script_pipeline.py`

- [ ] **Step 1: Write test for template injection**

Add to the end of `backend/tests/test_script_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_system_prompt_includes_script_template():
    from services.script_pipeline import _build_system_prompt

    persona = {
        "channel_name": "Test",
        "language": "English",
        "persona_text": "Casual",
        "script_template": [
            {"name": "Hook", "description": "Opening hook", "enabled": True, "order": 0},
            {"name": "Stats", "description": "Data with sources", "enabled": True, "order": 1},
            {"name": "Outro", "description": "Closing remarks", "enabled": False, "order": 2},
        ],
    }
    result = _build_system_prompt(persona, [])

    assert "Hook" in result
    assert "Opening hook" in result
    assert "Stats" in result
    assert "Outro" not in result  # disabled


@pytest.mark.asyncio
async def test_system_prompt_uses_default_when_no_template():
    from services.script_pipeline import _build_system_prompt

    persona = {
        "channel_name": "Test",
        "language": "English",
        "persona_text": "Casual",
    }
    result = _build_system_prompt(persona, [])

    assert "Hook / Opening" in result
    assert "Verified Sources" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_script_pipeline.py::test_system_prompt_includes_script_template -v`
Expected: FAIL — `_build_system_prompt` doesn't handle templates yet.

- [ ] **Step 3: Update `_build_system_prompt` in `backend/services/script_pipeline.py`**

Import the default sections at the top (after line 13):

```python
from routes.personas import DEFAULT_SCRIPT_SECTIONS
```

Add a `{script_structure}` placeholder to `SYSTEM_PROMPT_TEMPLATE`. Replace the line (around line 46):

```
- When writing scripts, include real statistics with verifiable source URLs
```

With:

```
- When writing scripts, include real statistics with verifiable source URLs
{script_structure}
```

Update `_build_system_prompt` to accept persona dict with optional `script_template` and build the structure:

```python
def _build_system_prompt(persona: dict, memories: list[dict]) -> str:
    if memories:
        memories_text = "## Your Learned Preferences\n\n" + "\n".join(
            f"- {m['content']}" for m in memories
        )
    else:
        memories_text = ""

    sections = persona.get("script_template") or DEFAULT_SCRIPT_SECTIONS
    enabled = sorted(
        [s for s in sections if s.get("enabled", True)],
        key=lambda s: s.get("order", 0),
    )
    if enabled:
        lines = ["- When writing scripts, structure them with these sections in this order:\n"]
        for i, s in enumerate(enabled, 1):
            lines.append(f"  {i}. **{s['name']}** — {s['description']}")
        lines.append("\n  Only include the sections listed above. Follow this structure exactly.")
        script_structure = "\n".join(lines)
    else:
        script_structure = ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        channel_name=persona["channel_name"],
        language=persona["language"],
        persona_text=persona["persona_text"],
        memories_section=memories_text,
        script_structure=script_structure,
    )
```

Also update the SYSTEM_PROMPT_TEMPLATE guidelines section — replace the line:

```
- When writing scripts, include real statistics with verifiable source URLs
```

With:

```
- When writing scripts, include real statistics with verifiable source URLs
{script_structure}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_script_pipeline.py -v`
Expected: All pass.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/services/script_pipeline.py backend/tests/test_script_pipeline.py
git commit -m "feat: inject script template sections into LLM system prompt"
```

---

### Task 4: Frontend — Update API Types

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add ScriptSection interface and update Persona**

In `frontend/src/lib/api.ts`, add the `ScriptSection` interface before the `Persona` interface (before line 146):

```typescript
export interface ScriptSection {
  name: string;
  description: string;
  enabled: boolean;
  order: number;
}
```

Update the `Persona` interface to include `script_template`:

```typescript
export interface Persona {
  id: string;
  user_id: string;
  channel_name: string;
  language: string;
  persona_text: string;
  script_template: ScriptSection[];
  created_at: string;
  updated_at: string;
}
```

Update the `upsertPersona` parameter type:

```typescript
export const upsertPersona = (data: {
  channel_name: string;
  language: string;
  persona_text: string;
  script_template?: ScriptSection[];
}) =>
  apiFetch<Persona>("/api/personas", {
    method: "PUT",
    body: JSON.stringify(data),
  });
```

- [ ] **Step 2: Lint and commit**

```bash
cd frontend && npx prettier --write src/lib/api.ts
git add frontend/src/lib/api.ts
git commit -m "feat: add ScriptSection type and script_template to Persona"
```

---

### Task 5: Frontend — Script Template Builder Component

**Files:**
- Create: `frontend/src/components/ScriptTemplateBuilder.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ScriptTemplateBuilder.tsx`:

```tsx
import { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Checkbox,
  IconButton,
  TextField,
  Button,
  Divider,
} from "@mui/material";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import type { ScriptSection } from "../lib/api";

const DEFAULT_SECTION_NAMES = new Set([
  "Hook / Opening",
  "Timing Table",
  "Stats & Data",
  "Talking Points",
  "Full Script",
  "Verified Sources",
]);

interface Props {
  sections: ScriptSection[];
  onChange: (sections: ScriptSection[]) => void;
}

export default function ScriptTemplateBuilder({ sections, onChange }: Props) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const sorted = [...sections].sort((a, b) => a.order - b.order);

  const reorder = (updated: ScriptSection[]) => {
    onChange(updated.map((s, i) => ({ ...s, order: i })));
  };

  const toggleEnabled = (index: number) => {
    const updated = [...sorted];
    updated[index] = { ...updated[index], enabled: !updated[index].enabled };
    reorder(updated);
  };

  const moveUp = (index: number) => {
    if (index === 0) return;
    const updated = [...sorted];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    reorder(updated);
  };

  const moveDown = (index: number) => {
    if (index === sorted.length - 1) return;
    const updated = [...sorted];
    [updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
    reorder(updated);
  };

  const removeSection = (index: number) => {
    const updated = sorted.filter((_, i) => i !== index);
    reorder(updated);
  };

  const addSection = () => {
    if (!newName.trim() || !newDesc.trim()) return;
    const updated = [
      ...sorted,
      {
        name: newName.trim(),
        description: newDesc.trim(),
        enabled: true,
        order: sorted.length,
      },
    ];
    reorder(updated);
    setNewName("");
    setNewDesc("");
    setAdding(false);
  };

  return (
    <Paper
      sx={{
        width: "100%",
        maxWidth: 640,
        p: 4,
        mt: 3,
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <Typography variant="h5" sx={{ fontWeight: 600 }}>
        Script Template
      </Typography>
      <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
        Customize the sections included in your generated scripts. Toggle,
        reorder, or add custom sections.
      </Typography>

      <Box>
        {sorted.map((section, index) => (
          <Box key={`${section.name}-${index}`}>
            {index > 0 && (
              <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />
            )}
            <Box
              sx={{
                display: "flex",
                alignItems: "flex-start",
                py: 1.5,
                opacity: section.enabled ? 1 : 0.4,
              }}
            >
              <Checkbox
                checked={section.enabled}
                onChange={() => toggleEnabled(index)}
                sx={{
                  color: "rgba(255,255,255,0.3)",
                  "&.Mui-checked": { color: "#7c3aed" },
                  mt: -0.5,
                }}
              />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {section.name}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{ color: "rgba(255,255,255,0.5)" }}
                >
                  {section.description}
                </Typography>
              </Box>
              <Box sx={{ display: "flex", gap: 0.5, ml: 1 }}>
                {!DEFAULT_SECTION_NAMES.has(section.name) && (
                  <IconButton
                    size="small"
                    onClick={() => removeSection(index)}
                    sx={{
                      color: "rgba(255,255,255,0.3)",
                      "&:hover": { color: "#ef4444" },
                    }}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
                <IconButton
                  size="small"
                  disabled={index === 0}
                  onClick={() => moveUp(index)}
                  sx={{ color: "rgba(255,255,255,0.3)" }}
                >
                  <ArrowUpwardIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  disabled={index === sorted.length - 1}
                  onClick={() => moveDown(index)}
                  sx={{ color: "rgba(255,255,255,0.3)" }}
                >
                  <ArrowDownwardIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          </Box>
        ))}
      </Box>

      {adding ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1 }}>
          <TextField
            label="Section Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            size="small"
            fullWidth
          />
          <TextField
            label="Description"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            size="small"
            fullWidth
            multiline
            minRows={2}
          />
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button
              variant="contained"
              size="small"
              onClick={addSection}
              disabled={!newName.trim() || !newDesc.trim()}
            >
              Add
            </Button>
            <Button
              size="small"
              onClick={() => {
                setAdding(false);
                setNewName("");
                setNewDesc("");
              }}
            >
              Cancel
            </Button>
          </Box>
        </Box>
      ) : (
        <Button
          startIcon={<AddIcon />}
          onClick={() => setAdding(true)}
          sx={{
            alignSelf: "flex-start",
            color: "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          Add Section
        </Button>
      )}
    </Paper>
  );
}
```

- [ ] **Step 2: Lint and commit**

```bash
cd frontend && npx prettier --write src/components/ScriptTemplateBuilder.tsx
git add frontend/src/components/ScriptTemplateBuilder.tsx
git commit -m "feat: add ScriptTemplateBuilder component"
```

---

### Task 6: Frontend — Integrate Builder into Settings Page

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Update SettingsPage to use the template builder**

Add import after line 24:

```typescript
import ScriptTemplateBuilder from "../components/ScriptTemplateBuilder";
import type { ScriptSection } from "../lib/api";
```

Add state after `memories` state (after line 37):

```typescript
  const [scriptTemplate, setScriptTemplate] = useState<ScriptSection[]>([]);
```

Update the `useEffect`'s persona loading to also set `scriptTemplate` (inside the `.then` callback, after line 48):

```typescript
          setScriptTemplate(persona.script_template || []);
```

Update `handleSave` to include `script_template` in the upsert call (replace lines 74-78):

```typescript
      await upsertPersona({
        channel_name: channelName.trim(),
        language: language.trim(),
        persona_text: personaText.trim(),
        script_template: scriptTemplate,
      });
```

Add the `ScriptTemplateBuilder` component between the persona `</Paper>` (line 197) and the memories `<Paper>` (line 199):

```tsx
      <ScriptTemplateBuilder
        sections={scriptTemplate}
        onChange={setScriptTemplate}
      />
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Lint and commit**

```bash
cd frontend && npx prettier --write src/pages/SettingsPage.tsx
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: integrate script template builder into settings page"
```

---

### Task 7: Full Test Run + Push

- [ ] **Step 1: Run backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All pass.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Lint everything**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd frontend && npx prettier --write src/**/*.tsx src/**/*.ts
```

- [ ] **Step 4: Push**

```bash
git push
```

---

### Task 8: Manual Smoke Test

- [ ] **Step 1: Test default template**

1. Log in, go to Settings
2. Verify 6 default sections appear in the Script Template card
3. All should be enabled with checkboxes checked

- [ ] **Step 2: Test customization**

1. Disable "Talking Points" — checkbox unchecked, row grayed out
2. Move "Stats & Data" above "Timing Table" using arrow buttons
3. Click "Add Section" — fill in "Sponsor Read" / "30-second sponsor integration"
4. Click Save — verify success toast
5. Refresh page — verify customizations persisted

- [ ] **Step 3: Test script generation uses template**

1. Start a script conversation
2. Verify the generated script follows the enabled sections in the order you set
3. Verify disabled sections are not included
4. Verify the custom section appears in the script
