# Script Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-stage YouTube script creation pipeline to youtube-manager, using server-guardian as the LLM brain.

**Architecture:** Sequential pipeline (no LangGraph) following the thumbnail creator pattern. Each stage calls server-guardian via `ask_guardian()`, streams SSE events, and persists messages to Supabase. Conversation `mode` column routes to the correct pipeline. Frontend renders new message types (topics, outline, script) with approval gates.

**Tech Stack:** FastAPI, httpx (server-guardian client), Supabase (PostgreSQL + Storage), React 18, MUI 6, react-markdown, Vite

**Base branch:** `origin/feat/thumbnail-creator` (all work builds on the existing thumbnail creator)

---

## File Map

### New Files (Backend)
| File | Responsibility |
|------|---------------|
| `backend/services/guardian.py` | Server-guardian HTTP client (`ask_guardian()`) |
| `backend/services/script_pipeline.py` | Script pipeline orchestrator (5 stages) |
| `backend/persona.py` | Hardcoded channel persona + formatter |
| `backend/tests/test_guardian.py` | Tests for guardian client |
| `backend/tests/test_script_pipeline.py` | Tests for script pipeline |
| `backend/tests/test_persona.py` | Tests for persona formatter |

### New Files (Frontend)
| File | Responsibility |
|------|---------------|
| `frontend/src/components/ScriptTopicList.tsx` | Topic suggestion cards with selection |
| `frontend/src/components/ScriptViewer.tsx` | Markdown renderer for outline/script |

### Modified Files
| File | Change |
|------|--------|
| `backend/config.py` | Add `guardian_url` setting |
| `backend/routes/chat.py` | Route by conversation mode |
| `backend/routes/conversations.py` | Accept `mode` on create |
| `backend/routes/assets.py` | Add `scripts` bucket |
| `backend/tests/test_chat.py` | Add mode-routing tests |
| `backend/tests/test_conversations.py` | Add mode field tests |
| `backend/tests/test_assets.py` | Add scripts bucket tests |
| `frontend/src/lib/api.ts` | Pass `mode` on create, add `onTopics` callback |
| `frontend/src/pages/ChatPage.tsx` | Mode selection, topic/approval handlers |
| `frontend/src/pages/AssetsPage.tsx` | Add Scripts tab |
| `frontend/src/components/MessageBubble.tsx` | Render topics/outline/script types |
| `frontend/src/components/ApprovalButtons.tsx` | Add Approve/Reject variant |
| `frontend/src/components/ThinkingBar.tsx` | Add script stage labels |
| `frontend/src/components/ContextPanel.tsx` | Mode indicator on conversations |
| `frontend/src/components/ChatArea.tsx` | Pass mode to empty state |

---

## Task 1: Server-Guardian Client

**Files:**
- Create: `backend/services/guardian.py`
- Modify: `backend/config.py`
- Test: `backend/tests/test_guardian.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_guardian.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_ask_guardian_returns_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Hello from guardian"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        from services.guardian import ask_guardian

        result = await ask_guardian("What is Python?")

    assert result == "Hello from guardian"
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "What is Python?" in str(call_args)


@pytest.mark.asyncio
async def test_ask_guardian_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = Exception("Server error")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        from services.guardian import ask_guardian

        with pytest.raises(Exception, match="Server error"):
            await ask_guardian("test")


@pytest.mark.asyncio
async def test_ask_guardian_with_context():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Contextual answer"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        from services.guardian import ask_guardian

        result = await ask_guardian("question", context="extra context")

    assert result == "Contextual answer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_guardian.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.guardian'`

- [ ] **Step 3: Add `guardian_url` to config**

In `backend/config.py`, add to the `Settings` class:

```python
guardian_url: str = "http://localhost:3000"
```

- [ ] **Step 4: Write the guardian client**

Create `backend/services/guardian.py`:

```python
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 120.0


async def ask_guardian(prompt: str, context: str = "") -> str:
    full_prompt = f"{prompt}\n\n{context}".strip() if context else prompt
    logger.info("ask_guardian prompt=%s", full_prompt[:120])

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{settings.guardian_url}/api/ask",
            json={"message": full_prompt},
        )
        response.raise_for_status()
        data = response.json()

    answer = data.get("response", "")
    logger.info("guardian responded, length=%d", len(answer))
    return answer
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_guardian.py -v`
Expected: 3 passed

- [ ] **Step 6: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 7: Commit**

```bash
git add backend/services/guardian.py backend/config.py backend/tests/test_guardian.py
git commit -m "feat: add server-guardian HTTP client"
```

---

## Task 2: Persona Module

**Files:**
- Create: `backend/persona.py`
- Test: `backend/tests/test_persona.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_persona.py`:

```python
from persona import PERSONA, format_persona


def test_persona_has_required_keys():
    assert "channel" in PERSONA
    assert "language" in PERSONA
    assert "tone" in PERSONA
    assert "avoid" in PERSONA


def test_format_persona_returns_string():
    result = format_persona()
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_persona_contains_channel_name():
    result = format_persona()
    assert "Além do Código" in result


def test_format_persona_contains_avoid_items():
    result = format_persona()
    for item in PERSONA["avoid"]:
        assert item in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_persona.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'persona'`

- [ ] **Step 3: Write the persona module**

Create `backend/persona.py`:

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


