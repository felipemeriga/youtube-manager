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
