# Agentic Script Pipeline + Configurable LLM Backend + User Memories

**Goal:** Replace the rigid state-machine script pipeline with an agentic conversational approach, add a configurable LLM backend (direct Anthropic API or Guardian fallback), and build a memory system that learns user preferences.

## 1. Configurable LLM Backend

### Fallback Chain

If `ANTHROPIC_API_KEY` is set in the environment, use the Anthropic SDK directly (`anthropic.AsyncAnthropic`). Otherwise, fall back to Guardian's HTTP API.

### New Abstraction: `backend/services/llm.py`

Two functions:

**`async def ask_llm(system: str, messages: list[dict]) -> str`**
- Takes a system prompt and conversation history (list of `{"role": "user"|"assistant", "content": "..."}`)
- If `ANTHROPIC_API_KEY` is set: calls `client.messages.create()` with the configured model
- If not: flattens system + messages into a single prompt string, sends to Guardian's `/api/ask` endpoint
- Returns the full response text

**`async def stream_llm(system: str, messages: list[dict]) -> AsyncGenerator[str, None]`**
- Same interface but yields tokens as they arrive
- Anthropic path: uses `client.messages.stream()` and yields `text` deltas
- Guardian path: calls `ask_llm` and yields the full response as a single chunk (Guardian doesn't support streaming)

### Config Changes

Add to `Settings` in `backend/config.py`:
- `anthropic_api_key: str = ""` — optional, enables direct API path
- `anthropic_model: str = "claude-sonnet-4-20250514"` — configurable model

### Delete

`backend/services/guardian.py` — Guardian logic moves into `llm.py` as the fallback path.

---

## 2. Agentic Script Pipeline

### Current Problem

The pipeline is a rigid state machine: `handle_ideation` → `handle_topic_selection` → `handle_script_approval`. The frontend sends a `msg_type` that selects a hardcoded handler. If the user types anything outside the expected flow (e.g. "make it shorter" instead of clicking reject), it restarts from ideation.

### New Approach

Replace all stage handlers with a single handler. Send the full conversation history + system prompt to the LLM and let it decide what action to take.

### System Prompt

```
You are a YouTube content strategist and scriptwriter.

{persona}

{memories}

You help the user create YouTube video scripts through natural conversation. Based on the conversation context, decide what action to take.

You MUST respond with ONLY a valid JSON object (no markdown fences, no extra text). Use one of these actions:

1. Suggest topics — when the user describes a video idea or asks for topic suggestions:
{"action": "topics", "data": [{"title": "...", "angle": "...", "why_timely": "...", "source_url": "...", "interest": "high|medium|low"}, ...], "message": "optional conversational text"}

2. Write/rewrite a script — when the user picks a topic, asks you to write, or gives feedback on an existing script:
{"action": "script", "content": "...full markdown script...", "message": "optional conversational text"}

3. Save the script — when the user explicitly approves or says to save:
{"action": "save", "message": "optional conversational text"}

4. Conversational reply — when you need to ask for clarification, acknowledge something, or chat:
{"action": "message", "content": "your reply"}

Guidelines:
- ALWAYS search the web for current information before suggesting topics or writing scripts
- When suggesting topics, research current news and trends from the last 1-2 weeks
- When writing scripts, include real statistics with verifiable source URLs
- Write all script content in {language}
- When the user gives feedback on a script (e.g. "too long", "more humor", "add more stats"), rewrite the script incorporating their feedback — do NOT restart from topic suggestions
- When the user says something like "save", "looks good", "approved", "perfect" about a script, use the "save" action
- When unclear what the user wants, ask for clarification using the "message" action
- After a script is saved, if the user brings up a new topic, start fresh topic suggestions
```

Note: The `{persona}` and `{memories}` placeholders are filled from the user's DB records. If no persona exists, the pipeline returns an error (same gate as before). If no memories exist, that section is omitted.

### Single Handler

`handle_script_chat_message` becomes:

1. Fetch persona from `channel_personas` (hard gate if missing)
2. Fetch memories from `user_memories`
3. Fetch all conversation messages from DB
4. Build system prompt with persona + memories
5. Save the new user message to DB
6. Convert DB messages to LLM chat format (`role` + `content`)
7. Call `ask_llm(system, messages)`
8. Parse JSON response to extract `action`
9. Execute action:
   - `topics`: save as message type `topics`, return SSE with topic data
   - `script`: save as message type `script`, return SSE with script content
   - `save`: find last script, upload to storage, save confirmation message, trigger memory extraction, return SSE with saved path
   - `message`: save as message type `text`, return SSE with text content
10. If action is `save` or if the response was a `script` rewrite after rejection feedback, trigger async memory extraction

### Removed

- `IDEATION_PROMPT_TEMPLATE` and `SCRIPT_PROMPT_TEMPLATE` — replaced by single system prompt
- `handle_ideation`, `handle_topic_selection`, `handle_script_approval` — replaced by single handler
- `_find_message`, `_find_last_message` — no longer needed (LLM sees full history)
- `_extract_duration` — LLM handles this naturally from conversation
- `format_persona` — inlined into system prompt builder
- `_NO_TOOLS` suffix — not needed with API calls

### Kept

- `sse_event` helper
- `slugify` helper
- `_save_message` helper
- `_get_messages` helper
- `get_supabase` helper
- `_extract_json_array` — renamed/adapted to parse the action JSON response

### Frontend Changes

Minimal. The backend maps LLM actions to the same message types the frontend already renders:

| LLM Action | DB message type | Frontend rendering |
|------------|----------------|-------------------|
| `topics` | `topics` | Topic selection cards |
| `script` | `script` | Markdown script viewer |
| `save` | `saved` | Save confirmation |
| `message` | `text` | Text bubble |

**Key change:** For script mode, the frontend always sends messages as `type: "text"`. No more `topic_selection`, `approve_script`, `reject_script` types from the frontend in script mode. The user just types naturally.

**Topic selection** still works via click — when a user clicks a topic card, the frontend sends a text message like `"I want to make a video about: {topic_title}"` instead of sending a numeric index.

**Approve/reject buttons** still appear on script messages, but:
- Approve sends: `"Save this script"` as text
- Reject sends the user's typed feedback as text (or a default `"Please rewrite this script"` if they just click reject)

### Multi-Script Support

Comes for free. The LLM sees the full conversation history. After saving one script, the user types a new topic and the LLM naturally suggests new topics.

---

## 3. User Memories

### Database

**Table: `user_memories`**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `user_id` | `uuid` | FK to `auth.users`, ON DELETE CASCADE |
| `content` | `text` | Not null. The extracted preference/learning |
| `source_action` | `text` | Not null. `approved` or `rejected` |
| `source_feedback` | `text` | Raw feedback that produced this memory |
| `created_at` | `timestamptz` | Default `now()` |

Index on `user_id`. RLS: users can SELECT and DELETE their own rows.

Max 20 memories per user, enforced at extraction time.

### Memory Extraction Flow

After a script is saved or after a rewrite (user gave feedback), fire-and-forget async:

1. Fetch user's existing memories
2. Call `ask_llm` with extraction prompt:
   ```
   You are analyzing a user's interaction with a YouTube script to extract preferences.

   Action: {approved|rejected}
   Topic: {topic_title}
   Feedback: {feedback or "none — user approved without changes"}

   Existing memories:
   {numbered list with IDs, or "none yet"}

   Rules:
   - Extract ONE concise, actionable preference from this interaction
   - If it contradicts an existing memory, return REPLACE:<id> followed by the new text
   - If it's redundant with an existing memory, return SKIP
   - Keep preferences actionable (e.g. "Prefers scripts under 10 minutes" not "User said too long")

   Return ONLY: the preference text, or REPLACE:<id> <new text>, or SKIP
   ```
3. Parse response:
   - `SKIP`: do nothing
   - `REPLACE:<id> <text>`: delete old, insert new
   - Otherwise: insert new. If count >= 20, delete oldest first

Runs after SSE response completes — never blocks user.

### Memory Injection

Memories are appended to the system prompt:

```
## Your Learned Preferences

- Prefers scripts under 10 minutes with tight pacing
- Likes controversial, opinionated angles
- Avoids corporate/formal tone
```

Omitted if no memories exist.

### API Routes

**`GET /api/memories`** — list user's memories, ordered by `created_at` desc

**`DELETE /api/memories/{memory_id}`** — delete a specific memory, returns 204

No create/update from frontend.

### Frontend — Settings Page Addition

Below the persona form, add "Learned Preferences" section:
- List of memory items with delete icon buttons
- Empty state: "No preferences learned yet. They'll appear as you approve and reject scripts."
- Fetch on mount via `GET /api/memories`
- Delete via `DELETE /api/memories/{id}`

---

## Files Summary

### Create
- `backend/services/llm.py` — LLM abstraction
- `backend/tests/test_llm.py`
- `backend/services/memory_extractor.py` — memory extraction
- `backend/tests/test_memory_extractor.py`
- `backend/routes/memories.py` — memory API
- `backend/tests/test_memories_route.py`

### Modify
- `backend/config.py` — add `anthropic_api_key`, `anthropic_model`
- `backend/services/script_pipeline.py` — rewrite to agentic
- `backend/tests/test_script_pipeline.py` — rewrite tests
- `backend/db/schema.sql` — add `user_memories` table
- `backend/main.py` — register memories router
- `frontend/src/lib/api.ts` — add memory functions
- `frontend/src/pages/SettingsPage.tsx` — add memories section
- `frontend/src/pages/ChatPage.tsx` — simplify script message sending

### Delete
- `backend/services/guardian.py` — absorbed into `llm.py`
- `backend/tests/test_guardian.py` — replaced by `test_llm.py`

## Out of Scope

- Streaming token-by-token to frontend (future enhancement — currently returns full response)
- Agentic thumbnail pipeline (separate effort)
- Memory editing from frontend (delete only)
- Tool use / function calling (using JSON action format instead)
