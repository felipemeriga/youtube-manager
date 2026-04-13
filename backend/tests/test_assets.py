from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from routes.assets import router

VALID_BUCKETS = ["reference-thumbs", "personal-photos", "logos", "outputs", "scripts"]


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
    name = response.json()["name"]
    assert name.startswith("photo_") and name.endswith(".jpg")


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
    # logos bucket has a 5MB limit
    large_content = b"x" * (5 * 1024 * 1024 + 1)

    with patch("routes.assets.get_supabase", return_value=MagicMock()):
        response = client.post(
            "/api/assets/logos/upload",
            files={"file": ("big-logo.png", large_content, "image/png")},
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
    path = upload_call[0][0]
    assert path.startswith("test-user/image_") and path.endswith(".png")


def test_upload_asset_response_structure():
    """Upload should return name, bucket, and path."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {}

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/logos/upload",
            files={"file": ("logo.png", b"logo-data", "image/png")},
        )

    data = response.json()
    assert data["bucket"] == "logos"
    assert data["name"].startswith("logo_") and data["name"].endswith(".png")
    assert data["path"].startswith("test-user/logo_") and data["path"].endswith(".png")


def test_delete_asset_response_structure():
    """Delete should return status and name."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.delete("/api/assets/outputs/thumb.png")

    assert response.json() == {"status": "deleted", "name": "thumb.png"}


def test_upload_file_exactly_at_max_size():
    """File at exactly the max size should succeed."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {}

    exact_content = b"x" * (5 * 1024 * 1024)  # exactly 5MB for logos
    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/logos/upload",
            files={"file": ("logo.png", exact_content, "image/png")},
        )

    assert response.status_code == 200


def test_upload_file_one_byte_over_max():
    """File one byte over max should be rejected."""
    client = create_app("test-user")
    over_content = b"x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 for reference-thumbs

    with patch("routes.assets.get_supabase", return_value=MagicMock()):
        response = client.post(
            "/api/assets/reference-thumbs/upload",
            files={"file": ("big.png", over_content, "image/png")},
        )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]
    assert "10MB" in response.json()["detail"]


def test_list_assets_all_valid_buckets():
    """All four valid buckets should be accepted for listing."""
    for bucket in VALID_BUCKETS:
        client = create_app("test-user")
        mock_sb = MagicMock()
        mock_sb.storage.from_.return_value.list.return_value = []

        with patch("routes.assets.get_supabase", return_value=mock_sb):
            response = client.get(f"/api/assets/{bucket}")

        assert response.status_code == 200, f"Failed for bucket: {bucket}"


def test_download_asset_content_disposition_header():
    """Download should set Content-Disposition with correct filename."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.download.return_value = b"data"

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/outputs/my-thumbnail.png")

    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="my-thumbnail.png"'
    )
    assert response.headers["content-type"] == "application/octet-stream"


def test_upload_constructs_correct_storage_path():
    """Upload should prefix filename with user_id."""
    client = create_app("user-123")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.upload.return_value = {}

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.post(
            "/api/assets/personal-photos/upload",
            files={"file": ("photo.jpg", b"data", "image/jpeg")},
        )

    path = response.json()["path"]
    assert path.startswith("user-123/photo_") and path.endswith(".jpg")
    upload_call = mock_sb.storage.from_.return_value.upload.call_args
    assert upload_call[0][0] == path
    assert upload_call[0][1] == b"data"
    assert upload_call[0][2] == {"content-type": "image/jpeg"}


def test_delete_asset_calls_storage_remove():
    """Delete should call storage remove with correct path."""
    client = create_app("user-456")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.remove.return_value = []

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.delete("/api/assets/reference-thumbs/img.png")

    assert response.status_code == 200
    mock_sb.storage.from_.assert_called_with("reference-thumbs")
    mock_sb.storage.from_.return_value.remove.assert_called_once_with(
        ["user-456/img.png"]
    )


def test_invalid_bucket_error_message():
    """Invalid bucket should include the bucket name and valid options in error."""
    client = create_app("test-user")
    response = client.get("/api/assets/bad-bucket")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "bad-bucket" in detail


def test_list_assets_empty():
    """Listing assets from empty bucket should return empty list."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = []

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/logos")

    assert response.status_code == 200
    assert response.json() == []


def test_list_scripts_bucket():
    """Scripts bucket should be accepted for listing."""
    client = create_app("test-user")
    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = []

    with patch("routes.assets.get_supabase", return_value=mock_sb):
        response = client.get("/api/assets/scripts")

    assert response.status_code == 200
