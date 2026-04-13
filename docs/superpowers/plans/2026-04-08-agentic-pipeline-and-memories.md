# Agentic Script Pipeline + Configurable LLM + User Memories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid script pipeline with an agentic LLM-driven flow, add a configurable LLM backend (Anthropic API or Guardian fallback), and build a memory system that learns user preferences.

**Architecture:** New `llm.py` abstraction handles Anthropic SDK or Guardian fallback. Script pipeline becomes a single handler that sends full conversation history to LLM with system prompt; LLM returns JSON actions (`topics`, `script`, `save`, `message`). Memory extractor runs async after script saves/rejections. Frontend simplifies script interactions to plain text messages.

**Tech Stack:** Python/FastAPI, Anthropic SDK, Supabase, React 18, MUI 6

---

### Task 1: Config — Add Anthropic Settings

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: Add new optional fields to Settings**

In `backend/config.py`, add after line 9 (`guardian_api_key`):

```python
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
```

- [ ] **Step 2: Verify tests still pass**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: All pass (new fields have defaults).

- [ ] **Step 3: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/config.py
git commit -m "feat: add anthropic_api_key and anthropic_model to config"
```

---

### Task 2: LLM Abstraction — `backend/services/llm.py`

**Files:**
- Create: `backend/services/llm.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_llm.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_ask_llm_uses_anthropic_when_key_set():
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = "sk-test"
    mock_settings.anthropic_model = "claude-sonnet-4-20250514"
    mock_settings.guardian_url = "http://localhost:3000"
    mock_settings.guardian_api_key = ""

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="LLM response")]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    with patch("services.llm.settings", mock_settings), patch(
        "services.llm.AsyncAnthropic", return_value=mock_client
    ):
        from services.llm import ask_llm

        result = await ask_llm(
            system="You are helpful",
            messages=[{"role": "user", "content": "Hello"}],
        )

    assert result == "LLM response"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["system"] == "You are helpful"
    assert call_kwargs["messages"] == [{"role": "user", "content": "Hello"}]


@pytest.mark.asyncio
async def test_ask_llm_falls_back_to_guardian_when_no_key():
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = ""
    mock_settings.guardian_url = "http://localhost:3000"
    mock_settings.guardian_api_key = "gkey"

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Guardian response"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.llm.settings", mock_settings), patch(
        "services.llm.httpx.AsyncClient", return_value=mock_client
    ):
        from services.llm import ask_llm

        result = await ask_llm(
            system="You are helpful",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "How are you?"},
            ],
        )

    assert result == "Guardian response"
    # Verify the prompt was flattened correctly
    call_args = mock_client.post.call_args
    prompt = call_args[1]["json"]["prompt"]
    assert "You are helpful" in prompt
    assert "Hello" in prompt
    assert "How are you?" in prompt


@pytest.mark.asyncio
async def test_ask_llm_guardian_includes_auth_header():
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = ""
    mock_settings.guardian_url = "http://localhost:3000"
    mock_settings.guardian_api_key = "secret-key"

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.llm.settings", mock_settings), patch(
        "services.llm.httpx.AsyncClient", return_value=mock_client
    ):
        from services.llm import ask_llm

        await ask_llm(system="sys", messages=[{"role": "user", "content": "hi"}])

    call_args = mock_client.post.call_args
    assert call_args[1]["headers"]["Authorization"] == "Bearer secret-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_llm.py -v`
Expected: FAIL — `services.llm` does not exist.

- [ ] **Step 3: Install anthropic SDK**

Run: `cd backend && uv add anthropic`

- [ ] **Step 4: Create `backend/services/llm.py`**

