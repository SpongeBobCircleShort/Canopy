from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio.config import load_config
from research.audio.dataset import ThreatAudioDataset
from research.audio.labels import LABELS
from research.audio.model import build_model

BACKGROUND_LABEL = "background_unknown"


def evaluate_artifact(model_dir: Path, manifest: Path, split: str = "test") -> dict:
    torch = _torch()
    config = load_config(model_dir / "config.yaml")
    dataset = ThreatAudioDataset(
        manifest,
        split=split,
        sample_rate=int(config["audio"]["sample_rate"]),
        clip_seconds=float(config["audio"]["clip_seconds"]),
        n_mels=int(config["audio"]["n_mels"]),
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=int(config["training"]["batch_size"]))
    checkpoint = torch.load(model_dir / "model.pt", map_location="cpu")
    model = build_model(len(LABELS))
    model.load_state_dict(checkpoint["state_dict"])
    metrics = evaluate_model(model, loader, torch.device("cpu"), threshold_policy=config.get("evaluation", {}))
    (model_dir / f"{split}_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def evaluate_model(model, loader, device, threshold_policy: dict | None = None) -> dict:
    torch = _torch()

    threshold_policy = threshold_policy or {}
    model.eval()
    predictions: list[int] = []
    targets: list[int] = []
    score_rows: list[list[float]] = []
    with torch.no_grad():
        for features, labels in loader:
            logits = model(features.to(device))
            probabilities = torch.softmax(logits, dim=1).cpu()
            predicted = probabilities.argmax(dim=1)
            predictions.extend(predicted.tolist())
            targets.extend(labels.tolist())
            score_rows.extend(probabilities.tolist())

    thresholds = _threshold_recommendations(targets, score_rows, threshold_policy)
    thresholded_predictions = _thresholded_predictions(score_rows, thresholds)
    raw_metrics = _prediction_metrics(targets, predictions)
    thresholded_metrics = _prediction_metrics(targets, thresholded_predictions)
    background_fp_summary = {
        "raw": _background_false_positive_summary(raw_metrics["confusion_matrix"]),
        "thresholded": _background_false_positive_summary(thresholded_metrics["confusion_matrix"]),
    }
    return {
        **raw_metrics,
        "threshold_recommendations": thresholds,
        "thresholded_metrics": thresholded_metrics,
        "background_false_positive_summary": background_fp_summary,
        "selection_score": _selection_score(thresholded_metrics, background_fp_summary["thresholded"], threshold_policy),
    }


def _prediction_metrics(targets: list[int], predictions: list[int]) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    matrix = confusion_matrix(targets, predictions, labels=list(range(len(LABELS))))
    report = classification_report(
        targets,
        predictions,
        labels=list(range(len(LABELS))),
        target_names=LABELS,
        output_dict=True,
        zero_division=0,
    )
    return {
        "accuracy": accuracy_score(targets, predictions),
        "macro_f1": f1_score(targets, predictions, average="macro", zero_division=0),
        "classification_report": report,
        "per_class_recall": {label: report[label]["recall"] for label in LABELS},
        "confusion_matrix": matrix.tolist(),
        "top_confusions": _top_confusions(matrix.tolist()),
    }


def _top_confusions(matrix: list[list[int]], limit: int = 10) -> list[dict]:
    confusions = []
    for actual_index, actual_label in enumerate(LABELS):
        for predicted_index, predicted_label in enumerate(LABELS):
            if actual_index == predicted_index:
                continue
            count = int(matrix[actual_index][predicted_index])
            if count:
                confusions.append({"actual": actual_label, "predicted": predicted_label, "count": count})
    return sorted(confusions, key=lambda item: item["count"], reverse=True)[:limit]


def _threshold_recommendations(targets: list[int], score_rows: list[list[float]], threshold_policy: dict) -> dict:
    recommendations = {}
    min_precision = threshold_policy.get("min_precision", {})
    threshold_step = float(threshold_policy.get("threshold_step", 0.05))
    threshold_values = []
    threshold = threshold_step
    while threshold <= 0.95 + 1e-9:
        threshold_values.append(round(threshold, 4))
        threshold += threshold_step
    for label_index, label in enumerate(LABELS):
        candidates = []
        for threshold in threshold_values:
            true_positive = false_positive = false_negative = 0
            for target, scores in zip(targets, score_rows, strict=True):
                predicted_positive = scores[label_index] >= threshold
                actual_positive = target == label_index
                if predicted_positive and actual_positive:
                    true_positive += 1
                elif predicted_positive and not actual_positive:
                    false_positive += 1
                elif not predicted_positive and actual_positive:
                    false_negative += 1
            precision = true_positive / max(true_positive + false_positive, 1)
            recall = true_positive / max(true_positive + false_negative, 1)
            f1 = 2 * precision * recall / max(precision + recall, 1e-12)
            candidates.append({"threshold": threshold, "precision": precision, "recall": recall, "f1": f1})
        precision_floor = float(min_precision.get(label, 0.0))
        qualified = [candidate for candidate in candidates if candidate["precision"] >= precision_floor and candidate["recall"] > 0]
        best = max(qualified or candidates, key=lambda item: (item["f1"], item["recall"], item["precision"]))
        recommendations[label] = {key: round(value, 4) for key, value in best.items()}
    return recommendations


def _thresholded_predictions(score_rows: list[list[float]], thresholds: dict) -> list[int]:
    background_index = LABELS.index(BACKGROUND_LABEL) if BACKGROUND_LABEL in LABELS else len(LABELS) - 1
    predictions = []
    for scores in score_rows:
        passing = [
            (index, score)
            for index, score in enumerate(scores)
            if score >= _threshold_value(thresholds.get(LABELS[index]), default=0.5)
        ]
        if passing:
            predictions.append(max(passing, key=lambda item: item[1])[0])
        else:
            predictions.append(background_index)
    return predictions


def _threshold_value(value, *, default: float) -> float:
    if isinstance(value, dict):
        value = value.get("threshold", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _background_false_positive_summary(matrix: list[list[int]]) -> dict:
    if BACKGROUND_LABEL not in LABELS:
        return {"support": 0, "threat_false_positive_count": 0, "threat_false_positive_rate": 0.0, "by_label": {}}
    background_index = LABELS.index(BACKGROUND_LABEL)
    background_row = matrix[background_index]
    support = sum(background_row)
    by_label = {
        label: {
            "count": int(background_row[index]),
            "rate": round(background_row[index] / support, 6) if support else 0.0,
        }
        for index, label in enumerate(LABELS)
        if label != BACKGROUND_LABEL
    }
    false_positive_count = sum(item["count"] for item in by_label.values())
    return {
        "support": int(support),
        "threat_false_positive_count": int(false_positive_count),
        "threat_false_positive_rate": round(false_positive_count / support, 6) if support else 0.0,
        "by_label": by_label,
    }


def _selection_score(thresholded_metrics: dict, background_fp_summary: dict, threshold_policy: dict) -> float:
    selection = threshold_policy.get("selection", {})
    score = float(thresholded_metrics["macro_f1"])
    score -= float(selection.get("background_false_positive_penalty", 0.0)) * float(background_fp_summary["threat_false_positive_rate"])
    for label, minimum in selection.get("min_recall", {}).items():
        recall = float(thresholded_metrics["per_class_recall"].get(label, 0.0))
        if recall < float(minimum):
            score -= float(minimum) - recall
    return score


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to evaluate the audio model") from exc
    return torch


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a Canopy acoustic threat model artifact.")
    parser.add_argument("--model", type=Path, required=True, help="Model artifact directory containing model.pt")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    print(json.dumps(evaluate_artifact(args.model, args.manifest, args.split), indent=2))


if __name__ == "__main__":
    main()
