from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_auth():
    app.dependency_overrides[get_current_user] = lambda: "user-123"
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_sb():
    sb = MagicMock()
    return sb


def _patch_client(mock_sb):
    return patch("routes.clips.get_async_client", new=AsyncMock(return_value=mock_sb))


def test_preflight_returns_metadata(mock_sb):
    from services.clips.models import VideoMetadata
    metadata = VideoMetadata(youtube_video_id="abc", title="Test", duration_seconds=300)
    with patch("routes.clips.fetch_metadata", new=AsyncMock(return_value=metadata)):
        r = client.post("/api/clips/jobs/preflight", json={"youtube_url": "https://youtu.be/abc"})
    assert r.status_code == 200
    assert r.json() == {"youtube_video_id": "abc", "title": "Test", "duration_seconds": 300}


def test_preflight_rejects_too_long(mock_sb):
    with patch("routes.clips.fetch_metadata", new=AsyncMock(side_effect=ValueError("exceeds 60 min"))):
        r = client.post("/api/clips/jobs/preflight", json={"youtube_url": "https://youtu.be/x"})
    assert r.status_code == 400
    assert "exceeds" in r.json()["detail"]


def test_create_job_inserts_and_starts_task(mock_sb):
    mock_sb.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "job-1", "youtube_url": "https://youtu.be/x"}])
    )
    with _patch_client(mock_sb), \
         patch("routes.clips.asyncio.create_task") as mock_create_task, \
         patch("routes.clips.register_task") as mock_reg:
        r = client.post("/api/clips/jobs", json={"youtube_url": "https://youtu.be/x"})
    assert r.status_code == 201
    assert r.json()["id"] == "job-1"
    mock_create_task.assert_called_once()
    mock_reg.assert_called_once()
