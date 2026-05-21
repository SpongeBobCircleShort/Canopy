from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from research.audio.audio_io import load_log_mel
from research.audio.config import load_config
from research.audio.labels import LABELS
from research.audio.manifest import MANIFEST_COLUMNS, ManifestRow, read_manifest, write_manifest
from research.audio.model import build_model, model_config_from_checkpoint

DEFAULT_TARGET_LABELS = {"chainsaw", "gunshot", "vehicle", "fire_crackle"}


def mine_hard_negatives(
    *,
    model_dir: Path,
    manifest: Path,
    output: Path,
    split: str = "train",
    min_confidence: float = 0.5,
    target_labels: set[str] | None = None,
    max_per_label: int = 250,
) -> list[ManifestRow]:
    torch = _torch()
    target_labels = target_labels or DEFAULT_TARGET_LABELS
    config = load_config(model_dir / "config.yaml")
    labels = json.loads((model_dir / "labels.json").read_text()) if (model_dir / "labels.json").exists() else LABELS
    checkpoint = torch.load(model_dir / "model.pt", map_location="cpu")
    model = build_model(len(labels), model_config=model_config_from_checkpoint(checkpoint, config.get("model", {})))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    background_rows = [row for row in read_manifest(manifest) if row["label"] == "background_unknown" and row["split"] == split]
    mined: list[ManifestRow] = []
    counts = {label: 0 for label in target_labels}
    for row in _progress(background_rows, desc="mine-hard-negatives"):
        scores = _score_clip(torch, model, Path(row["path"]), config, labels)
        predicted_label = max(scores, key=scores.get)
        confidence = scores[predicted_label]
        row = hard_negative_from_prediction(
            row,
            predicted_label=predicted_label,
            confidence=confidence,
            target_labels=target_labels,
            count_for_label=counts.get(predicted_label, 0),
            max_per_label=max_per_label,
            min_confidence=min_confidence,
        )
        if row is None:
            continue
        counts[predicted_label] += 1
        mined.append(row)

    if mined:
        write_manifest(output, mined)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="") as handle:
            csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS).writeheader()
    return mined


def hard_negative_from_prediction(
    row: dict[str, str],
    *,
    predicted_label: str,
    confidence: float,
    target_labels: set[str],
    count_for_label: int,
    max_per_label: int,
    min_confidence: float,
) -> ManifestRow | None:
    if predicted_label not in target_labels or confidence < min_confidence or count_for_label >= max_per_label:
        return None
    return ManifestRow(
        path=row["path"],
        label="background_unknown",
        source="hard_negative",
        split="train",
        duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] else None,
        license=row["license"],
        notes=(
            f"hard_negative_from={row['source']}; predicted={predicted_label}; "
            f"confidence={confidence:.4f}; source_notes={row['notes']}"
        ),
    )


def _score_clip(torch, model, audio_path: Path, config: dict, labels: list[str]) -> dict[str, float]:
    features = load_log_mel(
        audio_path,
        sample_rate=int(config["audio"]["sample_rate"]),
        clip_seconds=float(config["audio"]["clip_seconds"]),
        n_mels=int(config["audio"]["n_mels"]),
    ).unsqueeze(0)
    with torch.no_grad():
        probabilities = torch.softmax(model(features), dim=1)[0]
    return {label: float(probabilities[index].item()) for index, label in enumerate(labels)}


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to mine hard negatives") from exc
    return torch


def _progress(iterable, *, desc: str):
    try:
        from tqdm import tqdm
    except ImportError:
        return iterable
    return tqdm(iterable, desc=desc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine background clips that a trained model confuses with threat labels.")
    parser.add_argument("--model", type=Path, required=True, help="Model artifact directory containing model.pt")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--target-label", action="append", choices=sorted(DEFAULT_TARGET_LABELS))
    parser.add_argument("--max-per-label", type=int, default=250)
    args = parser.parse_args()

    rows = mine_hard_negatives(
        model_dir=args.model,
        manifest=args.manifest,
        output=args.output,
        split=args.split,
        min_confidence=args.min_confidence,
        target_labels=set(args.target_label) if args.target_label else DEFAULT_TARGET_LABELS,
        max_per_label=args.max_per_label,
    )
    print(json.dumps({"output": str(args.output), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
