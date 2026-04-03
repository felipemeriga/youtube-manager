from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.assets import router

VALID_BUCKETS = ["reference-thumbs", "personal-photos", "fonts", "outputs"]


def create_app(user_id: str) -> TestClient:
    app = FastAPI()

    async def mock_user():
        return user_id

    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    return TestClient(app)


def test_list_assets():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [
        {"name": "thumb1.png", "metadata": {"size": 12345}}
    ]

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/reference-thumbs")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "thumb1.png"


def test_list_assets_invalid_bucket():
    client = create_app("test-user")
    response = client.get("/api/assets/invalid-bucket")
    assert response.status_code == 400


def test_upload_asset():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {
        "Key": "test-user/photo.jpg"
    }

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/personal-photos/upload",
            files={"file": ("photo.jpg", b"fake-image-data", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "photo.jpg"


def test_delete_asset():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.remove.return_value = [{"name": "photo.jpg"}]

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.delete("/api/assets/personal-photos/photo.jpg")

    assert response.status_code == 200
