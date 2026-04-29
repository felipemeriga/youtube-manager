# YouTube Clips Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a YouTube clip creator that takes a video URL, auto-generates ranked vertical 9:16 short-clip candidates with hype scores, lets the user preview and select, and re-renders selected clips at full quality with burned-in captions.

**Architecture:** Two-phase pipeline — phase 1 generates all preview candidates upfront (yt-dlp download → caption/Whisper → LLM segment+score → ffmpeg cut+face-aware reframe → low-bitrate preview); phase 2 re-renders only user-selected clips at full quality with burned subtitles. DB-backed `clip_jobs` row drives state, asyncio task does the work, SSE pushes progress to a brand-new `/clips` page.

**Tech Stack:** FastAPI + asyncio, Supabase Postgres + Storage, yt-dlp, OpenAI Whisper API (fallback), MediaPipe face detection, ffmpeg subprocess, React + MUI, Server-Sent Events.

**Spec:** `docs/superpowers/specs/2026-04-29-youtube-clips-design.md`

**Branch:** `feat/security-perf-ux-tier3` (continuation of PR #8). All commits atomic, **NO `Co-Authored-By` trailer**.

---

## File Structure

### Backend (new)
```
backend/migrations/002_clips_tables.sql              # clip_jobs, clip_candidates, indexes, RLS
backend/services/clips/__init__.py                   # public exports
backend/services/clips/models.py                     # pydantic models for stage outputs
backend/services/clips/metadata.py                   # yt-dlp metadata fetch + duration validation
backend/services/clips/download.py                   # yt-dlp source download + Supabase upload
backend/services/clips/transcript.py                 # YT captions + Whisper fallback + cue normalization
backend/services/clips/segment.py                    # LLM segmentation + scoring + cap
backend/services/clips/face_detection.py             # MediaPipe wrapper → x-track per clip window
backend/services/clips/render_preview.py             # ffmpeg cut + reframe + low-bitrate encode
backend/services/clips/render_final.py               # ffmpeg high-quality + burn-in captions (.ass)
backend/services/clips/sse_broker.py                 # in-process per-job event queue (asyncio.Queue)
backend/services/clips/job_runner.py                 # pipeline orchestration + asyncio task registry
backend/services/clips/cleanup.py                    # TTL retention sweep
backend/services/clips/storage.py                    # path helpers + supabase upload/download/sign helpers
backend/routes/clips.py                              # all /api/clips/* endpoints
```

### Backend (modified)
```
backend/main.py                                      # register clips router + startup recovery hook
backend/config.py                                    # add OPENAI_API_KEY, CLIPS_CLEANUP_TOKEN, etc.
backend/pyproject.toml                               # yt-dlp, mediapipe, openai
```

### Backend tests (new)
```
backend/tests/test_clips_metadata.py
backend/tests/test_clips_transcript.py
backend/tests/test_clips_segment.py
backend/tests/test_clips_face_detection.py
backend/tests/test_clips_render_preview.py
backend/tests/test_clips_render_final.py
backend/tests/test_clips_sse_broker.py
backend/tests/test_clips_job_runner.py
backend/tests/test_clips_cleanup.py
backend/tests/test_clips_routes.py
backend/tests/fixtures/clips/                        # tiny mp4, fake VTT, sample LLM responses
```

### Frontend (new)
```
frontend/src/types/clips.ts                          # ClipJob, ClipCandidate, JobEvent types
frontend/src/api/clips.ts                            # fetch wrappers
frontend/src/hooks/useClipJobSSE.ts                  # SSE subscription
frontend/src/pages/ClipsPage.tsx                     # job list + new job form
frontend/src/pages/ClipJobPage.tsx                   # job detail (3 states)
frontend/src/components/clips/NewJobForm.tsx
frontend/src/components/clips/JobProgressPanel.tsx
frontend/src/components/clips/ClipGrid.tsx
frontend/src/components/clips/ClipCard.tsx
frontend/src/components/clips/ClipPreviewModal.tsx
frontend/src/components/clips/SelectionBar.tsx
frontend/src/components/clips/FinalRenderPanel.tsx
```

### Frontend (modified)
```
frontend/src/App.tsx                                 # add /clips and /clips/:jobId routes
frontend/src/components/IconRail.tsx                 # add Clips sidebar entry
```

---

## Phase A — Database

### Task A1: Create migration for clip_jobs and clip_candidates

**Files:**
- Create: `backend/migrations/002_clips_tables.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Migration 002: YouTube Clips feature
-- Tables: clip_jobs, clip_candidates

CREATE TABLE clip_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    youtube_url         TEXT NOT NULL,
    youtube_video_id    TEXT,
    title               TEXT,
    duration_seconds    INTEGER,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','processing','ready','rendering','completed','failed','expired')),
    current_stage       TEXT
                        CHECK (current_stage IS NULL OR current_stage IN
                            ('metadata','download','transcribe','segment','preview_render',
                             'await_selection','final_render','done')),
    progress_pct        INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    error_message       TEXT,
    source_storage_key  TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days')
);

CREATE TRIGGER update_clip_jobs_updated_at
    BEFORE UPDATE ON clip_jobs
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_clip_jobs_user_created ON clip_jobs (user_id, created_at DESC);
CREATE INDEX idx_clip_jobs_expires ON clip_jobs (expires_at) WHERE status != 'failed';

ALTER TABLE clip_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY clip_jobs_select ON clip_jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY clip_jobs_insert ON clip_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY clip_jobs_update ON clip_jobs FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY clip_jobs_delete ON clip_jobs FOR DELETE USING (auth.uid() = user_id);


CREATE TABLE clip_candidates (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id               UUID NOT NULL REFERENCES clip_jobs(id) ON DELETE CASCADE,
    start_seconds        DOUBLE PRECISION NOT NULL,
    end_seconds          DOUBLE PRECISION NOT NULL,
    duration_seconds     DOUBLE PRECISION NOT NULL,
    hype_score           DOUBLE PRECISION NOT NULL,
    hype_reasoning       TEXT,
    transcript_excerpt   TEXT,
    preview_storage_key  TEXT,
    preview_poster_key   TEXT,
    final_storage_key    TEXT,
    selected             BOOLEAN NOT NULL DEFAULT false,
    render_failed        BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clip_candidates_job_score ON clip_candidates (job_id, hype_score DESC);

ALTER TABLE clip_candidates ENABLE ROW LEVEL SECURITY;

CREATE POLICY clip_candidates_select ON clip_candidates FOR SELECT USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_insert ON clip_candidates FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_update ON clip_candidates FOR UPDATE USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
CREATE POLICY clip_candidates_delete ON clip_candidates FOR DELETE USING (
    EXISTS (SELECT 1 FROM clip_jobs WHERE clip_jobs.id = clip_candidates.job_id AND clip_jobs.user_id = auth.uid())
);
```

- [ ] **Step 2: Apply migration to local Supabase**

Run via the Supabase SQL editor or `psql $DATABASE_URL -f backend/migrations/002_clips_tables.sql`.
Expected: tables `clip_jobs` and `clip_candidates` created, RLS policies enabled.

- [ ] **Step 3: Verify with a select**

```sql
SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'clip%';
```
Expected: returns two rows.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/002_clips_tables.sql
git commit -m "feat(clips): add clip_jobs and clip_candidates tables"
```

---

## Phase B — Backend dependencies & config

### Task B1: Add Python dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add deps**

In `[project] dependencies` add:
```
"yt-dlp>=2024.10.0",
"mediapipe>=0.10.18",
"openai>=1.50.0",
```

- [ ] **Step 2: Lock and install**

```bash
cd backend && uv sync
```
Expected: lock updates, packages install, no errors.

- [ ] **Step 3: Verify ffmpeg is on PATH**

```bash
ffmpeg -version
```
Expected: prints ffmpeg version. If missing, document install (`brew install ffmpeg`) but don't block — runtime check will surface it.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(clips): add yt-dlp, mediapipe, openai backend deps"
```

### Task B2: Add config settings

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: Add fields to `Settings`**

```python
openai_api_key: str = ""
clips_cleanup_token: str = ""    # service token for /api/clips/cleanup
clips_tmp_dir: str = "/tmp/clips"
clips_bucket: str = "clips"
```

- [ ] **Step 2: Verify boot**

```bash
cd backend && .venv/bin/python -c "from config import settings; print(settings.clips_bucket)"
```
Expected: prints `clips`.

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat(clips): add config keys for openai, cleanup token, tmp dir, bucket"
```

---

## Phase C — Backend services (TDD)

> Throughout Phase C, run tests with: `cd backend && .venv/bin/python -m pytest tests/<file> -v`

### Task C1: Pydantic models for stage outputs

**Files:**
- Create: `backend/services/clips/__init__.py` (empty)
- Create: `backend/services/clips/models.py`
- Test: none — these are pure dataclasses, exercised via downstream tests.

- [ ] **Step 1: Create models**

```python
# backend/services/clips/models.py
from pydantic import BaseModel


class VideoMetadata(BaseModel):
    youtube_video_id: str
    title: str
    duration_seconds: int


class TranscriptCue(BaseModel):
    start: float
    end: float
    text: str


class CandidateClip(BaseModel):
    start_seconds: float
    end_seconds: float
    hype_score: float
    hype_reasoning: str
    transcript_excerpt: str

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds
```

- [ ] **Step 2: Quick import sanity check**

```bash
cd backend && .venv/bin/python -c "from services.clips.models import VideoMetadata, TranscriptCue, CandidateClip; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/clips/__init__.py backend/services/clips/models.py
git commit -m "feat(clips): add pydantic models for pipeline stages"
```

### Task C2: Metadata service — TDD

**Files:**
- Create: `backend/services/clips/metadata.py`
- Test: `backend/tests/test_clips_metadata.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_metadata.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.metadata import fetch_metadata, MAX_DURATION_SECONDS


@pytest.mark.asyncio
async def test_fetch_metadata_parses_ytdlp_json():
    fake_json = json.dumps({"id": "abc123", "title": "Test", "duration": 300})
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(return_value=fake_json)):
        m = await fetch_metadata("https://youtu.be/abc123")
    assert m.youtube_video_id == "abc123"
    assert m.title == "Test"
    assert m.duration_seconds == 300


@pytest.mark.asyncio
async def test_fetch_metadata_rejects_over_60_min():
    fake_json = json.dumps({"id": "abc", "title": "Long", "duration": 3601})
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(return_value=fake_json)):
        with pytest.raises(ValueError, match="exceeds 60 min"):
            await fetch_metadata("https://youtu.be/abc")


@pytest.mark.asyncio
async def test_fetch_metadata_invalid_url_propagates():
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(side_effect=RuntimeError("yt-dlp failed"))):
        with pytest.raises(RuntimeError):
            await fetch_metadata("https://bad")


def test_max_duration_constant():
    assert MAX_DURATION_SECONDS == 3600
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_metadata.py -v
```
Expected: ImportError / module not found.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/metadata.py
import asyncio
import json
import logging

from .models import VideoMetadata

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 3600


async def _run_ytdlp_dump(url: str) -> str:
    """Run `yt-dlp --dump-json --no-download <url>` and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--dump-json", "--no-download", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()[:500]}")
    return stdout.decode()


async def fetch_metadata(url: str) -> VideoMetadata:
    raw = await _run_ytdlp_dump(url)
    data = json.loads(raw)
    duration = int(data.get("duration") or 0)
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(f"Video duration {duration}s exceeds 60 min limit")
    return VideoMetadata(
        youtube_video_id=data["id"],
        title=data.get("title", ""),
        duration_seconds=duration,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_metadata.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/metadata.py backend/tests/test_clips_metadata.py
git commit -m "feat(clips): add metadata service with duration cap"
```

### Task C3: Storage helpers

