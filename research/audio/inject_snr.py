"""Synthetic SNR-injection evaluation set builder.

Mixes verified positive clips into background audio at controlled
signal-to-noise ratios and writes a manifest, so detection can be measured as a
function of how faint the event is. Debugged against RFCx background now; on
delivery day the same command runs against the field background manifest:

    python -m research.audio.inject_snr \
        --background-manifest data/audio/manifests/india_background_v1.csv \
        --positives-manifest data/audio/manifests/kaggle_chainsaw_manifest.csv \
        --snrs -10,-5,0,5 --per-snr 50 \
        --out-dir data/audio/synthetic/india_snr_v1

The mixing math (``mix_at_snr``) is numpy-only and unit-tested without the
audio stack; torchaudio is imported lazily for I/O, matching ``audio_io.py``.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from research.audio.labels import canonical_label
from research.audio.manifest import MANIFEST_COLUMNS, read_manifest

BACKGROUND_LABEL = "background_unknown"
DEFAULT_SNRS_DB = (-10.0, -5.0, 0.0, 5.0)
DEFAULT_SAMPLE_RATE = 16000


# ---------------------------------------------------------------------------
# Mixing math (numpy only)
# ---------------------------------------------------------------------------

def rms(waveform: np.ndarray) -> float:
    waveform = np.asarray(waveform, dtype=np.float64)
    if waveform.size == 0:
        raise ValueError("empty waveform")
    return float(np.sqrt(np.mean(np.square(waveform))))


def mix_at_snr(
    background: np.ndarray,
    event: np.ndarray,
    snr_db: float,
    *,
    offset: int = 0,
) -> np.ndarray:
    """Overlay ``event`` on ``background`` so event-to-background power is ``snr_db``.

    The event is RMS-scaled relative to the background, placed at ``offset``
    samples (truncated to fit), and the mix is peak-normalized only when it
    would clip.
    """
    background = np.asarray(background, dtype=np.float64)
    event = np.asarray(event, dtype=np.float64)
    if offset < 0 or offset >= background.size:
        raise ValueError("offset must fall inside the background clip")
    background_rms = rms(background)
    event_rms = rms(event)
    if background_rms == 0.0 or event_rms == 0.0:
        raise ValueError("cannot mix silent audio")

    target_event_rms = background_rms * (10.0 ** (snr_db / 20.0))
    scaled = event * (target_event_rms / event_rms)

    mixed = background.copy()
    length = min(scaled.size, background.size - offset)
    mixed[offset : offset + length] += scaled[:length]

    peak = float(np.abs(mixed).max())
    if peak > 1.0:
        mixed /= peak
    return mixed


# ---------------------------------------------------------------------------
# Dataset builder (torchaudio I/O)
# ---------------------------------------------------------------------------

def _torch_modules():
    import torch
    import torchaudio

    return torch, torchaudio


def _load_mono(path: Path, sample_rate: int) -> np.ndarray:
    _, torchaudio = _torch_modules()
    waveform, source_rate = torchaudio.load(str(path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if source_rate != sample_rate:
        waveform = torchaudio.functional.resample(waveform, source_rate, sample_rate)
    return waveform[0].numpy().astype(np.float64)


def _save_mono(path: Path, waveform: np.ndarray, sample_rate: int) -> None:
    torch, torchaudio = _torch_modules()
    tensor = torch.from_numpy(np.asarray(waveform, dtype=np.float32)).unsqueeze(0)
    torchaudio.save(str(path), tensor, sample_rate)


def _resolve(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else manifest_path.parent / path


def build(args: argparse.Namespace) -> Path:
    rng = np.random.default_rng(args.seed)
    background_manifest = Path(args.background_manifest)
    positives_manifest = Path(args.positives_manifest)

    background_rows = [
        row for row in read_manifest(background_manifest)
        if canonical_label(row["label"]) == BACKGROUND_LABEL
    ]
    positive_rows = [
        row for row in read_manifest(positives_manifest)
        if canonical_label(row["label"]) != BACKGROUND_LABEL
    ]
    if not background_rows or not positive_rows:
        raise SystemExit("need at least one background and one positive row")

    out_dir = Path(args.out_dir)
    (out_dir / "clips").mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []

    for snr_db in args.snrs:
        for index in range(args.per_snr):
            bg_row = background_rows[int(rng.integers(len(background_rows)))]
            pos_row = positive_rows[int(rng.integers(len(positive_rows)))]
            background = _load_mono(_resolve(background_manifest, bg_row["path"]), args.sample_rate)
            event = _load_mono(_resolve(positives_manifest, pos_row["path"]), args.sample_rate)
            offset = int(rng.integers(max(1, background.size // 2)))
            mixed = mix_at_snr(background, event, snr_db, offset=offset)

            label = canonical_label(pos_row["label"])
            name = f"{label}_snr{snr_db:+.0f}dB_{index:04d}.wav"
            clip_path = out_dir / "clips" / name
            _save_mono(clip_path, mixed, args.sample_rate)
            manifest_rows.append(
                {
                    "path": str(clip_path.resolve()),
                    "label": label,
                    "source": "snr_injection",
                    "split": "test",
                    "duration_seconds": f"{mixed.size / args.sample_rate:.6g}",
                    "license": f"derived: {bg_row.get('license', '')} + {pos_row.get('license', '')}",
                    "notes": (
                        f"snr_db={snr_db}; background={bg_row['path']}; event={pos_row['path']}; "
                        f"offset_samples={offset}"
                    ),
                }
            )

    # Pure background rows serve as the negatives for FP measurement.
    for index in range(args.background_rows):
        bg_row = background_rows[int(rng.integers(len(background_rows)))]
        manifest_rows.append(
            {
                "path": str(_resolve(background_manifest, bg_row["path"]).resolve()),
                "label": BACKGROUND_LABEL,
                "source": "snr_injection",
                "split": "test",
                "duration_seconds": bg_row.get("duration_seconds", ""),
                "license": bg_row.get("license", ""),
                "notes": "snr_db=; pure background negative",
            }
        )

    manifest_out = out_dir / "manifest.csv"
    with manifest_out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote {len(manifest_rows)} rows -> {manifest_out}")
    return manifest_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an SNR-injection evaluation set.")
    parser.add_argument("--background-manifest", type=Path, required=True)
    parser.add_argument("--positives-manifest", type=Path, required=True)
    parser.add_argument("--snrs", type=lambda s: tuple(float(v) for v in s.split(",")), default=DEFAULT_SNRS_DB)
    parser.add_argument("--per-snr", type=int, default=50, help="Mixed clips per SNR level")
    parser.add_argument("--background-rows", type=int, default=200, help="Pure-background negatives to include")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=56)
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
