import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.thumbnail_pipeline import handle_chat_message


@pytest.mark.asyncio
async def test_text_message_generates_plan():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = (
                "I'll create a tech-style thumbnail using your studio portrait..."
            )

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="Create a thumbnail for my Python tutorial. Title: Python Decorators",
                msg_type="text",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    stages = [e for e in events if "stage" in e]
    tokens = [e for e in events if "token" in e]
    done = [e for e in events if e.get("done")]
    plan_type = [e for e in events if e.get("message_type") == "plan"]

    assert any(s["stage"] == "analyzing" for s in stages)
    assert len(tokens) > 0
    assert len(done) == 1
    assert len(plan_type) == 1


@pytest.mark.asyncio
async def test_approval_triggers_generation():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {
            "role": "assistant",
            "content": "I'll use your studio portrait...",
            "type": "plan",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-2"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {
        "Key": "test-user/temp.png"
    }

    fake_image = b"\x89PNG\r\n\x1a\nfake-thumbnail"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    stages = [e for e in events if "stage" in e]
    image_events = [e for e in events if e.get("message_type") == "image"]

    assert any(s["stage"] == "generating" for s in stages)
    assert len(image_events) == 1
    assert "image_base64" in image_events[0]


@pytest.mark.asyncio
async def test_save_stores_to_outputs():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc.png",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-3"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"fake-image-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {
        "Key": "test-user/thumb.png"
    }
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("saved") is True


@pytest.mark.asyncio
async def test_save_without_image_returns_error():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {
            "role": "assistant",
            "content": "Here is a plan...",
            "type": "plan",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-4"}
    ]

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("error") == "No image found to save"


@pytest.mark.asyncio
async def test_regenerate_delegates_to_approval():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {
            "role": "assistant",
            "content": "I'll use your studio portrait...",
            "type": "plan",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-5"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {
        "Key": "test-user/temp.png"
    }

    fake_image = b"\x89PNG\r\n\x1a\nregenerated"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="Make it brighter",
                msg_type="regenerate",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    stages = [e for e in events if "stage" in e]
    image_events = [e for e in events if e.get("message_type") == "image"]

    assert any(s["stage"] == "generating" for s in stages)
    assert len(image_events) == 1


@pytest.mark.asyncio
async def test_text_message_updates_conversation_title():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-6"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = "Plan for your thumbnail"

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="A very long title that should be truncated to fifty characters maximum for the conversation",
                msg_type="text",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    # Verify the title update was called with truncated content
    update_calls = [
        c for c in mock_sb.table.return_value.update.call_args_list if "title" in str(c)
    ]
    assert len(update_calls) > 0