**Files:**
- Create: `backend/services/clips/storage.py`
- Test: `backend/tests/test_clips_storage.py` (path helper unit tests only — supabase calls covered via integration mocks elsewhere)

- [ ] **Step 1: Write failing tests for path helpers**

```python
# backend/tests/test_clips_storage.py
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
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_storage.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/storage.py
"""Storage path helpers and Supabase upload/download/sign wrappers for clips.

All paths are relative to the `clips` bucket. RLS isolation is enforced by
prefixing every key with `{user_id}/`.
"""
import logging
from pathlib import Path

from config import settings
from services.supabase_pool import get_async_client

logger = logging.getLogger(__name__)


def job_prefix(user_id: str, job_id: str) -> str:
    return f"{user_id}/{job_id}"


def source_key(user_id: str, job_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/source.mp4"


def preview_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/previews/{candidate_id}.mp4"


def preview_poster_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/previews/{candidate_id}.jpg"


def final_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/finals/{candidate_id}.mp4"


async def upload_file(local_path: Path, storage_key: str, content_type: str = "video/mp4") -> None:
    """Upload a local file to the clips bucket. Reuses existing Supabase 502 retry pattern."""
    sb = await get_async_client()
    data = local_path.read_bytes()
    # Reuse upload pattern from routes/assets.py (retry on 502 etc.)
    await sb.storage.from_(settings.clips_bucket).upload(
        storage_key, data, {"contentType": content_type, "upsert": "true"}
    )


async def download_file(storage_key: str, local_path: Path) -> None:
    sb = await get_async_client()
    data = await sb.storage.from_(settings.clips_bucket).download(storage_key)
    local_path.write_bytes(data)


async def signed_url(storage_key: str, ttl_seconds: int = 3600) -> str:
    sb = await get_async_client()
    res = await sb.storage.from_(settings.clips_bucket).create_signed_url(
        storage_key, ttl_seconds
    )
    return res["signedURL"]


async def remove_keys(storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    sb = await get_async_client()
    await sb.storage.from_(settings.clips_bucket).remove(storage_keys)
```

- [ ] **Step 4: Run path tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_storage.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/storage.py backend/tests/test_clips_storage.py
git commit -m "feat(clips): add storage path helpers and supabase wrappers"
```

### Task C4: Download service — TDD

**Files:**
- Create: `backend/services/clips/download.py`
- Test: `backend/tests/test_clips_download.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_download.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.download import download_source


@pytest.mark.asyncio
async def test_download_source_invokes_ytdlp_and_uploads(tmp_path):
    captured = {}

    async def fake_run(url, out_path):
        Path(out_path).write_bytes(b"fake mp4")
        captured["url"] = url
        captured["out"] = out_path

    async def fake_upload(local, key, content_type):
        captured["upload_local"] = str(local)
        captured["upload_key"] = key

    with patch("services.clips.download._run_ytdlp_download", new=fake_run), \
         patch("services.clips.download.upload_file", new=fake_upload):
        local_path = await download_source(
            url="https://youtu.be/abc",
            user_id="u1",
            job_id="j1",
            tmp_dir=tmp_path,
        )
    assert local_path.exists()
    assert captured["url"] == "https://youtu.be/abc"
    assert captured["upload_key"] == "u1/j1/source.mp4"


@pytest.mark.asyncio
async def test_download_source_propagates_failure(tmp_path):
    with patch("services.clips.download._run_ytdlp_download",
               new=AsyncMock(side_effect=RuntimeError("yt-dlp fail"))):
        with pytest.raises(RuntimeError):
            await download_source(
                url="https://youtu.be/x", user_id="u", job_id="j", tmp_dir=tmp_path,
            )
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_download.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/download.py
import asyncio
import logging
from pathlib import Path

from .storage import source_key, upload_file

logger = logging.getLogger(__name__)


