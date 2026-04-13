# Multi-Script Conversations + User Memories

**Goal:** Allow multiple script flows in the same conversation, and build a memory system that learns user preferences from script approvals/rejections.

## Feature 1: Multi-Script in Same Conversation

### Problem

`_find_message` returns the first message of a given type. After completing one script flow (ideation → topic selection → script → approval), starting a new flow in the same conversation reuses stale topics and text from the first round.

### Fix

Replace `_find_message` with `_find_last_message` in the handlers that look up context for the current round:

- **`handle_topic_selection`**: use `_find_last_message` for `topics` and `text` (currently uses `_find_message`)
- **`handle_script_approval`**: use `_find_last_message` for `topics`, `topic_selection`, `text`, and `script` (partially uses `_find_last_message` for `script` already, but uses `_find_message` for the others)

After a script is saved, the next `text` message from the user triggers `handle_ideation` again via the existing router — no router changes needed.

### Files

- Modify: `backend/services/script_pipeline.py` (change `_find_message` → `_find_last_message` calls)
- Modify: `backend/tests/test_script_pipeline.py` (add test for second round in same conversation)

---

## Feature 2: User Memories

### Database

**Table: `user_memories`**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `user_id` | `uuid` | FK to `auth.users`, ON DELETE CASCADE |
| `content` | `text` | Not null. The extracted preference/learning |
| `source_action` | `text` | Not null. `approved` or `rejected` |
| `source_feedback` | `text` | The raw feedback that produced this memory (empty for approvals) |
| `created_at` | `timestamptz` | Default `now()` |

Index on `user_id`. RLS: users can only SELECT and DELETE their own rows. INSERT/UPDATE handled by service key in the pipeline.

Max 20 memories per user. Enforced at extraction time, not at DB level.

### Memory Extraction Flow

After each script approval or rejection in `handle_script_approval`, fire-and-forget an async task:

1. Fetch user's existing memories from `user_memories`
2. Call Guardian with a memory extraction prompt:
   ```
   You are analyzing a user's feedback on a YouTube script to extract preferences.

   Action: {approved|rejected}
   Topic: {topic_title}
   Feedback: {feedback or "none — user approved without changes"}

   Existing memories:
   {numbered list of current memories, or "none yet"}

   Rules:
   - Extract ONE concise preference from this interaction
   - If it contradicts an existing memory, return REPLACE:<id> before the new text
   - If it's redundant with an existing memory, return SKIP
   - Keep preferences actionable (e.g. "Prefers scripts under 10 minutes" not "User said too long")

   Return ONLY: the preference text, or REPLACE:<id> <new text>, or SKIP
   ```
3. Parse the response:
   - If `SKIP`: do nothing
   - If `REPLACE:<id> <text>`: delete the old memory, insert new one
   - Otherwise: insert as new memory
4. If user has >= 20 memories and response is not SKIP/REPLACE, delete the oldest memory before inserting

This runs **after** the SSE response completes — never blocks the user.

### Memory Injection

In `handle_topic_selection` and `handle_script_approval` (rejection branch), after fetching the persona and before building the prompt, fetch the user's memories and append to the prompt:

```
## Your Learned Preferences

- Prefers scripts under 10 minutes with tight pacing
- Likes controversial, opinionated angles over neutral summaries
- Avoids corporate/formal tone
```

If no memories exist, omit this section entirely.

### API Routes

**`GET /api/memories`**
- Returns list of user's memories ordered by `created_at` desc
- Response: `[{ id, content, source_action, source_feedback, created_at }]`

**`DELETE /api/memories/{memory_id}`**
- Deletes a specific memory belonging to the authenticated user
- Response: 204

No create/update endpoints — memories are only created by the pipeline.

### Frontend — Settings Page Addition

Below the existing persona form, add a "Learned Preferences" section:

- Header: "Learned Preferences" with subtitle "Automatically extracted from your script feedback"
- List of memory cards, each showing:
  - The preference text
  - A delete icon button
- Empty state: "No preferences learned yet. They'll appear here as you approve and reject scripts."
- Fetched on mount alongside the persona (`GET /api/memories`)
- Delete calls `DELETE /api/memories/{id}` and removes from local state

### Files to Change

**Create:**
- `backend/routes/memories.py` — API routes
- `backend/tests/test_memories_route.py` — route tests
- `backend/services/memory_extractor.py` — extraction logic
- `backend/tests/test_memory_extractor.py` — extraction tests

**Modify:**
- `backend/db/schema.sql` — add `user_memories` table + RLS
- `backend/main.py` — register memories router
- `backend/services/script_pipeline.py` — multi-script fix + memory extraction trigger + memory injection
- `backend/tests/test_script_pipeline.py` — multi-script test + memory injection test
- `frontend/src/lib/api.ts` — add memory API functions
- `frontend/src/pages/SettingsPage.tsx` — add memories section

## Out of Scope

- Editing memories from the frontend (delete only)
- Memory summarization/compaction beyond the 20-cap replacement
- Memories for thumbnail pipeline
- Memory export/import
