from __future__ import annotations

from pathlib import Path

from research.audio.audio_io import load_and_preprocess_audio, load_log_mel, load_waveform_feature
from research.audio.labels import LABELS
from research.audio.manifest import read_manifest

BACKGROUND_LABEL = "background_unknown"


class ThreatAudioDataset:
    def __init__(
        self,
        manifest_path: str | Path,
        *,
        split: str,
        sample_rate: int,
        clip_seconds: float,
        n_mels: int,
        augment: bool = False,
        augmentation: dict | None = None,
        feature_type: str = "log_mel",
    ) -> None:
        self.rows = [row for row in read_manifest(manifest_path) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"No rows found for split={split}")
        self.sample_rate = sample_rate
        self.clip_seconds = clip_seconds
        self.n_mels = n_mels
        self.augment = augment
        self.augmentation = augmentation or {}
        self.feature_type = feature_type
        self.label_to_index = {label: index for index, label in enumerate(LABELS)}
        self.crop_mode = str(self.augmentation.get("crop_mode", "random" if augment else "center"))
        self.background_mix_labels = set(self.augmentation.get("background_mix_labels", LABELS))

        self._background_waveforms: list | None = None
        if augment and float(self.augmentation.get("background_mix_prob", 0.0)) > 0:
            background_paths = [row["path"] for row in self.rows if row["label"] == BACKGROUND_LABEL]
            if background_paths:
                self._background_waveforms = []
                max_backgrounds = int(self.augmentation.get("background_mix_max_clips", 200))
                for path in background_paths[:max_backgrounds]:
                    try:
                        waveform = load_and_preprocess_audio(
                            path,
                            sample_rate=sample_rate,
                            clip_seconds=clip_seconds,
                            crop_mode="random",
                        )
                        self._background_waveforms.append(waveform)
                    except Exception:  # noqa: BLE001
                        pass

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        background_waveforms = self._background_waveforms if row["label"] in self.background_mix_labels else None
        if self.feature_type == "waveform":
            features = load_waveform_feature(
                row["path"],
                sample_rate=self.sample_rate,
                clip_seconds=self.clip_seconds,
                augment=self.augment,
                augmentation=self.augmentation,
                background_waveforms=background_waveforms,
                crop_mode=self.crop_mode,
            )
        else:
            features = load_log_mel(
                row["path"],
                sample_rate=self.sample_rate,
                clip_seconds=self.clip_seconds,
                n_mels=self.n_mels,
                augment=self.augment,
                augmentation=self.augmentation,
                background_waveforms=background_waveforms,
                crop_mode=self.crop_mode,
            )
        return features, self.label_to_index[row["label"]]
