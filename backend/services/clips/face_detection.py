"""Face-aware cropping for vertical reframe.

Samples ~1 frame per second, runs MediaPipe face detection on each, returns a
smoothed (time, x_center) track. Falls back to image center if no face is
detected. The track is consumed by render_preview/render_final to drive the
ffmpeg crop X offset.

Uses MediaPipe's Tasks API (BlazeFace short-range). The legacy
`mediapipe.solutions` namespace was dropped from recent macOS arm64 wheels,
so the Tasks model is downloaded once on first use to a cache dir.
"""
import logging
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def _model_path() -> Path:
    return Path.home() / ".cache" / "youtube-manager" / "blaze_face_short_range.tflite"


def _ensure_model() -> Path:
    """Download the BlazeFace TFLite model on first use; cached afterwards."""
    path = _model_path()
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    logger.info("Downloading MediaPipe face detector model to %s", path)
    with httpx.stream("GET", _MODEL_URL, timeout=60.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    tmp.rename(path)
    return path


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

    Falls back to image center if MediaPipe finds nothing or the model fails
    to load.
    """
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    width, _ = _video_dimensions(video_path)
    sample_times = [float(i) for i in range(int(duration_seconds))]
    if not sample_times:
        sample_times = [0.0]

    try:
        model_path = _ensure_model()
    except Exception:
        logger.exception("Failed to load face detector model; falling back to center")
        return fallback_center(width, sample_times)

    options = mp_vision.FaceDetectorOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
        min_detection_confidence=0.5,
    )

    raw: list[tuple[float, int]] = []
    cap = cv2.VideoCapture(str(video_path))
    try:
        with mp_vision.FaceDetector.create_from_options(options) as detector:
            for t in sample_times:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = cap.read()
                if not ok:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = detector.detect(mp_image)
                if not result.detections:
                    continue
                # Largest detection (bounding_box gives pixel coords in input image)
                best = max(result.detections, key=lambda d: d.bounding_box.width)
                bbox = best.bounding_box
                cx = bbox.origin_x + bbox.width // 2
                raw.append((t, cx))
    finally:
        cap.release()

    if not raw:
        return fallback_center(width, sample_times)
    return smooth_x_track(raw, window=5)
