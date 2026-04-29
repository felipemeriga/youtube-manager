from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.personas import router


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def mock_supabase():
    return MagicMock()


def _patch_get_client(mock_sb):
    return patch(
        "routes.personas.get_async_client", new=AsyncMock(return_value=mock_sb)
    )


def test_get_persona_returns_404_when_not_found():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=MagicMock(data=None))

    with _patch_get_client(mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 404
    assert "Persona not found" in response.json()["detail"]


def test_get_persona_returns_data_when_exists():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=MagicMock(data={
        "user_id": user_id,
        "channel_name": "My Channel",
        "language": "en",
        "persona_text": "Friendly tech educator",
    }))

    with _patch_get_client(mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["channel_name"] == "My Channel"
    assert data["language"] == "en"
    assert data["persona_text"] == "Friendly tech educator"


def test_put_persona_upserts_and_returns_data():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.upsert.return_value.execute = AsyncMock(return_value=MagicMock(data=[
        {
            "user_id": user_id,
            "channel_name": "My Channel",
            "language": "pt",
            "persona_text": "Canal de tecnologia",
        }
    ]))

    payload = {
        "channel_name": "My Channel",
        "language": "pt",
        "persona_text": "Canal de tecnologia",
    }

    with _patch_get_client(mock_sb):
        response = client.put("/api/personas", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["channel_name"] == "My Channel"
    assert data["language"] == "pt"
    assert data["persona_text"] == "Canal de tecnologia"

    mock_sb.table.return_value.upsert.assert_called_once_with(
        {
            "user_id": user_id,
            "channel_name": "My Channel",
            "language": "pt",
            "persona_text": "Canal de tecnologia",
        },
        on_conflict="user_id",
    )


def test_delete_persona_returns_204():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(return_value=MagicMock(data=[
        {"user_id": user_id}
    ]))

    with _patch_get_client(mock_sb):
        response = client.delete("/api/personas")

    assert response.status_code == 204
    assert response.content == b""


def test_get_persona_includes_default_template_when_null():
    user_id = "test-user-id"
    client = create_app(user_id)

    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=MagicMock(data={
        "user_id": user_id,
        "channel_name": "My Channel",
        "language": "en",
        "persona_text": "Friendly",
        "script_template": None,
    }))

    with _patch_get_client(mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 200
    data = response.json()
    assert data["script_template"] is not None
    assert isinstance(data["script_template"], list)
    assert len(data["script_template"]) == 6
    assert data["script_template"][0]["name"] == "Hook / Opening"


def test_get_persona_returns_custom_template():
    user_id = "test-user-id"
    client = create_app(user_id)

    custom_template = [
        {"name": "Intro", "description": "Quick intro", "enabled": True, "order": 0},
    ]
    mock_sb = mock_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=MagicMock(data={
        "user_id": user_id,
        "channel_name": "My Channel",
        "language": "en",
        "persona_text": "Friendly",
        "script_template": custom_template,
    }))

    with _patch_get_client(mock_sb):
        response = client.get("/api/personas")

    assert response.status_code == 200
    assert response.json()["script_template"] == custom_template


def test_put_persona_with_script_template():
    user_id = "test-user-id"
    client = create_app(user_id)

    template = [
        {"name": "Hook", "description": "Opening hook", "enabled": True, "order": 0},
        {"name": "Script", "description": "Full script", "enabled": True, "order": 1},
    ]

    mock_sb = mock_supabase()
    mock_sb.table.return_value.upsert.return_value.execute = AsyncMock(return_value=MagicMock(data=[
        {
            "user_id": user_id,
            "channel_name": "Ch",
            "language": "en",
            "persona_text": "Fun",
            "script_template": template,
        }
    ]))

    with _patch_get_client(mock_sb):
        response = client.put(
            "/api/personas",
            json={
                "channel_name": "Ch",
                "language": "en",
                "persona_text": "Fun",
                "script_template": template,
            },
        )

    assert response.status_code == 200
    upsert_data = mock_sb.table.return_value.upsert.call_args[0][0]
    assert upsert_data["script_template"] == template
