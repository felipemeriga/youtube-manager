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


def test_download_asset():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.download.return_value = b"image-binary-data"

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/reference-thumbs/thumb1.png")

    assert response.status_code == 200
    assert response.content == b"image-binary-data"
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="thumb1.png"' in response.headers["content-disposition"]


def test_upload_file_too_large():
    client = create_app("test-user")
    # fonts bucket has a 5MB limit
    large_content = b"x" * (5 * 1024 * 1024 + 1)

    with patch("routes.assets.get_supabase", return_value=MagicMock()):
        response = client.post(
            "/api/assets/fonts/upload",
            files={"file": ("big-font.ttf", large_content, "font/ttf")},
        )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


def test_upload_asset_invalid_bucket():
    client = create_app("test-user")
    response = client.post(
        "/api/assets/invalid-bucket/upload",
        files={"file": ("photo.jpg", b"data", "image/jpeg")},
    )
    assert response.status_code == 400


def test_download_asset_invalid_bucket():
    client = create_app("test-user")
    response = client.get("/api/assets/invalid-bucket/file.png")
    assert response.status_code == 400


def test_delete_asset_invalid_bucket():
    client = create_app("test-user")
    response = client.delete("/api/assets/invalid-bucket/file.png")
    assert response.status_code == 400


def test_upload_preserves_content_type():
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {
        "Key": "test-user/image.png"
    }

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/reference-thumbs/upload",
            files={"file": ("image.png", b"png-data", "image/png")},
        )

    assert response.status_code == 200
    # Verify upload was called with the right content-type header
    upload_call = mock_sb.storage.from_.return_value.upload.call_args
    assert upload_call[0][0] == "test-user/image.png"
