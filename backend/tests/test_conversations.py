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

    mock_sb = MagicMock()

    conv_result = MagicMock()
    conv_result.data = {"id": "conv-1", "title": "Test", "user_id": user_id}

    msg_result = MagicMock()
    msg_result.data = [
        {
            "id": "msg-1",
            "role": "user",
            "content": "hello",
            "type": "text",
            "image_url": None,
        }
    ]

    def table_dispatch(name):
        q = MagicMock()
        if name == "conversations":
            q.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = conv_result
        else:
            q.select.return_value.eq.return_value.order.return_value.execute.return_value = msg_result
        return q

    mock_sb.table.side_effect = table_dispatch

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
    mock_sb.table.return_value.insert.assert_called_once_with(
        {"user_id": user_id, "mode": "thumbnail"}
    )


def test_get_nonexistent_conversation_returns_404():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = MagicMock()
    conv_result = MagicMock()
    conv_result.data = None
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = conv_result

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


def test_get_conversation_response_structure():
    """Response should include conversation fields plus messages array."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = MagicMock()

    conv_result = MagicMock()
    conv_result.data = {
        "id": "conv-1",
        "title": "Test",
        "user_id": user_id,
        "created_at": "2026-04-03T00:00:00Z",
        "updated_at": "2026-04-03T00:00:00Z",
    }
    msg_result = MagicMock()
    msg_result.data = []

    def table_dispatch(name):
        q = MagicMock()
        if name == "conversations":
            q.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = conv_result
        else:
            q.select.return_value.eq.return_value.order.return_value.execute.return_value = msg_result
        return q

    mock_sb.table.side_effect = table_dispatch

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1")

    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert data["id"] == "conv-1"
    assert data["title"] == "Test"
    assert data["user_id"] == user_id


def test_delete_conversation_response_body():
    """Delete should return status: deleted."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "conv-1"}
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.delete("/api/conversations/conv-1")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}


def test_create_conversation_returns_first_record():
    """Create should return the first element from the insert result."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "new-conv",
            "user_id": user_id,
            "title": None,
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations")

    data = response.json()
    assert data["id"] == "new-conv"
    assert data["user_id"] == user_id
    assert data["title"] is None


def test_get_conversation_with_multiple_messages():
    """Conversation should return all messages in order."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    conv_query = MagicMock()
    conv_query.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": "conv-1",
        "title": "Test",
        "user_id": user_id,
    }
    msg_query = MagicMock()
    msg_query.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "msg-1", "role": "user", "content": "hello", "type": "text"},
        {"id": "msg-2", "role": "assistant", "content": "plan", "type": "plan"},
        {"id": "msg-3", "role": "user", "content": "APPROVED", "type": "approval"},
    ]
    mock_sb.table.side_effect = lambda name: (
        conv_query if name == "conversations" else msg_query
    )

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1")

    data = response.json()
    assert len(data["messages"]) == 3
    assert data["messages"][0]["id"] == "msg-1"
    assert data["messages"][2]["type"] == "approval"


def test_create_conversation_with_script_mode():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "new-conv",
            "user_id": user_id,
            "mode": "script",
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations", json={"mode": "script"})

    assert response.status_code == 200
    assert response.json()["mode"] == "script"
    mock_sb.table.return_value.insert.assert_called_once_with(
        {"user_id": user_id, "mode": "script"}
    )


def test_create_conversation_default_mode_is_thumbnail():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "new-conv",
            "user_id": user_id,
            "mode": "thumbnail",
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        }
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    mock_sb.table.return_value.insert.assert_called_once_with(
        {"user_id": user_id, "mode": "thumbnail"}
    )


def test_list_conversations_preserves_order():
    """List should return conversations as provided by Supabase (ordered by updated_at desc)."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "conv-2", "updated_at": "2026-04-04T00:00:00Z"},
        {"id": "conv-1", "updated_at": "2026-04-03T00:00:00Z"},
    ]

    with patch("routes.conversations.get_supabase", return_value=mock_sb):
        response = client.get("/api/conversations")

    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "conv-2"
    assert data[1]["id"] == "conv-1"
