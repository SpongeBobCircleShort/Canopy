from __future__ import annotations

import argparse
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
    train_dataset = ThreatAudioDataset(manifest, split="train", sample_rate=sample_rate, clip_seconds=clip_seconds, n_mels=n_mels)
    val_dataset = ThreatAudioDataset(manifest, split="val", sample_rate=sample_rate, clip_seconds=clip_seconds, n_mels=n_mels)

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=True,
    )
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=int(config["training"]["batch_size"]))

    device = _select_device(config["training"]["device"])
    model = build_model(len(LABELS)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    loss_fn = torch.nn.CrossEntropyLoss()

    history = []
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
        val_metrics = evaluate_model(model, val_loader, device)
        history.append({"epoch": epoch + 1, "train_loss": total_loss / max(total_examples, 1), **val_metrics})

    artifact = {
        "model_version": config["model_version"],
        "labels": LABELS,
        "audio": config["audio"],
        "history": history,
    }
    torch.save({"state_dict": model.state_dict(), "artifact": artifact}, artifact_dir / "model.pt")
    (artifact_dir / "labels.json").write_text(json.dumps(LABELS, indent=2))
    (artifact_dir / "metrics.json").write_text(json.dumps(history[-1], indent=2))
    shutil.copyfile(config_path or Path(__file__).with_name("config.yaml"), artifact_dir / "config.yaml")
    return history[-1]


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