def format_persona() -> str:
    avoid_list = "\n".join(f"- {item}" for item in PERSONA["avoid"])
    return (
        f"# Channel Persona: {PERSONA['channel']}\n\n"
        f"**Language:** {PERSONA['language']}\n"
        f"**Tone:** {PERSONA['tone']}\n"
        f"**Humor:** {PERSONA['humor']}\n"
        f"**Approach:** {PERSONA['approach']}\n"
        f"**Style:** {PERSONA['style']}\n\n"
        f"**Avoid:**\n{avoid_list}\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_persona.py -v`
Expected: 4 passed

- [ ] **Step 5: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 6: Commit**

```bash
git add backend/persona.py backend/tests/test_persona.py
git commit -m "feat: add channel persona module"
```

---

## Task 3: Script Pipeline

**Files:**
- Create: `backend/services/script_pipeline.py`
- Test: `backend/tests/test_script_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_script_pipeline.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def mock_supabase():
    sb = AsyncMock()
    sb.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "msg-1"}])
    )
    sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{}])
    )
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data={"id": "conv-1", "mode": "script"})
    )
    sb.storage.from_.return_value.upload = AsyncMock()
    return sb


SAMPLE_TOPICS_JSON = json.dumps([
    {
        "title": "AI Agents in 2026",
        "angle": "practical use cases",
        "timeliness": "new frameworks released this week",
        "interest": "high",
    },
    {
        "title": "Rust for Web",
        "angle": "replacing Node.js",
        "timeliness": "trending on HackerNews",
        "interest": "medium",
    },
])


@pytest.mark.asyncio
async def test_handle_ideation_streams_topics():
    sb = mock_supabase()

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value=SAMPLE_TOPICS_JSON,
    ):
        with patch("services.script_pipeline.get_supabase", return_value=sb):
            from services.script_pipeline import handle_ideation

            events = []
            async for event in handle_ideation("conv-1", "AI topics", "user-1"):
                events.append(event)

    event_data = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data: ")]
    stages = [d for d in event_data if "stage" in d]
    assert any(d.get("stage") == "finding_trends" for d in stages)
    done_events = [d for d in event_data if d.get("done")]
    assert len(done_events) == 1
    assert done_events[0].get("message_type") == "topics"


@pytest.mark.asyncio
async def test_handle_topic_selection_streams_research_and_outline():
    sb = mock_supabase()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[
            {"type": "topics", "role": "assistant", "content": SAMPLE_TOPICS_JSON},
        ])
    )

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        side_effect=["Research findings here", "## Outline\n- Section 1"],
    ):
        with patch("services.script_pipeline.get_supabase", return_value=sb):
            from services.script_pipeline import handle_topic_selection

            events = []
            async for event in handle_topic_selection("conv-1", 0, "user-1"):
                events.append(event)

    event_data = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data: ")]
    stages = [d.get("stage") for d in event_data if "stage" in d]
    assert "researching" in stages
    assert "writing_outline" in stages


@pytest.mark.asyncio
async def test_handle_outline_approval_approved():
    sb = mock_supabase()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[
            {"type": "topics", "role": "assistant", "content": SAMPLE_TOPICS_JSON},
            {"type": "topic_selection", "role": "user", "content": "0"},
            {"type": "research", "role": "assistant", "content": "Research data"},
            {"type": "outline", "role": "assistant", "content": "## Outline"},
        ])
    )

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value="# Full Script\nHello world",
    ):
        with patch("services.script_pipeline.get_supabase", return_value=sb):
            from services.script_pipeline import handle_outline_approval

            events = []
            async for event in handle_outline_approval("conv-1", True, "", "user-1"):
                events.append(event)

    event_data = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data: ")]
    stages = [d.get("stage") for d in event_data if "stage" in d]
    assert "writing_script" in stages


@pytest.mark.asyncio
async def test_handle_outline_approval_rejected():
    sb = mock_supabase()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[
            {"type": "research", "role": "assistant", "content": "Research data"},
            {"type": "outline", "role": "assistant", "content": "## Outline"},
        ])
    )

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value="## Revised Outline",
    ):
        with patch("services.script_pipeline.get_supabase", return_value=sb):
            from services.script_pipeline import handle_outline_approval

            events = []
            async for event in handle_outline_approval(
                "conv-1", False, "Add more sections", "user-1"
            ):
                events.append(event)

    event_data = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data: ")]
    stages = [d.get("stage") for d in event_data if "stage" in d]
    assert "writing_outline" in stages


@pytest.mark.asyncio
async def test_handle_script_approval_saves_to_storage():
    sb = mock_supabase()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[
            {"type": "topic_selection", "role": "user", "content": "0"},
            {"type": "topics", "role": "assistant", "content": SAMPLE_TOPICS_JSON},
            {"type": "script", "role": "assistant", "content": "# Script content"},
        ])
    )

    with patch("services.script_pipeline.get_supabase", return_value=sb):
        from services.script_pipeline import handle_script_approval

        events = []
        async for event in handle_script_approval("conv-1", True, "", "user-1"):
            events.append(event)

    event_data = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data: ")]
    done_events = [d for d in event_data if d.get("done")]
    assert len(done_events) == 1
    assert done_events[0].get("saved") is True
    sb.storage.from_.assert_called_with("scripts")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_script_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.script_pipeline'`

- [ ] **Step 3: Write the script pipeline**

Create `backend/services/script_pipeline.py`:

```python
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from persona import format_persona
from services.guardian import ask_guardian

logger = logging.getLogger(__name__)


async def get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")[:60]


IDEATION_PROMPT = (
    "You are a YouTube content strategist. Suggest 5-10 video topics based on "
    "RECENT news and trends (last 1-2 weeks). The channel is a Brazilian Portuguese "
    "tech channel. For each topic, provide: title, angle, why it's timely, and "
    "estimated audience interest (high/medium/low). "
    "Return ONLY a valid JSON array, no markdown fences."
)

RESEARCH_PROMPT = (
    "Research this topic in depth: {topic}. Find recent articles, data, "
    "statistics, expert opinions, and real-world examples. Provide a structured "
    "summary with sources. Focus on content from the last 1-2 weeks."
)

OUTLINE_PROMPT = (
    "{persona}\n\n"
    "Based on this research:\n{research}\n\n"
    "Create a video outline for the topic: {topic}. Include:\n"
    "- Hook (first 30 seconds)\n"
    "- Sections with key points and estimated duration\n"
    "- Transitions between sections\n"
    "- Call to action\n"
    "- Total estimated video duration\n\n"
    "Format as structured markdown."
)

SCRIPT_PROMPT = (
    "{persona}\n\n"
    "Based on this outline:\n{outline}\n\n"
    "And this research:\n{research}\n\n"
    "Write a complete video script in Brazilian Portuguese. Include:\n"
    "- Word-for-word dialogue for each section\n"
    "- Timing markers\n"
    "- Notes for visual cues / B-roll suggestions\n"
    "- Stats and data with inline citations from the research\n\n"
    "Format as markdown with clear section headers."
)


async def _save_message(sb, conversation_id: str, role: str, content: str, msg_type: str):
    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "type": msg_type,
            }
        )
        .execute()
    )


async def _get_messages(sb, conversation_id: str) -> list[dict]:
    response = (
        await sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return response.data


def _find_message(messages: list[dict], msg_type: str) -> dict | None:
    return next((m for m in messages if m["type"] == msg_type), None)


def _find_last_message(messages: list[dict], msg_type: str) -> dict | None:
    return next((m for m in reversed(messages) if m["type"] == msg_type), None)


async def handle_ideation(
    conversation_id: str, user_message: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info("ideation conversation=%s user=%s", conversation_id, user_id)
    sb = await get_supabase()

    await _save_message(sb, conversation_id, "user", user_message, "text")
    await (
        sb.table("conversations")
        .update({"title": user_message[:50]})
        .eq("id", conversation_id)
        .execute()
    )

    yield sse_event({"stage": "finding_trends"})

    prompt = IDEATION_PROMPT
    if user_message:
        prompt += f"\n\nUser context: {user_message}"

    topics_response = await ask_guardian(prompt)

    await _save_message(sb, conversation_id, "assistant", topics_response, "topics")

    yield sse_event({"message_type": "topics", "content": topics_response})
    yield sse_event({"done": True, "message_type": "topics"})


async def handle_topic_selection(
    conversation_id: str, topic_index: int, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "topic_selection conversation=%s topic=%d user=%s",
        conversation_id,
        topic_index,
        user_id,
    )
    sb = await get_supabase()

    await _save_message(
        sb, conversation_id, "user", str(topic_index), "topic_selection"
    )

    messages = await _get_messages(sb, conversation_id)
    topics_msg = _find_message(messages, "topics")
    if not topics_msg:
        yield sse_event({"error": "No topics found", "done": True})
        return

    topics = json.loads(topics_msg["content"])
    if topic_index < 0 or topic_index >= len(topics):
        yield sse_event({"error": "Invalid topic index", "done": True})
        return

    selected_topic = topics[topic_index]
    topic_title = selected_topic.get("title", "Unknown topic")

    # Stage 2: Research
    yield sse_event({"stage": "researching"})
    research_prompt = RESEARCH_PROMPT.format(topic=topic_title)
    research = await ask_guardian(research_prompt)
    await _save_message(sb, conversation_id, "assistant", research, "research")
    yield sse_event({"message_type": "research", "content": research})

    # Stage 3: Outline
    yield sse_event({"stage": "writing_outline"})
    persona = format_persona()
    outline_prompt = OUTLINE_PROMPT.format(
        persona=persona, research=research, topic=topic_title
    )
    outline = await ask_guardian(outline_prompt)
    await _save_message(sb, conversation_id, "assistant", outline, "outline")

    yield sse_event({"message_type": "outline", "content": outline})
    yield sse_event({"done": True, "message_type": "outline"})


async def handle_outline_approval(
    conversation_id: str, approved: bool, feedback: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "outline_approval conversation=%s approved=%s user=%s",
        conversation_id,
        approved,
        user_id,
    )
    sb = await get_supabase()

    approval_content = "approved" if approved else f"rejected: {feedback}"
    await _save_message(sb, conversation_id, "user", approval_content, "approval")

    messages = await _get_messages(sb, conversation_id)
    research_msg = _find_last_message(messages, "research")
    research = research_msg["content"] if research_msg else ""

    if approved:
        # Stage 4: Script
        outline_msg = _find_last_message(messages, "outline")
        outline = outline_msg["content"] if outline_msg else ""

        yield sse_event({"stage": "writing_script"})
        persona = format_persona()
        script_prompt = SCRIPT_PROMPT.format(
            persona=persona, outline=outline, research=research
        )
        script = await ask_guardian(script_prompt)
        await _save_message(sb, conversation_id, "assistant", script, "script")

        yield sse_event({"message_type": "script", "content": script})
        yield sse_event({"done": True, "message_type": "script"})
    else:
        # Re-run outline with feedback
        outline_msg = _find_last_message(messages, "outline")
        previous_outline = outline_msg["content"] if outline_msg else ""

        yield sse_event({"stage": "writing_outline"})
        persona = format_persona()
        outline_prompt = OUTLINE_PROMPT.format(
            persona=persona, research=research, topic="(see previous outline)"
        )
        outline_prompt += (
            f"\n\nPrevious outline:\n{previous_outline}\n\n"
            f"User feedback: {feedback}\n"
            "Please revise the outline based on this feedback."
        )
        outline = await ask_guardian(outline_prompt)
        await _save_message(sb, conversation_id, "assistant", outline, "outline")

        yield sse_event({"message_type": "outline", "content": outline})
        yield sse_event({"done": True, "message_type": "outline"})


async def handle_script_approval(
    conversation_id: str, approved: bool, feedback: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_approval conversation=%s approved=%s user=%s",
        conversation_id,
        approved,
        user_id,
    )
    sb = await get_supabase()

    approval_content = "approved" if approved else f"rejected: {feedback}"
    await _save_message(sb, conversation_id, "user", approval_content, "approval")

    if approved:
        # Stage 5: Save
        yield sse_event({"stage": "saving"})
        messages = await _get_messages(sb, conversation_id)
        script_msg = _find_last_message(messages, "script")
        topics_msg = _find_message(messages, "topics")
        selection_msg = _find_message(messages, "topic_selection")

        script_content = script_msg["content"] if script_msg else ""

        # Derive filename from topic
        topic_title = "script"
        if topics_msg and selection_msg:
            try:
                topics = json.loads(topics_msg["content"])
                idx = int(selection_msg["content"])
                topic_title = topics[idx].get("title", "script")
            except (json.JSONDecodeError, IndexError, ValueError):
                pass

        slug = slugify(topic_title)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{slug}-{timestamp}.md"
        storage_path = f"{user_id}/{filename}"

        await sb.storage.from_("scripts").upload(
            storage_path,
            script_content.encode("utf-8"),
            {"content-type": "text/markdown"},
        )

        await _save_message(
            sb,
            conversation_id,
            "assistant",
            f"Script saved as {filename}",
            "saved",
        )

        yield sse_event(
            {"done": True, "saved": True, "path": storage_path, "content": f"Script saved as {filename}"}
        )
    else:
        # Re-run script with feedback
        messages = await _get_messages(sb, conversation_id)
        outline_msg = _find_last_message(messages, "outline")
        research_msg = _find_last_message(messages, "research")
        script_msg = _find_last_message(messages, "script")

        outline = outline_msg["content"] if outline_msg else ""
        research = research_msg["content"] if research_msg else ""
        previous_script = script_msg["content"] if script_msg else ""

        yield sse_event({"stage": "writing_script"})
        persona = format_persona()
        script_prompt = SCRIPT_PROMPT.format(
            persona=persona, outline=outline, research=research
        )
        script_prompt += (
            f"\n\nPrevious script:\n{previous_script[:2000]}\n\n"
            f"User feedback: {feedback}\n"
            "Please revise the script based on this feedback."
        )
        script = await ask_guardian(script_prompt)
        await _save_message(sb, conversation_id, "assistant", script, "script")

        yield sse_event({"message_type": "script", "content": script})
        yield sse_event({"done": True, "message_type": "script"})


async def handle_script_chat_message(
    conversation_id: str,
    content: str,
    msg_type: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_chat type=%s conversation=%s user=%s",
        msg_type,
        conversation_id,
        user_id,
    )
    try:
        if msg_type == "text":
            async for event in handle_ideation(conversation_id, content, user_id):
                yield event
        elif msg_type == "topic_selection":
            topic_index = int(content)
            async for event in handle_topic_selection(
                conversation_id, topic_index, user_id
            ):
                yield event
        elif msg_type == "approve_outline":
            async for event in handle_outline_approval(
                conversation_id, True, "", user_id
            ):
                yield event
        elif msg_type == "reject_outline":
            async for event in handle_outline_approval(
                conversation_id, False, content, user_id
            ):
                yield event
        elif msg_type == "approve_script":
            async for event in handle_script_approval(
                conversation_id, True, "", user_id
            ):
                yield event
        elif msg_type == "reject_script":
            async for event in handle_script_approval(
                conversation_id, False, content, user_id
            ):
                yield event
        else:
            logger.warning("unknown script message type=%s", msg_type)
            yield sse_event({"error": f"Unknown type: {msg_type}", "done": True})
    except Exception as e:
        logger.exception("error in script pipeline type=%s: %s", msg_type, e)
        yield sse_event({"error": str(e), "done": True})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_script_pipeline.py -v`
Expected: 5 passed

- [ ] **Step 5: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 6: Commit**

```bash
git add backend/services/script_pipeline.py backend/tests/test_script_pipeline.py
git commit -m "feat: add script creation pipeline with 5 stages"
```

---

## Task 4: Conversation Mode Support

**Files:**
- Modify: `backend/routes/conversations.py`
- Modify: `backend/tests/test_conversations.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_conversations.py`:

```python
def test_create_conversation_with_script_mode(client, valid_user_id):
    with patch("routes.conversations.get_current_user", return_value=valid_user_id):
        with patch("routes.conversations.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": "new-id", "user_id": valid_user_id, "mode": "script"}])
            )
            response = client.post("/api/conversations", json={"mode": "script"})

    assert response.status_code == 200
    mock_sb.return_value.table.return_value.insert.assert_called_once()
    call_args = mock_sb.return_value.table.return_value.insert.call_args[0][0]
    assert call_args["mode"] == "script"


def test_create_conversation_default_mode_is_thumbnail(client, valid_user_id):
    with patch("routes.conversations.get_current_user", return_value=valid_user_id):
        with patch("routes.conversations.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.insert.return_value.execute.return_value = (
                MagicMock(data=[{"id": "new-id", "user_id": valid_user_id, "mode": "thumbnail"}])
            )
            response = client.post("/api/conversations")

    assert response.status_code == 200
    call_args = mock_sb.return_value.table.return_value.insert.call_args[0][0]
    assert call_args.get("mode", "thumbnail") == "thumbnail"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_conversations.py::test_create_conversation_with_script_mode -v`
Expected: FAIL

- [ ] **Step 3: Modify conversations route to accept mode**

In `backend/routes/conversations.py`, add a request model and update `create_conversation`:

```python
from pydantic import BaseModel
from typing import Optional


class CreateConversationRequest(BaseModel):
    mode: str = "thumbnail"
```

Update the `create_conversation` endpoint:

```python
@router.post("/api/conversations")
async def create_conversation(
    request: Optional[CreateConversationRequest] = None,
    user_id: str = Depends(get_current_user),
):
    sb = get_supabase()
    mode = request.mode if request else "thumbnail"
    result = (
        sb.table("conversations")
        .insert({"user_id": user_id, "mode": mode})
        .execute()
    )
    return result.data[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_conversations.py -v`
Expected: All passed

- [ ] **Step 5: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/conversations.py backend/tests/test_conversations.py
git commit -m "feat: add mode field to conversation creation"
```

---

## Task 5: Chat Route Mode Dispatch

**Files:**
- Modify: `backend/routes/chat.py`
- Modify: `backend/tests/test_chat.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_chat.py`:

```python
def test_chat_dispatches_to_script_pipeline_for_script_mode():
    client = create_app("test-user")

    async def fake_script_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'finding_trends'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
        MagicMock(data={"id": "conv-1", "mode": "script", "user_id": "test-user"})
    )

    with patch("routes.chat.get_supabase", return_value=mock_sb):
        with patch(
            "routes.chat.handle_script_chat_message",
            side_effect=fake_script_stream,
        ) as mock_script:
            response = client.post(
                "/api/chat",
                json={
                    "conversation_id": "conv-1",
                    "content": "AI topics",
                    "type": "text",
                },
            )

    assert response.status_code == 200
    mock_script.assert_called_once()


