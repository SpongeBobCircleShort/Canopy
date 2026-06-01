from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from research.audio.config import load_config
from research.audio.dataset import ThreatAudioDataset
from research.audio.evaluate import (
    _background_false_positive_summary,
    _feature_type,
    _prediction_metrics,
    _thresholded_predictions,
)
from research.audio.labels import LABELS
from research.audio.model import build_model, model_config_from_checkpoint

BACKGROUND_LABEL = "background_unknown"

DEFAULT_MIN_RECALL = {
    "chainsaw": 0.55,
    "gunshot": 0.65,
    "vehicle": 0.40,
    "fire_crackle": 0.40,
}


def calibrate_artifact(
    model_dir: Path,
    manifest: Path,
    *,
    threshold_step: float = 0.05,
    max_background_fp_rate: float = 0.20,
    min_recall: dict[str, float] | None = None,
) -> dict:
    torch = _torch()
    model_dir = Path(model_dir)
    manifest = Path(manifest)
    config = load_config(model_dir / "config.yaml")
    checkpoint = torch.load(model_dir / "model.pt", map_location="cpu", weights_only=False)
    model_config = model_config_from_checkpoint(checkpoint, config.get("model", {}))
    labels = json.loads((model_dir / "labels.json").read_text()) if (model_dir / "labels.json").exists() else LABELS
    model = build_model(len(labels), model_config=model_config)
    model.load_state_dict(checkpoint["state_dict"])

    val_targets, val_scores = _score_split(
        model,
        manifest,
        split="val",
        config=config,
        model_config=model_config,
        batch_size=int(config["training"]["batch_size"]),
    )
    thresholds, calibration_metrics = select_thresholds(
        val_targets,
        val_scores,
        labels=labels,
        threshold_values=_threshold_values(threshold_step),
        max_background_fp_rate=max_background_fp_rate,
        min_recall=min_recall or DEFAULT_MIN_RECALL,
    )

    test_targets, test_scores = _score_split(
        model,
        manifest,
        split="test",
        config=config,
        model_config=model_config,
        batch_size=int(config["training"]["batch_size"]),
    )
    test_metrics = metrics_for_thresholds(test_targets, test_scores, thresholds, labels=labels)

    deployment_artifact = {
        "thresholds": thresholds,
        "source": "validation_calibration",
        "threshold_step": threshold_step,
        "max_background_fp_rate": max_background_fp_rate,
        "min_recall": min_recall or DEFAULT_MIN_RECALL,
        "model_version": checkpoint.get("artifact", {}).get("model_version", config.get("model_version")),
    }
    (model_dir / "deployment_thresholds.json").write_text(json.dumps(deployment_artifact, indent=2))
    (model_dir / "calibration_metrics.json").write_text(json.dumps(calibration_metrics, indent=2))
    (model_dir / "test_metrics_deployment_thresholds.json").write_text(json.dumps(test_metrics, indent=2))
    return {
        "deployment_thresholds": deployment_artifact,
        "calibration_metrics": calibration_metrics,
        "test_metrics": test_metrics,
    }


