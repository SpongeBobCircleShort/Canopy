import numpy as np
import pytest

from research.audio import eval_probe as ep


def test_recording_key_strips_time_window():
    assert ep.recording_key("tambopata_2019_abc-uuid_40-43.wav") == "tambopata_2019_abc-uuid"
    assert ep.recording_key("/data/warsi_xy_120-123.flac") == "warsi_xy"
    assert ep.recording_key("no_window.wav") == "no_window"  # nothing to strip


def test_calibrate_threshold_respects_fp_target():
    bg = np.arange(100, dtype=float)  # 0..99
    thr = ep.calibrate_threshold(bg, 0.10)  # ~90th percentile
    assert (bg > thr).mean() <= 0.10 + 0.01
    assert ep.calibrate_threshold(np.array([]), 0.1) == 0.0


def test_recall_and_fp_at_threshold():
    labels = np.array([1, 1, 1, 0, 0])
    scores = np.array([0.9, 0.8, 0.2, 0.1, 0.95])
    assert ep.recall_at_threshold(labels, scores, 0.5) == pytest.approx(2 / 3)
    assert ep.false_positive_rate(labels, scores, 0.5) == pytest.approx(0.5)


def test_event_recall_groups_by_recording():
    # two recordings; rec A has a clip above threshold, rec B does not
    paths = ["site_A_0-3.wav", "site_A_3-6.wav", "site_B_0-3.wav"]
    labels = np.array([1, 1, 1])
    scores = np.array([0.2, 0.9, 0.1])  # A fires (0.9), B does not
    recall, n_events = ep.event_recall(paths, labels, scores, threshold=0.5)
    assert n_events == 2
    assert recall == pytest.approx(0.5)
    # min_hits=2 -> A no longer counts (only one clip above)
    recall2, _ = ep.event_recall(paths, labels, scores, threshold=0.5, min_hits=2)
    assert recall2 == pytest.approx(0.0)


def test_event_recall_beats_clip_recall_for_continuous_events():
    # a single event with 4 clips, one above threshold -> clip recall 0.25, event recall 1.0
    paths = [f"rec_{i*3}-{i*3+3}.wav" for i in range(4)]
    labels = np.array([1, 1, 1, 1])
    scores = np.array([0.1, 0.1, 0.9, 0.1])
    assert ep.recall_at_threshold(labels, scores, 0.5) == pytest.approx(0.25)
    recall, n = ep.event_recall(paths, labels, scores, 0.5)
    assert n == 1 and recall == pytest.approx(1.0)


def test_bootstrap_ci_brackets_and_orders():
    rng = np.random.default_rng(0)
    labels = np.array([0] * 50 + [1] * 50)
    scores = np.concatenate([rng.normal(0, 1, 50), rng.normal(2, 1, 50)])  # separable
    lo, hi = ep.bootstrap_auroc_ci(labels, scores, n_boot=200, seed=1)
    assert 0.5 < lo <= hi <= 1.0


def test_weighted_mean_ignores_nan():
    assert ep.weighted_mean([0.8, float("nan"), 0.6], [10, 5, 30]) == pytest.approx((0.8 * 10 + 0.6 * 30) / 40)
