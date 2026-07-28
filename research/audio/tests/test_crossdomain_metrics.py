import numpy as np
import pytest

from research.audio import crossdomain_metrics as cm

CH = cm.LABELS.index("chainsaw")
BG = cm.BACKGROUND_INDEX


def _probs(rows):
    return np.array(rows, dtype=np.float64)


def test_thresholded_predictions_matches_evaluate_semantics():
    # chainsaw thr 0.85, background thr 0.05; highest passing class wins, else bg.
    thresholds = {"chainsaw": 0.85, "gunshot": 0.75, "vehicle": 0.75, "fire_crackle": 0.85, "background_unknown": 0.05}
    probs = _probs([
        [0.90, 0.0, 0.0, 0.0, 0.10],  # chainsaw passes -> chainsaw
        [0.50, 0.0, 0.0, 0.0, 0.50],  # nothing passes threat thr -> background
        [0.86, 0.0, 0.0, 0.87, 0.0],  # both pass; fire higher -> fire_crackle
    ])
    preds = cm.thresholded_predictions(probs, thresholds)
    assert preds.tolist() == [CH, BG, cm.LABELS.index("fire_crackle")]


def test_argmax_predictions():
    probs = _probs([[0.1, 0.2, 0.7, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 1.0]])
    assert cm.argmax_predictions(probs).tolist() == [2, BG]


def test_background_threat_fp_rate():
    targets = np.array([BG, BG, BG, BG])
    preds = np.array([CH, BG, 2, BG])  # 2 of 4 background predicted as a threat
    assert cm.background_threat_fp_rate(targets, preds) == pytest.approx(0.5)
    assert cm.background_threat_fp_rate(np.array([CH]), np.array([CH])) is None  # no bg


def test_per_class_recall_and_macro_f1():
    targets = np.array([CH, CH, BG, BG])
    preds = np.array([CH, BG, BG, BG])
    rec = cm.per_class_recall(targets, preds)
    assert rec["chainsaw"] == pytest.approx(0.5)
    assert rec["background_unknown"] == pytest.approx(1.0)
    assert rec["gunshot"] is None  # absent class -> None, not 0
    assert 0.0 <= cm.macro_f1(targets, preds) <= 1.0


def test_class_vs_background_auc_perfect_and_chance():
    # Perfectly separable: chainsaw clips score high, background low.
    probs = _probs([[0.9, 0, 0, 0, 0.1], [0.8, 0, 0, 0, 0.2], [0.2, 0, 0, 0, 0.8], [0.1, 0, 0, 0, 0.9]])
    targets = np.array([CH, CH, BG, BG])
    assert cm.class_vs_background_auc(probs, targets, CH) == pytest.approx(1.0)
    # Reversed -> AUC 0.0
    assert cm.class_vs_background_auc(probs[::-1], targets, CH) == pytest.approx(0.0)


def test_class_vs_background_auc_ties_give_half():
    probs = _probs([[0.5, 0, 0, 0, 0.5]] * 4)
    targets = np.array([CH, CH, BG, BG])
    assert cm.class_vs_background_auc(probs, targets, CH) == pytest.approx(0.5)


def test_class_vs_background_auc_matches_sklearn_on_random():
    sklearn = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    n = 200
    scores = rng.random(n)
    labels = rng.integers(0, 2, n)  # 1 = chainsaw, 0 = background
    probs = np.zeros((n, len(cm.LABELS)))
    probs[:, CH] = scores
    targets = np.where(labels == 1, CH, BG)
    ours = cm.class_vs_background_auc(probs, targets, CH)
    ref = sklearn.roc_auc_score(labels, scores)
    assert ours == pytest.approx(ref, abs=1e-9)


def test_bootstrap_ci_brackets_point_and_handles_none():
    rng = np.random.default_rng(1)
    values = rng.random(500)

    def mean_metric(indices):
        return float(values[indices].mean())

    ci = cm.bootstrap_ci(mean_metric, values.size, n_boot=500, seed=3)
    assert ci["lo"] <= ci["point"] <= ci["hi"]
    assert ci["hi"] - ci["lo"] < 0.2  # reasonably tight for n=500

    assert cm.bootstrap_ci(lambda idx: None, 10)["point"] is None
