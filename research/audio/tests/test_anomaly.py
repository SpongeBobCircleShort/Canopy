import numpy as np
import pytest

from research.audio import anomaly


def _background(n=400, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, size=(n, dim))


def _artifact(prototypes=None, dim=16, fp_target=0.01):
    background = anomaly.fit_background(_background(dim=dim), fp_target=fp_target)
    prototypes = prototypes if prototypes is not None else anomaly.empty_prototypes(dim)
    return anomaly.build_artifact(background, prototypes, embedder={"model_dir": "x"})


def test_in_distribution_scores_low_oob_scores_high():
    artifact = _artifact()
    rng = np.random.default_rng(1)
    inlier = rng.normal(0.0, 1.0, size=16)
    outlier = np.full(16, 12.0)  # far from the background cloud

    inlier_result = anomaly.score_embedding(inlier, artifact)
    outlier_result = anomaly.score_embedding(outlier, artifact)

    assert inlier_result["anomaly_score"] < 0.9
    assert outlier_result["anomaly_score"] > inlier_result["anomaly_score"]
    assert outlier_result["anomaly_score"] >= 0.99
    assert outlier_result["is_anomaly"] is True


def test_threshold_respects_fp_target():
    # With fp_target=0.05 the threshold sits at the 95th background percentile,
    # so roughly 5% of background should be flagged anomalous (not ~100%).
    artifact = _artifact(fp_target=0.05)
    bg = _background(seed=7)
    flagged = [anomaly.score_embedding(row, artifact)["is_anomaly"] for row in bg]
    rate = sum(flagged) / len(flagged)
    assert 0.0 <= rate <= 0.15


def test_empty_prototypes_yield_unknown():
    artifact = _artifact()
    result = anomaly.score_embedding(np.full(16, 8.0), artifact)
    assert result["predicted_kind"] == "unknown"
    assert result["likelihoods"] == {"unknown": pytest.approx(1.0)}


def test_prototype_match_picks_correct_class():
    dim = 16
    rng = np.random.default_rng(2)
    chainsaw_dir = rng.normal(size=dim)
    vehicle_dir = rng.normal(size=dim)
    emb = np.vstack(
        [chainsaw_dir * 5 + rng.normal(scale=0.1, size=dim) for _ in range(10)]
        + [vehicle_dir * 5 + rng.normal(scale=0.1, size=dim) for _ in range(10)]
    )
    labels = ["chainsaw"] * 10 + ["vehicle"] * 10
    prototypes = anomaly.fit_prototypes(emb, labels)
    artifact = _artifact(prototypes=prototypes, dim=dim)

    result = anomaly.score_embedding(chainsaw_dir * 7, artifact)
    assert result["predicted_kind"] == "chainsaw"
    assert result["likelihoods"]["chainsaw"] > result["likelihoods"]["vehicle"]
    assert "unknown" in result["likelihoods"]
    assert sum(result["likelihoods"].values()) == pytest.approx(1.0, abs=1e-6)


def test_save_and_load_roundtrip(tmp_path):
    prototypes = anomaly.fit_prototypes(
        np.vstack([np.ones(16), np.ones(16) * 0.9]), ["chainsaw", "chainsaw"]
    )
    artifact = _artifact(prototypes=prototypes)
    anomaly.save_artifact(artifact, tmp_path)
    loaded = anomaly.load_artifact(tmp_path)

    point = np.full(16, 3.0)
    before = anomaly.score_embedding(point, artifact)
    after = anomaly.score_embedding(point, loaded)
    assert before["anomaly_score"] == pytest.approx(after["anomaly_score"])
    assert before["predicted_kind"] == after["predicted_kind"]
