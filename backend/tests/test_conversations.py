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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    assert response.json()["id"] == "new-conv"


class _ChainableMock:
    """A mock that returns itself for any chained method call, until execute()."""

    def __init__(self, execute_data=None):
        self._execute_data = execute_data

    def __getattr__(self, name):
        if name == "execute":
            result = MagicMock()
            result.data = self._execute_data
            return lambda: result
        return lambda *a, **kw: self


def _make_sb_for_get_conv(conv_data, msg_data):
    """Build a mock supabase for get_conversation endpoint."""
    mock_sb = MagicMock()

    def table_fn(name):
        if name == "conversations":
            return _ChainableMock(execute_data=conv_data)
        return _ChainableMock(execute_data=msg_data)

    mock_sb.table = table_fn
    return mock_sb


def test_get_conversation_with_messages():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = _make_sb_for_get_conv(
        conv_data={"id": "conv-1", "title": "Test", "user_id": user_id},
        msg_data=[
            {
                "id": "msg-1",
                "role": "user",
                "content": "hello",
                "type": "text",
                "image_url": None,
            }
        ],
    )

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.post("/api/conversations")

    assert response.status_code == 200
    # Verify the insert was called with the correct user_id
    mock_sb.table.return_value.insert.assert_called_once_with(
        {"user_id": user_id, "mode": "thumbnail"}
    )


def test_get_nonexistent_conversation_returns_404():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = _make_sb_for_get_conv(conv_data=None, msg_data=[])

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.get("/api/conversations/nonexistent-id")

    assert response.status_code == 404
    assert "Conversation not found" in response.json()["detail"]


def test_delete_nonexistent_conversation_returns_404():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.delete("/api/conversations/nonexistent-id")

    assert response.status_code == 404
    assert "Conversation not found" in response.json()["detail"]


def test_list_conversations_empty():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == []


def test_get_conversation_response_structure():
    """Response should include conversation fields plus messages array."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = _make_sb_for_get_conv(
        conv_data={
            "id": "conv-1",
            "title": "Test",
            "user_id": user_id,
            "created_at": "2026-04-03T00:00:00Z",
            "updated_at": "2026-04-03T00:00:00Z",
        },
        msg_data=[],
    )

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.post("/api/conversations")

    data = response.json()
    assert data["id"] == "new-conv"
    assert data["user_id"] == user_id
    assert data["title"] is None


def test_get_conversation_with_multiple_messages():
    """Conversation should return all messages in order."""
    user_id = "test-user-id"
    client = create_app(user_id)

    # Messages come from DB in desc order; code reverses them to chronological
    mock_sb = _make_sb_for_get_conv(
        conv_data={"id": "conv-1", "title": "Test", "user_id": user_id},
        msg_data=[
            {"id": "msg-3", "role": "user", "content": "APPROVED", "type": "approval"},
            {"id": "msg-2", "role": "assistant", "content": "plan", "type": "plan"},
            {"id": "msg-1", "role": "user", "content": "hello", "type": "text"},
        ],
    )

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
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

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.get("/api/conversations")

    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "conv-2"
    assert data[1]["id"] == "conv-1"


def test_get_conversation_has_more_flag():
    """When message count equals limit, has_more should be True."""
    user_id = "test-user-id"
    client = create_app(user_id)

    # Return exactly 2 messages (matching limit=2)
    mock_sb = _make_sb_for_get_conv(
        conv_data={"id": "conv-1", "title": "Test", "user_id": user_id},
        msg_data=[
            {"id": "msg-2", "role": "assistant", "content": "hi", "type": "text"},
            {"id": "msg-1", "role": "user", "content": "hello", "type": "text"},
        ],
    )

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1?limit=2")

    data = response.json()
    assert data["has_more"] is True
    assert len(data["messages"]) == 2


def test_get_conversation_has_more_false_when_fewer():
    """When message count is less than limit, has_more should be False."""
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = _make_sb_for_get_conv(
        conv_data={"id": "conv-1", "title": "Test", "user_id": user_id},
        msg_data=[
            {"id": "msg-1", "role": "user", "content": "hello", "type": "text"},
        ],
    )

    with patch("routes.conversations.get_sync_client", return_value=mock_sb):
        response = client.get("/api/conversations/conv-1?limit=50")

    data = response.json()
    assert data["has_more"] is False
