from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio.config import load_config
from research.audio.dataset import ThreatAudioDataset
from research.audio.labels import LABELS
from research.audio.model import build_model


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
    metrics = evaluate_model(model, loader, torch.device("cpu"))
    (model_dir / f"{split}_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def evaluate_model(model, loader, device) -> dict:
    torch = _torch()
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    model.eval()
    predictions: list[int] = []
    targets: list[int] = []
    confidences: list[float] = []
    score_rows: list[list[float]] = []
    with torch.no_grad():
        for features, labels in loader:
            logits = model(features.to(device))
            probabilities = torch.softmax(logits, dim=1).cpu()
            predicted = probabilities.argmax(dim=1)
            predictions.extend(predicted.tolist())
            targets.extend(labels.tolist())
            confidences.extend(probabilities.max(dim=1).values.tolist())
            score_rows.extend(probabilities.tolist())

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
        "top_confusions": _top_confusions(matrix),
        "threshold_recommendations": _threshold_recommendations(targets, score_rows),
    }


def _top_confusions(matrix, limit: int = 10) -> list[dict]:
    confusions = []
    for actual_index, actual_label in enumerate(LABELS):
        for predicted_index, predicted_label in enumerate(LABELS):
            if actual_index == predicted_index:
                continue
            count = int(matrix[actual_index][predicted_index])
            if count:
                confusions.append({"actual": actual_label, "predicted": predicted_label, "count": count})
    return sorted(confusions, key=lambda item: item["count"], reverse=True)[:limit]


def _threshold_recommendations(targets: list[int], score_rows: list[list[float]]) -> dict:
    recommendations = {}
    for label_index, label in enumerate(LABELS):
        best = {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        for threshold_step in range(5, 96, 5):
            threshold = threshold_step / 100
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
            if f1 > best["f1"]:
                best = {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1}
        recommendations[label] = {key: round(value, 4) for key, value in best.items()}
    return recommendations


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