```python
import logging
from typing import AsyncGenerator

import httpx
from anthropic import AsyncAnthropic

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 600.0


async def ask_llm(system: str, messages: list[dict]) -> str:
    if settings.anthropic_api_key:
        return await _ask_anthropic(system, messages)
    return await _ask_guardian(system, messages)


async def stream_llm(
    system: str, messages: list[dict]
) -> AsyncGenerator[str, None]:
    if settings.anthropic_api_key:
        async for token in _stream_anthropic(system, messages):
            yield token
    else:
        result = await _ask_guardian(system, messages)
        yield result


async def _ask_anthropic(system: str, messages: list[dict]) -> str:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=16384,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def _stream_anthropic(
    system: str, messages: list[dict]
) -> AsyncGenerator[str, None]:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=16384,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _ask_guardian(system: str, messages: list[dict]) -> str:
    prompt_parts = [f"System: {system}\n"]
    for msg in messages:
        role = msg["role"].capitalize()
        prompt_parts.append(f"{role}: {msg['content']}\n")
    full_prompt = "\n".join(prompt_parts).strip()

    logger.info("ask_guardian prompt=%s", full_prompt[:120])
    headers = {}
    if settings.guardian_api_key:
        headers["Authorization"] = f"Bearer {settings.guardian_api_key}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{settings.guardian_url}/api/ask",
            json={"prompt": full_prompt},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
    answer = data.get("response", "")
    logger.info("llm responded via guardian, length=%d", len(answer))
    return answer
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_llm.py -v`
Expected: All 3 pass.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/services/llm.py backend/tests/test_llm.py pyproject.toml uv.lock
git commit -m "feat: add LLM abstraction with Anthropic SDK and Guardian fallback"
```

---

### Task 3: Database — `user_memories` Table

**Files:**
- Modify: `backend/db/schema.sql`

- [ ] **Step 1: Append user_memories table to schema.sql**

Append after the `channel_personas` RLS block at the end of `backend/db/schema.sql`:

```sql
-- user_memories
CREATE TABLE user_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    source_action   TEXT NOT NULL CHECK (source_action IN ('approved', 'rejected')),
    source_feedback TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_memories_user_id ON user_memories(user_id);

ALTER TABLE user_memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_memories_select ON user_memories
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_memories_delete ON user_memories
    FOR DELETE USING (auth.uid() = user_id);
```

- [ ] **Step 2: Run SQL in Supabase dashboard**

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.sql
git commit -m "feat: add user_memories table with RLS"
```

---

### Task 4: Memory Extractor — `backend/services/memory_extractor.py`

**Files:**
- Create: `backend/services/memory_extractor.py`
- Create: `backend/tests/test_memory_extractor.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_memory_extractor.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_extract_memory_inserts_new():
    mock_sb = MagicMock()

    # No existing memories
    memories_result = MagicMock()
    memories_result.data = []
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=memories_result
    )
    mock_sb.table.return_value.insert.return_value.execute = AsyncMock()

    with patch(
        "services.memory_extractor.ask_llm",
        new_callable=AsyncMock,
        return_value="Prefers scripts under 10 minutes",
    ):
        from services.memory_extractor import extract_memory

        await extract_memory(
            sb=mock_sb,
            user_id="user-1",
            action="rejected",
            topic="AI trends",
            feedback="Too long, make it shorter",
        )

    mock_sb.table.return_value.insert.assert_called_once()
    insert_data = mock_sb.table.return_value.insert.call_args[0][0]
    assert insert_data["content"] == "Prefers scripts under 10 minutes"
    assert insert_data["source_action"] == "rejected"
    assert insert_data["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_extract_memory_skips_when_redundant():
    mock_sb = MagicMock()

    memories_result = MagicMock()
    memories_result.data = [
        {"id": "mem-1", "content": "Prefers short scripts"}
    ]
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=memories_result
    )

    with patch(
        "services.memory_extractor.ask_llm",
        new_callable=AsyncMock,
        return_value="SKIP",
    ):
        from services.memory_extractor import extract_memory

        await extract_memory(
            sb=mock_sb,
            user_id="user-1",
            action="rejected",
            topic="AI",
            feedback="Too long",
        )

    mock_sb.table.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_extract_memory_replaces_existing():
    mock_sb = MagicMock()

    memories_result = MagicMock()
    memories_result.data = [
        {"id": "mem-1", "content": "Prefers 15 min scripts"}
    ]
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=memories_result
    )
    mock_sb.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock()
    mock_sb.table.return_value.insert.return_value.execute = AsyncMock()

    with patch(
        "services.memory_extractor.ask_llm",
        new_callable=AsyncMock,
        return_value="REPLACE:mem-1 Prefers scripts under 10 minutes",
    ):
        from services.memory_extractor import extract_memory

        await extract_memory(
            sb=mock_sb,
            user_id="user-1",
            action="rejected",
            topic="AI",
            feedback="Make it 10 min max",
        )

    # Should delete old and insert new
    mock_sb.table.return_value.delete.return_value.eq.assert_called()
    mock_sb.table.return_value.insert.assert_called_once()
    insert_data = mock_sb.table.return_value.insert.call_args[0][0]
    assert insert_data["content"] == "Prefers scripts under 10 minutes"


@pytest.mark.asyncio
async def test_extract_memory_evicts_oldest_at_cap():
    mock_sb = MagicMock()

    # 20 existing memories
    memories_result = MagicMock()
    memories_result.data = [
        {"id": f"mem-{i}", "content": f"Pref {i}"} for i in range(20)
    ]
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=memories_result
    )
    mock_sb.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock()
    mock_sb.table.return_value.insert.return_value.execute = AsyncMock()

    with patch(
        "services.memory_extractor.ask_llm",
        new_callable=AsyncMock,
        return_value="New preference",
    ):
        from services.memory_extractor import extract_memory

        await extract_memory(
            sb=mock_sb,
            user_id="user-1",
            action="approved",
            topic="AI",
            feedback="",
        )

    # Should delete oldest (last in the list since ordered desc)
    mock_sb.table.return_value.delete.return_value.eq.assert_called()
    mock_sb.table.return_value.insert.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_memory_extractor.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `backend/services/memory_extractor.py`**

```python
import logging
import re

