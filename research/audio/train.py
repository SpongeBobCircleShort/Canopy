from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import random
import shutil
from pathlib import Path

from research.audio.config import load_config
from research.audio.dataset import ThreatAudioDataset
from research.audio.evaluate import evaluate_model
from research.audio.labels import LABELS
from research.audio.model import build_model


def train(manifest: Path, config_path: Path | None, artifact_dir: Path | None = None) -> dict:
    torch = _torch()
    config = load_config(config_path)
    _seed_everything(int(config["training"]["seed"]))

    artifact_dir = artifact_dir or Path(config["paths"]["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)

    sample_rate = int(config["audio"]["sample_rate"])
    clip_seconds = float(config["audio"]["clip_seconds"])
    n_mels = int(config["audio"]["n_mels"])
    augmentation = config.get("augmentation", {})
    evaluation = config.get("evaluation", {})
    train_dataset = ThreatAudioDataset(
        manifest,
        split="train",
        sample_rate=sample_rate,
        clip_seconds=clip_seconds,
        n_mels=n_mels,
        augment=bool(augmentation.get("enabled", False)),
        augmentation=augmentation,
    )
    val_dataset = ThreatAudioDataset(manifest, split="val", sample_rate=sample_rate, clip_seconds=clip_seconds, n_mels=n_mels)
    test_dataset = ThreatAudioDataset(manifest, split="test", sample_rate=sample_rate, clip_seconds=clip_seconds, n_mels=n_mels)

    class_weights = _class_weights(train_dataset.rows, torch)
    sampler = (
        _weighted_sampler(
            train_dataset.rows,
            class_weights,
            torch,
            power=float(config["training"].get("sampler_weight_power", 1.0)),
            label_multipliers=config["training"].get("sampler_label_multipliers"),
        )
        if config["training"].get("weighted_sampler", False)
        else None
    )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=sampler is None,
        sampler=sampler,
    )
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=int(config["training"]["batch_size"]))
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=int(config["training"]["batch_size"]))

    device = _select_device(config["training"]["device"])
    model = build_model(len(LABELS)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    loss_weights = class_weights.to(device) if config["training"].get("class_weighting", False) else None
    loss_fn = torch.nn.CrossEntropyLoss(weight=loss_weights)

    history = []
    best_val_macro_f1 = -1.0
    best_state_dict = deepcopy(model.state_dict())
    best_val_metrics: dict | None = None
    best_epoch = 0
    for epoch in range(int(config["training"]["epochs"])):
        model.train()
        total_loss = 0.0
        total_examples = 0
        for features, labels in train_loader:
            features = features.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            logits = model(features)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * labels.numel()
            total_examples += labels.numel()
        val_metrics = evaluate_model(model, val_loader, device, threshold_policy=evaluation)
        epoch_summary = {"epoch": epoch + 1, "train_loss": total_loss / max(total_examples, 1), **val_metrics}
        history.append(epoch_summary)
        progress = {
            "epoch": epoch + 1,
            "epochs": int(config["training"]["epochs"]),
            "train_loss": round(epoch_summary["train_loss"], 6),
            "val_accuracy": round(epoch_summary["accuracy"], 6),
            "val_macro_f1": round(epoch_summary["macro_f1"], 6),
            "val_thresholded_macro_f1": round(epoch_summary["thresholded_metrics"]["macro_f1"], 6),
            "val_background_threat_fp_rate": round(epoch_summary["background_false_positive_summary"]["thresholded"]["threat_false_positive_rate"], 6),
            "selection_score": round(epoch_summary["selection_score"], 6),
            "val_per_class_recall": {label: round(epoch_summary["per_class_recall"][label], 6) for label in LABELS},
        }
        print(json.dumps(progress), flush=True)
        if config["training"].get("checkpoint_each_epoch", False):
            torch.save(
                {"state_dict": model.state_dict(), "artifact": {"model_version": config["model_version"], "labels": LABELS, "audio": config["audio"], "epoch": epoch + 1}},
                artifact_dir / f"checkpoint_epoch_{epoch + 1:03d}.pt",
            )
        if epoch_summary["selection_score"] > best_val_macro_f1:
            best_val_macro_f1 = epoch_summary["selection_score"]
            best_state_dict = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
            best_val_metrics = epoch_summary
            best_epoch = epoch + 1

    model.load_state_dict(best_state_dict)
    test_metrics = evaluate_model(model, test_loader, device, threshold_policy=evaluation)
    best_val_metrics = best_val_metrics or history[-1]

    artifact = {
        "model_version": config["model_version"],
        "labels": LABELS,
        "audio": config["audio"],
        "augmentation": augmentation,
        "evaluation": evaluation,
        "training": config["training"],
        "best_epoch": best_epoch,
        "history": history,
    }
    torch.save({"state_dict": model.state_dict(), "artifact": artifact}, artifact_dir / "model.pt")
    torch.save({"state_dict": model.state_dict(), "artifact": artifact}, artifact_dir / "best_model.pt")
    (artifact_dir / "labels.json").write_text(json.dumps(LABELS, indent=2))
    (artifact_dir / "history.json").write_text(json.dumps(history, indent=2))
    (artifact_dir / "val_metrics.json").write_text(json.dumps(best_val_metrics, indent=2))
    (artifact_dir / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2))
    (artifact_dir / "metrics.json").write_text(json.dumps({"validation": best_val_metrics, "test": test_metrics}, indent=2))
    shutil.copyfile(config_path or Path(__file__).with_name("config.yaml"), artifact_dir / "config.yaml")
    return test_metrics


def _class_weights(rows: list[dict], torch):
    counts = Counter(row["label"] for row in rows)
    total = sum(counts.values())
    weights = [total / (len(LABELS) * max(counts.get(label, 0), 1)) for label in LABELS]
    return torch.tensor(weights, dtype=torch.float32)


def _weighted_sampler(rows: list[dict], class_weights, torch, *, power: float, label_multipliers: dict | None):
    label_to_index = {label: index for index, label in enumerate(LABELS)}
    if label_multipliers:
        sample_weights = [float(label_multipliers.get(row["label"], 1.0)) for row in rows]
    else:
        sample_weights = [float(class_weights[label_to_index[row["label"]]] ** power) for row in rows]
    return torch.utils.data.WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)


def _select_device(requested: str):
    torch = _torch()
    if requested == "auto":
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(requested)


def _seed_everything(seed: int) -> None:
    torch = _torch()
    random.seed(seed)
    torch.manual_seed(seed)


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to train the audio model") from exc
    return torch


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Canopy acoustic threat CNN baseline.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()

    metrics = train(args.manifest, args.config, args.artifact_dir)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
