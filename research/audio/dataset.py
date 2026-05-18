from __future__ import annotations

from pathlib import Path

from research.audio.audio_io import load_log_mel
from research.audio.labels import LABELS
from research.audio.manifest import read_manifest


class ThreatAudioDataset:
    def __init__(self, manifest_path: str | Path, *, split: str, sample_rate: int, clip_seconds: float, n_mels: int) -> None:
        self.rows = [row for row in read_manifest(manifest_path) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"No rows found for split={split}")
        self.sample_rate = sample_rate
        self.clip_seconds = clip_seconds
        self.n_mels = n_mels
        self.label_to_index = {label: index for index, label in enumerate(LABELS)}

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        features = load_log_mel(
            row["path"],
            sample_rate=self.sample_rate,
            clip_seconds=self.clip_seconds,
            n_mels=self.n_mels,
        )
        return features, self.label_to_index[row["label"]]
