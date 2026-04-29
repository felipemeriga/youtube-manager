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


def test_list_jobs(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "j1"}, {"id": "j2"}])
    )
    with _patch_client(mock_sb):
        r = client.get("/api/clips/jobs")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_job_returns_with_candidates(mock_sb):
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    job_chain.execute = AsyncMock(return_value=MagicMock(data={"id": "j1", "user_id": "user-123"}))
    cand_chain = mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value
    cand_chain.execute = AsyncMock(return_value=MagicMock(data=[{"id": "c1", "hype_score": 9}]))

    with _patch_client(mock_sb):
        r = client.get("/api/clips/jobs/j1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "j1"
    assert len(body["candidates"]) == 1


def test_get_job_404_when_not_found(mock_sb):
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    job_chain.execute = AsyncMock(return_value=MagicMock(data=None))
    with _patch_client(mock_sb):
        r = client.get("/api/clips/jobs/missing")
    assert r.status_code == 404


def test_sse_events_streams_published_events(mock_sb):
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    job_chain.execute = AsyncMock(return_value=MagicMock(data={"id": "j1", "user_id": "user-123"}))

    # Use a custom subscribe that returns a queue pre-populated with a terminal
    # event ("ready" causes the route to break out of its loop). Publishing via
    # the live broker doesn't work here because TestClient's streaming runs the
    # route in a separate event loop — an asyncio.Queue is bound to the loop on
    # which `get` is awaited, so we must seed the queue from inside that loop.
    import asyncio
    from services.clips import sse_broker as broker_mod

    real_subscribe = broker_mod.broker.subscribe

    def subscribe_with_event(job_id):
        q = real_subscribe(job_id)
        q.put_nowait({"type": "progress", "stage": "metadata", "pct": 5})
        q.put_nowait({"type": "ready"})  # terminate the stream cleanly
        return q

    with _patch_client(mock_sb), \
         patch.object(broker_mod.broker, "subscribe", side_effect=subscribe_with_event):
        with client.stream("GET", "/api/clips/jobs/j1/events") as resp:
            assert resp.status_code == 200
            chunks = []
            for chunk in resp.iter_text():
                chunks.append(chunk)
                if any("progress" in c for c in chunks):
                    break
            assert any("progress" in c for c in chunks)
            # Verify SSE framing
            assert any(c.startswith("data: ") for c in chunks)


def test_cancel_job(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data={"id": "j1", "status": "processing"})
    )
    mock_sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
    with _patch_client(mock_sb), patch("routes.clips.cancel_task", return_value=True):
        r = client.post("/api/clips/jobs/j1/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_render_endpoint_marks_selected_and_starts_task(mock_sb):
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    job_chain.execute = AsyncMock(return_value=MagicMock(data={
        "id": "j1", "user_id": "user-123", "status": "ready",
        "source_storage_key": "user-123/j1/source.mp4",
    }))
    mock_sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock()
    mock_sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

    with _patch_client(mock_sb), \
         patch("routes.clips.asyncio.create_task") as mock_create:
        r = client.post(
            "/api/clips/jobs/j1/render",
            json={"candidate_ids": ["c1", "c2"]},
        )
    assert r.status_code == 202
    mock_create.assert_called_once()