@pytest.mark.asyncio
async def test_text_message_with_existing_assets():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-7"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    # Return files for each bucket
    mock_sb.storage.from_.return_value.list.return_value = [
        {"name": "file1.png"},
        {"name": "file2.png"},
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"file-bytes"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = "I see your 2 reference images"

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="Create a thumbnail",
                msg_type="text",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    # Guardian should have been called with asset summary
    guardian_call = mock_guardian.call_args
    assert "Reference thumbnails:" in guardian_call[1]["prompt"]


@pytest.mark.asyncio
async def test_sse_event_format():
    """sse_event should return properly formatted SSE data line."""
    from services.thumbnail_pipeline import sse_event

    result = sse_event({"stage": "analyzing"})
    assert result == 'data: {"stage": "analyzing"}\n\n'


@pytest.mark.asyncio
async def test_sse_event_with_special_characters():
    """sse_event should handle special characters in JSON."""
    from services.thumbnail_pipeline import sse_event

    result = sse_event({"content": 'He said "hello"'})
    parsed = json.loads(result.replace("data: ", "").strip())
    assert parsed["content"] == 'He said "hello"'


@pytest.mark.asyncio
async def test_fetch_all_assets_skips_empty_names():
    """fetch_all_assets should skip files with empty or missing name."""
    from services.thumbnail_pipeline import fetch_all_assets

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [
        {"name": "valid.png"},
        {"name": ""},
        {"name": None},
        {},
        {"name": "another.png"},
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"data"

    result = fetch_all_assets(mock_sb, "user-1", "reference-thumbs")

    assert len(result) == 2
    assert mock_sb.storage.from_.return_value.download.call_count == 2


@pytest.mark.asyncio
async def test_fetch_all_assets_empty_bucket():
    """fetch_all_assets with empty bucket should return empty list."""
    from services.thumbnail_pipeline import fetch_all_assets

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = []

    result = fetch_all_assets(mock_sb, "user-1", "reference-thumbs")

    assert result == []
    mock_sb.storage.from_.return_value.download.assert_not_called()


@pytest.mark.asyncio
async def test_handle_approval_without_plan_message():
    """handle_approval should still work when no plan message exists."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.upload.return_value = {}

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    # Should still generate image even without plan
    image_events = [e for e in events if e.get("message_type") == "image"]
    assert len(image_events) == 1

    # Verify prompt includes user request but not plan
    prompt = mock_gen.call_args[1]["prompt"]
    assert "User request:" in prompt
    assert "Approved plan:" not in prompt


@pytest.mark.asyncio
async def test_handle_approval_without_any_messages():
    """handle_approval should work even with empty message history."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.upload.return_value = {}

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    image_events = [e for e in events if e.get("message_type") == "image"]
    assert len(image_events) == 1

    # Prompt should only have the generation instruction
    prompt = mock_gen.call_args[1]["prompt"]
    assert "Generate a professional YouTube thumbnail" in prompt
    assert "User request:" not in prompt
    assert "Approved plan:" not in prompt


@pytest.mark.asyncio
async def test_handle_save_image_without_image_url():
    """handle_save with image message missing image_url should return error."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": None,
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("error") == "No image found to save"


@pytest.mark.asyncio
async def test_handle_save_image_with_empty_image_url():
    """handle_save with image message having empty string image_url should return error."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0].get("error") == "No image found to save"


@pytest.mark.asyncio
async def test_handle_regenerate_with_empty_content():
    """handle_regenerate with empty content should default to 'REGENERATE'."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {"role": "assistant", "content": "Plan...", "type": "plan"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.upload.return_value = {}

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="",
                msg_type="regenerate",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    # Verify the regenerate message was saved with default content
    insert_calls = mock_sb.table.return_value.insert.call_args_list
    regen_msg = insert_calls[0][0][0]
    assert regen_msg["content"] == "REGENERATE"
    assert regen_msg["type"] == "regenerate"


@pytest.mark.asyncio
async def test_unknown_msg_type_produces_no_events():
    """Unknown message type should silently produce no events."""
    mock_sb = MagicMock()

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
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
async def test_text_message_title_truncated_to_50_chars():
    """Conversation title should be truncated to 50 characters."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []

    long_content = "x" * 100

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = "plan"

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content=long_content,
                msg_type="text",
                user_id="test-user",
            ):
                events.append(event)

    # Find the update call with title
    update_call = mock_sb.table.return_value.update.call_args
    title_arg = update_call[0][0]["title"]
    assert len(title_arg) == 50
    assert title_arg == "x" * 50


@pytest.mark.asyncio
async def test_handle_approval_stores_image_in_outputs():
    """handle_approval should upload generated image to outputs bucket."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "Create a thumbnail", "type": "text"},
        {"role": "assistant", "content": "Plan...", "type": "plan"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.upload.return_value = {}

    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    # Verify upload was called on outputs bucket
    from_calls = [str(c) for c in mock_sb.storage.from_.call_args_list]
    assert any("outputs" in c for c in from_calls)

    # Verify image message was saved with image_url
    insert_calls = mock_sb.table.return_value.insert.call_args_list
    image_msg = next(c[0][0] for c in insert_calls if c[0][0].get("type") == "image")
    assert image_msg["role"] == "assistant"
    assert image_msg["image_url"].startswith("test-user/temp_")


@pytest.mark.asyncio
async def test_handle_approval_image_base64_in_event():
    """handle_approval should include base64-encoded image in SSE event."""
    import base64

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"role": "user", "content": "test", "type": "text"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.upload.return_value = {}

    fake_image = b"\x89PNG\r\n\x1a\nfake-thumb"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = fake_image

            events = []
            async for event in handle_chat_message(
                conversation_id="conv-1",
                content="APPROVED",
                msg_type="approval",
                user_id="test-user",
            ):
                events.append(json.loads(event.replace("data: ", "").strip()))

    image_event = next(e for e in events if e.get("message_type") == "image")
    decoded = base64.b64decode(image_event["image_base64"])
    assert decoded == fake_image
    assert "image_url" in image_event


@pytest.mark.asyncio
async def test_handle_save_renames_temp_to_final():
    """handle_save should download temp, re-upload with final name, and remove temp."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc12345.png",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"image-data"
    mock_sb.storage.from_.return_value.upload.return_value = {}
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    done = [e for e in events if e.get("done")]
    assert done[0]["saved"] is True
    assert "thumbnail_" in done[0]["path"]

    # Verify temp was removed
    mock_sb.storage.from_.return_value.remove.assert_called_once_with(
        ["test-user/temp_abc12345.png"]
    )

    # Verify upload used final path
    upload_call = mock_sb.storage.from_.return_value.upload.call_args
    assert upload_call[0][0].startswith("test-user/thumbnail_")


@pytest.mark.asyncio
async def test_handle_save_updates_message_image_url():
    """handle_save should update the image message with the final URL."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-99",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_xyz.png",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"data"
    mock_sb.storage.from_.return_value.upload.return_value = {}
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    # Verify the messages table update was called
    update_calls = mock_sb.table.return_value.update.call_args_list
    assert len(update_calls) > 0
    # The update should set image_url with the new path
    image_url_update = update_calls[0][0][0]
    assert "image_url" in image_url_update
    assert image_url_update["image_url"].startswith("test-user/thumbnail_")


@pytest.mark.asyncio
async def test_handle_save_confirmation_message():
    """handle_save should insert a confirmation text message."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "img-msg-1",
            "role": "assistant",
            "content": "Generated thumbnail",
            "type": "image",
            "image_url": "test-user/temp_abc.png",
        },
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"data"
    mock_sb.storage.from_.return_value.upload.return_value = {}
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        events = []
        async for event in handle_chat_message(
            conversation_id="conv-1",
            content="SAVE_OUTPUT",
            msg_type="save",
            user_id="test-user",
        ):
            events.append(json.loads(event.replace("data: ", "").strip()))

    # Verify confirmation message was inserted
    insert_calls = mock_sb.table.return_value.insert.call_args_list
    # First insert is the save user message, second is the confirmation
    assert len(insert_calls) == 2
    confirmation_msg = insert_calls[1][0][0]
    assert confirmation_msg["role"] == "assistant"
    assert confirmation_msg["type"] == "text"
    assert "Thumbnail saved to outputs" in confirmation_msg["content"]


