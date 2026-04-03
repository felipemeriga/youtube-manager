import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from services.thumbnail_pipeline import handle_chat_message


@pytest.mark.asyncio
async def test_text_message_generates_plan():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch("services.thumbnail_pipeline.ask_guardian", new_callable=AsyncMock) as mock_guardian:
            mock_guardian.return_value = "I'll create a tech-style thumbnail using your studio portrait..."

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
        {"role": "assistant", "content": "I'll use your studio portrait...", "type": "plan"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-2"}]
    mock_sb.storage.from_.return_value.list.return_value = []
    mock_sb.storage.from_.return_value.download.return_value = b"fake-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {"Key": "test-user/temp.png"}

    fake_image = b"\x89PNG\r\n\x1a\nfake-thumbnail"

    with patch("services.thumbnail_pipeline.get_supabase", return_value=mock_sb):
        with patch("services.thumbnail_pipeline.generate_thumbnail", new_callable=AsyncMock) as mock_gen:
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
        {"id": "img-msg-1", "role": "assistant", "content": "Generated thumbnail", "type": "image", "image_url": "test-user/temp_abc.png"},
    ]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-3"}]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    mock_sb.storage.from_.return_value.download.return_value = b"fake-image-bytes"
    mock_sb.storage.from_.return_value.upload.return_value = {"Key": "test-user/thumb.png"}
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
    assert done[0].get("saved") == True
