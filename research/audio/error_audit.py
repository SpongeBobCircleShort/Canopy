from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from research.audio.config import load_config
from research.audio.dataset import ThreatAudioDataset
from research.audio.evaluate import _feature_type
from research.audio.infer import _load_thresholds
from research.audio.labels import LABELS
from research.audio.model import build_model, model_config_from_checkpoint

BACKGROUND_LABEL = "background_unknown"

AUDIT_COLUMNS = [
    "split",
    "path",
    "source",
    "true_label",
    "raw_predicted_label",
    "thresholded_predicted_label",
    "predicted_label",
    "is_error",
    "error_type",
    "review_priority",
    "review_reason",
    "predicted_score",
    "true_label_score",
    "margin",
    "second_label",
    "second_score",
    "duration_seconds",
    "license",
    "notes",
    *[f"score_{label}" for label in LABELS],
]


def audit_artifact(
    model_dir: Path,
    manifest: Path,
    output: Path,
    *,
    split: str = "test",
    top_confusions_output: Path | None = None,
    limit: int | None = None,
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
    model.eval()

    dataset = ThreatAudioDataset(
        manifest,
        split=split,
        sample_rate=int(config["audio"]["sample_rate"]),
        clip_seconds=float(config["audio"]["clip_seconds"]),
        n_mels=int(config["audio"]["n_mels"]),
        feature_type=_feature_type(model_config),
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=int(config["training"]["batch_size"]))
    score_rows: list[list[float]] = []
    with torch.no_grad():
        for features, _targets in loader:
            probabilities = torch.softmax(model(features), dim=1).cpu()
            score_rows.extend(probabilities.tolist())

    thresholds = _load_thresholds(model_dir)
    rows = build_audit_rows(dataset.rows, score_rows, labels=labels, thresholds=thresholds)
    rows = sorted(rows, key=_audit_sort_key)
    if limit is not None:
        rows = rows[:limit]

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_audit_columns(labels))
        writer.writeheader()
        writer.writerows(rows)

    top_confusions = summarize_top_confusions(rows)
    if top_confusions_output is None:
        top_confusions_output = output.with_name(f"{output.stem}_top_confusions.json")
    top_confusions_output.parent.mkdir(parents=True, exist_ok=True)
    top_confusions_output.write_text(json.dumps(top_confusions, indent=2))
    return {
        "output": str(output),
        "top_confusions_output": str(top_confusions_output),
        "rows": len(rows),
        "errors": sum(row["is_error"] == "1" for row in rows),
        "top_confusions": top_confusions,
    }


def build_audit_rows(
    manifest_rows: list[dict[str, str]],
    score_rows: list[list[float]],
    *,
    labels: list[str],
    thresholds: dict[str, float] | None = None,
) -> list[dict[str, str]]:
    thresholds = thresholds or {}
    output_rows = []
    for manifest_row, scores in zip(manifest_rows, score_rows, strict=True):
        score_map = {label: float(scores[index]) for index, label in enumerate(labels)}
        ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
        true_label = manifest_row["label"]
        raw_predicted_label = ranked[0][0]
        thresholded_predicted_label = _thresholded_label(score_map, thresholds, labels=labels)
        predicted_label = thresholded_predicted_label if thresholds else raw_predicted_label
        predicted_score = score_map[predicted_label]
        second_label, second_score = ranked[1] if len(ranked) > 1 else ("", 0.0)
        true_label_score = score_map.get(true_label, 0.0)
        row = {
            "split": manifest_row.get("split", ""),
            "path": manifest_row.get("path", ""),
            "source": manifest_row.get("source", ""),
            "true_label": true_label,
            "raw_predicted_label": raw_predicted_label,
            "thresholded_predicted_label": thresholded_predicted_label,
            "predicted_label": predicted_label,
            "predicted_score": _format_float(predicted_score),
            "true_label_score": _format_float(true_label_score),
            "margin": _format_float(predicted_score - true_label_score),
            "second_label": second_label,
            "second_score": _format_float(second_score),
            "duration_seconds": manifest_row.get("duration_seconds", ""),
            "license": manifest_row.get("license", ""),
            "notes": manifest_row.get("notes", ""),
        }
        row["is_error"] = "0" if predicted_label == true_label else "1"
        row["error_type"] = _error_type(true_label, predicted_label)
        row["review_priority"] = _review_priority(row, score_map)
        row["review_reason"] = _review_reason(row)
        for label in labels:
            row[f"score_{label}"] = _format_float(score_map[label])
        output_rows.append(row)
    return output_rows


