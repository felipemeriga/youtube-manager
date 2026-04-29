from services.clips.storage import (
    source_key, preview_key, preview_poster_key, final_key, job_prefix,
)


def test_source_key():
    assert source_key("u1", "j1") == "u1/j1/source.mp4"


def test_preview_key():
    assert preview_key("u1", "j1", "c1") == "u1/j1/previews/c1.mp4"


def test_preview_poster_key():
    assert preview_poster_key("u1", "j1", "c1") == "u1/j1/previews/c1.jpg"


def test_final_key():
    assert final_key("u1", "j1", "c1") == "u1/j1/finals/c1.mp4"


def test_job_prefix():
    assert job_prefix("u1", "j1") == "u1/j1"
