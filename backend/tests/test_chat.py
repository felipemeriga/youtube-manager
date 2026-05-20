import json
from unittest.mock import patch, MagicMock, AsyncMock
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
    """Build an async-Supabase mock whose conversation lookup returns ``mode``."""
    mock_sb = MagicMock()
    conv_result = MagicMock()
    conv_result.data = {"mode": mode}
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
        return_value=conv_result
    )
    return mock_sb


def test_chat_endpoint_returns_sse_stream():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'generating'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch(
            "routes.chat.get_async_client", new_callable=AsyncMock, return_value=mock_sb
        ),
        patch("routes.chat.thumbnail_stream", side_effect=fake_stream),
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


def test_chat_endpoint_default_type_is_text():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch(
            "routes.chat.get_async_client", new_callable=AsyncMock, return_value=mock_sb
        ),
        patch("routes.chat.thumbnail_stream", side_effect=fake_stream) as mock_thumb,
    ):
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "conv-1",
                "content": "Hello",
            },
        )

    assert response.status_code == 200
    mock_thumb.assert_called_once_with(
        conversation_id="conv-1",
        content="Hello",
        user_id="test-user",
        image_url=None,
        platforms=None,
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


def test_chat_endpoint_empty_body_returns_422():
    client = create_app("test-user")
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_endpoint_stream_body_content():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'stage': 'generating'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch(
            "routes.chat.get_async_client", new_callable=AsyncMock, return_value=mock_sb
        ),
        patch("routes.chat.thumbnail_stream", side_effect=fake_stream),
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
    assert 'data: {"stage": "generating"}' in body
    assert 'data: {"done": true}' in body


def test_chat_dispatches_to_script_pipeline_for_script_mode():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("script")

    with (
        patch(
            "routes.chat.get_async_client", new_callable=AsyncMock, return_value=mock_sb
        ),
        patch(
            "routes.chat.handle_script_chat_message", side_effect=fake_stream
        ) as mock_script,
        patch("routes.chat.thumbnail_stream") as mock_thumbnail,
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


def test_chat_dispatches_to_thumbnail_stream_for_thumbnail_mode():
    client = create_app("test-user")

    async def fake_stream(*args, **kwargs):
        yield f"data: {json.dumps({'done': True})}\n\n"

    mock_sb = mock_supabase_with_mode("thumbnail")

    with (
        patch(
            "routes.chat.get_async_client", new_callable=AsyncMock, return_value=mock_sb
        ),
        patch(
            "routes.chat.thumbnail_stream", side_effect=fake_stream
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
        user_id="test-user",
        image_url=None,
        platforms=None,
    )
    mock_script.assert_not_called()
