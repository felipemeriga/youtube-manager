import json
import base64
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.thumbnail_pipeline import handle_chat_message


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
    chain.select.return_value.eq.return_value.maybe_single.return_value.execute = (
        AsyncMock(return_value=MagicMock(data=None))
    )

    storage = sb.storage.from_.return_value
    storage.list = AsyncMock(return_value=overrides.get("files", []))
    storage.download = AsyncMock(return_value=overrides.get("download", b"fake-bytes"))
    storage.upload = AsyncMock(return_value=overrides.get("upload", {}))
    storage.remove = AsyncMock(return_value=[])

    return sb


async def collect_events(conversation_id, content, msg_type, user_id, sb):
    events = []
    mock_get_sb = AsyncMock(return_value=sb)
    with patch("services.thumbnail_pipeline.get_supabase", mock_get_sb):
        async for event in handle_chat_message(
            conversation_id=conversation_id,
            content=content,
            msg_type=msg_type,
            user_id=user_id,
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))
    return events


@pytest.fixture(autouse=True)
def mock_research():
    with patch(
        "services.thumbnail_pipeline._research_topic",
        new_callable=AsyncMock,
        return_value="",
    ):
        yield


@pytest.mark.asyncio
async def test_text_message_generates_background():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake-background"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = await collect_events(
                "conv-1",
                "Create a thumbnail for my Python tutorial",
                "text",
                "test-user",
                sb,
            )

    stages = [e for e in events if "stage" in e]
    bg_events = [e for e in events if e.get("message_type") == "background"]
    done = [e for e in events if e.get("done")]

    assert any(s["stage"] == "generating" for s in stages)
    assert len(bg_events) == 1
    assert "image_base64" in bg_events[0]
    assert len(done) == 1


@pytest.mark.asyncio
async def test_text_message_passes_prompt_to_generator():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            await collect_events(
                "conv-1", "Make a gaming thumbnail", "text", "test-user", sb
            )

    prompt = mock_gen.call_args[1]["prompt"]
    assert "Make a gaming thumbnail" in prompt
    assert "BACKGROUND" in prompt


@pytest.mark.asyncio
async def test_text_message_updates_conversation_title():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            await collect_events(
                "conv-1",
                "A very long title that should be truncated to fifty characters maximum",
                "text",
                "test-user",
                sb,
            )

    update_calls = [
        c for c in sb.table.return_value.update.call_args_list if "title" in str(c)
    ]
    assert len(update_calls) > 0


@pytest.mark.asyncio
async def test_text_message_title_truncated_to_50_chars():
    sb = make_async_sb()
    long_content = "x" * 100
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            async for _ in handle_chat_message(
                conversation_id="conv-1",
                content=long_content,
                msg_type="text",
                user_id="test-user",
            ):
                pass

    update_call = sb.table.return_value.update.call_args
    title_arg = update_call[0][0]["title"]
    assert len(title_arg) == 50


@pytest.mark.asyncio
async def test_text_message_saves_user_message():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            async for _ in handle_chat_message(
                conversation_id="conv-1",
                content="My thumbnail request",
                msg_type="text",
                user_id="test-user",
            ):
                pass

    first_insert = sb.table.return_value.insert.call_args_list[0][0][0]
    assert first_insert["conversation_id"] == "conv-1"
    assert first_insert["role"] == "user"
    assert first_insert["content"] == "My thumbnail request"
    assert first_insert["type"] == "text"


@pytest.mark.asyncio
async def test_text_message_saves_background_message():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            async for _ in handle_chat_message(
                conversation_id="conv-1",
                content="Create a thumbnail",
                msg_type="text",
                user_id="test-user",
            ):
                pass

    bg_insert = sb.table.return_value.insert.call_args_list[1][0][0]
    assert bg_insert["role"] == "assistant"
    assert bg_insert["type"] == "background"
    assert bg_insert["image_url"].startswith("test-user/bg_")


@pytest.mark.asyncio
async def test_text_message_image_base64_in_event():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake-thumb"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = await collect_events(
                "conv-1", "Create a thumbnail", "text", "test-user", sb
            )

    bg_event = next(e for e in events if e.get("message_type") == "background")
    decoded = base64.b64decode(bg_event["image_base64"])
    assert decoded == fake_image
    assert "image_url" in bg_event


@pytest.mark.asyncio
async def test_text_message_stores_in_outputs():
    sb = make_async_sb()
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            await collect_events(
                "conv-1", "Create a thumbnail", "text", "test-user", sb
            )

    from_calls = [str(c) for c in sb.storage.from_.call_args_list]
    assert any("outputs" in c for c in from_calls)


@pytest.mark.asyncio
async def test_save_stores_to_outputs():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc.png",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    events = await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("saved") is True


