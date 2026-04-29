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
