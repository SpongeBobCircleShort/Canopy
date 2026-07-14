import numpy as np
import pytest

from research.audio import screen_soundscapes as screen


def _corpus(n_inliers=60, n_outliers=5, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    inliers = rng.normal(0.0, 1.0, size=(n_inliers, dim))
    outliers = rng.normal(9.0, 0.3, size=(n_outliers, dim))  # a tight, far cluster = hidden "threats"
    embeddings = np.vstack([inliers, outliers])
    outlier_idx = np.arange(n_inliers, n_inliers + n_outliers)
    return embeddings, outlier_idx


def test_iterative_refit_isolates_hidden_outliers():
    embeddings, outlier_idx = _corpus()
    result = screen.iterative_robust_background(embeddings, drop_frac=0.05, rounds=3)

    kept = result["kept_mask"]
    # Every injected "threat" is dropped from the purified normal set.
    assert not kept[outlier_idx].any()
    # The bulk of genuine background is retained.
    inlier_mask = np.ones(embeddings.shape[0], dtype=bool)
    inlier_mask[outlier_idx] = False
    assert kept[inlier_mask].sum() >= inlier_mask.sum() - 5
    assert result["rounds_run"] >= 1


def test_outliers_score_above_background():
    embeddings, outlier_idx = _corpus()
    scores = screen.iterative_robust_background(embeddings, drop_frac=0.05, rounds=3)["scores"]
    inlier_mask = np.ones(embeddings.shape[0], dtype=bool)
    inlier_mask[outlier_idx] = False
    assert scores[outlier_idx].min() > float(np.median(scores[inlier_mask]))


def test_iterative_background_guards_small_and_bad_input():
    with pytest.raises(ValueError):
        screen.iterative_robust_background(np.zeros((3, 4)))  # below min_keep
    with pytest.raises(ValueError):
        screen.iterative_robust_background(np.zeros((20, 4)), drop_frac=0.9)


def test_ensemble_max_and_weighted_and_passthrough():
    anom = np.array([0.2, 0.9, 0.4])
    tag = np.array([0.8, 0.1, 0.5])
    assert np.allclose(screen.ensemble_suspicion(anom, tag, mode="max"), [0.8, 0.9, 0.5])
    assert np.allclose(screen.ensemble_suspicion(anom, tag, mode="weighted", weight=0.5), [0.5, 0.5, 0.45])
    # No tagger -> anomaly scores unchanged.
    assert np.allclose(screen.ensemble_suspicion(anom, None), anom)
    with pytest.raises(ValueError):
        screen.ensemble_suspicion(anom, np.array([0.1, 0.2]))


def _rows():
    return [
        {"path": "a.mp3", "label": "background_unknown", "source": "xeno_canto", "split": "train",
         "duration_seconds": "12.5", "license": "//creativecommons.org/licenses/by/4.0/", "notes": "xc:1"},
        {"path": "b.mp3", "label": "background_unknown", "source": "xeno_canto", "split": "train",
         "duration_seconds": "", "license": "", "notes": "xc:2"},
    ]


def test_partition_splits_and_annotates():
    rows = _rows()
    suspicion = np.array([0.95, 0.10])
    clean, flagged = screen.partition_rows(rows, suspicion, threshold=0.9)
    assert len(flagged) == 1 and flagged[0].path == "a.mp3"
    assert len(clean) == 1 and clean[0].path == "b.mp3"
    assert flagged[0].label == "background_unknown"
    assert "REVIEW" in flagged[0].notes and "suspicion:0.950" in flagged[0].notes
    assert "clean" in clean[0].notes


def test_partition_length_mismatch_raises():
    with pytest.raises(ValueError):
        screen.partition_rows(_rows(), np.array([0.5]), threshold=0.9)


def test_ranked_review_sorted_desc():
    ranked = screen.ranked_review(_rows(), np.array([0.1, 0.9]))
    assert [row["path"] for row, _ in ranked] == ["b.mp3", "a.mp3"]
    assert ranked[0][1] == 0.9