def test_chat_dispatches_to_thumbnail_pipeline_for_thumbnail_mode():
    client = create_app("test-user")

    async def fake_thumb_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
        MagicMock(data={"id": "conv-1", "mode": "thumbnail", "user_id": "test-user"})
    )

    with patch("routes.chat.get_supabase", return_value=mock_sb):
        with patch(
            "routes.chat.handle_chat_message",
            side_effect=fake_thumb_stream,
        ) as mock_thumb:
            response = client.post(
                "/api/chat",
                json={
                    "conversation_id": "conv-1",
                    "content": "Create thumbnail",
                    "type": "text",
                },
            )

    assert response.status_code == 200
    mock_thumb.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chat.py::test_chat_dispatches_to_script_pipeline_for_script_mode -v`
Expected: FAIL

- [ ] **Step 3: Update chat route to dispatch by mode**

Replace `backend/routes/chat.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

from auth import get_current_user
from config import settings
from services.thumbnail_pipeline import handle_chat_message
from services.script_pipeline import handle_script_chat_message

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"


@router.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    conv = (
        sb.table("conversations")
        .select("mode")
        .eq("id", request.conversation_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    mode = conv.data.get("mode", "thumbnail") if conv.data else "thumbnail"

    if mode == "script":
        stream = handle_script_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            msg_type=request.type,
            user_id=user_id,
        )
    else:
        stream = handle_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            msg_type=request.type,
            user_id=user_id,
        )

    return StreamingResponse(stream, media_type="text/event-stream")
