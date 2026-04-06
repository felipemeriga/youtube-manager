import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.script_pipeline import handle_script_chat_message


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

    storage = sb.storage.from_.return_value
    storage.upload = AsyncMock(return_value={})

    return sb


async def collect_events(conversation_id, content, msg_type, user_id, sb):
    events = []
    mock_get_sb = AsyncMock(return_value=sb)
    with patch("services.script_pipeline.get_supabase", mock_get_sb):
        async for event in handle_script_chat_message(
            conversation_id=conversation_id,
            content=content,
            msg_type=msg_type,
            user_id=user_id,
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))
    return events


@pytest.mark.asyncio
async def test_handle_ideation_streams_topics():
    sb = make_async_sb()
    fake_topics = '[{"title": "AI News", "angle": "test"}]'

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value=fake_topics,
    ):
        events = await collect_events(
            "conv-1", "Give me video ideas", "text", "test-user", sb
        )

    stages = [e for e in events if "stage" in e]
    done = [e for e in events if e.get("done")]

    assert any(s["stage"] == "finding_trends" for s in stages)
    assert len(done) == 1
    assert done[0].get("message_type") == "topics"


@pytest.mark.asyncio
async def test_handle_topic_selection_streams_script():
    sb = make_async_sb()

    messages_data = MagicMock()
    messages_data.data = [
        {"role": "user", "content": "Give me ideas about AI", "type": "text"},
        {
            "role": "assistant",
            "content": '[{"title": "AI in 2026", "angle": "test"}]',
            "type": "topics",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value="# Full Script\n\nContent here",
    ):
        events = await collect_events(
            "conv-1", "0", "topic_selection", "test-user", sb
        )

    stages = [e.get("stage") for e in events if "stage" in e]
    done = [e for e in events if e.get("done")]

    assert "writing_script" in stages
    assert len(done) == 1
    assert done[0].get("message_type") == "script"


@pytest.mark.asyncio
async def test_handle_topic_selection_extracts_duration():
    sb = make_async_sb()

    messages_data = MagicMock()
    messages_data.data = [
        {
            "role": "user",
            "content": "Give me ideas about AI, 20 min video",
            "type": "text",
        },
        {
            "role": "assistant",
            "content": '[{"title": "AI in 2026", "angle": "test"}]',
            "type": "topics",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    captured_prompt = None

    async def capture_guardian(prompt, context=""):
        nonlocal captured_prompt
        captured_prompt = prompt
        return "# Script"

    with patch(
        "services.script_pipeline.ask_guardian",
        side_effect=capture_guardian,
    ):
        await collect_events("conv-1", "0", "topic_selection", "test-user", sb)

    assert "20 minutos" in captured_prompt


@pytest.mark.asyncio
async def test_handle_script_approval_saves_to_storage():
    sb = make_async_sb()

    messages_data = MagicMock()
    messages_data.data = [
        {"role": "user", "content": "Give me ideas", "type": "text"},
        {
            "role": "assistant",
            "content": '[{"title": "AI in 2026"}]',
            "type": "topics",
        },
        {"role": "user", "content": "0", "type": "topic_selection"},
        {
            "role": "assistant",
            "content": "# Full Script\n\nContent here",
            "type": "script",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    events = await collect_events("conv-1", "", "approve_script", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("saved") is True

    sb.storage.from_.assert_called_with("scripts")
    sb.storage.from_.return_value.upload.assert_called_once()
    upload_args = sb.storage.from_.return_value.upload.call_args
    assert upload_args[0][0].startswith("test-user/")
    assert upload_args[0][0].endswith(".md")


@pytest.mark.asyncio
async def test_handle_script_approval_rejected():
    sb = make_async_sb()

    messages_data = MagicMock()
    messages_data.data = [
        {"role": "user", "content": "Give me ideas", "type": "text"},
        {
            "role": "assistant",
            "content": '[{"title": "AI in 2026"}]',
            "type": "topics",
        },
        {"role": "user", "content": "0", "type": "topic_selection"},
        {
            "role": "assistant",
            "content": "# Old Script",
            "type": "script",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=messages_data
    )

    with patch(
        "services.script_pipeline.ask_guardian",
        new_callable=AsyncMock,
        return_value="# Revised Script",
    ):
        events = await collect_events(
            "conv-1", "Make it shorter", "reject_script", "test-user", sb
        )

    stages = [e.get("stage") for e in events if "stage" in e]
    done = [e for e in events if e.get("done")]

    assert "writing_script" in stages
    assert len(done) == 1
    assert done[0].get("message_type") == "script"