from services.llm import ask_llm

logger = logging.getLogger(__name__)

MAX_MEMORIES = 20

EXTRACTION_PROMPT = """You are analyzing a user's interaction with a YouTube script to extract preferences.

Action: {action}
Topic: {topic}
Feedback: {feedback}

Existing memories:
{memories}

Rules:
- Extract ONE concise, actionable preference from this interaction
- If it contradicts an existing memory, return REPLACE:<id> followed by the new text
- If it's redundant with an existing memory, return SKIP
- Keep preferences actionable (e.g. "Prefers scripts under 10 minutes" not "User said too long")

Return ONLY: the preference text, or REPLACE:<id> <new text>, or SKIP"""


async def extract_memory(
    sb,
    user_id: str,
    action: str,
    topic: str,
    feedback: str,
) -> None:
    try:
        result = (
            await sb.table("user_memories")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        existing = result.data or []

        if existing:
            memories_text = "\n".join(
                f"- [{m['id']}] {m['content']}" for m in existing
            )
        else:
            memories_text = "none yet"

        prompt = EXTRACTION_PROMPT.format(
            action=action,
            topic=topic,
            feedback=feedback or "none — user approved without changes",
            memories=memories_text,
        )

        response = await ask_llm(
            system="You extract user preferences from script feedback.",
            messages=[{"role": "user", "content": prompt}],
        )
        response = response.strip()

        if response == "SKIP":
            logger.info("memory extraction: SKIP for user=%s", user_id)
            return

        replace_match = re.match(r"REPLACE:(\S+)\s+(.*)", response, re.DOTALL)
        if replace_match:
            old_id = replace_match.group(1)
            new_content = replace_match.group(2).strip()
            await (
                sb.table("user_memories")
                .delete()
                .eq("id", old_id)
                .execute()
            )
            await (
                sb.table("user_memories")
                .insert(
                    {
                        "user_id": user_id,
                        "content": new_content,
                        "source_action": action,
                        "source_feedback": feedback or "",
                    }
                )
                .execute()
            )
            logger.info(
                "memory extraction: REPLACE %s for user=%s", old_id, user_id
            )
            return

        # New memory
        if len(existing) >= MAX_MEMORIES:
            oldest = existing[-1]
            await (
                sb.table("user_memories")
                .delete()
                .eq("id", oldest["id"])
                .execute()
            )
            logger.info(
                "memory extraction: evicted oldest %s for user=%s",
                oldest["id"],
                user_id,
            )

        await (
            sb.table("user_memories")
            .insert(
                {
                    "user_id": user_id,
                    "content": response,
                    "source_action": action,
                    "source_feedback": feedback or "",
                }
            )
            .execute()
        )
        logger.info("memory extraction: new memory for user=%s", user_id)

    except Exception:
        logger.exception("memory extraction failed for user=%s", user_id)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_memory_extractor.py -v`
Expected: All 4 pass.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/services/memory_extractor.py backend/tests/test_memory_extractor.py
git commit -m "feat: add memory extractor with LLM-based preference extraction"
```

---

### Task 5: Memories API Route

**Files:**
- Create: `backend/routes/memories.py`
- Create: `backend/tests/test_memories_route.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_memories_route.py`:

```python
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.memories import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase():
    return MagicMock()


def test_list_memories_returns_data():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "m1", "content": "Prefers short scripts", "source_action": "rejected"}
    ]

    with patch("routes.memories.get_supabase", return_value=mock_sb):
        response = client.get("/api/memories")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["content"] == "Prefers short scripts"


def test_list_memories_empty():
    client = create_app("test-user-id")

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    with patch("routes.memories.get_supabase", return_value=mock_sb):
        response = client.get("/api/memories")

    assert response.status_code == 200
    assert response.json() == []


def test_delete_memory_returns_204():
    client = create_app("test-user-id")

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "m1"}
    ]

    with patch("routes.memories.get_supabase", return_value=mock_sb):
        response = client.delete("/api/memories/m1")

    assert response.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_memories_route.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `backend/routes/memories.py`**

```python
from fastapi import APIRouter, Depends, Response
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


@router.get("/api/memories")
async def list_memories(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("user_memories")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/api/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str, user_id: str = Depends(get_current_user)
):
    sb = get_supabase()
    sb.table("user_memories").delete().eq("id", memory_id).eq(
        "user_id", user_id
    ).execute()
    return Response(status_code=204)
```

- [ ] **Step 4: Register in main.py**

In `backend/main.py`, add import after line 9:

```python
from routes.memories import router as memories_router
```

Add after the last `include_router` line:

```python
app.include_router(memories_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_memories_route.py -v`
Expected: All 3 pass.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add backend/routes/memories.py backend/tests/test_memories_route.py backend/main.py
git commit -m "feat: add memories API route with list and delete endpoints"
```

---

### Task 6: Rewrite Script Pipeline — Agentic Handler

**Files:**
- Rewrite: `backend/services/script_pipeline.py`
- Rewrite: `backend/tests/test_script_pipeline.py`

This is the core task. The entire script pipeline is rewritten from a rigid state machine to a single agentic handler.

- [ ] **Step 1: Write new tests**

Replace `backend/tests/test_script_pipeline.py` entirely:

```python
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.script_pipeline import handle_script_chat_message


def make_async_sb(**overrides):
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

    persona_data = overrides.get(
        "persona_data",
        {
            "channel_name": "Test Channel",
            "language": "English",
            "persona_text": "Casual and direct",
        },
    )
    persona_result = MagicMock()
    persona_result.data = persona_data
    chain.select.return_value.eq.return_value.maybe_single.return_value.execute = (
        AsyncMock(return_value=persona_result)
    )

    storage = sb.storage.from_.return_value
    storage.upload = AsyncMock(return_value={})

    return sb


async def collect_events(conversation_id, content, user_id, sb):
    events = []
    mock_get_sb = AsyncMock(return_value=sb)
    with patch("services.script_pipeline.get_supabase", mock_get_sb):
        async for event in handle_script_chat_message(
            conversation_id=conversation_id,
            content=content,
            user_id=user_id,
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))
    return events


@pytest.mark.asyncio
async def test_topics_action_returns_topics_event():
    sb = make_async_sb()
    llm_response = json.dumps({
        "action": "topics",
        "data": [{"title": "AI News", "angle": "test"}],
    })

    with patch(
        "services.script_pipeline.ask_llm",
        new_callable=AsyncMock,
        return_value=llm_response,
    ):
        events = await collect_events("conv-1", "Video ideas about AI", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("message_type") == "topics"


@pytest.mark.asyncio
async def test_script_action_returns_script_event():
    sb = make_async_sb()
    llm_response = json.dumps({
        "action": "script",
        "content": "# Full Script\n\nContent here",
    })

    with patch(
        "services.script_pipeline.ask_llm",
        new_callable=AsyncMock,
        return_value=llm_response,
    ):
        events = await collect_events("conv-1", "Write about AI", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("message_type") == "script"


@pytest.mark.asyncio
async def test_save_action_uploads_to_storage():
    sb = make_async_sb()

    # Existing messages include a script
    messages_data = MagicMock()
    messages_data.data = [
        {"role": "assistant", "content": "# My Script", "type": "script"},
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    llm_response = json.dumps({"action": "save", "message": "Script saved!"})

    with patch(
        "services.script_pipeline.ask_llm",
        new_callable=AsyncMock,
        return_value=llm_response,
    ), patch(
        "services.script_pipeline.extract_memory",
        new_callable=AsyncMock,
    ):
        events = await collect_events("conv-1", "Save it", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("saved") is True
    sb.storage.from_.assert_called_with("scripts")


@pytest.mark.asyncio
async def test_message_action_returns_text_event():
    sb = make_async_sb()
    llm_response = json.dumps({
        "action": "message",
        "content": "Could you clarify what angle you want?",
    })

    with patch(
        "services.script_pipeline.ask_llm",
        new_callable=AsyncMock,
        return_value=llm_response,
    ):
        events = await collect_events("conv-1", "Make a video", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("message_type") == "text"
    assert "clarify" in done[0].get("content", "").lower()


@pytest.mark.asyncio
async def test_no_persona_returns_error():
    sb = make_async_sb(persona_data=None)

    events = await collect_events("conv-1", "ideas", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert "error" in done[0]
    assert "persona" in done[0]["error"].lower()


@pytest.mark.asyncio
async def test_sets_conversation_title_on_first_message():
    sb = make_async_sb()

    # No existing messages
    messages_data = MagicMock()
    messages_data.data = []
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    llm_response = json.dumps({"action": "message", "content": "ok"})

    with patch(
        "services.script_pipeline.ask_llm",
        new_callable=AsyncMock,
        return_value=llm_response,
    ):
        await collect_events("conv-1", "AI video ideas", "test-user", sb)

    sb.table.return_value.update.assert_called()
```

- [ ] **Step 2: Rewrite `backend/services/script_pipeline.py`**

Replace the entire file:

```python
import asyncio
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from services.llm import ask_llm
from services.memory_extractor import extract_memory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a YouTube content strategist and scriptwriter.

## Channel Persona: {channel_name}

**Language:** {language}

{persona_text}

{memories_section}

You help the user create YouTube video scripts through natural conversation. Based on the conversation context, decide what action to take.

You MUST respond with ONLY a valid JSON object (no markdown fences, no extra text). Use one of these actions:

1. Suggest topics — when the user describes a video idea or asks for topic suggestions:
{{"action": "topics", "data": [{{"title": "...", "angle": "...", "why_timely": "...", "source_url": "...", "interest": "high|medium|low"}}, ...], "message": "optional conversational text"}}

2. Write/rewrite a script — when the user picks a topic, asks you to write, or gives feedback on an existing script:
{{"action": "script", "content": "...full markdown script...", "message": "optional conversational text"}}

3. Save the script — when the user explicitly approves or says to save:
{{"action": "save", "message": "optional conversational text"}}

4. Conversational reply — when you need to ask for clarification, acknowledge something, or chat:
{{"action": "message", "content": "your reply"}}

Guidelines:
- ALWAYS search the web for current information before suggesting topics or writing scripts
- When suggesting topics, research current news and trends from the last 1-2 weeks
- When writing scripts, include real statistics with verifiable source URLs
- Write all script content in {language}
- When the user gives feedback on a script (e.g. "too long", "more humor"), rewrite incorporating feedback — do NOT restart from topic suggestions
- When the user says "save", "looks good", "approved", "perfect" about a script, use the "save" action
- When unclear, ask for clarification using the "message" action
- After a script is saved, if the user brings up a new topic, start fresh topic suggestions
- Suggest 5-10 topics when using the "topics" action, each with title, angle, why_timely, source_url, and interest level"""


async def get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60]


async def _save_message(
    sb, conversation_id: str, role: str, content: str, msg_type: str
):
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


async def _get_user_persona(sb, user_id: str) -> dict | None:
    result = (
        await sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


async def _get_user_memories(sb, user_id: str) -> list[dict]:
    result = (
        await sb.table("user_memories")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def _build_system_prompt(persona: dict, memories: list[dict]) -> str:
    if memories:
        memories_text = "## Your Learned Preferences\n\n" + "\n".join(
            f"- {m['content']}" for m in memories
        )
    else:
        memories_text = ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        channel_name=persona["channel_name"],
        language=persona["language"],
        persona_text=persona["persona_text"],
        memories_section=memories_text,
    )


def _messages_to_chat(messages: list[dict]) -> list[dict]:
    chat = []
    for msg in messages:
        role = msg["role"]
        if role not in ("user", "assistant"):
            continue
        content = msg["content"]
        # For topics stored as JSON, wrap in context
        if msg.get("type") == "topics" and role == "assistant":
            content = json.dumps({"action": "topics", "data": json.loads(content)})
        chat.append({"role": role, "content": content})
    return chat


def _parse_action(response_text: str) -> dict:
    # Try to extract JSON from the response
    text = response_text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: treat entire response as a message
    return {"action": "message", "content": response_text}


async def handle_script_chat_message(
    conversation_id: str,
    content: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_chat conversation=%s user=%s",
        conversation_id,
        user_id,
    )
    try:
        sb = await get_supabase()

        # Fetch persona (hard gate)
        persona = await _get_user_persona(sb, user_id)
        if not persona:
            yield sse_event(
                {
                    "error": "Please set up your channel persona in Settings before generating scripts.",
                    "done": True,
                }
            )
            return

        # Fetch memories
        memories = await _get_user_memories(sb, user_id)

        # Get existing messages
        existing_messages = await _get_messages(sb, conversation_id)

        # Set title on first message
        if not existing_messages:
            await (
                sb.table("conversations")
                .update({"title": content[:50]})
                .eq("id", conversation_id)
                .execute()
            )

        # Save user message
        await _save_message(sb, conversation_id, "user", content, "text")

        yield sse_event({"stage": "thinking"})

        # Build LLM request
        system = _build_system_prompt(persona, memories)
        chat_messages = _messages_to_chat(existing_messages)
        chat_messages.append({"role": "user", "content": content})

        # Call LLM
        response_text = await ask_llm(system, chat_messages)
        action = _parse_action(response_text)
        action_type = action.get("action", "message")

        if action_type == "topics":
            topics_data = action.get("data", [])
            topics_json = json.dumps(topics_data)
            await _save_message(
                sb, conversation_id, "assistant", topics_json, "topics"
            )
            yield sse_event(
                {"done": True, "message_type": "topics", "content": topics_json}
            )

        elif action_type == "script":
            script_content = action.get("content", "")
            await _save_message(
                sb, conversation_id, "assistant", script_content, "script"
            )
            yield sse_event(
                {"done": True, "message_type": "script", "content": script_content}
            )

        elif action_type == "save":
            # Find the last script to save
            all_messages = await _get_messages(sb, conversation_id)
            script_msg = next(
                (m for m in reversed(all_messages) if m["type"] == "script"),
                None,
            )
            script_content = script_msg["content"] if script_msg else ""

            slug = slugify(content) if content.strip() else "script"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = f"{user_id}/{slug}-{timestamp}.md"

            await sb.storage.from_("scripts").upload(
                path,
                script_content.encode("utf-8"),
                {"content-type": "text/markdown"},
            )

            save_message = action.get("message", f"Script saved to {path}")
            await _save_message(
                sb, conversation_id, "assistant", save_message, "saved"
            )

            yield sse_event({"done": True, "saved": True, "path": path})

            # Trigger memory extraction (fire and forget)
            asyncio.create_task(
                extract_memory(
                    sb=sb,
                    user_id=user_id,
                    action="approved",
                    topic=slug,
                    feedback="",
                )
            )

        elif action_type == "message":
            msg_content = action.get("content", "")
            await _save_message(
                sb, conversation_id, "assistant", msg_content, "text"
            )
            yield sse_event(
                {"done": True, "message_type": "text", "content": msg_content}
            )

        else:
            # Unknown action, treat as message
            await _save_message(
                sb, conversation_id, "assistant", response_text, "text"
            )
            yield sse_event(
                {"done": True, "message_type": "text", "content": response_text}
            )

    except Exception as e:
        logger.exception("error in script pipeline: %s", e)
        yield sse_event({"error": str(e), "done": True})
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_script_pipeline.py -v`
Expected: All 6 pass.

- [ ] **Step 4: Run full test suite**

Run: `cd backend && uv run pytest -v`
Expected: Some old tests that reference `ask_guardian` may fail in `test_chat.py`. Fix any import issues.

- [ ] **Step 5: Update chat route**

In `backend/routes/chat.py`, the `handle_script_chat_message` signature changed — it no longer takes `msg_type`. Update line 38-43:

```python
    if mode == "script":
        stream = handle_script_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            user_id=user_id,
        )
```

- [ ] **Step 6: Delete old files**

```bash
rm backend/services/guardian.py backend/tests/test_guardian.py
```

- [ ] **Step 7: Fix any remaining test imports**

Check if any other test files import `ask_guardian` and update them. Run: `cd backend && uv run pytest -v`

- [ ] **Step 8: Lint and commit**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
git add -A
git commit -m "feat: rewrite script pipeline to agentic single-handler with LLM abstraction"
```

---

### Task 7: Frontend — Simplify Script Chat Flow

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add memory API functions to `frontend/src/lib/api.ts`**

Append to the end of the file:

```typescript
export interface Memory {
  id: string;
  user_id: string;
  content: string;
  source_action: string;
  source_feedback: string;
  created_at: string;
}

export const listMemories = () =>
  apiFetch<Memory[]>("/api/memories");

export const deleteMemory = (id: string) =>
  apiFetch<void>(`/api/memories/${id}`, { method: "DELETE" });
```

- [ ] **Step 2: Update ChatPage.tsx — simplify script message handling**

In `frontend/src/pages/ChatPage.tsx`, update the topic select handler (line 279-281) to send text instead of numeric index:

```typescript
  const handleTopicSelect = (index: number) => {
    if (!selectedId) return;
    // Find the topic title from messages and send as natural text
    const topicsMsg = messages.find((m) => m.type === "topics");
    if (topicsMsg) {
      try {
        const topics = JSON.parse(topicsMsg.content);
        const topic = topics[index];
        const title = topic?.title || `Topic ${index + 1}`;
        sendMessage(`I want to make a video about: ${title}`);
      } catch {
        sendMessage(`I choose topic ${index + 1}`);
      }
    } else {
      sendMessage(`I choose topic ${index + 1}`);
    }
  };
```

Update the approve handler (line 284-291):

```typescript
  const handleApprove = () => {
    if (!selectedId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "image") {
      sendMessage("SAVE_OUTPUT", "save");
    } else if (lastMsg?.type === "script") {
      sendMessage("Save this script");
    }
  };
```

Update the reject handler (line 294-301):

```typescript
  const handleReject = () => {
    if (!selectedId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "image") {
      sendMessage("REGENERATE", "regenerate");
    } else if (lastMsg?.type === "script") {
      sendMessage("Please rewrite this script with improvements");
    }
  };
```

Simplify `detectPendingStage` for script mode (lines 67-75):

```typescript
    if (mode === "script") {
      if (lastMsg.type === "text") return "thinking";
    } else {
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 4: Lint and commit**

```bash
cd frontend && npx prettier --write src/pages/ChatPage.tsx src/lib/api.ts
git add frontend/src/pages/ChatPage.tsx frontend/src/lib/api.ts
git commit -m "feat: simplify script chat to use natural text messages"
```

---

### Task 8: Frontend — Memories Section on Settings Page

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Update SettingsPage to include memories**

In `frontend/src/pages/SettingsPage.tsx`, update the imports (line 12):

```typescript
import {
  getPersona,
  upsertPersona,
  listMemories,
  deleteMemory,
} from "../lib/api";
import type { Memory } from "../lib/api";
```

Add state for memories after the existing state declarations (after line 24):

```typescript
  const [memories, setMemories] = useState<Memory[]>([]);
```

Update the `useEffect` to also fetch memories (replace lines 26-43):

```typescript
  useEffect(() => {
    Promise.all([
      getPersona().catch(() => null),
      listMemories().catch(() => []),
    ])
      .then(([persona, mems]) => {
        if (persona) {
          setChannelName(persona.channel_name);
          setLanguage(persona.language);
          setPersonaText(persona.persona_text);
        }
        setMemories(mems);
      })
      .catch(() => {
        setSnackbar({
          open: true,
          message: "Failed to load settings",
          severity: "error",
        });
      })
      .finally(() => setLoading(false));
  }, []);
```

Add a delete handler after `handleSave`:

```typescript
  const handleDeleteMemory = async (id: string) => {
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to delete memory",
        severity: "error",
      });
    }
  };
```

Add the memories section after the closing `</Paper>` tag (before `<Snackbar>`). Add these imports at the top: `IconButton, List, ListItem, ListItemText, Divider` from `@mui/material` and `DeleteIcon` from `@mui/icons-material/Delete`.

```tsx
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
          Learned Preferences
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
          Automatically extracted from your script feedback. These help the AI
          match your style over time.
        </Typography>

        {memories.length === 0 ? (
          <Typography
            variant="body2"
            sx={{ color: "rgba(255,255,255,0.3)", py: 2 }}
          >
            No preferences learned yet. They'll appear here as you approve and
            reject scripts.
          </Typography>
        ) : (
          <List disablePadding>
            {memories.map((memory, index) => (
              <Box key={memory.id}>
                {index > 0 && (
                  <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />
                )}
                <ListItem
                  secondaryAction={
                    <IconButton
                      edge="end"
                      onClick={() => handleDeleteMemory(memory.id)}
                      sx={{
                        color: "rgba(255,255,255,0.3)",
                        "&:hover": { color: "#ef4444" },
                      }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  }
                  sx={{ px: 0 }}
                >
                  <ListItemText
                    primary={memory.content}
                    primaryTypographyProps={{ variant: "body2" }}
                  />
                </ListItem>
              </Box>
            ))}
          </List>
        )}
      </Paper>
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Lint and commit**

```bash
cd frontend && npx prettier --write src/pages/SettingsPage.tsx
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add learned preferences section to settings page"
```

---

### Task 9: Cleanup and Full Test Run

**Files:**
- Possibly modify various test files for import fixes

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && uv run pytest -v`

Fix any import errors or test failures related to:
- References to deleted `guardian.py`
- Updated `handle_script_chat_message` signature (no `msg_type`)
- Any other cascading changes

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npx vite build`

- [ ] **Step 3: Lint everything**

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd frontend && npx prettier --write src/**/*.tsx src/**/*.ts
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test and import issues after pipeline rewrite"
```

---

### Task 10: Manual Smoke Test

- [ ] **Step 1: Set ANTHROPIC_API_KEY in .env**

Add `ANTHROPIC_API_KEY=sk-ant-...` to `backend/.env`

- [ ] **Step 2: Start backend and frontend**

```bash
cd backend && uv run uvicorn main:app --reload --port 8000 &
cd frontend && npm run dev &
```

- [ ] **Step 3: Test agentic flow**

1. Log in, create a script conversation
2. Type "I want to make a video about AI agents" — should get topic suggestions
3. Click a topic — should get a full script
4. Type "make it shorter and more provocative" — should rewrite (NOT restart)
5. Type "Save this script" — should save
6. Type "Now let's do one about Rust vs Go" — should get new topics (multi-script)

- [ ] **Step 4: Test memories**

1. After saving a script, go to Settings
2. Check if a learned preference appeared
3. Delete a preference and verify it's removed

- [ ] **Step 5: Test without API key (Guardian fallback)**

Remove `ANTHROPIC_API_KEY` from `.env`, restart backend, verify script flow works through Guardian.

- [ ] **Step 6: Test persona gate**

Delete persona, start script conversation — should see error with Settings link.
