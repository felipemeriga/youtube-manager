# Per-User Channel Persona

**Goal:** Replace the hardcoded channel persona with a per-user persona stored in Supabase, editable from a new Settings page. This makes the app channel-agnostic — any user can configure their own channel identity.

## Current State

- `backend/persona.py` defines a hardcoded `PERSONA` dict for "Além do Código" (channel name, language, tone, humor, approach, style, avoid list).
- `backend/services/script_pipeline.py` imports `format_persona()` and embeds hardcoded references to "Brazilian Portuguese tech channel" in prompt templates.
- `backend/tests/test_persona.py` asserts the literal string "Além do Código".
- No UI exists for persona management.

## Database

### Table: `channel_personas`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `user_id` | `uuid` | Unique, FK to `auth.users`, ON DELETE CASCADE |
| `channel_name` | `text` | Not null |
| `language` | `text` | Not null |
| `persona_text` | `text` | Not null, free-text personality/style description |
| `created_at` | `timestamptz` | Default `now()` |
| `updated_at` | `timestamptz` | Default `now()` |

**RLS policies:**
- SELECT: `auth.uid() = user_id`
- INSERT: `auth.uid() = user_id`
- UPDATE: `auth.uid() = user_id`
- DELETE: `auth.uid() = user_id`

The unique constraint on `user_id` enforces one persona per user at the DB level.

## Backend

### New API Routes

Route group under `/api/personas`, all requiring Supabase JWT auth.

**`GET /api/personas`**
- Returns the authenticated user's persona or 404 if none exists.
- Response: `{ id, channel_name, language, persona_text, created_at, updated_at }`

**`PUT /api/personas`**
- Upserts the authenticated user's persona (insert if none, update if exists).
- Request body: `{ channel_name: string, language: string, persona_text: string }`
- Response: the saved persona object.

**`DELETE /api/personas`**
- Deletes the authenticated user's persona.
- Response: 204 No Content.

### Persona Formatting

Delete `backend/persona.py` (the hardcoded dict). Replace with a function in the personas route module or a small utility that takes a persona DB row and formats it for prompt injection:

```
Channel: {channel_name}
Language: {language}

{persona_text}
```

### Script Pipeline Changes

In `backend/services/script_pipeline.py`:

- Remove `from persona import format_persona`.
- At the start of script conversations, fetch the user's persona from the DB via the Supabase client.
- If no persona exists, return an error SSE event: `{"type": "error", "message": "Please set up your channel persona in Settings before generating scripts."}` and stop the pipeline.
- Replace hardcoded "Brazilian Portuguese tech channel" in `IDEATION_PROMPT_TEMPLATE` with `{channel_name}`.
- Replace hardcoded "Brazilian Portuguese" in `SCRIPT_PROMPT_TEMPLATE` with `{language}`.
- Pass the formatted persona text where `format_persona()` was previously called.

### Thumbnail Pipeline

No changes. Thumbnail generation does not use the persona.

## Frontend

### Settings Page (`/settings`)

- Accessible via a gear icon in the sidebar navigation.
- Route: `/settings`

**Form fields:**
- **Channel Name** — text input, required
- **Language** — text input, required
- **Persona** — large text area (6-8 rows), required. Placeholder: "Describe your channel's personality, tone, style, humor, what to avoid..."

**Behavior:**
- On mount, `GET /api/personas`. If 200, populate form. If 404, show empty form.
- Save button calls `PUT /api/personas`. Show success toast on save.
- Simple form validation: all fields required, non-empty.

### Script Pipeline Gate

When a user starts a script conversation and the backend returns the "no persona" error, display the error message in the chat with a link to `/settings`.

### Sidebar Change

Add a gear icon at the bottom of the sidebar that navigates to `/settings`.

## Files to Change

### Delete
- `backend/persona.py`
- `backend/tests/test_persona.py`

### Modify
- `backend/services/script_pipeline.py` — dynamic persona lookup, parameterized prompts
- `backend/tests/test_script_pipeline.py` — update mocks for new persona source
- Frontend sidebar component — add gear icon link
- Frontend router — add `/settings` route
- Frontend API client — add persona CRUD functions

### Create
- `backend/db/schema.sql` or migration — `channel_personas` table + RLS
- `backend/routes/personas.py` — new API route group
- `frontend/src/pages/SettingsPage.tsx` — persona settings form
- `frontend/src/components/SettingsPage.css` or styled equivalent

## Testing

### Backend
- Test persona CRUD routes (create, read, update, delete)
- Test script pipeline rejects when no persona exists
- Test script pipeline uses fetched persona in prompts
- Test format function with various persona inputs

### Frontend
- Settings page renders empty form when no persona
- Settings page populates form when persona exists
- Save persists and shows success feedback
- Script chat shows error + link when no persona

## Out of Scope

- Multiple personas per user
- Persona templates or presets
- Migration of the existing hardcoded persona into a user's row (users create their own)
- Changes to deployment domain references in docs/README
