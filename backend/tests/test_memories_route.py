from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.memories import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase():
    """Build a MagicMock supabase client whose query chain ends in an AsyncMock execute().

    The supabase-py async client mirrors sync: builder methods (.table, .select,
    .eq, .order, .delete, ...) are sync, but .execute() is awaitable. MagicMock's
    auto-chained returns work for the builder; we explicitly attach AsyncMock to
    .execute on every leaf the route calls.
    """
    return MagicMock()


def _patch_get_client(mock_sb):
    """get_async_client is itself a coroutine in the route, so the patch target
    needs to be an AsyncMock returning the mock_sb."""
    return patch(
        "routes.memories.get_async_client", new=AsyncMock(return_value=mock_sb)
    )


def test_list_memories_returns_data():
    user_id = "test-user-id"
    client = create_app(user_id)

    memories = [
        {
            "id": "mem-1",
            "user_id": user_id,
            "content": "Prefers short scripts",
            "created_at": "2026-04-08",
        },
        {
            "id": "mem-2",
            "user_id": user_id,
            "content": "Likes bullet points",
            "created_at": "2026-04-07",
        },
    ]
    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=memories)
    )

    with _patch_get_client(mock_sb):
        response = client.get("/api/memories")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "mem-1"
    assert data[0]["content"] == "Prefers short scripts"
    assert data[1]["id"] == "mem-2"


def test_list_memories_returns_empty_list():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with _patch_get_client(mock_sb):
        response = client.get("/api/memories")

    assert response.status_code == 200
    assert response.json() == []


def test_delete_memory_returns_204():
    user_id = "test-user-id"
    memory_id = "mem-abc-123"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    delete_chain = MagicMock()
    delete_chain.eq.return_value = delete_chain
    delete_chain.execute = AsyncMock(return_value=MagicMock(data=[]))
    mock_sb.table.return_value.delete.return_value = delete_chain

    with _patch_get_client(mock_sb):
        response = client.delete(f"/api/memories/{memory_id}")

    assert response.status_code == 204
    assert response.content == b""

    # Verify scoped to both memory_id and user_id
    delete_chain.eq.assert_any_call("id", memory_id)
    delete_chain.eq.assert_any_call("user_id", user_id)