@pytest.mark.asyncio
async def test_save_without_image_returns_error():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    events = await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("error") == "No image found to save"


@pytest.mark.asyncio
async def test_save_image_without_image_url():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": None,
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    events = await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("error") == "No image found to save"


@pytest.mark.asyncio
async def test_save_renames_temp_to_final():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc12345.png",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    events = await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    done = [e for e in events if e.get("done")]
    assert done[0]["saved"] is True
    assert "thumbnail_" in done[0]["path"]

    sb.storage.from_.return_value.remove.assert_called_once_with(
        ["test-user/temp_abc12345.png"]
    )


@pytest.mark.asyncio
async def test_save_updates_message_image_url():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "img-msg-99",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_xyz.png",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    update_calls = sb.table.return_value.update.call_args_list
    assert len(update_calls) > 0
    image_url_update = update_calls[0][0][0]
    assert "image_url" in image_url_update
    assert image_url_update["image_url"].startswith("test-user/thumbnail_")


@pytest.mark.asyncio
async def test_save_confirmation_message():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc.png",
        },
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    await collect_events("conv-1", "SAVE_OUTPUT", "save", "test-user", sb)

    insert_calls = sb.table.return_value.insert.call_args_list
    assert len(insert_calls) == 2
    confirmation_msg = insert_calls[1][0][0]
    assert confirmation_msg["role"] == "assistant"
    assert confirmation_msg["type"] == "text"
    assert "Thumbnail saved as" in confirmation_msg["content"]


@pytest.mark.asyncio
async def test_regenerate_uses_original_request():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    fake_image = b"\x89PNG\r\n\x1a\nregenerated"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = await collect_events(
                "conv-1", "Make it brighter", "regenerate", "test-user", sb
            )

    bg_events = [e for e in events if e.get("message_type") == "background"]
    assert len(bg_events) == 1

    prompt = mock_gen.call_args[1]["prompt"]
    assert "Create a thumbnail" in prompt
    assert "Make it brighter" in prompt


@pytest.mark.asyncio
async def test_regenerate_without_feedback():
    sb = make_async_sb()
    execute_result = MagicMock()
    execute_result.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
    ]
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=execute_result
    )

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = fake_image

            await collect_events("conv-1", "", "regenerate", "test-user", sb)

    # The regenerate handler fetches messages then calls step1_background
    # with original content; check that generate_background was called
    assert mock_gen.called


@pytest.mark.asyncio
async def test_unknown_msg_type_produces_no_events():
    sb = make_async_sb()

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="hello",
            msg_type="unknown_type",
            user_id="test-user",
        ):
            events.append(event)

    assert events == []


@pytest.mark.asyncio
async def test_sse_event_format():
    from services.thumbnail_pipeline import sse_event

    result = sse_event({"stage": "generating"})
    assert result == 'data: {"stage": "generating"}\n\n'


@pytest.mark.asyncio
async def test_sse_event_with_special_characters():
    from services.thumbnail_pipeline import sse_event

    result = sse_event({"content": 'He said "hello"'})
    parsed = json.loads(result.replace("data: ", "").strip())
    assert parsed["content"] == 'He said "hello"'


@pytest.mark.asyncio
async def test_fetch_all_assets_skips_empty_names():
    from services.thumbnail_pipeline import fetch_all_assets

    sb = MagicMock()
    sb.storage.from_.return_value.list = AsyncMock(
        return_value=[
            {"name": "valid.png"},
            {"name": ""},
            {"name": None},
            {},
            {"name": "another.png"},
        ]
    )
    sb.storage.from_.return_value.download = AsyncMock(return_value=b"data")

    result = await fetch_all_assets(sb, "user-1", "reference-thumbs")

    assert len(result) == 2
    assert sb.storage.from_.return_value.download.call_count == 2


@pytest.mark.asyncio
async def test_fetch_all_assets_empty_bucket():
    from services.thumbnail_pipeline import fetch_all_assets

    sb = MagicMock()
    sb.storage.from_.return_value.list = AsyncMock(return_value=[])

    result = await fetch_all_assets(sb, "user-1", "reference-thumbs")

    assert result == []
    sb.storage.from_.return_value.download.assert_not_called()


@pytest.mark.asyncio
async def test_error_in_pipeline_returns_error_event():
    sb = make_async_sb()

    with patch(
        "services.thumbnail_pipeline.get_supabase",
        AsyncMock(return_value=sb),
    ):
        with patch(
            "services.thumbnail_pipeline.generate_background",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.side_effect = Exception("Gemini API error")

            events = await collect_events(
                "conv-1", "Create a thumbnail", "text", "test-user", sb
            )

    error_events = [e for e in events if e.get("error")]
    assert len(error_events) == 1
    assert "Gemini API error" in error_events[0]["error"]
    assert error_events[0]["done"] is True
