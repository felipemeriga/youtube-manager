# Script Creator — Design Spec

## Overview

Add a YouTube script creation pipeline to youtube-manager. Users interact through the existing chat UI to generate video scripts via a multi-stage workflow. Server-guardian (Claude) handles all intelligence — ideation, research, outlining, and script writing. No LangGraph, no external research tools.

## Pipeline Stages

### Stage 1: Ideation

Server-guardian suggests 5–10 video topics based on **recent news and trends** (last 1–2 weeks). If the user typed an initial message (e.g., "I want something about AI"), it's appended as context to the ideation prompt.

**Output:** JSON array of topics, each with title, angle, timeliness rationale, and estimated audience interest (high/medium/low).

**UI:** Topic cards rendered via `ScriptTopicList` component. User clicks one to select.

### Stage 2: Research

Server-guardian deep-researches the selected topic using its MCP tools. Produces a structured summary with sources, data, statistics, and expert opinions focused on recent content.

**Output:** Structured markdown summary streamed to chat.

**No approval gate** — auto-continues to Stage 3. Research summary remains visible in chat.

### Stage 3: Outline

Server-guardian generates a video outline injected with the channel persona. Includes hook (first 30 seconds), sections with key points and estimated durations, transitions, call to action, and total estimated video duration.

**Output:** Structured markdown.

**UI:** Rendered inline via `ScriptViewer`. User sees [Approve] / [Reject] buttons.

### Stage 4: Script

Server-guardian writes the full video script in Brazilian Portuguese, using the persona, approved outline, and research findings. Includes word-for-word dialogue, timing markers, visual cue/B-roll notes, and stats with inline citations.

**Output:** Full markdown script.

**UI:** Rendered inline via `ScriptViewer`. User sees [Approve] / [Reject] buttons.

### Stage 5: Save

Approved script is saved as a `.md` file to Supabase Storage `scripts` bucket.

**Naming:** `{user_id}/{slugified-topic}-{timestamp}.md`

### Rejection Flow

On rejection at any approval gate, the user can type feedback in chat. The rejected stage re-runs with feedback appended to the prompt.

## Backend Architecture

### New Files

#### `backend/services/script_pipeline.py`

Pipeline orchestrator with one async function per stage:

- `handle_ideation(conversation_id, user_message, user_id)` — Calls server-guardian with ideation prompt. Saves `topics` message to DB. Streams SSE events.
- `handle_topic_selection(conversation_id, topic_index, user_id)` — Records selection. Makes two sequential server-guardian calls: first research, then outline. Each call streams its own SSE events and saves its own message to DB. The outline call receives the research output as context.
- `handle_outline_approval(conversation_id, approved, feedback, user_id)` — If approved, calls script generation. If rejected, re-runs outline with feedback.
- `handle_script_approval(conversation_id, approved, feedback, user_id)` — If approved, saves script to storage. If rejected, re-runs script generation with feedback.
- `handle_save(conversation_id, user_id)` — Saves approved script to `scripts` bucket.

Each function follows the same pattern as `thumbnail_pipeline.py`: call `ask_guardian()`, stream SSE events, save messages to DB.

#### `backend/persona.py`

Hardcoded persona configuration:

```python
PERSONA = {
    "channel": "Além do Código",
    "language": "Brazilian Portuguese",
    "tone": "conversational, informal, provocative",
    "humor": "uses humor naturally, not forced",
    "approach": "takes a position, never neutral",
    "style": "direct, uses real examples, challenges conventional wisdom",
    "avoid": ["sounding like a guru", "generic advice", "corporate tone"],
}
```

`format_persona() -> str` converts the dict to markdown for prompt injection. Used in outline and script stages only.

### Modified Files

#### `backend/routes/chat.py`

Existing chat SSE endpoint dispatches to the correct pipeline based on conversation `mode`:

- `mode == 'thumbnail'` → `thumbnail_pipeline` (existing)
- `mode == 'script'` → `script_pipeline` (new)

Message `type` field determines which stage function to call within the script pipeline.

#### `backend/routes/assets.py`

Add `scripts` to allowed buckets list. File size limit: 5MB.

#### `backend/routes/conversations.py`

Accept `mode` field on conversation creation (`POST /api/conversations`). Default: `'thumbnail'`.

#### `backend/services/guardian.py` (new — was removed during thumbnail refactor)

Async HTTP client that calls server-guardian's `/api/ask` endpoint via httpx. Single function: `ask_guardian(prompt, context="") -> str`.

#### `backend/config.py`

