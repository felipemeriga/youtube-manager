# Script Template Builder

**Goal:** Let users customize the structure of generated scripts via a section-based builder UI, stored per-user and injected into the LLM system prompt.

## Database

Add a `script_template` JSONB column to the existing `channel_personas` table:

```sql
ALTER TABLE channel_personas ADD COLUMN script_template JSONB DEFAULT NULL;
```

When `NULL`, the backend uses a hardcoded default. When set, contains the user's customized section list.

## Data Shape

```json
[
  {"name": "Hook / Opening", "description": "Provocative hook in the first 30 seconds", "enabled": true, "order": 0},
  {"name": "Timing Table", "description": "Markdown table with Section, Time, Duration", "enabled": true, "order": 1},
  {"name": "Stats & Data", "description": "6-10 verified statistics with real source URLs", "enabled": true, "order": 2},
  {"name": "Talking Points", "description": "5-8 punchy one-liner quotes ready to say on camera", "enabled": true, "order": 3},
  {"name": "Full Script", "description": "Word-for-word dialogue organized by section with timing", "enabled": true, "order": 4},
  {"name": "Verified Sources", "description": "Numbered list of all sources with real URLs", "enabled": true, "order": 5}
]
```

## Default Template

Hardcoded in the backend as `DEFAULT_SCRIPT_SECTIONS`. Used when `script_template` is `NULL`. The 6 sections above represent the structure from the original hardcoded script prompt.

Users start with this default rendered in the UI. Any modifications are saved to the DB column.

## Backend Changes

### Config / Constants

Add `DEFAULT_SCRIPT_SECTIONS` list in `script_pipeline.py` (or a shared constants file).

### Persona Route

- Add `script_template` as an optional field to `PersonaRequest` (list of section dicts, defaults to `None`)
- `PUT /api/personas` stores `script_template` in the JSONB column
- `GET /api/personas` returns `script_template` from DB. If `NULL`, return the `DEFAULT_SCRIPT_SECTIONS` so the frontend always has sections to render

### System Prompt Injection

In `_build_system_prompt`, convert enabled sections (sorted by `order`) into a prompt block:

```
When writing scripts, structure them with these sections in this order:

1. **Hook / Opening** — Provocative hook in the first 30 seconds
2. **Stats & Data** — 6-10 verified statistics with real source URLs
3. **Full Script** — Word-for-word dialogue organized by section with timing
4. **Verified Sources** — Numbered list of all sources with real URLs

Only include the sections listed above. Follow this structure exactly.
```

Disabled sections are excluded. The numbered list gives the LLM clear structure without hardcoding any language-specific headings.

## Frontend — Template Builder

Located on the Settings page, between the persona form and the learned preferences section. Contained in its own Paper card.

### Layout

```
Script Template
Customize the sections included in your generated scripts.

┌─────────────────────────────────────────────────┐
│ ☑  Hook / Opening                          ↑ ↓  │
│    Provocative hook in the first 30 seconds      │
├─────────────────────────────────────────────────┤
│ ☑  Timing Table                            ↑ ↓  │
│    Markdown table with Section, Time, Duration   │
├─────────────────────────────────────────────────┤
│ ☑  Stats & Data                            ↑ ↓  │
│    6-10 verified statistics with real source URLs│
├─────────────────────────────────────────────────┤
│ ☐  Talking Points                     ✕    ↑ ↓  │
│    5-8 punchy one-liner quotes...    (grayed)    │
├─────────────────────────────────────────────────┤
│ ☑  Full Script                             ↑ ↓  │
│    Word-for-word dialogue organized by section   │
├─────────────────────────────────────────────────┤
│ ☑  Verified Sources                        ↑ ↓  │
│    Numbered list of all sources with real URLs   │
└─────────────────────────────────────────────────┘

[+ Add Section]
```

### Interactions

- **Toggle checkbox** — enables/disables a section. Disabled sections are grayed out but remain in the list for easy re-enabling.
- **Up/down arrows** — reorder sections. Up arrow disabled on first item, down arrow disabled on last.
- **Delete (✕)** — only visible on custom (user-added) sections. Default sections cannot be deleted, only disabled.
- **Add Section** — clicking opens an inline form at the bottom with two fields: "Section Name" and "Description". Clicking "Add" appends it to the list as enabled.
- **All changes are local state** until the user clicks the existing "Save" button, which sends the full persona + template to `PUT /api/personas`.

### Styling

- MUI components: `Checkbox`, `IconButton` (ArrowUpward, ArrowDownward, Close), `TextField`, `Paper`, `List`/`ListItem`
- Follows existing dark theme with `sx` props
- Disabled sections get `opacity: 0.4`
- Consistent with the rest of the Settings page

## Files to Change

- Modify: `backend/db/schema.sql` — add column migration SQL
- Modify: `backend/routes/personas.py` — accept/return `script_template`
- Modify: `backend/tests/test_personas_route.py` — test template in upsert/get
- Modify: `backend/services/script_pipeline.py` — add `DEFAULT_SCRIPT_SECTIONS`, inject into system prompt
- Modify: `backend/tests/test_script_pipeline.py` — test template injection
- Modify: `frontend/src/lib/api.ts` — update `Persona` interface with `script_template`
- Modify: `frontend/src/pages/SettingsPage.tsx` — add template builder UI

## Out of Scope

- Genre presets / starter templates (future enhancement)
- Drag-and-drop reordering (using up/down arrows instead)
- Per-section advanced options (word count limits, etc.)
- Template sharing between users
