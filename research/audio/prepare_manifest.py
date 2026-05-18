from __future__ import annotations

import argparse
import csv
from pathlib import Path

from research.audio.labels import LABEL_ALIASES, canonical_label
from research.audio.manifest import ManifestRow, write_manifest


ESC50_CLASS_MAP = {
    "chainsaw": "chainsaw",
    "crackling_fire": "fire_crackle",
    "engine": "vehicle",
    "siren": "vehicle",
    "helicopter": "vehicle",
    "airplane": "vehicle",
    "train": "vehicle",
}

URBANSOUND8K_CLASS_MAP = {
    "gun_shot": "gunshot",
    "engine_idling": "vehicle",
    "car_horn": "vehicle",
    "siren": "vehicle",
    "jackhammer": "chainsaw",
}


def build_rows(esc50_root: Path | None, urbansound8k_root: Path | None, canopy_root: Path | None) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    if esc50_root:
        rows.extend(_rows_from_esc50(esc50_root))
    if urbansound8k_root:
        rows.extend(_rows_from_urbansound8k(urbansound8k_root))
    if canopy_root:
        rows.extend(_rows_from_canopy_tree(canopy_root))
    if not rows:
        raise ValueError("No dataset roots were provided or no supported labels were found")
    return rows


def _rows_from_esc50(root: Path) -> list[ManifestRow]:
    meta_path = root / "meta" / "esc50.csv"
    audio_dir = root / "audio"
    rows: list[ManifestRow] = []
    with meta_path.open(newline="") as handle:
        for record in csv.DictReader(handle):
            category = record["category"]
            if category not in ESC50_CLASS_MAP:
                continue
            fold = int(record["fold"])
            rows.append(
                ManifestRow(
                    path=str((audio_dir / record["filename"]).resolve()),
                    label=ESC50_CLASS_MAP[category],
                    source="esc50",
                    split=_fold_to_split(fold),
                    duration_seconds=5.0,
                    license="CC BY-NC",
                    notes=f"esc50_category={category}; fold={fold}",
                )
            )
    return rows


def _rows_from_urbansound8k(root: Path) -> list[ManifestRow]:
    meta_path = root / "metadata" / "UrbanSound8K.csv"
    audio_root = root / "audio"
    rows: list[ManifestRow] = []
    with meta_path.open(newline="") as handle:
        for record in csv.DictReader(handle):
            class_name = record["class"]
            if class_name not in URBANSOUND8K_CLASS_MAP:
                continue
            fold = int(record["fold"])
            rows.append(
                ManifestRow(
                    path=str((audio_root / f"fold{fold}" / record["slice_file_name"]).resolve()),
                    label=URBANSOUND8K_CLASS_MAP[class_name],
                    source="urbansound8k",
                    split=_fold_to_split(fold),
                    duration_seconds=None,
                    license="see-dataset-license",
                    notes=f"urbansound_class={class_name}; fold={fold}",
                )
            )
    return rows


def _rows_from_canopy_tree(root: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for label_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if label_dir.name not in LABEL_ALIASES:
            continue
        label = canonical_label(label_dir.name)
        for audio_path in sorted(label_dir.glob("*")):
            if audio_path.suffix.lower() not in {".wav", ".flac", ".mp3", ".ogg", ".m4a"}:
                continue
            rows.append(
                ManifestRow(
                    path=str(audio_path.resolve()),
                    label=label,
                    source="canopy",
                    split="train",
                    license="canopy-internal",
                    notes=f"canopy_label_dir={label_dir.name}",
                )
            )
    return rows


def _fold_to_split(fold: int) -> str:
    if fold == 10:
        return "test"
    if fold == 9:
        return "val"
    return "train"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Canopy audio threat manifest from local datasets.")
    parser.add_argument("--esc50-root", type=Path)
    parser.add_argument("--urbansound8k-root", type=Path)
    parser.add_argument("--canopy-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = build_rows(args.esc50_root, args.urbansound8k_root, args.canopy_root)
    write_manifest(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
