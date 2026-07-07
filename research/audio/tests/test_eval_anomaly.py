import numpy as np
import pytest

from research.audio import anomaly, eval_anomaly


def _clusters(dim=16, seed=0):
    """Synthetic embeddings: background at origin, two well-separated classes."""
    rng = np.random.default_rng(seed)
    background = rng.normal(0.0, 1.0, size=(300, dim))
    chainsaw = rng.normal(0.0, 0.5, size=(60, dim))
    chainsaw[:, 0] += 10.0
    gunshot = rng.normal(0.0, 0.5, size=(60, dim))
    gunshot[:, 1] += 10.0
    return background, chainsaw, gunshot


def _fitted_background(background):
    return anomaly.fit_background(background, fp_target=0.10)


def test_site_of_parses_notes():
    notes = "rfcx_split=train; site_id=tambopata; forest_domain_v1=true"
    assert eval_anomaly.site_of(notes) == "tambopata"
    assert eval_anomaly.site_of("no site here") == ""
    assert eval_anomaly.site_of("") == ""


def test_split_masks_partition_rows():
    labels = ["background_unknown", "chainsaw", "background_unknown", "chainsaw"]
    splits = ["train", "train", "test", "test"]
    masks = eval_anomaly.split_masks(labels, splits)
    assert masks["train_background"].tolist() == [True, False, False, False]
    assert masks["train_positive"].tolist() == [False, True, False, False]
    assert masks["test_background"].tolist() == [False, False, True, False]
    assert masks["test_positive"].tolist() == [False, False, False, True]
    assert not masks["val_background"].any()


def test_calibrate_threshold_meets_fp_gate_with_max_recall():
    scores = np.linspace(0.0, 1.0, 101)  # 101 evenly spaced background scores
    threshold = eval_anomaly.calibrate_threshold(scores, fp_target=0.10)
    fp = np.mean(scores >= threshold)
    assert fp <= 0.10
    # Smallest qualifying threshold: one step lower would break the gate.
    lower_candidates = scores[scores < threshold]
    if lower_candidates.size:
        assert np.mean(scores >= lower_candidates.max()) > 0.10


def test_calibrate_threshold_identical_scores_returns_fp_zero_threshold():
    scores = np.full(50, 0.7)
    threshold = eval_anomaly.calibrate_threshold(scores, fp_target=0.10)
    assert np.mean(scores >= threshold) == 0.0


def test_operating_point_metrics():
    scores = np.array([0.99, 0.99, 0.10, 0.99, 0.05, 0.99])
    kinds = np.array(["chainsaw", "unknown", "unknown", "chainsaw", "unknown", "unknown"])
    labels = ["chainsaw", "chainsaw", "chainsaw", "background_unknown", "background_unknown", "background_unknown"]
    point = eval_anomaly.operating_point(scores, kinds, labels, threshold=0.5)
    chainsaw = point["classes"]["chainsaw"]
    assert chainsaw["count"] == 3
    assert chainsaw["flagged_recall"] == pytest.approx(2 / 3)
    assert chainsaw["attributed_recall"] == pytest.approx(1 / 3)
    assert chainsaw["attributed_of_flagged"] == pytest.approx(0.5)
    assert point["background_fp_rate"] == pytest.approx(2 / 3)


def test_threshold_sweep_auc_separated_and_random():
    rng = np.random.default_rng(3)
    separated = eval_anomaly.threshold_sweep(rng.uniform(0.0, 0.4, 200), rng.uniform(0.6, 1.0, 200))
    assert separated["auc"] > 0.99
    same = rng.uniform(0.0, 1.0, 400)
    overlapping = eval_anomaly.threshold_sweep(same[:200], same[200:])
    assert 0.4 < overlapping["auc"] < 0.6


def test_subsample_per_class_caps_each_class():
    labels = ["a"] * 10 + ["b"] * 3
    keep = eval_anomaly.subsample_per_class(labels, 5, np.random.default_rng(0))
    kept_labels = [labels[i] for i in keep]
    assert kept_labels.count("a") == 5
    assert kept_labels.count("b") == 3  # fewer than k -> keep all


