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
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def evaluate_model(model, loader, device) -> dict:
    torch = _torch()
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    model.eval()
    predictions: list[int] = []
    targets: list[int] = []
    confidences: list[float] = []
    with torch.no_grad():
        for features, labels in loader:
            logits = model(features.to(device))
            probabilities = torch.softmax(logits, dim=1).cpu()
            predicted = probabilities.argmax(dim=1)
            predictions.extend(predicted.tolist())
            targets.extend(labels.tolist())
            confidences.extend(probabilities.max(dim=1).values.tolist())

    return {
        "macro_f1": f1_score(targets, predictions, average="macro", zero_division=0),
        "classification_report": classification_report(targets, predictions, labels=list(range(len(LABELS))), target_names=LABELS, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(targets, predictions, labels=list(range(len(LABELS)))).tolist(),
        "threshold_recommendations": {
            label: round(_mean_confidence_for_label(index, predictions, confidences), 4)
            for index, label in enumerate(LABELS)
        },
    }


def _mean_confidence_for_label(label_index: int, predictions: list[int], confidences: list[float]) -> float:
    values = [confidence for prediction, confidence in zip(predictions, confidences, strict=True) if prediction == label_index]
    return sum(values) / len(values) if values else 0.5


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