async def _run_ytdlp_download(url: str, out_path: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b",
        "--merge-output-format", "mp4",
        "-o", str(out_path),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {stderr.decode()[:500]}")


async def download_source(
    url: str,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> Path:
    """Download YouTube video and upload to Supabase. Returns local file path."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / "source.mp4"
    await _run_ytdlp_download(url, local_path)
    await upload_file(local_path, source_key(user_id, job_id), "video/mp4")
    logger.info("Downloaded source for job %s, size=%d", job_id, local_path.stat().st_size)
    return local_path
```

- [ ] **Step 4: Run — expect pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_download.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/download.py backend/tests/test_clips_download.py
git commit -m "feat(clips): add yt-dlp source download + supabase upload"
```

### Task C5: Transcript service — TDD

**Files:**
- Create: `backend/services/clips/transcript.py`
- Test: `backend/tests/test_clips_transcript.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_transcript.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.transcript import (
    fetch_transcript, parse_vtt, is_broken_captions,
)


SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.500
Welcome to my channel.

00:00:02.500 --> 00:00:05.000
Today we're talking about Python.
"""


def test_parse_vtt_returns_cues():
    cues = parse_vtt(SAMPLE_VTT)
    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == 2.5
    assert cues[0].text == "Welcome to my channel."


def test_is_broken_captions_empty():
    assert is_broken_captions([]) is True


def test_is_broken_captions_too_few():
    cues = [type("C", (), {"text": f"line {i}"})() for i in range(3)]
    assert is_broken_captions(cues) is True


def test_is_broken_captions_mostly_music_tags():
    cues = [type("C", (), {"text": t})() for t in
            ["[Music]", "[Music]", "[Applause]", "[Music]", "[Music]", "[Music]"]]
    assert is_broken_captions(cues) is True


def test_is_broken_captions_normal_passes():
    cues = [type("C", (), {"text": "Hello world this is content"})() for _ in range(10)]
    assert is_broken_captions(cues) is False


@pytest.mark.asyncio
async def test_fetch_transcript_uses_yt_captions_when_good(tmp_path):
    vtt_path = tmp_path / "captions.en.vtt"
    vtt_path.write_text(SAMPLE_VTT * 5)  # 10 cues

    async def fake_dl(url, out_dir):
        return vtt_path

    with patch("services.clips.transcript._download_yt_captions", new=fake_dl):
        cues = await fetch_transcript("https://youtu.be/x", tmp_path / "audio.mp3", tmp_path)
    assert len(cues) >= 5


@pytest.mark.asyncio
async def test_fetch_transcript_falls_back_to_whisper(tmp_path):
    # YT captions return None → fallback
    async def fake_dl(url, out_dir):
        return None

    fake_whisper_cues = [
        type("C", (), {"start": 0.0, "end": 1.0, "text": "hi"})(),
        type("C", (), {"start": 1.0, "end": 2.0, "text": "there"})(),
    ]

    async def fake_whisper(audio_path):
        return fake_whisper_cues

    with patch("services.clips.transcript._download_yt_captions", new=fake_dl), \
         patch("services.clips.transcript._whisper_transcribe", new=fake_whisper):
        cues = await fetch_transcript("https://youtu.be/x", tmp_path / "audio.mp3", tmp_path)
    assert len(cues) == 2
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_transcript.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/transcript.py
import asyncio
import logging
import re
from pathlib import Path

from config import settings

from .models import TranscriptCue

logger = logging.getLogger(__name__)

VTT_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(content: str) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln and ln != "WEBVTT"]
        if not lines:
            continue
        ts_line = next((ln for ln in lines if "-->" in ln), None)
        if not ts_line:
            continue
        m = VTT_TIMESTAMP_RE.search(ts_line)
        if not m:
            continue
        start = _ts_to_seconds(*m.groups()[:4])
        end = _ts_to_seconds(*m.groups()[4:])
        text = " ".join(ln for ln in lines if ln is not ts_line and "-->" not in ln).strip()
        if text:
            cues.append(TranscriptCue(start=start, end=end, text=text))
    return cues


def is_broken_captions(cues: list) -> bool:
    if len(cues) < 5:
        return True
    music_tag_re = re.compile(r"\[(music|applause|laughter|silence)\]", re.IGNORECASE)
    music_count = sum(1 for c in cues if music_tag_re.fullmatch(c.text.strip()))
    if music_count / len(cues) > 0.5:
        return True
    return False


async def _download_yt_captions(url: str, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--write-auto-subs", "--sub-langs", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--convert-subs", "vtt",
        "-o", str(out_dir / "captions.%(ext)s"),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    candidates = list(out_dir.glob("captions*.vtt"))
    return candidates[0] if candidates else None


async def _whisper_transcribe(audio_path: Path) -> list[TranscriptCue]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    with audio_path.open("rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    cues: list[TranscriptCue] = []
    # Group words into ~5s cues for downstream sentence-aware segmentation
    current_words: list[str] = []
    current_start: float | None = None
    last_end: float = 0.0
    for w in getattr(result, "words", []) or []:
        if current_start is None:
            current_start = w.start
        current_words.append(w.word)
        last_end = w.end
        if last_end - current_start >= 5.0 or w.word.endswith((".", "?", "!")):
            cues.append(TranscriptCue(
                start=current_start, end=last_end, text=" ".join(current_words).strip(),
            ))
            current_words = []
            current_start = None
    if current_words and current_start is not None:
        cues.append(TranscriptCue(
            start=current_start, end=last_end, text=" ".join(current_words).strip(),
        ))
    return cues


async def fetch_transcript(
    url: str,
    audio_path: Path,
    tmp_dir: Path,
) -> list[TranscriptCue]:
    """Try YouTube auto-captions first; fall back to Whisper if missing/broken.

    Retries Whisper once on failure before raising.
    """
    vtt_path = await _download_yt_captions(url, tmp_dir)
    if vtt_path and vtt_path.exists():
        cues = parse_vtt(vtt_path.read_text())
        if not is_broken_captions(cues):
            logger.info("Using YT captions: %d cues", len(cues))
            return cues
        logger.info("YT captions broken (%d cues) — falling back to Whisper", len(cues))
    else:
        logger.info("YT captions missing — falling back to Whisper")

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            return await _whisper_transcribe(audio_path)
        except Exception as e:
            last_err = e
            logger.warning("Whisper attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"Transcription failed: {last_err}")
```

- [ ] **Step 4: Run — expect pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_transcript.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/transcript.py backend/tests/test_clips_transcript.py
git commit -m "feat(clips): add transcript service with YT captions + Whisper fallback"
```

### Task C6: Segmentation + scoring service — TDD

**Files:**
- Create: `backend/services/clips/segment.py`
- Test: `backend/tests/test_clips_segment.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_segment.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import TranscriptCue
from services.clips.segment import segment_and_score, candidate_cap


def test_candidate_cap_short_video():
    # 5 minutes → ceil(5/2) = 3 candidates
    assert candidate_cap(300) == 3


def test_candidate_cap_long_video():
    # 60 minutes → ceil(60/2) = 30 → capped at 20
    assert candidate_cap(3600) == 20


def test_candidate_cap_one_minute_min_one():
    assert candidate_cap(60) == 1


@pytest.mark.asyncio
async def test_segment_and_score_parses_llm_json():
    cues = [TranscriptCue(start=i, end=i + 2, text=f"line {i}") for i in range(0, 60, 2)]
    fake_response = json.dumps([
        {"start_time": 0, "end_time": 30, "hype_score": 9.0,
         "reasoning": "strong hook", "transcript_excerpt": "line 0..."},
        {"start_time": 30, "end_time": 50, "hype_score": 7.0,
         "reasoning": "good payoff", "transcript_excerpt": "line 30..."},
    ])
    with patch("services.clips.segment._ask_llm_for_segments", new=AsyncMock(return_value=fake_response)):
        result = await segment_and_score(cues, duration_seconds=60)
    assert len(result) == 2
    assert result[0].hype_score == 9.0
    assert result[0].duration_seconds == 30


@pytest.mark.asyncio
async def test_segment_caps_to_max():
    cues = [TranscriptCue(start=i, end=i + 1, text=f"l{i}") for i in range(120)]
    items = [
        {"start_time": i * 2, "end_time": i * 2 + 30, "hype_score": 10 - (i * 0.1),
         "reasoning": "x", "transcript_excerpt": "x"}
        for i in range(50)
    ]
    fake_response = json.dumps(items)
    with patch("services.clips.segment._ask_llm_for_segments", new=AsyncMock(return_value=fake_response)):
        # 120 sec / 2 = 1, capped — actually duration=120 → ceil(2)=1, cap=min(20, 1)=1
        result = await segment_and_score(cues, duration_seconds=1200)
    assert len(result) == 10  # 1200s = 20min → cap at min(20, 10) = 10


@pytest.mark.asyncio
async def test_segment_retries_on_invalid_json():
    cues = [TranscriptCue(start=0, end=5, text="hi")]
    valid_response = json.dumps([
        {"start_time": 0, "end_time": 5, "hype_score": 5.0,
         "reasoning": "ok", "transcript_excerpt": "hi"},
    ])
    mock = AsyncMock(side_effect=["not json", "still bad", valid_response])
    with patch("services.clips.segment._ask_llm_for_segments", new=mock):
        result = await segment_and_score(cues, duration_seconds=60)
    assert len(result) == 1
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_segment.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/segment.py
import json
import logging
import math

from services.llm import ask_llm

from .models import CandidateClip, TranscriptCue

logger = logging.getLogger(__name__)


SEGMENT_SYSTEM_PROMPT = """You analyze video transcripts to find the most viral, clip-worthy moments
suitable for vertical Shorts/Reels. You return a JSON array of clip candidates.

Rules:
- Each clip must be between 15 and 60 seconds
- Prefer 20-45 seconds
- Start and end must align with sentence boundaries from the transcript
- hype_score is 0-10 (higher = more viral potential)
- reasoning is one short sentence

Return JSON only, no prose."""


SEGMENT_USER_PROMPT_TEMPLATE = """Transcript with timestamps:
{transcript}

Return a JSON array. Each item: {{
  "start_time": number (seconds),
  "end_time": number (seconds),
  "hype_score": number 0-10,
  "reasoning": string (one sentence),
  "transcript_excerpt": string (the dialogue inside the clip window)
}}"""


def candidate_cap(duration_seconds: int) -> int:
    return min(20, max(1, math.ceil(duration_seconds / 60 / 2)))


def _format_transcript(cues: list[TranscriptCue]) -> str:
    return "\n".join(f"[{c.start:.1f}s] {c.text}" for c in cues)


async def _ask_llm_for_segments(prompt: str) -> str:
    return await ask_llm(
        system=SEGMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )


async def segment_and_score(
    cues: list[TranscriptCue],
    duration_seconds: int,
) -> list[CandidateClip]:
    prompt = SEGMENT_USER_PROMPT_TEMPLATE.format(transcript=_format_transcript(cues))
    last_err: Exception | None = None
    for attempt in range(3):
        raw = await _ask_llm_for_segments(prompt)
        try:
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("```", 2)[1]
                if stripped.startswith("json"):
                    stripped = stripped[4:]
            data = json.loads(stripped)
            candidates = [
                CandidateClip(
                    start_seconds=float(item["start_time"]),
                    end_seconds=float(item["end_time"]),
                    hype_score=float(item["hype_score"]),
                    hype_reasoning=item.get("reasoning", ""),
                    transcript_excerpt=item.get("transcript_excerpt", ""),
                )
                for item in data
            ]
            candidates.sort(key=lambda c: c.hype_score, reverse=True)
            cap = candidate_cap(duration_seconds)
            return candidates[:cap]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_err = e
            logger.warning("Segment LLM parse attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"LLM segment parsing failed after 3 attempts: {last_err}")
```

- [ ] **Step 4: Run — expect pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_segment.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/segment.py backend/tests/test_clips_segment.py
git commit -m "feat(clips): add LLM segmentation and hype scoring"
```

### Task C7: Face detection service — TDD

**Files:**
- Create: `backend/services/clips/face_detection.py`
- Test: `backend/tests/test_clips_face_detection.py`

- [ ] **Step 1: Write failing tests for the smoothing helper**

```python
# backend/tests/test_clips_face_detection.py
from services.clips.face_detection import smooth_x_track, fallback_center


def test_smooth_x_track_simple_average():
    raw = [(0.0, 100), (1.0, 110), (2.0, 105)]
    smoothed = smooth_x_track(raw, window=3)
    assert len(smoothed) == 3
    assert smoothed[1][1] == round((100 + 110 + 105) / 3)


def test_smooth_x_track_handles_empty():
    assert smooth_x_track([], window=3) == []


def test_fallback_center():
    assert fallback_center(video_width=1920, sample_times=[0.0, 1.0, 2.0]) == [
        (0.0, 960), (1.0, 960), (2.0, 960),
    ]
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_face_detection.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/face_detection.py
"""Face-aware cropping for vertical reframe.

Samples ~1 frame per second, runs MediaPipe face detection on each, returns a
smoothed (time, x_center) track. Falls back to image center if no face is
detected. The track is consumed by render_preview/render_final to drive the
ffmpeg crop X offset.
"""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def fallback_center(video_width: int, sample_times: list[float]) -> list[tuple[float, int]]:
    cx = video_width // 2
    return [(t, cx) for t in sample_times]


def smooth_x_track(
    raw: list[tuple[float, int]], window: int = 3
) -> list[tuple[float, int]]:
    if not raw:
        return []
    n = len(raw)
    result: list[tuple[float, int]] = []
    half = window // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        avg = round(sum(p[1] for p in raw[lo:hi]) / (hi - lo))
        result.append((raw[i][0], avg))
    return result


def _video_dimensions(video_path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(video_path),
        ]
    ).decode().strip()
    w, h = out.split("x")
    return int(w), int(h)


def detect_face_track(video_path: Path, duration_seconds: float) -> list[tuple[float, int]]:
    """Sample ~1 fps, return smoothed face center-x track.

    Falls back to image center if MediaPipe finds nothing.
    """
    import cv2
    import mediapipe as mp

    width, _ = _video_dimensions(video_path)
    sample_times = [float(i) for i in range(int(duration_seconds))]
    if not sample_times:
        sample_times = [0.0]

    mp_face = mp.solutions.face_detection
    raw: list[tuple[float, int]] = []
    cap = cv2.VideoCapture(str(video_path))
    try:
        with mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
            for t in sample_times:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = cap.read()
                if not ok:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = detector.process(rgb)
                if not results.detections:
                    continue
                # Largest detection
                best = max(
                    results.detections,
                    key=lambda d: d.location_data.relative_bounding_box.width,
                )
                bbox = best.location_data.relative_bounding_box
                cx = int((bbox.xmin + bbox.width / 2) * width)
                raw.append((t, cx))
    finally:
        cap.release()

    if not raw:
        return fallback_center(width, sample_times)
    return smooth_x_track(raw, window=5)
```

- [ ] **Step 4: Run unit tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_face_detection.py -v
```
Expected: 3 passed. (`detect_face_track` itself is exercised in render_preview integration tests.)

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/face_detection.py backend/tests/test_clips_face_detection.py
git commit -m "feat(clips): add MediaPipe face-aware crop track"
```

### Task C8: Preview render service — TDD

**Files:**
- Create: `backend/services/clips/render_preview.py`
- Test: `backend/tests/test_clips_render_preview.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_render_preview.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import CandidateClip
from services.clips.render_preview import (
    build_crop_filter, render_one_preview,
)


def test_build_crop_filter_centered():
    track = [(0.0, 960), (1.0, 960), (2.0, 960)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    # 9:16 of height 1080 → width 607.5 → 608. center x = 960 - 304 = 656
    assert "crop=608:1080:656:0" in f
    assert "scale=720:1280" in f


def test_build_crop_filter_clamps_left():
    track = [(0.0, 50)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    assert "crop=608:1080:0:0" in f


def test_build_crop_filter_clamps_right():
    track = [(0.0, 1900)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    # max x_offset = 1920 - 608 = 1312
    assert "crop=608:1080:1312:0" in f


@pytest.mark.asyncio
async def test_render_one_preview_orchestrates(tmp_path):
    candidate = CandidateClip(
        start_seconds=10, end_seconds=40, hype_score=8,
        hype_reasoning="x", transcript_excerpt="y",
    )
    source = tmp_path / "source.mp4"
    source.write_bytes(b"")

    with patch("services.clips.render_preview._ffmpeg_cut", new=AsyncMock()) as cut, \
         patch("services.clips.render_preview.detect_face_track", return_value=[(0.0, 960)]) as det, \
         patch("services.clips.render_preview._video_dims", return_value=(1920, 1080)), \
         patch("services.clips.render_preview._ffmpeg_reframe", new=AsyncMock()) as reframe, \
         patch("services.clips.render_preview._ffmpeg_poster", new=AsyncMock()) as poster, \
         patch("services.clips.render_preview.upload_file", new=AsyncMock()) as upload:
        result = await render_one_preview(
            candidate=candidate, candidate_id="c1", source=source,
            user_id="u1", job_id="j1", tmp_dir=tmp_path,
        )

    assert cut.await_count == 1
    assert reframe.await_count == 1
    assert poster.await_count == 1
    assert upload.await_count == 2  # mp4 + jpg
    assert result["preview_storage_key"] == "u1/j1/previews/c1.mp4"
    assert result["preview_poster_key"] == "u1/j1/previews/c1.jpg"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_render_preview.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/render_preview.py
import asyncio
import logging
import subprocess
from pathlib import Path

from .face_detection import detect_face_track
from .models import CandidateClip
from .storage import preview_key, preview_poster_key, upload_file

logger = logging.getLogger(__name__)


def _video_dims(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(path),
        ]
    ).decode().strip()
    w, h = out.split("x")
    return int(w), int(h)


def build_crop_filter(
    track: list[tuple[float, int]],
    video_height: int,
    video_width: int,
) -> str:
    """Return the ffmpeg -vf string for a 9:16 vertical crop.

    Uses the median X from the smoothed track (avoids whipping). Clamps so the
    crop window stays inside the source frame.
    """
    crop_w = (video_height * 9) // 16
    if track:
        xs = sorted(int(p[1]) for p in track)
        cx = xs[len(xs) // 2]
    else:
        cx = video_width // 2
    x_offset = max(0, min(cx - crop_w // 2, video_width - crop_w))
    return f"crop={crop_w}:{video_height}:{x_offset}:0,scale=720:1280"


async def _ffmpeg_cut(source: Path, start: float, end: float, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", str(source),
        "-c", "copy",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg cut failed: {stderr.decode()[:500]}")


async def _ffmpeg_reframe(clip: Path, vf: str, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(clip),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "30", "-preset", "fast",
        "-c:a", "aac", "-b:a", "96k",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg reframe failed: {stderr.decode()[:500]}")


async def _ffmpeg_poster(clip: Path, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(clip),
        "-ss", "0.5",
        "-vframes", "1",
        "-q:v", "3",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg poster failed: {stderr.decode()[:500]}")


async def render_one_preview(
    candidate: CandidateClip,
    candidate_id: str,
    source: Path,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> dict[str, str]:
    """Cut → reframe → poster → upload. Returns storage keys."""
    cut_path = tmp_dir / f"{candidate_id}_cut.mp4"
    preview_path = tmp_dir / f"{candidate_id}_preview.mp4"
    poster_path = tmp_dir / f"{candidate_id}.jpg"

    await _ffmpeg_cut(source, candidate.start_seconds, candidate.end_seconds, cut_path)
    width, height = _video_dims(cut_path)
    track = detect_face_track(cut_path, candidate.duration_seconds)
    vf = build_crop_filter(track=track, video_height=height, video_width=width)

    await _ffmpeg_reframe(cut_path, vf, preview_path)
    await _ffmpeg_poster(preview_path, poster_path)

    p_key = preview_key(user_id, job_id, candidate_id)
    pp_key = preview_poster_key(user_id, job_id, candidate_id)
    await upload_file(preview_path, p_key, "video/mp4")
    await upload_file(poster_path, pp_key, "image/jpeg")

    cut_path.unlink(missing_ok=True)
    return {"preview_storage_key": p_key, "preview_poster_key": pp_key}


async def render_all_previews(
    candidates: list[tuple[str, CandidateClip]],
    source: Path,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
    max_concurrent: int = 3,
    on_progress=None,
) -> list[dict]:
    """Render previews concurrently. on_progress is called with (done, total)."""
    sem = asyncio.Semaphore(max_concurrent)
    total = len(candidates)
    done = 0
    results: list[dict] = []

    async def one(cid: str, cand: CandidateClip):
        nonlocal done
        async with sem:
            try:
                keys = await render_one_preview(
                    cand, cid, source, user_id, job_id, tmp_dir
                )
                results.append({"candidate_id": cid, **keys, "render_failed": False})
            except Exception as e:
                logger.exception("Preview render failed for candidate %s: %s", cid, e)
                results.append({"candidate_id": cid, "render_failed": True})
            finally:
                done += 1
                if on_progress:
                    on_progress(done, total)

    await asyncio.gather(*(one(cid, c) for cid, c in candidates))
    return results
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_render_preview.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/render_preview.py backend/tests/test_clips_render_preview.py
git commit -m "feat(clips): add ffmpeg cut+reframe preview render with face-aware crop"
```

### Task C9: Final render service (with caption burn-in) — TDD

**Files:**
- Create: `backend/services/clips/render_final.py`
- Test: `backend/tests/test_clips_render_final.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_render_final.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import CandidateClip, TranscriptCue
from services.clips.render_final import build_ass_file, render_one_final


def test_build_ass_file_writes_overlapping_cues(tmp_path):
    cues = [
        TranscriptCue(start=0, end=2, text="before clip"),
        TranscriptCue(start=10, end=12, text="hello"),
        TranscriptCue(start=12, end=14, text="world"),
        TranscriptCue(start=50, end=52, text="after clip"),
    ]
    out = tmp_path / "clip.ass"
    build_ass_file(cues, clip_start=10, clip_end=20, out_path=out)
    body = out.read_text()
    assert "hello" in body
    assert "world" in body
    assert "before clip" not in body
    assert "after clip" not in body
    # Times should be normalized to clip start (subtract 10s)
    assert "0:00:00.00" in body  # "hello" starts at 0 in clip-local time


@pytest.mark.asyncio
async def test_render_one_final_orchestrates(tmp_path):
    candidate = CandidateClip(
        start_seconds=10, end_seconds=40, hype_score=8,
        hype_reasoning="x", transcript_excerpt="y",
    )
    cues = [TranscriptCue(start=10, end=12, text="hi")]
    source = tmp_path / "source.mp4"
    source.write_bytes(b"")

    with patch("services.clips.render_final._ffmpeg_render_with_subs", new=AsyncMock()) as render, \
         patch("services.clips.render_final.detect_face_track", return_value=[(0.0, 960)]), \
         patch("services.clips.render_final._video_dims", return_value=(1920, 1080)), \
         patch("services.clips.render_final.upload_file", new=AsyncMock()) as upload:
        key = await render_one_final(
            candidate=candidate, candidate_id="c1", source=source,
            cues=cues, user_id="u1", job_id="j1", tmp_dir=tmp_path,
        )
    assert render.await_count == 1
    assert upload.await_count == 1
    assert key == "u1/j1/finals/c1.mp4"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_render_final.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/render_final.py
import asyncio
import logging
from pathlib import Path

from .face_detection import detect_face_track
from .models import CandidateClip, TranscriptCue
from .render_preview import _video_dims, build_crop_filter
from .storage import final_key, upload_file

logger = logging.getLogger(__name__)


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H80000000,1,1,3,1,2,40,40,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _seconds_to_ass_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass_file(
    cues: list[TranscriptCue],
    clip_start: float,
    clip_end: float,
    out_path: Path,
) -> None:
    """Write a .ass file containing only the cues that overlap [clip_start, clip_end].

    Times are normalized so the clip's first cue starts near 0:00:00.
    """
    lines: list[str] = [ASS_HEADER]
    for cue in cues:
        if cue.end <= clip_start or cue.start >= clip_end:
            continue
        local_start = max(0.0, cue.start - clip_start)
        local_end = min(clip_end - clip_start, cue.end - clip_start)
        text = cue.text.replace("\n", " ").replace(",", "\\,")
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass_ts(local_start)},"
            f"{_seconds_to_ass_ts(local_end)},Default,,0,0,0,,{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


async def _ffmpeg_render_with_subs(
    source: Path, start: float, end: float, vf_with_subs: str, out: Path,
) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", str(source),
        "-vf", vf_with_subs,
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg final render failed: {stderr.decode()[:500]}")


async def render_one_final(
    candidate: CandidateClip,
    candidate_id: str,
    source: Path,
    cues: list[TranscriptCue],
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> str:
    """Render full-quality vertical clip with burned-in captions. Returns storage key."""
    ass_path = tmp_dir / f"{candidate_id}.ass"
    out_path = tmp_dir / f"{candidate_id}_final.mp4"

    build_ass_file(cues, candidate.start_seconds, candidate.end_seconds, ass_path)
    width, height = _video_dims(source)
    track = detect_face_track(source, candidate.duration_seconds)
    crop_scale = build_crop_filter(track=track, video_height=height, video_width=width)
    # ffmpeg subtitles filter takes the .ass path; escape special chars for filter args
    ass_escaped = str(ass_path).replace(":", "\\:").replace("'", "\\'")
    vf = f"{crop_scale},subtitles='{ass_escaped}'"

    await _ffmpeg_render_with_subs(
        source, candidate.start_seconds, candidate.end_seconds, vf, out_path
    )
    key = final_key(user_id, job_id, candidate_id)
    await upload_file(out_path, key, "video/mp4")
    return key
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_render_final.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/render_final.py backend/tests/test_clips_render_final.py
git commit -m "feat(clips): add high-quality final render with burned-in captions"
```

### Task C10: SSE broker — TDD

**Files:**
- Create: `backend/services/clips/sse_broker.py`
- Test: `backend/tests/test_clips_sse_broker.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_sse_broker.py
import asyncio

import pytest

from services.clips.sse_broker import broker


@pytest.mark.asyncio
async def test_publish_then_subscribe_receives():
    job_id = "job-A"
    queue = broker.subscribe(job_id)
    await broker.publish(job_id, {"type": "progress", "pct": 10})
    evt = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert evt["pct"] == 10
    broker.unsubscribe(job_id, queue)


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive():
    job_id = "job-B"
    q1 = broker.subscribe(job_id)
    q2 = broker.subscribe(job_id)
    await broker.publish(job_id, {"type": "ready"})
    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1["type"] == "ready"
    assert e2["type"] == "ready"
    broker.unsubscribe(job_id, q1)
    broker.unsubscribe(job_id, q2)


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_no_error():
    await broker.publish("nobody", {"type": "x"})  # should not raise
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_sse_broker.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/sse_broker.py
"""In-process per-job SSE event broker.

A single FastAPI process hosts the asyncio task that runs the clip pipeline.
Each connected SSE client subscribes via `subscribe(job_id)`, getting back an
asyncio.Queue. The pipeline calls `publish(job_id, event)` after each stage.
On disconnect the client calls `unsubscribe(job_id, queue)`.
"""
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class _Broker:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        if job_id in self._subscribers and queue in self._subscribers[job_id]:
            self._subscribers[job_id].remove(queue)
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    async def publish(self, job_id: str, event: dict) -> None:
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for job %s, dropping event", job_id)


broker = _Broker()
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_sse_broker.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/sse_broker.py backend/tests/test_clips_sse_broker.py
git commit -m "feat(clips): add in-process SSE broker for job progress events"
```

### Task C11: Job runner — pipeline orchestration

**Files:**
- Create: `backend/services/clips/job_runner.py`
- Test: `backend/tests/test_clips_job_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_job_runner.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.clips.job_runner import (
    run_pipeline, register_task, get_task, cancel_task, recover_orphans,
)
from services.clips.models import CandidateClip, TranscriptCue, VideoMetadata


@pytest.mark.asyncio
async def test_register_get_cancel():
    import asyncio
    async def long_running():
        await asyncio.sleep(10)
    task = asyncio.create_task(long_running())
    register_task("j1", task)
    assert get_task("j1") is task
    assert cancel_task("j1") is True
    assert get_task("j1") is None
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_run_pipeline_happy_path(tmp_path):
    job_id = "job-x"
    user_id = "user-x"
    url = "https://youtu.be/x"

    metadata = VideoMetadata(youtube_video_id="x", title="t", duration_seconds=120)
    cues = [TranscriptCue(start=0, end=2, text="hi")]
    candidates = [
        CandidateClip(start_seconds=0, end_seconds=30, hype_score=9,
                      hype_reasoning="r", transcript_excerpt="e"),
    ]

    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
    sb.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "cand-1"}])
    )

    with patch("services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)), \
         patch("services.clips.job_runner.fetch_metadata", new=AsyncMock(return_value=metadata)), \
         patch("services.clips.job_runner.download_source",
               new=AsyncMock(return_value=tmp_path / "source.mp4")), \
         patch("services.clips.job_runner.fetch_transcript", new=AsyncMock(return_value=cues)), \
         patch("services.clips.job_runner.segment_and_score", new=AsyncMock(return_value=candidates)), \
         patch("services.clips.job_runner.render_all_previews",
               new=AsyncMock(return_value=[
                   {"candidate_id": "cand-1",
                    "preview_storage_key": "k1", "preview_poster_key": "k1.jpg",
                    "render_failed": False},
               ])), \
         patch("services.clips.job_runner.broker") as br:
        await run_pipeline(job_id=job_id, user_id=user_id, url=url, tmp_dir=tmp_path)

    # Should have published progress + ready events
    assert br.publish.await_count >= 2


@pytest.mark.asyncio
async def test_recover_orphans_marks_processing_as_failed():
    sb = MagicMock()
    sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "j1"}, {"id": "j2"}])
    )
    with patch("services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)):
        n = await recover_orphans()
    assert n == 2
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_job_runner.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/job_runner.py
"""Pipeline orchestration: run_pipeline runs all stages in sequence, updates
clip_jobs row, publishes SSE events, and inserts clip_candidates rows.

Maintains a registry of in-flight asyncio tasks for cancellation.
"""
import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from config import settings
from services.supabase_pool import get_async_client

from .download import download_source
from .metadata import fetch_metadata
from .render_preview import render_all_previews
from .segment import segment_and_score
from .sse_broker import broker
from .transcript import fetch_transcript

logger = logging.getLogger(__name__)


_active_tasks: dict[str, asyncio.Task] = {}


def register_task(job_id: str, task: asyncio.Task) -> None:
    _active_tasks[job_id] = task


def get_task(job_id: str) -> asyncio.Task | None:
    task = _active_tasks.get(job_id)
    if task and task.done():
        _active_tasks.pop(job_id, None)
        return None
    return task


def cancel_task(job_id: str) -> bool:
    task = _active_tasks.pop(job_id, None)
    if task is None:
        return False
    task.cancel()
    return True


async def _update_job(job_id: str, fields: dict) -> None:
    sb = await get_async_client()
    await sb.table("clip_jobs").update(fields).eq("id", job_id).execute()


async def _publish_progress(job_id: str, stage: str, pct: int) -> None:
    await broker.publish(job_id, {"type": "progress", "stage": stage, "pct": pct})


async def run_pipeline(
    job_id: str,
    user_id: str,
    url: str,
    tmp_dir: Path,
) -> None:
    sb = await get_async_client()
    job_tmp = tmp_dir / job_id
    job_tmp.mkdir(parents=True, exist_ok=True)

    try:
        await _update_job(job_id, {"status": "processing", "current_stage": "metadata", "progress_pct": 1})
        await _publish_progress(job_id, "metadata", 1)
        metadata = await fetch_metadata(url)
        await _update_job(job_id, {
            "title": metadata.title,
            "duration_seconds": metadata.duration_seconds,
            "youtube_video_id": metadata.youtube_video_id,
            "current_stage": "download",
            "progress_pct": 5,
        })
        await _publish_progress(job_id, "download", 5)

        source = await download_source(url=url, user_id=user_id, job_id=job_id, tmp_dir=job_tmp)
        await _update_job(job_id, {"current_stage": "transcribe", "progress_pct": 25,
                                    "source_storage_key": f"{user_id}/{job_id}/source.mp4"})
        await _publish_progress(job_id, "transcribe", 25)

        # Extract audio for whisper fallback
        audio_path = job_tmp / "audio.mp3"
        audio_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "libmp3lame", "-q:a", "5",
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await audio_proc.wait()

        cues = await fetch_transcript(url, audio_path, job_tmp)
        await _update_job(job_id, {"current_stage": "segment", "progress_pct": 45})
        await _publish_progress(job_id, "segment", 45)

        candidates = await segment_and_score(cues, duration_seconds=metadata.duration_seconds)
        await _update_job(job_id, {"current_stage": "preview_render", "progress_pct": 55})
        await _publish_progress(job_id, "preview_render", 55)

        # Pre-create candidate rows so we have IDs before render
        candidate_ids: list[tuple[str, object]] = []
        for c in candidates:
            cid = str(uuid.uuid4())
            await sb.table("clip_candidates").insert({
                "id": cid,
                "job_id": job_id,
                "start_seconds": c.start_seconds,
                "end_seconds": c.end_seconds,
                "duration_seconds": c.duration_seconds,
                "hype_score": c.hype_score,
                "hype_reasoning": c.hype_reasoning,
                "transcript_excerpt": c.transcript_excerpt,
            }).execute()
            candidate_ids.append((cid, c))

        total = len(candidate_ids)

        def on_progress(done: int, total_: int):
            pct = 55 + int(40 * (done / total_)) if total_ else 95
            asyncio.create_task(_publish_progress(job_id, "preview_render", pct))

        results = await render_all_previews(
            candidates=candidate_ids,
            source=source,
            user_id=user_id,
            job_id=job_id,
            tmp_dir=job_tmp,
            on_progress=on_progress,
        )

        succeeded = [r for r in results if not r.get("render_failed")]
        if total > 0 and len(succeeded) / total < 0.5:
            raise RuntimeError(f"Too many candidate renders failed ({len(succeeded)}/{total})")

        for r in results:
            updates = {"render_failed": r.get("render_failed", False)}
            if not r.get("render_failed"):
                updates["preview_storage_key"] = r["preview_storage_key"]
                updates["preview_poster_key"] = r["preview_poster_key"]
            await sb.table("clip_candidates").update(updates).eq("id", r["candidate_id"]).execute()

        await _update_job(job_id, {
            "status": "ready",
            "current_stage": "await_selection",
            "progress_pct": 100,
        })
        # Fetch final candidate list for SSE payload
        cand_res = await (
            sb.table("clip_candidates").select("*").eq("job_id", job_id).order("hype_score", desc=True).execute()
        )
        await broker.publish(job_id, {"type": "ready", "candidates": cand_res.data})

    except asyncio.CancelledError:
        await _update_job(job_id, {"status": "failed", "error_message": "Cancelled by user"})
        await broker.publish(job_id, {"type": "error", "message": "Cancelled by user"})
        raise
    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        await _update_job(job_id, {"status": "failed", "error_message": str(e)[:500]})
        await broker.publish(job_id, {"type": "error", "message": str(e)})
    finally:
        _active_tasks.pop(job_id, None)
        if job_tmp.exists():
            shutil.rmtree(job_tmp, ignore_errors=True)


async def recover_orphans() -> int:
    """On app startup, mark any processing/rendering rows as failed."""
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .update({"status": "failed", "error_message": "Server restart"})
        .in_("status", ["processing", "rendering"])
        .execute()
    )
    return len(res.data or [])
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_job_runner.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/job_runner.py backend/tests/test_clips_job_runner.py
git commit -m "feat(clips): add pipeline orchestrator with task registry and crash recovery"
```

### Task C12: Cleanup service — TDD

**Files:**
- Create: `backend/services/clips/cleanup.py`
- Test: `backend/tests/test_clips_cleanup.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_cleanup.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.clips.cleanup import sweep_expired


@pytest.mark.asyncio
async def test_sweep_deletes_source_and_previews_marks_expired():
    sb = MagicMock()
    expired_jobs = [
        {"id": "j1", "user_id": "u1", "source_storage_key": "u1/j1/source.mp4"},
    ]
    candidates = [
        {"id": "c1", "preview_storage_key": "u1/j1/previews/c1.mp4",
         "preview_poster_key": "u1/j1/previews/c1.jpg",
         "final_storage_key": None},
    ]
    sb.table.return_value.select.return_value.lt.return_value.neq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=expired_jobs)
    )
    sb.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=candidates)
    )
    sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=expired_jobs)
    )
    sb.table.return_value.delete.return_value.eq.return_value.is_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "c1"}])
    )

    with patch("services.clips.cleanup.get_async_client", new=AsyncMock(return_value=sb)), \
         patch("services.clips.cleanup.remove_keys", new=AsyncMock()) as remove:
        result = await sweep_expired()

    # Should remove 3 keys: source + preview mp4 + preview jpg
    remove_call_keys = remove.await_args.args[0]
    assert "u1/j1/source.mp4" in remove_call_keys
    assert "u1/j1/previews/c1.mp4" in remove_call_keys
    assert "u1/j1/previews/c1.jpg" in remove_call_keys
    assert result["jobs_expired"] == 1
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_cleanup.py -v
```
Expected: import error.

- [ ] **Step 3: Implement**

```python
# backend/services/clips/cleanup.py
"""TTL retention sweep.

Triggered by an external scheduler hitting POST /api/clips/cleanup with the
service token. Removes source MP4s and unselected preview files for any job
past expires_at, deletes orphan candidate rows, and marks the job 'expired'.
Final renders are NEVER auto-deleted.
"""
import logging

from services.supabase_pool import get_async_client

from .storage import remove_keys

logger = logging.getLogger(__name__)


async def sweep_expired() -> dict:
    sb = await get_async_client()
    expired = await (
        sb.table("clip_jobs")
        .select("id, user_id, source_storage_key")
        .lt("expires_at", "now()")
        .neq("status", "expired")
        .execute()
    )
    expired_jobs = expired.data or []
    if not expired_jobs:
        return {"jobs_expired": 0, "files_removed": 0}

    job_ids = [j["id"] for j in expired_jobs]
    cands = await (
        sb.table("clip_candidates")
        .select("id, preview_storage_key, preview_poster_key, final_storage_key")
        .in_("job_id", job_ids)
        .execute()
    )
    keys_to_remove: list[str] = []
    for j in expired_jobs:
        if j.get("source_storage_key"):
            keys_to_remove.append(j["source_storage_key"])
    for c in cands.data or []:
        if c.get("preview_storage_key"):
            keys_to_remove.append(c["preview_storage_key"])
        if c.get("preview_poster_key"):
            keys_to_remove.append(c["preview_poster_key"])

    await remove_keys(keys_to_remove)

    # Delete orphan candidate rows (no final render)
    await (
        sb.table("clip_candidates")
        .delete()
        .in_("job_id", job_ids)
        .is_("final_storage_key", "null")
        .execute()
    )

    await (
        sb.table("clip_jobs")
        .update({"status": "expired", "source_storage_key": None})
        .in_("id", job_ids)
        .execute()
    )

    return {"jobs_expired": len(expired_jobs), "files_removed": len(keys_to_remove)}
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_cleanup.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/clips/cleanup.py backend/tests/test_clips_cleanup.py
git commit -m "feat(clips): add TTL retention sweep service"
```

---

## Phase D — Backend routes (TDD)

### Task D1: Routes module — preflight + create job

**Files:**
- Create: `backend/routes/clips.py`
- Test: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_clips_routes.py
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
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_routes.py -v
```
Expected: import / 404 errors (router not registered yet — that comes in Task D7).

- [ ] **Step 3: Implement (initial routes file)**

```python
# backend/routes/clips.py
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from config import settings
from services.clips.cleanup import sweep_expired
from services.clips.job_runner import (
    cancel_task, register_task, run_pipeline,
)
from services.clips.metadata import fetch_metadata
from services.clips.sse_broker import broker
from services.clips.storage import signed_url
from services.supabase_pool import get_async_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clips")


class PreflightRequest(BaseModel):
    youtube_url: str


class CreateJobRequest(BaseModel):
    youtube_url: str


@router.post("/jobs/preflight")
async def preflight(req: PreflightRequest, user_id: str = Depends(get_current_user)):
    try:
        metadata = await fetch_metadata(req.youtube_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch metadata: {e}")
    return {
        "youtube_video_id": metadata.youtube_video_id,
        "title": metadata.title,
        "duration_seconds": metadata.duration_seconds,
    }


@router.post("/jobs", status_code=201)
async def create_job(req: CreateJobRequest, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .insert({"user_id": user_id, "youtube_url": req.youtube_url, "status": "pending"})
        .execute()
    )
    job = res.data[0]
    tmp_dir = Path(settings.clips_tmp_dir)
    task = asyncio.create_task(run_pipeline(
        job_id=job["id"], user_id=user_id, url=req.youtube_url, tmp_dir=tmp_dir,
    ))
    register_task(job["id"], task)
    return job
```

- [ ] **Step 4: Register the router (proceed to D7 if want green; or run tests now and fail on 404)**

For now, append to `backend/main.py`:
```python
from routes.clips import router as clips_router
app.include_router(clips_router)
```
(This will be redone in Task D7 with the lifespan changes — simplest to include now.)

- [ ] **Step 5: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_routes.py::test_preflight_returns_metadata tests/test_clips_routes.py::test_preflight_rejects_too_long tests/test_clips_routes.py::test_create_job_inserts_and_starts_task -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/clips.py backend/tests/test_clips_routes.py backend/main.py
git commit -m "feat(clips): add preflight and create-job endpoints"
```

### Task D2: List jobs and get job detail endpoints — TDD

**Files:**
- Modify: `backend/routes/clips.py`
- Modify: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Append failing tests**

```python
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
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && .venv/bin/python -m pytest tests/test_clips_routes.py::test_list_jobs tests/test_clips_routes.py::test_get_job_returns_with_candidates tests/test_clips_routes.py::test_get_job_404_when_not_found -v
```
Expected: failures (endpoints not implemented).

- [ ] **Step 3: Append routes**

```python
@router.get("/jobs")
async def list_jobs(user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .select("id, youtube_url, title, duration_seconds, status, progress_pct, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    cand_res = await (
        sb.table("clip_candidates")
        .select("*")
        .eq("job_id", job_id)
        .order("hype_score", desc=True)
        .execute()
    )
    return {**job_res.data, "candidates": cand_res.data}
```

- [ ] **Step 4: Run tests**

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clips.py backend/tests/test_clips_routes.py
git commit -m "feat(clips): add list-jobs and get-job-detail endpoints"
```

### Task D3: SSE events endpoint — TDD

**Files:**
- Modify: `backend/routes/clips.py`
- Modify: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Append failing test**

```python
def test_sse_events_streams_published_events(mock_sb):
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    job_chain.execute = AsyncMock(return_value=MagicMock(data={"id": "j1", "user_id": "user-123"}))

    with _patch_client(mock_sb):
        # Publish an event before the request so the queue has data immediately
        import asyncio
        from services.clips.sse_broker import broker as live_broker
        asyncio.get_event_loop().run_until_complete(
            live_broker.publish("j1", {"type": "progress", "stage": "metadata", "pct": 5})
        )
        with client.stream("GET", "/api/clips/jobs/j1/events") as resp:
            assert resp.status_code == 200
            # Read first chunk
            chunks = []
            for chunk in resp.iter_text():
                chunks.append(chunk)
                if any("progress" in c for c in chunks):
                    break
            assert any("progress" in c for c in chunks)
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Append route**

```python
@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("id").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = broker.subscribe(job_id)

    async def event_stream():
        import json
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("ready", "error", "render_complete_all"):
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # SSE comment line keeps connection alive
        finally:
            broker.unsubscribe(job_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test**

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clips.py backend/tests/test_clips_routes.py
git commit -m "feat(clips): add SSE events endpoint with heartbeat"
```

### Task D4: Cancel endpoint — TDD

**Files:**
- Modify: `backend/routes/clips.py`
- Modify: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Append failing test**

```python
def test_cancel_job(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data={"id": "j1", "status": "processing"})
    )
    mock_sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
    with _patch_client(mock_sb), patch("routes.clips.cancel_task", return_value=True):
        r = client.post("/api/clips/jobs/j1/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Append route**

```python
@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("id, status").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    cancel_task(job_id)
    await (
        sb.table("clip_jobs")
        .update({"status": "failed", "error_message": "Cancelled by user"})
        .eq("id", job_id)
        .execute()
    )
    return {"status": "cancelled"}
```

- [ ] **Step 4: Run test**

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clips.py backend/tests/test_clips_routes.py
git commit -m "feat(clips): add job cancellation endpoint"
```

### Task D5: Final-render endpoint — TDD

**Files:**
- Modify: `backend/routes/clips.py`
- Modify: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Append failing test**

```python
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
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Append route**

```python
class RenderRequest(BaseModel):
    candidate_ids: list[str]


@router.post("/jobs/{job_id}/render", status_code=202)
async def render_finals(
    job_id: str,
    req: RenderRequest,
    user_id: str = Depends(get_current_user),
):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_res.data["status"] not in ("ready", "completed"):
        raise HTTPException(status_code=400, detail=f"Cannot render — job status is {job_res.data['status']}")

    await (
        sb.table("clip_candidates")
        .update({"selected": True})
        .in_("id", req.candidate_ids)
        .execute()
    )
    await (
        sb.table("clip_jobs")
        .update({"status": "rendering", "current_stage": "final_render", "progress_pct": 0})
        .eq("id", job_id)
        .execute()
    )

    from services.clips.job_runner import run_finals_pipeline  # added in next task
    tmp_dir = Path(settings.clips_tmp_dir)
    task = asyncio.create_task(run_finals_pipeline(
        job_id=job_id, user_id=user_id, candidate_ids=req.candidate_ids, tmp_dir=tmp_dir,
    ))
    register_task(job_id, task)
    return {"status": "rendering", "candidate_ids": req.candidate_ids}
```

- [ ] **Step 4: Add `run_finals_pipeline` to `job_runner.py`**

```python
# Append to backend/services/clips/job_runner.py
from .render_final import render_one_final
from .storage import download_file
from .transcript import parse_vtt


async def run_finals_pipeline(
    job_id: str,
    user_id: str,
    candidate_ids: list[str],
    tmp_dir: Path,
) -> None:
    sb = await get_async_client()
    job_tmp = tmp_dir / f"{job_id}_finals"
    job_tmp.mkdir(parents=True, exist_ok=True)

    try:
        # Pull source + candidates + cues
        job_res = await sb.table("clip_jobs").select("*").eq("id", job_id).single().execute()
        cands_res = await (
            sb.table("clip_candidates").select("*").in_("id", candidate_ids).execute()
        )
        candidates_data = cands_res.data or []

        source = job_tmp / "source.mp4"
        await download_file(job_res.data["source_storage_key"], source)

        # We previously didn't persist cues — re-fetch transcript for accuracy
        from .transcript import fetch_transcript
        audio_path = job_tmp / "audio.mp3"
        audio_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "libmp3lame", "-q:a", "5",
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await audio_proc.wait()
        cues = await fetch_transcript(job_res.data["youtube_url"], audio_path, job_tmp)

        total = len(candidates_data)
        for i, cand_row in enumerate(candidates_data):
            from .models import CandidateClip
            candidate = CandidateClip(
                start_seconds=cand_row["start_seconds"],
                end_seconds=cand_row["end_seconds"],
                hype_score=cand_row["hype_score"],
                hype_reasoning=cand_row.get("hype_reasoning") or "",
                transcript_excerpt=cand_row.get("transcript_excerpt") or "",
            )
            try:
                key = await render_one_final(
                    candidate=candidate,
                    candidate_id=cand_row["id"],
                    source=source,
                    cues=cues,
                    user_id=user_id,
                    job_id=job_id,
                    tmp_dir=job_tmp,
                )
                signed = await signed_url_helper(key)
                await sb.table("clip_candidates").update({"final_storage_key": key}).eq("id", cand_row["id"]).execute()
                await broker.publish(job_id, {
                    "type": "render_complete",
                    "candidate_id": cand_row["id"],
                    "signed_url": signed,
                })
            except Exception as e:
                logger.exception("Final render failed for %s: %s", cand_row["id"], e)
                await broker.publish(job_id, {
                    "type": "render_failed",
                    "candidate_id": cand_row["id"],
                    "error": str(e)[:200],
                })
            await broker.publish(job_id, {
                "type": "render_progress",
                "candidate_id": cand_row["id"],
                "pct": int(100 * (i + 1) / total),
            })

        await sb.table("clip_jobs").update({
            "status": "completed", "current_stage": "done", "progress_pct": 100,
        }).eq("id", job_id).execute()
        await broker.publish(job_id, {"type": "render_complete_all"})

    except asyncio.CancelledError:
        await sb.table("clip_jobs").update({
            "status": "failed", "error_message": "Cancelled during final render",
        }).eq("id", job_id).execute()
        raise
    except Exception as e:
        logger.exception("Finals pipeline failed for %s", job_id)
        await sb.table("clip_jobs").update({
            "status": "failed", "error_message": str(e)[:500],
        }).eq("id", job_id).execute()
    finally:
        _active_tasks.pop(job_id, None)
        import shutil
        shutil.rmtree(job_tmp, ignore_errors=True)


async def signed_url_helper(key: str) -> str:
    from .storage import signed_url
    return await signed_url(key)
```

- [ ] **Step 5: Run test**

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/clips.py backend/services/clips/job_runner.py backend/tests/test_clips_routes.py
git commit -m "feat(clips): add finals render endpoint and pipeline"
```

### Task D6: Signed URL helper for previews + cleanup endpoint — TDD

**Files:**
- Modify: `backend/routes/clips.py`
- Modify: `backend/tests/test_clips_routes.py`

- [ ] **Step 1: Append failing tests**

```python
def test_get_candidate_signed_url(mock_sb):
    chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    chain.execute = AsyncMock(return_value=MagicMock(data={
        "id": "c1",
        "preview_storage_key": "user-123/j1/previews/c1.mp4",
    }))
    # Also need parent job to verify ownership
    job_chain = mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value
    # The above already covers the candidate; ownership done via RLS join in real
    with _patch_client(mock_sb), \
         patch("routes.clips.signed_url", new=AsyncMock(return_value="https://signed/url")):
        r = client.get("/api/clips/candidates/c1/preview-url")
    assert r.status_code == 200
    assert r.json()["url"] == "https://signed/url"


def test_cleanup_requires_token():
    r = client.post("/api/clips/cleanup", headers={"X-Service-Token": "wrong"})
    assert r.status_code == 401


def test_cleanup_with_correct_token(mock_sb, monkeypatch):
    monkeypatch.setattr("config.settings.clips_cleanup_token", "secret")
    with patch("routes.clips.sweep_expired", new=AsyncMock(return_value={"jobs_expired": 1, "files_removed": 3})):
        r = client.post("/api/clips/cleanup", headers={"X-Service-Token": "secret"})
    assert r.status_code == 200
    assert r.json() == {"jobs_expired": 1, "files_removed": 3}
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Append routes**

```python
@router.get("/candidates/{candidate_id}/preview-url")
async def get_preview_url(candidate_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    # RLS will ensure the candidate belongs to a job owned by user_id
    res = await (
        sb.table("clip_candidates")
        .select("id, preview_storage_key, job_id")
        .eq("id", candidate_id)
        .single()
        .execute()
    )
    if not res.data or not res.data.get("preview_storage_key"):
        raise HTTPException(status_code=404, detail="Preview not available")
    url = await signed_url(res.data["preview_storage_key"], ttl_seconds=3600)
    return {"url": url}


@router.get("/candidates/{candidate_id}/final-url")
async def get_final_url(candidate_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_candidates")
        .select("id, final_storage_key")
        .eq("id", candidate_id)
        .single()
        .execute()
    )
    if not res.data or not res.data.get("final_storage_key"):
        raise HTTPException(status_code=404, detail="Final not rendered")
    url = await signed_url(res.data["final_storage_key"], ttl_seconds=3600)
    return {"url": url}


@router.post("/cleanup")
async def cleanup_endpoint(x_service_token: str = Header(default="")):
    if not settings.clips_cleanup_token or x_service_token != settings.clips_cleanup_token:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return await sweep_expired()
```

- [ ] **Step 4: Run tests**

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clips.py backend/tests/test_clips_routes.py
git commit -m "feat(clips): add preview/final signed-URL and cleanup endpoints"
```

### Task D7: Register router and crash-recovery startup hook

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add to lifespan**

In `backend/main.py`, modify the `lifespan` async context manager to call `recover_orphans` on startup:

```python
@asynccontextmanager
async def lifespan(app):
    if settings.database_url:
        from services.thumbnail_graph import get_thumbnail_graph
        await get_thumbnail_graph()
        logger.info("LangGraph thumbnail graph initialized with PostgresSaver")
    else:
        logger.warning("DATABASE_URL not set — thumbnail graph will use fallback")

    # Clip job recovery
    try:
        from services.clips.job_runner import recover_orphans
        n = await recover_orphans()
        if n:
            logger.info("Recovered %d orphaned clip jobs (marked failed)", n)
    except Exception:
        logger.exception("Clip orphan recovery failed (non-fatal)")

    yield
```

And confirm the router import + include lines are present (they were added in D1):

```python
from routes.clips import router as clips_router
# ...
app.include_router(clips_router)
```

- [ ] **Step 2: Smoke test full backend test suite**

```bash
cd backend && .venv/bin/python -m pytest -v
```
Expected: all clips tests pass; existing tests untouched.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(clips): register router and add crash-recovery startup hook"
```

---

## Phase E — Frontend

### Task E1: Types + API client

**Files:**
- Create: `frontend/src/types/clips.ts`
- Create: `frontend/src/api/clips.ts`

- [ ] **Step 1: Create `types/clips.ts`**

```typescript
export type ClipJobStatus =
  | "pending" | "processing" | "ready" | "rendering" | "completed" | "failed" | "expired";

export type ClipJobStage =
  | "metadata" | "download" | "transcribe" | "segment"
  | "preview_render" | "await_selection" | "final_render" | "done";

export interface ClipJobSummary {
  id: string;
  youtube_url: string;
  title: string | null;
  duration_seconds: number | null;
  status: ClipJobStatus;
  progress_pct: number;
  created_at: string;
}

export interface ClipCandidate {
  id: string;
  job_id: string;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  hype_score: number;
  hype_reasoning: string | null;
  transcript_excerpt: string | null;
  preview_storage_key: string | null;
  preview_poster_key: string | null;
  final_storage_key: string | null;
  selected: boolean;
  render_failed: boolean;
}

export interface ClipJob extends ClipJobSummary {
  current_stage: ClipJobStage | null;
  error_message: string | null;
  candidates: ClipCandidate[];
}

export type JobEvent =
  | { type: "progress"; stage: ClipJobStage; pct: number }
  | { type: "ready"; candidates: ClipCandidate[] }
  | { type: "render_progress"; candidate_id: string; pct: number }
  | { type: "render_complete"; candidate_id: string; signed_url: string }
  | { type: "render_failed"; candidate_id: string; error: string }
  | { type: "render_complete_all" }
  | { type: "error"; message: string };

export interface PreflightResponse {
  youtube_video_id: string;
  title: string;
  duration_seconds: number;
}
```

- [ ] **Step 2: Create `api/clips.ts`**

```typescript
import { ClipJob, ClipJobSummary, PreflightResponse } from "../types/clips";
import { supabase } from "../lib/supabase";

async function authHeader(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession();
  return { Authorization: `Bearer ${data.session?.access_token ?? ""}` };
}

async function jsonFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = { "Content-Type": "application/json", ...(await authHeader()), ...(init.headers || {}) };
  const r = await fetch(url, { ...init, headers });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `${r.status}`);
  return r.json();
}

export const clipsApi = {
  preflight: (youtube_url: string) =>
    jsonFetch<PreflightResponse>("/api/clips/jobs/preflight", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
    }),

  createJob: (youtube_url: string) =>
    jsonFetch<ClipJobSummary>("/api/clips/jobs", {
      method: "POST",
      body: JSON.stringify({ youtube_url }),
    }),

  listJobs: () => jsonFetch<ClipJobSummary[]>("/api/clips/jobs"),

  getJob: (id: string) => jsonFetch<ClipJob>(`/api/clips/jobs/${id}`),

  cancel: (id: string) =>
    jsonFetch<{ status: string }>(`/api/clips/jobs/${id}/cancel`, { method: "POST" }),

  render: (id: string, candidate_ids: string[]) =>
    jsonFetch<{ status: string }>(`/api/clips/jobs/${id}/render`, {
      method: "POST",
      body: JSON.stringify({ candidate_ids }),
    }),

  previewUrl: (candidateId: string) =>
    jsonFetch<{ url: string }>(`/api/clips/candidates/${candidateId}/preview-url`),

  finalUrl: (candidateId: string) =>
    jsonFetch<{ url: string }>(`/api/clips/candidates/${candidateId}/final-url`),
};
```

- [ ] **Step 3: Verify TS compiles**

```bash
cd frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/clips.ts frontend/src/api/clips.ts
git commit -m "feat(clips): add frontend types and API client"
```

### Task E2: useClipJobSSE hook

**Files:**
- Create: `frontend/src/hooks/useClipJobSSE.ts`

- [ ] **Step 1: Implement**

```typescript
import { useEffect, useRef } from "react";
import { JobEvent } from "../types/clips";
import { supabase } from "../lib/supabase";

export function useClipJobSSE(
  jobId: string | null,
  onEvent: (e: JobEvent) => void,
) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let abort: AbortController | null = null;

    (async () => {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? "";
      abort = new AbortController();
      try {
        const resp = await fetch(`/api/clips/jobs/${jobId}/events`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: abort.signal,
        });
        if (!resp.ok || !resp.body) return;
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const events = buf.split("\n\n");
          buf = events.pop() ?? "";
          for (const block of events) {
            const dataLine = block.split("\n").find(l => l.startsWith("data: "));
            if (!dataLine) continue;
            try {
              const parsed: JobEvent = JSON.parse(dataLine.slice(6));
              handlerRef.current(parsed);
            } catch (e) { /* heartbeat or malformed; ignore */ }
          }
        }
      } catch (e) { /* aborted */ }
    })();

    return () => { cancelled = true; abort?.abort(); };
  }, [jobId]);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useClipJobSSE.ts