```

- [ ] **Step 4: Run all chat tests**

Run: `cd backend && python -m pytest tests/test_chat.py -v`
Expected: All passed

- [ ] **Step 5: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/chat.py backend/tests/test_chat.py
git commit -m "feat: route chat to script or thumbnail pipeline by conversation mode"
```

---

## Task 6: Scripts Bucket in Assets

**Files:**
- Modify: `backend/routes/assets.py`
- Modify: `backend/tests/test_assets.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_assets.py`:

```python
def test_list_scripts_bucket(client, valid_user_id):
    with patch("routes.assets.get_current_user", return_value=valid_user_id):
        with patch("routes.assets.get_supabase") as mock_sb:
            mock_sb.return_value.storage.from_.return_value.list.return_value = [
                {"name": "my-script.md", "id": "1"}
            ]
            mock_sb.return_value.storage.from_.return_value.get_public_url.return_value = (
                "https://test.supabase.co/storage/v1/object/public/scripts/user/my-script.md"
            )
            response = client.get("/api/assets/scripts")

    assert response.status_code == 200
    assert len(response.json()) == 1
    mock_sb.return_value.storage.from_.assert_called_with("scripts")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_assets.py::test_list_scripts_bucket -v`
Expected: FAIL — 400 "Invalid bucket"