def test_end_to_end_holdout_protocol_on_synthetic_clusters():
    background, chainsaw, _ = _clusters()
    fitted = _fitted_background(background[:200])
    prototypes = anomaly.fit_prototypes(chainsaw[:40], ["chainsaw"] * 40)
    artifact = anomaly.build_artifact(fitted, prototypes)

    val_scores = eval_anomaly.score_all(background[200:250], artifact)["anomaly_score"]
    threshold = eval_anomaly.calibrate_threshold(val_scores, fp_target=0.10)

    test_embeddings = np.concatenate([background[250:], chainsaw[40:]])
    test_labels = ["background_unknown"] * 50 + ["chainsaw"] * 20
    scored = eval_anomaly.score_all(test_embeddings, artifact)
    point = eval_anomaly.operating_point(scored["anomaly_score"], scored["predicted_kind"], test_labels, threshold)

    assert point["background_fp_rate"] <= 0.20
    assert point["classes"]["chainsaw"]["flagged_recall"] > 0.9
    assert point["classes"]["chainsaw"]["attributed_recall"] > 0.9


def test_prototype_k_curve_lights_up_with_k():
    background, chainsaw, _ = _clusters()
    fitted = _fitted_background(background[:200])
    test_embeddings = np.concatenate([background[250:], chainsaw[40:]])
    test_labels = ["background_unknown"] * 50 + ["chainsaw"] * 20

    curve = eval_anomaly.prototype_k_curve(
        fitted, chainsaw[:40], ["chainsaw"] * 40, test_embeddings, test_labels,
        threshold=0.9, ks=(0, 5), n_seeds=3,
    )
    at_zero = curve[0]["classes"]["chainsaw"]["attributed_recall_mean"]
    at_five = curve[1]["classes"]["chainsaw"]["attributed_recall_mean"]
    assert at_zero == 0.0  # no prototypes -> everything honestly unknown
    assert at_five > 0.9  # a handful of verified positives light the label up


def test_unknown_class_holdout_keeps_mass_on_unknown():
    background, chainsaw, gunshot = _clusters()
    fitted = _fitted_background(background[:200])
    train_pos = np.concatenate([chainsaw[:40], gunshot[:40]])
    train_labels = ["chainsaw"] * 40 + ["gunshot"] * 40
    test_embeddings = np.concatenate([background[250:], chainsaw[40:]])
    test_labels = ["background_unknown"] * 50 + ["chainsaw"] * 20

    result = eval_anomaly.unknown_class_holdout(
        fitted, train_pos, train_labels, test_embeddings, test_labels,
        heldout_class="chainsaw", threshold=0.9,
    )
    assert result["remaining_prototypes"] == ["gunshot"]
    assert result["flagged_recall"] > 0.9  # still flagged as anomalous
    assert result["predicted_unknown_of_flagged"] > 0.9  # ... but honestly unknown
    assert result["mean_unknown_mass_of_flagged"] > 0.5


def test_unknown_class_holdout_requires_class_in_test():
    background, chainsaw, _ = _clusters()
    fitted = _fitted_background(background[:200])
    with pytest.raises(ValueError):
        eval_anomaly.unknown_class_holdout(
            fitted, chainsaw[:10], ["chainsaw"] * 10, background[250:], ["background_unknown"] * 50,
            heldout_class="gunshot", threshold=0.9,
        )


def test_mix_at_snr_scales_event_power():
    from research.audio.inject_snr import mix_at_snr, rms

    rng = np.random.default_rng(0)
    background = rng.normal(0.0, 0.05, 16000)
    event = rng.normal(0.0, 0.5, 4000)

    mixed = mix_at_snr(background, event, snr_db=0.0, offset=1000)
    injected = mixed[1000:5000] - background[1000:5000]
    # At 0 dB the injected event's RMS matches the background RMS.
    assert rms(injected) == pytest.approx(rms(background), rel=1e-6)

    quiet = mix_at_snr(background, event, snr_db=-20.0, offset=1000)
    injected_quiet = quiet[1000:5000] - background[1000:5000]
    assert rms(injected_quiet) == pytest.approx(rms(background) * 0.1, rel=1e-6)


def test_mix_at_snr_truncates_and_normalizes():
    from research.audio.inject_snr import mix_at_snr

    background = np.full(1000, 0.5)
    event = np.ones(2000)
    mixed = mix_at_snr(background, event, snr_db=20.0, offset=900)
    assert mixed.size == 1000
    assert np.abs(mixed).max() <= 1.0

    with pytest.raises(ValueError):
        mix_at_snr(background, event, snr_db=0.0, offset=1000)