git commit -m "feat(clips): add SSE subscription hook"
```

### Task E3: NewJobForm

**Files:**
- Create: `frontend/src/components/clips/NewJobForm.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useState } from "react";
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  TextField, Typography, Alert,
} from "@mui/material";
import { clipsApi } from "../../api/clips";

export default function NewJobForm({ onCreated }: { onCreated: (jobId: string) => void }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ duration: number; title: string } | null>(null);

  async function submit() {
    setError(null);
    setLoading(true);
    try {
      const meta = await clipsApi.preflight(url);
      if (meta.duration_seconds > 1800) {
        setConfirm({ duration: meta.duration_seconds, title: meta.title });
      } else {
        await create();
      }
    } catch (e: any) { setError(e.message || "Preflight failed"); }
    finally { setLoading(false); }
  }

  async function create() {
    setLoading(true);
    try {
      const job = await clipsApi.createJob(url);
      onCreated(job.id);
      setUrl("");
      setConfirm(null);
    } catch (e: any) { setError(e.message || "Failed to create job"); }
    finally { setLoading(false); }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField
          fullWidth size="small" placeholder="YouTube URL"
          value={url} onChange={e => setUrl(e.target.value)} disabled={loading}
        />
        <Button variant="contained" onClick={submit} disabled={loading || !url}>
          {loading ? "…" : "Generate clips"}
        </Button>
      </Box>
      <Typography variant="caption" color="text.secondary">
        ≤60 min videos. Processing takes ~2 min per minute of video.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Dialog open={!!confirm} onClose={() => setConfirm(null)}>
        <DialogTitle>Long video</DialogTitle>
        <DialogContent>
          {confirm && (
            <Typography>
              "{confirm.title}" is {Math.round(confirm.duration / 60)} min long. Processing will take ~{Math.round(confirm.duration / 30)} min and use significant compute. Continue?
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>Cancel</Button>
          <Button onClick={create} variant="contained">Continue</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

- [ ] **Step 2: Build check**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/clips/NewJobForm.tsx
git commit -m "feat(clips): add NewJobForm with preflight + 30-min warning modal"
```

### Task E4: JobProgressPanel

**Files:**
- Create: `frontend/src/components/clips/JobProgressPanel.tsx`

- [ ] **Step 1: Implement**

```tsx
import { Box, LinearProgress, Typography, Button } from "@mui/material";
import { ClipJob } from "../../types/clips";

const STAGE_LABELS: Record<string, string> = {
  metadata: "Reading video metadata…",
  download: "Downloading video…",
  transcribe: "Transcribing audio…",
  segment: "Scoring clip-worthy moments…",
  preview_render: "Rendering preview clips…",
  final_render: "Rendering final clips…",
};

export default function JobProgressPanel({
  job, onCancel,
}: { job: ClipJob; onCancel: () => void }) {
  const label = STAGE_LABELS[job.current_stage ?? ""] ?? "Working…";
  return (
    <Box sx={{ p: 4, maxWidth: 600, mx: "auto" }}>
      <Typography variant="h6" gutterBottom>{job.title || job.youtube_url}</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>{label}</Typography>
      <LinearProgress variant="determinate" value={job.progress_pct} sx={{ my: 2 }} />
      <Typography variant="caption">{job.progress_pct}%</Typography>
      <Box sx={{ mt: 2 }}>
        <Button onClick={onCancel} color="error" variant="outlined" size="small">
          Cancel
        </Button>
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/clips/JobProgressPanel.tsx
git commit -m "feat(clips): add JobProgressPanel"
```

### Task E5: ClipCard + ClipPreviewModal

**Files:**
- Create: `frontend/src/components/clips/ClipCard.tsx`
- Create: `frontend/src/components/clips/ClipPreviewModal.tsx`

- [ ] **Step 1: Implement ClipCard**

```tsx
import { useEffect, useRef, useState } from "react";
import { Box, Card, Checkbox, Chip, Typography } from "@mui/material";
import { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function ClipCard({
  candidate, selected, onToggleSelect, onClick,
}: {
  candidate: ClipCandidate;
  selected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let mounted = true;
    clipsApi.previewUrl(candidate.id)
      .then(({ url }) => { if (mounted) setPreviewUrl(url); })
      .catch(() => {});
    return () => { mounted = false; };
  }, [candidate.id]);

  return (
    <Card
      onClick={onClick}
      sx={{ position: "relative", cursor: "pointer", overflow: "hidden", aspectRatio: "9 / 16" }}
      onMouseEnter={() => videoRef.current?.play().catch(() => {})}
      onMouseLeave={() => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime = 0; } }}
    >
      {previewUrl ? (
        <video
          ref={videoRef}
          src={previewUrl}
          muted
          loop
          playsInline
          preload="metadata"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <Box sx={{ width: "100%", height: "100%", bgcolor: "rgba(255,255,255,0.04)" }} />
      )}
      <Chip
        label={candidate.hype_score.toFixed(1)}
        size="small"
        color="primary"
        sx={{ position: "absolute", top: 8, left: 8, fontWeight: 600 }}
      />
      <Checkbox
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={onToggleSelect}
        sx={{ position: "absolute", top: 0, right: 0, color: "white",
          "&.Mui-checked": { color: "#a78bfa" } }}
      />
      <Box sx={{ position: "absolute", bottom: 0, left: 0, right: 0,
                 p: 1, bgcolor: "rgba(0,0,0,0.6)" }}>
        <Typography variant="caption" sx={{ color: "white" }}>
          {formatTime(candidate.start_seconds)} → {formatTime(candidate.end_seconds)} · {Math.round(candidate.duration_seconds)}s
        </Typography>
        {candidate.hype_reasoning && (
          <Typography variant="caption" sx={{ color: "rgba(255,255,255,0.7)", display: "block" }}>
            {candidate.hype_reasoning}
          </Typography>
        )}
      </Box>
    </Card>
  );
}
```

- [ ] **Step 2: Implement ClipPreviewModal**

```tsx
import { Dialog, IconButton, Box } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useEffect, useState } from "react";
import { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

export default function ClipPreviewModal({
  candidate, open, onClose,
}: { candidate: ClipCandidate | null; open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate) return;
    clipsApi.previewUrl(candidate.id).then(r => setUrl(r.url));
  }, [candidate]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <Box sx={{ position: "relative", bgcolor: "black" }}>
        <IconButton
          onClick={onClose}
          sx={{ position: "absolute", top: 8, right: 8, color: "white", zIndex: 1 }}
        >
          <CloseIcon />
        </IconButton>
        {url && <video src={url} controls autoPlay style={{ width: "100%" }} />}
      </Box>
    </Dialog>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/clips/ClipCard.tsx frontend/src/components/clips/ClipPreviewModal.tsx
git commit -m "feat(clips): add ClipCard and ClipPreviewModal"
```

### Task E6: ClipGrid + SelectionBar

**Files:**
- Create: `frontend/src/components/clips/ClipGrid.tsx`
- Create: `frontend/src/components/clips/SelectionBar.tsx`

- [ ] **Step 1: Implement ClipGrid**

```tsx
import { Box } from "@mui/material";
import { ClipCandidate } from "../../types/clips";
import ClipCard from "./ClipCard";

export default function ClipGrid({
  candidates, selected, onToggleSelect, onClickCard,
}: {
  candidates: ClipCandidate[];
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onClickCard: (c: ClipCandidate) => void;
}) {
  return (
    <Box sx={{
      display: "grid", gap: 2,
      gridTemplateColumns: {
        xs: "1fr",
        sm: "repeat(2, 1fr)",
        md: "repeat(3, 1fr)",
        lg: "repeat(4, 1fr)",
      },
    }}>
      {candidates.map(c => (
        <ClipCard
          key={c.id}
          candidate={c}
          selected={selected.has(c.id)}
          onToggleSelect={() => onToggleSelect(c.id)}
          onClick={() => onClickCard(c)}
        />
      ))}
    </Box>
  );
}
```

- [ ] **Step 2: Implement SelectionBar**

```tsx
import { Box, Button, Typography } from "@mui/material";

export default function SelectionBar({
  count, onRender, disabled,
}: { count: number; onRender: () => void; disabled?: boolean }) {
  if (count === 0) return null;
  return (
    <Box sx={{
      position: "sticky", bottom: 0, left: 0, right: 0,
      p: 2, bgcolor: "background.paper",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      zIndex: 2,
    }}>
      <Typography>{count} selected</Typography>
      <Button variant="contained" onClick={onRender} disabled={disabled}>
        Render selected clips
      </Button>
    </Box>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/clips/ClipGrid.tsx frontend/src/components/clips/SelectionBar.tsx
git commit -m "feat(clips): add ClipGrid and SelectionBar"
```

### Task E7: FinalRenderPanel

**Files:**
- Create: `frontend/src/components/clips/FinalRenderPanel.tsx`

- [ ] **Step 1: Implement**

```tsx
import { Box, Button, Card, LinearProgress, Typography } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

export default function FinalRenderPanel({
  selected, progress, signedUrls, onBack,
}: {
  selected: ClipCandidate[];
  progress: Record<string, number>;
  signedUrls: Record<string, string>;
  onBack: () => void;
}) {
  async function download(id: string) {
    const url = signedUrls[id] ?? (await clipsApi.finalUrl(id)).url;
    const a = document.createElement("a");
    a.href = url;
    a.download = `clip-${id}.mp4`;
    a.click();
  }

  return (
    <Box>
      <Button onClick={onBack} size="small" sx={{ mb: 2 }}>← Back to grid</Button>
      <Box sx={{
        display: "grid", gap: 2,
        gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" },
      }}>
        {selected.map(c => {
          const pct = progress[c.id] ?? 0;
          const done = !!signedUrls[c.id];
          return (
            <Card key={c.id} sx={{ p: 2 }}>
              <Typography variant="caption" sx={{ display: "block", mb: 1 }}>
                {c.hype_reasoning || `Score ${c.hype_score.toFixed(1)}`}
              </Typography>
              {done ? (
                <Button
                  startIcon={<DownloadIcon />}
                  variant="contained"
                  onClick={() => download(c.id)}
                  fullWidth
                >
                  Download
                </Button>
              ) : (
                <>
                  <LinearProgress variant="determinate" value={pct} />
                  <Typography variant="caption">{pct}%</Typography>
                </>
              )}
            </Card>
          );
        })}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/clips/FinalRenderPanel.tsx
git commit -m "feat(clips): add FinalRenderPanel with per-clip progress + download"
```

### Task E8: ClipsPage

**Files:**
- Create: `frontend/src/pages/ClipsPage.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useEffect, useState } from "react";
import { Box, Typography, List, ListItem, ListItemButton, ListItemText, Chip } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { ClipJobSummary } from "../types/clips";
import { clipsApi } from "../api/clips";
import NewJobForm from "../components/clips/NewJobForm";

export default function ClipsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ClipJobSummary[]>([]);

  async function refresh() {
    setJobs(await clipsApi.listJobs());
  }
  useEffect(() => { refresh(); }, []);

  return (
    <Box sx={{ p: 4, maxWidth: 800, mx: "auto" }}>
      <Typography variant="h5" gutterBottom>YouTube Clips</Typography>
      <NewJobForm onCreated={(id) => navigate(`/clips/${id}`)} />
      <Typography variant="subtitle2" sx={{ mt: 4, mb: 1 }}>Past jobs</Typography>
      <List>
        {jobs.map(j => (
          <ListItem key={j.id} disablePadding>
            <ListItemButton onClick={() => navigate(`/clips/${j.id}`)}>
              <ListItemText
                primary={j.title || j.youtube_url}
                secondary={`${j.duration_seconds ?? "?"}s · ${new Date(j.created_at).toLocaleString()}`}
              />
              <Chip label={j.status} size="small" />
            </ListItemButton>
          </ListItem>
        ))}
        {jobs.length === 0 && (
          <Typography variant="body2" color="text.secondary">No jobs yet.</Typography>
        )}
      </List>
    </Box>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ClipsPage.tsx
git commit -m "feat(clips): add ClipsPage with job list and creation form"
```

### Task E9: ClipJobPage (the main attraction)

**Files:**
- Create: `frontend/src/pages/ClipJobPage.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useEffect, useMemo, useState } from "react";
import { Box, Alert } from "@mui/material";
import { useParams, useNavigate } from "react-router-dom";
import { ClipJob, ClipCandidate, JobEvent } from "../types/clips";
import { clipsApi } from "../api/clips";
import { useClipJobSSE } from "../hooks/useClipJobSSE";
import JobProgressPanel from "../components/clips/JobProgressPanel";
import ClipGrid from "../components/clips/ClipGrid";
import ClipPreviewModal from "../components/clips/ClipPreviewModal";
import SelectionBar from "../components/clips/SelectionBar";
import FinalRenderPanel from "../components/clips/FinalRenderPanel";

export default function ClipJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<ClipJob | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewing, setPreviewing] = useState<ClipCandidate | null>(null);
  const [renderProgress, setRenderProgress] = useState<Record<string, number>>({});
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});

  async function refresh() {
    if (!jobId) return;
    setJob(await clipsApi.getJob(jobId));
  }
  useEffect(() => { refresh(); }, [jobId]);

  useClipJobSSE(jobId ?? null, (e: JobEvent) => {
    if (e.type === "progress") {
      setJob(j => j ? { ...j, current_stage: e.stage, progress_pct: e.pct } : j);
    } else if (e.type === "ready") {
      refresh();
    } else if (e.type === "render_progress") {
      setRenderProgress(p => ({ ...p, [e.candidate_id]: e.pct }));
    } else if (e.type === "render_complete") {
      setSignedUrls(u => ({ ...u, [e.candidate_id]: e.signed_url }));
    } else if (e.type === "render_complete_all") {
      refresh();
    }
  });

  const selectedCandidates = useMemo(
    () => job?.candidates.filter(c => selected.has(c.id)) ?? [],
    [job, selected],
  );

  if (!job) return <Box sx={{ p: 4 }}>Loading…</Box>;

  if (job.status === "failed") {
    return (
      <Box sx={{ p: 4, maxWidth: 600, mx: "auto" }}>
        <Alert severity="error">{job.error_message || "Job failed"}</Alert>
      </Box>
    );
  }

  if (["pending", "processing"].includes(job.status)) {
    return (
      <JobProgressPanel
        job={job}
        onCancel={async () => { await clipsApi.cancel(job.id); refresh(); }}
      />
    );
  }

  if (["rendering", "completed"].includes(job.status) && selectedCandidates.length > 0) {
    return (
      <Box sx={{ p: 4 }}>
        <FinalRenderPanel
          selected={selectedCandidates}
          progress={renderProgress}
          signedUrls={signedUrls}
          onBack={() => setSelected(new Set())}
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4 }}>
      <ClipGrid
        candidates={job.candidates}
        selected={selected}
        onToggleSelect={(id) => setSelected(s => {
          const next = new Set(s);
          next.has(id) ? next.delete(id) : next.add(id);
          return next;
        })}
        onClickCard={setPreviewing}
      />
      <ClipPreviewModal
        candidate={previewing}
        open={!!previewing}
        onClose={() => setPreviewing(null)}
      />
      <SelectionBar
        count={selected.size}
        onRender={async () => {
          await clipsApi.render(job.id, Array.from(selected));
          refresh();
        }}
      />
    </Box>
  );
}
```

- [ ] **Step 2: Build check**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ClipJobPage.tsx
git commit -m "feat(clips): add ClipJobPage orchestrating the three job states"
```

### Task E10: Wire routes + sidebar entry

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/IconRail.tsx`

- [ ] **Step 1: Add routes to App.tsx**

Add imports and routes inside the protected `<Route>` parent:

```tsx
import ClipsPage from "./pages/ClipsPage";
import ClipJobPage from "./pages/ClipJobPage";
// ...
<Route path="/clips" element={<ClipsPage />} />
<Route path="/clips/:jobId" element={<ClipJobPage />} />
```

- [ ] **Step 2: Add sidebar entry to IconRail.tsx**

```tsx
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";

// inside the rail, between Assets and Settings:
<Tooltip title="Clips" placement="right">
  <IconButton
    onClick={() => navigate("/clips")}
    sx={{
      color: location.pathname.startsWith("/clips") ? "#a78bfa" : "rgba(255,255,255,0.4)",
      backgroundColor: location.pathname.startsWith("/clips") ? "rgba(124,58,237,0.12)" : "transparent",
      "&:hover": { color: "#a78bfa", backgroundColor: "rgba(124,58,237,0.08)" },
      transition: "all 0.2s ease",
    }}
  >
    <VideoLibraryIcon fontSize="small" />
  </IconButton>
</Tooltip>
```

- [ ] **Step 3: Build check**

```bash
cd frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/IconRail.tsx
git commit -m "feat(clips): wire /clips routes and sidebar entry"
```

### Task E11: Manual smoke test

- [ ] **Step 1: Run end-to-end with a short test video**

1. Start backend: `cd backend && uv run uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `/clips`, paste a short YouTube URL (≤2 min ideally for first test), submit
4. Confirm progress bar advances through stages
5. When ready, confirm grid renders with previews and scores
6. Hover a card → preview should auto-play silently
7. Click card → modal opens with audio
8. Select 1-2 cards → render bar appears
9. Click "Render selected clips" → progress bars per clip
10. Click Download when each completes — verify the MP4 has burned-in captions

- [ ] **Step 2: Push branch**

```bash
git push origin feat/security-perf-ux-tier3
```

- [ ] **Step 3: Update PR #8 description**

```bash
gh pr edit 8 --body "$(cat <<'EOF'
[existing description...]

## YouTube Clips Creator

New /clips page that takes a YouTube URL and produces ranked vertical 9:16 short-clip candidates with viral hype scores. User selects favorites; backend re-renders selected clips at full quality with burned-in captions for download.

- New `clip_jobs` and `clip_candidates` tables
- `services/clips/` pipeline: yt-dlp → captions/Whisper → LLM segmentation → ffmpeg cut + face-aware reframe → preview render
- SSE progress events using existing pattern
- Two-phase render (cheap previews → high-quality finals only on selected)
- 7-day TTL on source/previews; finals persist
EOF
)"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Two-phase pipeline (preview → final): Tasks C8, C9, D5
- ✅ DB-backed `clip_jobs` row + asyncio + SSE: Tasks A1, C10, C11
- ✅ Crash recovery: Task D7
- ✅ Hard 60-min cap with 30-min warning: Tasks C2 (cap), E3 (modal)
- ✅ YT captions + Whisper fallback + broken detection: Task C5
- ✅ Transcript-only LLM scoring with sentence-bounded buckets: Task C6
- ✅ Adaptive candidate cap: Task C6 (`candidate_cap`)
- ✅ Face-aware crop via MediaPipe: Tasks C7, C8
- ✅ Burned captions only on finals: Task C9 (no captions in C8)
- ✅ Ranked grid + click-preview + select: Tasks E5, E6, E9
- ✅ Brand new page: Tasks E8, E9, E10
- ✅ Storage layout + 7-day TTL: Tasks C3, C12
- ✅ Service-token cleanup endpoint: Task D6

**Placeholder scan:** No TBDs, every code block is complete, no "similar to Task N" references.

**Type consistency:** `CandidateClip`, `TranscriptCue`, `VideoMetadata` defined in C1, used identically across C2/C5/C6/C8/C9/C11. `JobEvent` discriminated-union types match between SSE broker payloads and frontend hook.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-youtube-clips.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