def summarize_top_confusions(rows: list[dict[str, str]], limit: int = 20) -> list[dict[str, str | int]]:
    counts: dict[tuple[str, str, str], int] = {}
    for row in rows:
        if row["is_error"] != "1":
            continue
        key = (row["true_label"], row["predicted_label"], row["error_type"])
        counts[key] = counts.get(key, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [
        {"true_label": true_label, "predicted_label": predicted_label, "error_type": error_type, "count": count}
        for (true_label, predicted_label, error_type), count in sorted_counts[:limit]
    ]


def _thresholded_label(score_map: dict[str, float], thresholds: dict[str, float], *, labels: list[str]) -> str:
    if not thresholds:
        return max(score_map, key=score_map.get)
    background_label = BACKGROUND_LABEL if BACKGROUND_LABEL in labels else labels[-1]
    passing = [
        (label, score)
        for label, score in score_map.items()
        if score >= thresholds.get(label, 0.5)
    ]
    if passing:
        return max(passing, key=lambda item: item[1])[0]
    return background_label


def _error_type(true_label: str, predicted_label: str) -> str:
    if true_label == predicted_label:
        return "correct"
    if true_label == BACKGROUND_LABEL and predicted_label != BACKGROUND_LABEL:
        return "background_false_positive"
    if true_label != BACKGROUND_LABEL and predicted_label == BACKGROUND_LABEL:
        return "threat_false_negative"
    return "threat_confusion"


def _review_priority(row: dict[str, str], score_map: dict[str, float]) -> str:
    error_type = row["error_type"]
    if error_type == "background_false_positive":
        return "1"
    if error_type == "threat_false_negative":
        return "2"
    if error_type == "threat_confusion":
        return "3"
    predicted_score = float(row["predicted_score"])
    second_score = float(row["second_score"] or 0.0)
    true_label_score = score_map.get(row["true_label"], 0.0)
    if predicted_score - second_score < 0.10 or predicted_score - true_label_score < 0.10:
        return "4"
    return "9"


def _review_reason(row: dict[str, str]) -> str:
    if row["error_type"] == "background_false_positive":
        return "Background clip predicted as threat; add/relabel as hard negative if label is correct."
    if row["error_type"] == "threat_false_negative":
        return "Threat clip fell to background; verify label quality and collect similar positives."
    if row["error_type"] == "threat_confusion":
        return "Threat class confused with another threat; verify taxonomy and acoustic overlap."
    if row["review_priority"] == "4":
        return "Correct but low margin; review if source label is weak."
    return ""


def _audit_sort_key(row: dict[str, str]) -> tuple[int, float, float, str]:
    return (
        int(row["review_priority"]),
        -float(row["predicted_score"]),
        -float(row["margin"]),
        row["path"],
    )


def _audit_columns(labels: list[str]) -> list[str]:
    score_columns = [f"score_{label}" for label in labels]
    return [column for column in AUDIT_COLUMNS if not column.startswith("score_")] + score_columns


def _format_float(value: float) -> str:
    return f"{float(value):.6f}"


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to audit audio model errors") from exc
    return torch


def main() -> None:
    parser = argparse.ArgumentParser(description="Export per-clip audio model errors for listening review.")
    parser.add_argument("--model", type=Path, required=True, help="Model artifact directory containing model.pt")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--top-confusions-output", type=Path)
    parser.add_argument("--limit", type=int, help="Optional maximum number of sorted audit rows to write")
    args = parser.parse_args()

    result = audit_artifact(
        args.model,
        args.manifest,
        args.output,
        split=args.split,
        top_confusions_output=args.top_confusions_output,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