def select_thresholds(
    targets: list[int],
    score_rows: list[list[float]],
    *,
    labels: list[str],
    threshold_values: list[float],
    max_background_fp_rate: float,
    min_recall: dict[str, float],
) -> tuple[dict[str, float], dict]:
    best_thresholds: dict[str, float] | None = None
    best_rank: tuple | None = None
    targets_array = np.asarray(targets, dtype=np.int64)
    scores_array = np.asarray(score_rows, dtype=np.float32)
    background_index = labels.index(BACKGROUND_LABEL) if BACKGROUND_LABEL in labels else len(labels) - 1

    for values in itertools.product(threshold_values, repeat=len(labels)):
        predictions = _thresholded_predictions_array(
            scores_array,
            np.asarray(values, dtype=np.float32),
            background_index,
        )
        rank = _candidate_rank_from_predictions(
            targets_array,
            predictions,
            labels=labels,
            max_background_fp_rate=max_background_fp_rate,
            min_recall=min_recall,
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_thresholds = {label: threshold for label, threshold in zip(labels, values, strict=True)}

    assert best_thresholds is not None
    best_metrics = metrics_for_thresholds(targets, score_rows, best_thresholds, labels=labels)
    return best_thresholds, {
        **best_metrics,
        "deployment_thresholds": best_thresholds,
        "calibration_constraints": {
            "max_background_fp_rate": max_background_fp_rate,
            "min_recall": min_recall,
            "constraints_met": bool(best_rank[0]) if best_rank else False,
        },
    }


def metrics_for_thresholds(
    targets: list[int],
    score_rows: list[list[float]],
    thresholds: dict[str, float],
    *,
    labels: list[str] | None = None,
) -> dict:
    labels = labels or LABELS
    raw_predictions = [max(range(len(scores)), key=lambda index: scores[index]) for scores in score_rows]
    thresholded_predictions = _thresholded_predictions(score_rows, thresholds)
    raw_metrics = _prediction_metrics(targets, raw_predictions)
    thresholded_metrics = _prediction_metrics(targets, thresholded_predictions)
    background_fp_summary = {
        "raw": _background_false_positive_summary(raw_metrics["confusion_matrix"]),
        "thresholded": _background_false_positive_summary(thresholded_metrics["confusion_matrix"]),
    }
    return {
        **raw_metrics,
        "threshold_recommendations": {
            label: {"threshold": round(float(thresholds[label]), 4)} for label in labels
        },
        "thresholded_metrics": thresholded_metrics,
        "background_false_positive_summary": background_fp_summary,
    }


def _candidate_rank(metrics: dict, *, max_background_fp_rate: float, min_recall: dict[str, float]) -> tuple:
    thresholded = metrics["thresholded_metrics"]
    return _rank_values(
        macro_f1=float(thresholded["macro_f1"]),
        recalls=thresholded["per_class_recall"],
        background_fp_rate=float(metrics["background_false_positive_summary"]["thresholded"]["threat_false_positive_rate"]),
        max_background_fp_rate=max_background_fp_rate,
        min_recall=min_recall,
    )


def _candidate_rank_from_predictions(
    targets: np.ndarray,
    predictions: np.ndarray,
    *,
    labels: list[str],
    max_background_fp_rate: float,
    min_recall: dict[str, float],
) -> tuple:
    matrix = np.zeros((len(labels), len(labels)), dtype=np.int64)
    np.add.at(matrix, (targets, predictions), 1)
    support = matrix.sum(axis=1)
    predicted_support = matrix.sum(axis=0)
    true_positive = np.diag(matrix)
    recalls_array = np.divide(
        true_positive,
        support,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=support != 0,
    )
    precision = np.divide(
        true_positive,
        predicted_support,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=predicted_support != 0,
    )
    f1 = np.divide(
        2 * precision * recalls_array,
        precision + recalls_array,
        out=np.zeros_like(precision, dtype=np.float64),
        where=(precision + recalls_array) != 0,
    )
    background_index = labels.index(BACKGROUND_LABEL) if BACKGROUND_LABEL in labels else len(labels) - 1
    background_support = support[background_index]
    background_false_positives = int(background_support - matrix[background_index, background_index])
    background_fp_rate = float(background_false_positives / background_support) if background_support else 0.0
    return _rank_values(
        macro_f1=float(f1.mean()),
        recalls={label: float(recalls_array[index]) for index, label in enumerate(labels)},
        background_fp_rate=background_fp_rate,
        max_background_fp_rate=max_background_fp_rate,
        min_recall=min_recall,
    )


def _thresholded_predictions_array(
    scores: np.ndarray,
    thresholds: np.ndarray,
    background_index: int,
) -> np.ndarray:
    masked_scores = np.where(scores >= thresholds, scores, -1.0)
    predictions = masked_scores.argmax(axis=1)
    predictions[masked_scores.max(axis=1) < 0] = background_index
    return predictions


def _rank_values(
    *,
    macro_f1: float,
    recalls: dict[str, float],
    background_fp_rate: float,
    max_background_fp_rate: float,
    min_recall: dict[str, float],
) -> tuple:
    recall_shortfall = sum(max(0.0, float(floor) - float(recalls.get(label, 0.0))) for label, floor in min_recall.items())
    background_shortfall = max(0.0, float(background_fp_rate) - max_background_fp_rate)
    constraints_met = recall_shortfall == 0 and background_shortfall == 0
    penalized_score = macro_f1 - (2.0 * recall_shortfall) - (2.0 * background_shortfall)
    background_recall = float(recalls.get(BACKGROUND_LABEL, 0.0))
    return (
        1 if constraints_met else 0,
        penalized_score,
        macro_f1,
        background_recall,
        -float(background_fp_rate),
    )


def _score_split(model, manifest: Path, *, split: str, config: dict, model_config: dict, batch_size: int):
    torch = _torch()
    dataset = ThreatAudioDataset(
        manifest,
        split=split,
        sample_rate=int(config["audio"]["sample_rate"]),
        clip_seconds=float(config["audio"]["clip_seconds"]),
        n_mels=int(config["audio"]["n_mels"]),
        feature_type=_feature_type(model_config),
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size)
    model.eval()
    targets: list[int] = []
    score_rows: list[list[float]] = []
    with torch.no_grad():
        for features, labels in loader:
            probabilities = torch.softmax(model(features), dim=1).cpu()
            targets.extend(labels.tolist())
            score_rows.extend(probabilities.tolist())
    return targets, score_rows


def _threshold_values(step: float) -> list[float]:
    values = []
    threshold = step
    while threshold <= 0.95 + 1e-9:
        values.append(round(threshold, 4))
        threshold += step
    return values


def _parse_label_floors(values: list[str] | None) -> dict[str, float]:
    if not values:
        return DEFAULT_MIN_RECALL
    parsed = {}
    for value in values:
        label, floor = value.split("=", 1)
        parsed[label.strip()] = float(floor)
    return parsed


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to calibrate audio thresholds") from exc
    return torch


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate deployment thresholds for a Canopy audio model.")
    parser.add_argument("--model", type=Path, required=True, help="Model artifact directory containing model.pt")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--max-background-fp-rate", type=float, default=0.20)
    parser.add_argument("--min-recall", nargs="*", help="Per-label floors like chainsaw=0.55 gunshot=0.65")
    args = parser.parse_args()

    result = calibrate_artifact(
        args.model,
        args.manifest,
        threshold_step=args.threshold_step,
        max_background_fp_rate=args.max_background_fp_rate,
        min_recall=_parse_label_floors(args.min_recall),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
