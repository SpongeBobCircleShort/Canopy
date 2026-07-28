"""Synthesize in-domain threat positives by mixing threats into Indian background.

We have Indian forest background audio but no Indian threat recordings (no chainsaw
was ever recorded in an Indian forest with our channel). Prototypes built purely
from Amazonian/urban threats therefore sit in the wrong acoustic channel. This
module bridges that: it mixes real threat sounds (chainsaw, gunshot, vehicle) into
real Indian forest background at controlled signal-to-noise ratios, producing
matched positives that share the Indian soundscape and recording channel.

The mixing math is pure numpy and unit-tested; only ``synthesize`` touches files.

Example:

    python -m research.audio.mix_soundscapes \
        --background-manifest data/audio/gbif_india_screened/manifest_clean.csv \
        --background-dir data/audio/gbif_india \
        --positives-manifest data/audio/manifests/positives_threats.csv \
        --out-dir data/audio/india_synthetic --per-label 150
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

from research.audio.manifest import ManifestRow, write_manifest

SR = 32000
EPS = 1e-9
SOURCE = "synthetic_mix"


def rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(signal)) + EPS))


def fit_length(background: np.ndarray, length: int, rng: random.Random) -> np.ndarray:
    """Return a background segment of exactly ``length`` samples (tile if short,
    random crop if long)."""
    if len(background) == 0:
        return np.zeros(length, dtype=np.float64)
    if len(background) < length:
        reps = int(np.ceil(length / len(background)))
        background = np.tile(background, reps)
    if len(background) > length:
        start = rng.randint(0, len(background) - length)
        background = background[start:start + length]
    return background[:length]


def mix_at_snr(background: np.ndarray, threat: np.ndarray, snr_db: float, rng: random.Random) -> np.ndarray:
    """Mix a threat over background at a target SNR (threat is the signal).

    The background is length-matched to the threat, the threat is scaled so that
    ``20*log10(rms(threat)/rms(background)) == snr_db``, and the sum is peak-limited
    to avoid clipping.
    """
    background = fit_length(background, len(threat), rng)
    target_threat_rms = rms(background) * (10.0 ** (snr_db / 20.0))
    threat_scaled = threat * (target_threat_rms / rms(threat))
    mixed = background + threat_scaled
    peak = float(np.max(np.abs(mixed)))
    if peak > 1.0:
        mixed = mixed / peak * 0.98
    return mixed


def _load(path: Path) -> np.ndarray:
    import librosa

    waveform, _ = librosa.load(str(path), sr=SR, mono=True)
    return np.asarray(waveform, dtype=np.float64)


def synthesize(
    background_paths: list[Path],
    positives_by_label: dict[str, list[Path]],
    out_dir: Path,
    *,
    per_label: int = 150,
    snr_range: tuple[float, float] = (-5.0, 15.0),
    seed: int = 0,
) -> Path:
    import soundfile as sf

    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[ManifestRow] = []
    for label, threat_paths in positives_by_label.items():
        if not threat_paths or not background_paths:
            continue
        for i in range(per_label):
            threat_path = rng.choice(threat_paths)
            bg_path = rng.choice(background_paths)
            snr = rng.uniform(*snr_range)
            try:
                threat = _load(threat_path)
                background = _load(bg_path)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip mix ({label}): {exc}")
                continue
            if len(threat) == 0:
                continue
            mixed = mix_at_snr(background, threat, snr, rng)
            name = f"mix_{label}_{i:04d}.wav"
            sf.write(str(out_dir / name), mixed, SR)
            rows.append(ManifestRow(
                path=name, label=label, source=SOURCE, split="train",
                duration_seconds=round(len(mixed) / SR, 3), license="",
                notes=f"threat:{threat_path.name} bg:{bg_path.name} snr:{snr:.1f}dB",
            ))
    manifest_path = out_dir / "manifest.csv"
    if rows:
        write_manifest(manifest_path, rows)
    print(f"Synthesized {len(rows)} in-domain positives -> {out_dir}")
    return manifest_path


def _paths_from_manifest(manifest: Path, audio_dir: Path, label: str | None = None) -> list[Path]:
    import csv

    out: list[Path] = []
    for row in csv.DictReader(manifest.open()):
        if label is not None and row.get("label") != label:
            continue
        p = Path(row["path"])
        p = audio_dir / p if not p.is_absolute() else p
        if p.exists():
            out.append(p)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Mix threats into Indian background for in-domain positives.")
    parser.add_argument("--background-manifest", type=Path, required=True)
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--positives-manifest", type=Path, required=True)
    parser.add_argument("--positives-dir", type=Path, default=None)
    parser.add_argument("--labels", default="chainsaw,gunshot,vehicle", help="Comma-separated threat labels")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--per-label", type=int, default=150)
    parser.add_argument("--snr-min", type=float, default=-5.0)
    parser.add_argument("--snr-max", type=float, default=15.0)
    args = parser.parse_args()

    background = _paths_from_manifest(args.background_manifest, args.background_dir)
    pos_dir = args.positives_dir or args.positives_manifest.parent
    positives = {lbl: _paths_from_manifest(args.positives_manifest, pos_dir, lbl) for lbl in args.labels.split(",")}
    print(f"background: {len(background)} clips; positives: {{{', '.join(f'{k}:{len(v)}' for k, v in positives.items())}}}")
    synthesize(background, positives, args.out_dir, per_label=args.per_label, snr_range=(args.snr_min, args.snr_max))


if __name__ == "__main__":
    main()