Add `guardian_url` setting (default: `http://localhost:3000`).

### Existing Files (No Changes)

- `backend/auth.py` — No changes.

## Message Types

New message types for script conversations:

| type | role | purpose |
|------|------|---------|
| `text` | user | Initial request or feedback |
| `topics` | assistant | JSON array of suggested topics |
| `topic_selection` | user | User picked topic N |
| `research` | assistant | Research findings summary (markdown) |
| `outline` | assistant | Video outline (markdown) |
| `approval` | user | Approve/reject with optional feedback |
| `script` | assistant | Full generated script (markdown) |
| `save` | user | Trigger save to storage |
| `saved` | assistant | Confirmation with storage path |

## Server-Guardian Prompts

### Ideation Prompt

```
You are a YouTube content strategist. Suggest 5-10 video topics based on
RECENT news and trends (last 1-2 weeks). The channel is a Brazilian Portuguese
tech channel. For each topic, provide: title, angle, why it's timely, and
estimated audience interest (high/medium/low). Format as JSON array.

{optional user context}
```

### Research Prompt

```
Research this topic in depth: {selected_topic}. Find recent articles, data,
statistics, expert opinions, and real-world examples. Provide a structured
summary with sources. Focus on content from the last 1-2 weeks.
```

### Outline Prompt

```
{formatted_persona}

Based on this research: {research_findings}

Create a video outline for the topic: {topic}. Include:
- Hook (first 30 seconds)
- Sections with key points and estimated duration
- Transitions between sections
- Call to action
- Total estimated video duration

Format as structured markdown.
```

### Script Prompt

```
{formatted_persona}

Based on this outline: {outline}
And this research: {research_findings}

Write a complete video script in Brazilian Portuguese. Include:
- Word-for-word dialogue for each section
- Timing markers
- Notes for visual cues / B-roll suggestions
- Stats and data with inline citations from the research

Format as markdown with clear section headers.
```

Prompts will be refined over time and eventually synced with existing Notion scripts.

## Frontend Architecture

### New Components

#### `ScriptTopicList.tsx`

Renders 5–10 topic suggestions as selectable cards. Each card shows:
- Topic title
- Angle / approach
- Why it's timely
- Interest level badge (high/medium/low)

Clicking a card sends a `topic_selection` message to the chat endpoint.

#### `ScriptViewer.tsx`

Renders outline and script content as formatted markdown. Uses the existing `react-markdown` setup. Displayed inline within `MessageBubble`.

### Modified Components

#### `ChatPage.tsx`

- Mode selection when creating a new conversation (dialog or toggle: "Thumbnail" / "Script")
- Sets `mode` field on conversation creation API call

#### `MessageBubble.tsx`

Handle new message types:
- `topics` → render `ScriptTopicList`
- `research` → render collapsible markdown summary
- `outline` → render `ScriptViewer`
- `script` → render `ScriptViewer`

#### `ApprovalButtons.tsx`

Show [Approve] / [Reject] buttons for `outline` and `script` message types in script-mode conversations.

#### `ContextPanel.tsx`

Show a mode indicator (small icon or label) on each conversation in the sidebar list to distinguish script vs thumbnail conversations.

#### `AssetsPage.tsx`

Add a **Scripts** tab that:
- Lists `.md` files from the `scripts` bucket
- Previews markdown inline (reusing `react-markdown`)
- Supports download as `.md` file
- Supports delete

## Database Changes

### Conversations Table

```sql
ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'thumbnail';
```

No new tables. The existing `messages` table supports the new type values without schema changes.

## Supabase Storage

### New Bucket: `scripts`

- Scoped by `user_id/` prefix (consistent with other buckets)
- Files: `.md` (markdown)
- Naming: `{user_id}/{slugified-topic}-{timestamp}.md`
- Max file size: 5MB
- RLS: same policy as other buckets (user can only access own files)

## SSE Streaming Events

Same event format as thumbnail pipeline:

```json
{"stage": "finding_trends"}
{"stage": "researching"}
{"stage": "writing_outline"}
{"stage": "writing_script"}
{"stage": "saving"}
{"token": "..."}
{"done": true, "saved": true, "path": "scripts/..."}
{"error": "..."}
```

## What's NOT Included

- **No LangGraph** — conversation history is the state machine
- **No Tavily / Playwright** — server-guardian handles all research
- **No YouTube API** — server-guardian suggests topics from general knowledge of recent trends
- **No SEO metadata generation** — removed per user request
- **No persona settings UI** — hardcoded, editable in code only
- **No Notion sync** — future enhancement