@pytest.mark.asyncio
async def test_text_message_saves_user_message():
    """handle_text_message should save the user message to DB."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = "plan"

            async for _ in handle_chat_message(
                conversation_id="conv-1",
                content="My thumbnail request",
                msg_type="text",
                user_id="test-user",
            ):
                pass

    # First insert should be the user message
    first_insert = mock_sb.table.return_value.insert.call_args_list[0][0][0]
    assert first_insert["conversation_id"] == "conv-1"
    assert first_insert["role"] == "user"
    assert first_insert["content"] == "My thumbnail request"
    assert first_insert["type"] == "text"


@pytest.mark.asyncio
async def test_text_message_saves_plan_message():
    """handle_text_message should save the plan as assistant message."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-1"}
    ]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {}
    ]
    mock_sb.storage.from_.return_value.list.return_value = []

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch(
            "services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock
        ) as mock_guardian:
            mock_guardian.return_value = "Here is the plan"

            async for _ in handle_chat_message(
                conversation_id="conv-1",
                content="Create a thumbnail",
                msg_type="text",
                user_id="test-user",
            ):
                pass

    # Second insert should be the plan message
    plan_insert = mock_sb.table.return_value.insert.call_args_list[1][0][0]
    assert plan_insert["role"] == "assistant"
    assert plan_insert["content"] == "Here is the plan"
    assert plan_insert["type"] == "plan"