- [ ] **Step 3: Add scripts bucket**

In `backend/routes/assets.py`, update:

```python
VALID_BUCKETS = {"reference-thumbs", "personal-photos", "logos", "outputs", "scripts"}
MAX_FILE_SIZES = {
    "reference-thumbs": 10 * 1024 * 1024,
    "personal-photos": 10 * 1024 * 1024,
    "logos": 5 * 1024 * 1024,
    "outputs": 10 * 1024 * 1024,
    "scripts": 5 * 1024 * 1024,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_assets.py -v`
Expected: All passed

- [ ] **Step 5: Lint and format**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/assets.py backend/tests/test_assets.py
git commit -m "feat: add scripts bucket to assets endpoints"
```

---

## Task 7: Backend Dependency — httpx

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Check if httpx is already a dependency**

Run: `cd backend && grep httpx pyproject.toml`

If httpx is already listed, skip this task. If not:

- [ ] **Step 2: Add httpx to dependencies**

Add `httpx>=0.27` to the `dependencies` list in `backend/pyproject.toml`.

- [ ] **Step 3: Install**

Run: `cd backend && pip install -e .` or `uv sync`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add httpx dependency for guardian client"
```

---

## Task 8: ThinkingBar Script Stages

**Files:**
- Modify: `frontend/src/components/ThinkingBar.tsx`

- [ ] **Step 1: Add script stage labels**

In `frontend/src/components/ThinkingBar.tsx`, update `STAGE_LABELS`:

```typescript
const STAGE_LABELS: Record<string, string> = {
  analyzing: "Analyzing your assets...",
  generating: "Generating thumbnail...",
  finding_trends: "Finding recent trends...",
  researching: "Researching topic in depth...",
  writing_outline: "Writing video outline...",
  writing_script: "Writing full script...",
  saving: "Saving script...",
};
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThinkingBar.tsx
git commit -m "feat: add script pipeline stage labels to ThinkingBar"
```

