from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.conversations import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase():
    mock_sb = MagicMock()
    return mock_sb


def test_list_conversations():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "conv-1",
            "title": "Test",
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "conv-1"


def test_create_conversation():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "new-conv",
            "user_id": user_id,
            "title": None,
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    assert response.json()["id"] == "new-conv"


def test_get_conversation_with_messages():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    conv_query = MagicMock()
    conv_query.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "conv-1",
        "title": "Test",
        "user_id": user_id,
    }
    msg_query = MagicMock()
    msg_query.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "msg-1",
            "role": "user",
            "content": "hello",
            "type": "text",
            "image_url": None,
        }
    ]
    mock_sb.table.side_effect = lambda name: (
        conv_query if name == "conversations" else msg_query
    )

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1")

    assert response.status_code == 200
    assert response.json()["id"] == "conv-1"
    assert len(response.json()["messages"]) == 1


def test_delete_conversation():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "conv-1"}
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.delete("/api/conversations/conv-1")

    assert response.status_code == 200


def test_create_conversation_with_title_in_insert():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "new-conv-2",
            "user_id": user_id,
            "title": None,
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    # Verify the insert was called with the correct user_id
    mock_sb.table.return_value.insert.assert_called_once_with({"user_id": user_id})


def test_get_nonexistent_conversation_returns_404():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    conv_query = MagicMock()
    conv_query.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    mock_sb.table.return_value = conv_query

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations/nonexistent-id")

    assert response.status_code == 404
    assert "Conversation not found" in response.json()["detail"]


def test_delete_nonexistent_conversation_returns_404():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.delete("/api/conversations/nonexistent-id")

    assert response.status_code == 404
    assert "Conversation not found" in response.json()["detail"]


def test_list_conversations_empty():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == []
