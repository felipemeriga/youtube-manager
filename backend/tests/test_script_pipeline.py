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
    llm_response = json.dumps(
        {
            "action": "topics",
            "data": [{"title": "AI News", "angle": "test"}],
        }
    )

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
    llm_response = json.dumps(
        {
            "action": "script",
            "content": "# Full Script\n\nContent here",
        }
    )

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

    messages_data = MagicMock()
    messages_data.data = [
        {"role": "assistant", "content": "# My Script", "type": "script"},
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    llm_response = json.dumps({"action": "save", "message": "Script saved!"})

    with (
        patch(
            "services.script_pipeline.ask_llm",
            new_callable=AsyncMock,
            return_value=llm_response,
        ),
        patch(
            "services.script_pipeline.extract_memory",
            new_callable=AsyncMock,
        ),
    ):
        events = await collect_events("conv-1", "Save it", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("saved") is True
    sb.storage.from_.assert_called_with("scripts")


@pytest.mark.asyncio
async def test_message_action_returns_text_event():
    sb = make_async_sb()
    llm_response = json.dumps(
        {
            "action": "message",
            "content": "Could you clarify what angle you want?",
        }
    )

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


@pytest.mark.asyncio
async def test_system_prompt_includes_script_template():
    from services.script_pipeline import _build_system_prompt

    persona = {
        "channel_name": "Test",
        "language": "English",
        "persona_text": "Casual",
        "script_template": [
            {
                "name": "Hook",
                "description": "Opening hook",
                "enabled": True,
                "order": 0,
            },
            {
                "name": "Stats",
                "description": "Data with sources",
                "enabled": True,
                "order": 1,
            },
            {
                "name": "Outro",
                "description": "Closing remarks",
                "enabled": False,
                "order": 2,
            },
        ],
    }
    result = _build_system_prompt(persona, [])

    assert "Hook" in result
    assert "Opening hook" in result
    assert "Stats" in result
    assert "Outro" not in result


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


@pytest.mark.asyncio
async def test_persona_memories_messages_run_concurrently():
    """The three independent reads should be issued concurrently."""
    import asyncio
    from services import script_pipeline

    started = []
    finished = []

    async def slow_persona(sb, user_id):
        started.append("persona")
        await asyncio.sleep(0.05)
        finished.append("persona")
        return {"channel_name": "X", "language": "en", "persona_text": "p"}

    async def slow_memories(sb, user_id):
        started.append("memories")
        await asyncio.sleep(0.05)
        finished.append("memories")
        return []

    async def slow_messages(sb, conversation_id):
        started.append("messages")
        await asyncio.sleep(0.05)
        finished.append("messages")
        return []

    sb = make_async_sb()
    mock_get_sb = AsyncMock(return_value=sb)

    with (
        patch("services.script_pipeline.get_supabase", mock_get_sb),
        patch.object(script_pipeline, "_get_user_persona", slow_persona),
        patch.object(script_pipeline, "_get_user_memories", slow_memories),
        patch.object(script_pipeline, "_get_messages", slow_messages),
        patch("services.script_pipeline.ask_llm", AsyncMock(return_value="ok")),
    ):
        start = asyncio.get_event_loop().time()
        async for _ in script_pipeline.handle_script_chat_message(
            conversation_id="c1",
            content="hi",
            user_id="u1",
        ):
            pass
        elapsed = asyncio.get_event_loop().time() - start

    # All three started before any finished -> concurrent execution.
    assert started[:3].count("persona") == 1
    assert started[:3].count("memories") == 1
    assert started[:3].count("messages") == 1
    # If sequential, elapsed >= 0.15s; concurrent should be ~0.05s + overhead.
    assert elapsed < 0.12, f"Expected concurrent (<0.12s), got {elapsed:.3f}s"