---

## Task 9: ApprovalButtons Variants

**Files:**
- Modify: `frontend/src/components/ApprovalButtons.tsx`

- [ ] **Step 1: Add approve/reject variant**

Replace `frontend/src/components/ApprovalButtons.tsx`:

```tsx
import { Box, Button } from "@mui/material";
import SaveIcon from "@mui/icons-material/Save";
import RefreshIcon from "@mui/icons-material/Refresh";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";

interface ApprovalButtonsProps {
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
  variant?: "thumbnail" | "script";
}

export default function ApprovalButtons({
  onApprove,
  onReject,
  disabled,
  variant = "thumbnail",
}: ApprovalButtonsProps) {
  if (variant === "script") {
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

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ApprovalButtons.tsx
git commit -m "feat: add approve/reject variant to ApprovalButtons"
```

---

## Task 10: ScriptTopicList Component

**Files:**
- Create: `frontend/src/components/ScriptTopicList.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ScriptTopicList.tsx`:

```tsx
import { Box, Card, CardActionArea, CardContent, Typography, Chip } from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";

interface Topic {
  title: string;
  angle: string;
  timeliness: string;
  interest: string;
}

interface ScriptTopicListProps {
  topics: Topic[];
  onSelect: (index: number) => void;
  disabled?: boolean;
}

const interestColors: Record<string, string> = {
  high: "#10b981",
  medium: "#f59e0b",
  low: "#6b7280",
};

export default function ScriptTopicList({
  topics,
  onSelect,
  disabled,
}: ScriptTopicListProps) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
        Select a topic to develop:
      </Typography>
      {topics.map((topic, index) => (
        <Card
          key={index}
          sx={{
            backgroundColor: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            "&:hover": {
              border: "1px solid rgba(124,58,237,0.4)",
              backgroundColor: "rgba(124,58,237,0.05)",
            },
          }}
        >
          <CardActionArea onClick={() => onSelect(index)} disabled={disabled}>
            <CardContent sx={{ py: 1.5, px: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                <TrendingUpIcon sx={{ fontSize: 16, color: "#7c3aed" }} />
                <Typography variant="subtitle2" sx={{ color: "rgba(255,255,255,0.95)" }}>
                  {topic.title}
                </Typography>
                <Chip
                  label={topic.interest}
                  size="small"
                  sx={{
                    ml: "auto",
                    height: 20,
                    fontSize: 11,
                    backgroundColor: `${interestColors[topic.interest] || "#6b7280"}22`,
                    color: interestColors[topic.interest] || "#6b7280",
                    border: `1px solid ${interestColors[topic.interest] || "#6b7280"}44`,
                  }}
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: 13 }}>
                {topic.angle}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: 12, mt: 0.5, display: "block" }}>
                {topic.timeliness}
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
    </Box>
  );
}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ScriptTopicList.tsx
git commit -m "feat: add ScriptTopicList component for topic selection"
```

---

## Task 11: ScriptViewer Component

**Files:**
- Create: `frontend/src/components/ScriptViewer.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ScriptViewer.tsx`:

```tsx
import { Box } from "@mui/material";
import ReactMarkdown from "react-markdown";

interface ScriptViewerProps {
  content: string;
}

export default function ScriptViewer({ content }: ScriptViewerProps) {
  return (
    <Box
      sx={{
        mt: 1,
        p: 2,
        borderRadius: 1.5,
        backgroundColor: "rgba(0,0,0,0.2)",
        border: "1px solid rgba(255,255,255,0.06)",
        maxHeight: 500,
        overflow: "auto",
        fontSize: 14,
        lineHeight: 1.7,
      }}
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </Box>
  );
}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ScriptViewer.tsx
git commit -m "feat: add ScriptViewer markdown renderer component"
```

---

## Task 12: MessageBubble Script Message Types

**Files:**
- Modify: `frontend/src/components/MessageBubble.tsx`

- [ ] **Step 1: Update MessageBubble to handle new types**

In `frontend/src/components/MessageBubble.tsx`, add imports at the top:

```tsx
import ScriptTopicList from "./ScriptTopicList";
import ScriptViewer from "./ScriptViewer";
```

Add `onTopicSelect` and `conversationMode` to the props interface:

```tsx
interface MessageBubbleProps {
  message: Message;
  onApprove?: () => void;
  onReject?: () => void;
  onTopicSelect?: (index: number) => void;
  isLatest?: boolean;
  isStreaming?: boolean;
  conversationMode?: string;
}
```

Update the component to destructure the new props and render new message types. After the existing image rendering block and before the markdown block, add:

```tsx
{message.type === "topics" && onTopicSelect && (() => {
  try {
    const topics = JSON.parse(message.content);
    return (
      <ScriptTopicList
        topics={topics}
        onSelect={onTopicSelect}
        disabled={!isLatest || isStreaming}
      />
    );
  } catch {
    return null;
  }
})()}

{(message.type === "outline" || message.type === "script") && (
  <ScriptViewer content={message.content} />
)}

{message.type === "research" && (
  <ScriptViewer content={message.content} />
)}
```

Update the approval buttons section to show the script variant:

```tsx
{showButtons && message.type === "image" && (
  <ApprovalButtons onApprove={onApprove!} onReject={onReject!} />
)}

{showButtons && (message.type === "outline" || message.type === "script") && (
  <ApprovalButtons
    onApprove={onApprove!}
    onReject={onReject!}
    variant="script"
  />
)}
```

For `topics`, `outline`, `script`, and `research` types, skip the default ReactMarkdown rendering. Wrap the existing markdown block:

```tsx
{message.type !== "topics" && message.type !== "outline" && message.type !== "script" && message.type !== "research" && (
  <Box sx={{ fontSize: 14, lineHeight: 1.6, ...markdownStyles }}>
    <ReactMarkdown>{message.content}</ReactMarkdown>
  </Box>
)}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MessageBubble.tsx
git commit -m "feat: render topics, outline, script, research message types in MessageBubble"
```

---

## Task 13: ChatArea — Pass New Props

**Files:**
- Modify: `frontend/src/components/ChatArea.tsx`

- [ ] **Step 1: Update ChatArea props and rendering**

Add to `ChatAreaProps`:

```tsx
interface ChatAreaProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  currentStage: string | null;
  onSend: (content: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onTopicSelect?: (index: number) => void;
  conversationMode?: string;
}
```

Update the destructured props to include `onTopicSelect` and `conversationMode`.

Update the empty state text based on mode:

```tsx
{isEmpty && (
  <Box sx={{ /* ...existing styles... */ }}>
    {/* ...existing icon... */}
    <Typography variant="h6" color="text.secondary">
      {conversationMode === "script"
        ? "Describe the video you want to create"
        : "Describe the thumbnail you want"}
    </Typography>
    <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400, textAlign: "center" }}>
      {conversationMode === "script"
        ? "Tell me about the topic or ask for trending suggestions. I'll help you create a full video script."
        : "Include the video title and any style preferences. The agent will analyze your references and create a plan."}
    </Typography>
  </Box>
)}
```

Pass `onTopicSelect` and `conversationMode` to each `MessageBubble`:

```tsx
<MessageBubble
  key={msg.id || i}
  message={msg}
  isLatest={i === messages.length - 1 && !isStreaming}
  isStreaming={false}
  onApprove={onApprove}
  onReject={onReject}
  onTopicSelect={onTopicSelect}
  conversationMode={conversationMode}
/>
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatArea.tsx
git commit -m "feat: pass topic selection and mode props through ChatArea"
```

---

## Task 14: API Client — Mode and Topics Support

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Update createConversation to accept mode**

In `frontend/src/lib/api.ts`, update `createConversation`:

```typescript
export const createConversation = (mode: string = "thumbnail") =>
  apiFetch<Record<string, unknown>>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
```

Add `onTopics` callback to `StreamCallbacks`:

```typescript
interface StreamCallbacks {
  onToken: (token: string) => void;
  onStage: (stage: string) => void;
  onImage: (base64: string, url: string) => void;
  onDone: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  onTopics?: (content: string) => void;
}
```

In the `streamChat` SSE parser, after the `data.image_base64` check, add:

```typescript
if (data.message_type === "topics" && data.content && callbacks.onTopics) {
  callbacks.onTopics(data.content as string);
}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add mode param to createConversation and onTopics callback"
```

---

## Task 15: ChatPage — Mode Selection and Script Handlers

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Add mode state and selection dialog**

Add imports:

```tsx
import { Dialog, DialogTitle, DialogContent, Button, Stack, Typography } from "@mui/material";
import DescriptionIcon from "@mui/icons-material/Description";
import ImageIcon from "@mui/icons-material/Image";
```

Add state:

```tsx
const [conversationMode, setConversationMode] = useState<string>("thumbnail");
const [showModeDialog, setShowModeDialog] = useState(false);
```

- [ ] **Step 2: Update conversation creation**

Replace `handleCreateConversation`:

```tsx
const handleCreateConversation = () => {
  setShowModeDialog(true);
};

const handleModeSelect = async (mode: string) => {
  setShowModeDialog(false);
  const conv = await createConversation(mode);
  const newConv = conv as unknown as Conversation;
  setConversations((prev) => [newConv, ...prev]);
  setSelectedId(newConv.id);
  setMessages([]);
  setConversationMode(mode);
};
```

Update `handleSelectConversation` to set mode:

```tsx
const handleSelectConversation = async (id: string) => {
  setSelectedId(id);
  const data = await getConversation(id);
  const convData = data as { messages: Message[]; mode?: string };
  setMessages(convData.messages || []);
  setConversationMode(convData.mode || "thumbnail");
};
```

- [ ] **Step 3: Add script-specific handlers**

```tsx
const handleTopicSelect = (index: number) => {
  if (!selectedId) return;
  doStream(selectedId, String(index), "topic_selection");
};

const handleApprove = () => {
  if (!selectedId) return;
  const lastMsg = messages[messages.length - 1];
  if (lastMsg?.type === "image") {
    sendMessage("SAVE_OUTPUT", "save");
  } else if (lastMsg?.type === "outline") {
    doStream(selectedId, "", "approve_outline");
  } else if (lastMsg?.type === "script") {
    doStream(selectedId, "", "approve_script");
  }
};

const handleReject = () => {
  if (!selectedId) return;
  const lastMsg = messages[messages.length - 1];
  if (lastMsg?.type === "image") {
    sendMessage("REGENERATE", "regenerate");
  } else if (lastMsg?.type === "outline") {
    // TODO: could prompt for feedback via ChatInput, for now send empty
    doStream(selectedId, "", "reject_outline");
  } else if (lastMsg?.type === "script") {
    doStream(selectedId, "", "reject_script");
  }
};
```

- [ ] **Step 4: Update doStream onDone to handle script message types**

In the `onDone` callback inside `doStream`, update to handle content from SSE:

```tsx
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
    newMessage.content = (data.content as string) || "Saved!";
    newMessage.type = "text";
  }
  setMessages((prev) => [...prev, newMessage]);
  setStreamingContent("");
  setIsStreaming(false);
  setCurrentStage(null);
  loadConversations();
},
```

- [ ] **Step 5: Pass new props to ChatArea**

