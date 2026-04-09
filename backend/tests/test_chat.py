import json
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.chat import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase_with_mode(mode: str = "thumbnail"):
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "mode": mode
    }
    return mock_sb


def test_chat_endpoint_returns_sse_stream():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'analyzing'})}\n\n"
        yield f"data: {json.dumps({'token': 'Hello '})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_handle,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Create a thumbnail",
                "type": "text",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    mock_handle.assert_called_once_with(
        conversation_id="conv-1",
        content="Create a thumbnail",
        msg_type="text",
        user_id="test-user",
    )


def test_chat_endpoint_default_type_is_text():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_handle,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Hello",
            },
        )

    assert response.status_code == 200
    mock_handle.assert_called_once_with(
        conversation_id="conv-1",
        content="Hello",
        msg_type="text",
        user_id="test-user",
    )


def test_chat_endpoint_approval_type():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'generating'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_handle,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "APPROVED",
                "type": "approval",
            },
        )

    assert response.status_code == 200
    mock_handle.assert_called_once_with(
        conversation_id="conv-1",
        content="APPROVED",
        msg_type="approval",
        user_id="test-user",
    )


def test_chat_endpoint_missing_conversation_id_returns_422():
    client = create_app("test-user")
    response = client.post(
        "/api/chat",
        json={"content": "Hello"},
    )
    assert response.status_code == 422


def test_chat_endpoint_missing_content_returns_422():
    client = create_app("test-user")
    response = client.post(
        "/api/chat",
        json={"conversation_id": "conv-1"},
    )
    assert response.status_code == 422


def test_chat_endpoint_save_type():
    """Save message type should be passed through correctly."""
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True, 'saved': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_handle,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "SAVE_OUTPUT",
                "type": "save",
            },
        )

    assert response.status_code == 200
    mock_handle.assert_called_once_with(
        conversation_id="conv-1",
        content="SAVE_OUTPUT",
        msg_type="save",
        user_id="test-user",
    )


def test_chat_endpoint_regenerate_type():
    """Regenerate message type should be passed through correctly."""
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'generating'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_handle,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Make it brighter",
                "type": "regenerate",
            },
        )

    assert response.status_code == 200
    mock_handle.assert_called_once_with(
        conversation_id="conv-1",
        content="Make it brighter",
        msg_type="regenerate",
        user_id="test-user",
    )


def test_chat_endpoint_empty_body_returns_422():
    """Empty JSON body should return 422."""
    client = create_app("test-user")
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_endpoint_stream_body_content():
    """Verify the actual SSE data in the response body."""
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'analyzing'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch("routes.chat.handle_chat_message", side_effect=fake_stream),
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "test",
                "type": "text",
            },
        )

    body = response.text
    assert 'data: {"stage": "analyzing"}' in body
    assert 'data: {"done": true}' in body


def test_chat_dispatches_to_script_pipeline_for_script_mode():
    """When conversation mode is 'script', handle_script_chat_message is called."""
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("script")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_script_chat_message", side_effect=fake_stream
        ) as mock_script,
        patch("routes.chat.handle_chat_message") as mock_thumbnail,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Write a script",
                "type": "text",
            },
        )

    assert response.status_code == 200
    mock_script.assert_called_once_with(
        conversation_id="conv-1",
        content="Write a script",
        user_id="test-user",
        model=None,
    )
    mock_thumbnail.assert_not_called()


def test_chat_dispatches_to_thumbnail_pipeline_for_thumbnail_mode():
    """When conversation mode is 'thumbnail', handle_chat_message is called."""
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch("routes.chat.get_supabase", return_value=mock_sb),
        patch(
            "routes.chat.handle_chat_message", side_effect=fake_stream
        ) as mock_thumbnail,
        patch("routes.chat.handle_script_chat_message") as mock_script,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Create a thumbnail",
                "type": "text",
            },
        )

    assert response.status_code == 200
    mock_thumbnail.assert_called_once_with(
        conversation_id="conv-1",
        content="Create a thumbnail",
        msg_type="text",
        user_id="test-user",
    )
    mock_script.assert_not_called()