```tsx
<ChatArea
  messages={messages}
  streamingContent={streamingContent}
  isStreaming={isStreaming}
  currentStage={currentStage}
  onSend={handleSend}
  onApprove={handleApprove}
  onReject={handleReject}
  onTopicSelect={handleTopicSelect}
  conversationMode={conversationMode}
/>
```

- [ ] **Step 6: Add mode selection dialog**

At the end of the return, before the closing `</Box>`:

```tsx
<Dialog
  open={showModeDialog}
  onClose={() => setShowModeDialog(false)}
  PaperProps={{
    sx: {
      backgroundColor: "rgba(30,30,40,0.95)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(255,255,255,0.1)",
      borderRadius: 3,
    },
  }}
>
  <DialogTitle>New Conversation</DialogTitle>
  <DialogContent>
    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
      What would you like to create?
    </Typography>
    <Stack spacing={1.5}>
      <Button
        variant="outlined"
        startIcon={<ImageIcon />}
        onClick={() => handleModeSelect("thumbnail")}
        sx={{
          justifyContent: "flex-start",
          borderColor: "rgba(255,255,255,0.15)",
          color: "text.primary",
          py: 1.5,
          "&:hover": { borderColor: "#7c3aed", backgroundColor: "rgba(124,58,237,0.08)" },
        }}
      >
        Thumbnail
      </Button>
      <Button
        variant="outlined"
        startIcon={<DescriptionIcon />}
        onClick={() => handleModeSelect("script")}
        sx={{
          justifyContent: "flex-start",
          borderColor: "rgba(255,255,255,0.15)",
          color: "text.primary",
          py: 1.5,
          "&:hover": { borderColor: "#7c3aed", backgroundColor: "rgba(124,58,237,0.08)" },
        }}
      >
        Video Script
      </Button>
    </Stack>
  </DialogContent>
</Dialog>
```

- [ ] **Step 7: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 8: Lint and format**

Run: `cd frontend && npx eslint --fix src/pages/ChatPage.tsx && npx prettier --write src/pages/ChatPage.tsx`

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "feat: add mode selection dialog and script pipeline handlers to ChatPage"
```

---

## Task 16: ContextPanel Mode Indicator

**Files:**
- Modify: `frontend/src/components/ContextPanel.tsx`

- [ ] **Step 1: Add mode indicator**

Add imports:

```tsx
import DescriptionIcon from "@mui/icons-material/Description";
import ImageIcon from "@mui/icons-material/Image";
```

Update the `Conversation` interface to include `mode`:

```tsx
interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
  mode?: string;
}
```

In the `ListItemText` area, add a mode icon before the text:

```tsx
<Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flex: 1, minWidth: 0 }}>
  {conv.mode === "script" ? (
    <DescriptionIcon sx={{ fontSize: 14, color: "rgba(255,255,255,0.3)", flexShrink: 0 }} />
  ) : (
    <ImageIcon sx={{ fontSize: 14, color: "rgba(255,255,255,0.3)", flexShrink: 0 }} />
  )}
  <ListItemText
    primary={conv.title || "New conversation"}
    primaryTypographyProps={{
      noWrap: true,
      fontSize: 13,
      color: "text.primary",
    }}
  />
</Box>
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ContextPanel.tsx
git commit -m "feat: add mode icon indicator to conversation list"
```

---

## Task 17: AssetsPage Scripts Tab

**Files:**
- Modify: `frontend/src/pages/AssetsPage.tsx`

- [ ] **Step 1: Add scripts bucket to BUCKETS array**

In `frontend/src/pages/AssetsPage.tsx`, update `BUCKETS`:

```typescript
const BUCKETS = [
  { key: "reference-thumbs", label: "Reference Thumbnails", accept: "image/*" },
  { key: "personal-photos", label: "Personal Photos", accept: "image/*" },
  { key: "logos", label: "Logos", accept: "image/*" },
  { key: "outputs", label: "Generated Outputs", accept: "image/*" },
  { key: "scripts", label: "Scripts", accept: ".md" },
];
```

The existing `AssetGrid` renders images, but scripts are `.md` files. Update the upload condition to also hide upload for scripts (they're created by the pipeline):

```tsx
{currentBucket.key !== "outputs" && currentBucket.key !== "scripts" && (
  <Box sx={{ mb: 3 }}>
    <AssetUpload
      onUpload={handleUpload}
      accept={currentBucket.accept}
      fileStatuses={fileStatuses}
    />
  </Box>
)}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AssetsPage.tsx
git commit -m "feat: add Scripts tab to AssetsPage"
```

---

## Task 18: Database Migration — Add mode column

**Files:**
- Create: `backend/migrations/001_add_conversation_mode.sql`

- [ ] **Step 1: Create migration file**

Create `backend/migrations/001_add_conversation_mode.sql`:

```sql
-- Add mode column to conversations table
-- Values: 'thumbnail' (default, backward compatible) or 'script'
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'thumbnail';
```

- [ ] **Step 2: Document in commit message that this must be run manually**

```bash
mkdir -p backend/migrations
git add backend/migrations/001_add_conversation_mode.sql
git commit -m "chore: add SQL migration for conversation mode column

Run manually against Supabase: backend/migrations/001_add_conversation_mode.sql"
```

---

## Task 19: Full Backend Test Suite

**Files:**
- All test files

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter on full backend**

Run: `cd backend && ruff check --fix && ruff format`

- [ ] **Step 3: Commit if any formatting changes**

```bash
git add -u backend/
git commit -m "chore: lint and format backend"
```

---

## Task 20: Full Frontend Build

**Files:**
- All frontend files

- [ ] **Step 1: Run full build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Run linter**

Run: `cd frontend && npx eslint --fix src/ && npx prettier --write src/`

- [ ] **Step 3: Commit if any formatting changes**

```bash
git add -u frontend/
git commit -m "chore: lint and format frontend"
```
