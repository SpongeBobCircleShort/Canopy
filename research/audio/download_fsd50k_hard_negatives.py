from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from research.audio.download_fsd50k_candidates import (
    download_selected_candidates,
    selected_override_fnames,
    write_candidate_curation_sheet,
    write_split_overrides,
)
from research.audio.download_fsd50k_candidates import _labels as fsd50k_labels

# Clip-level FSD50K tags useful as chainsaw/vehicle false-alarm hard negatives (train only).
FSD50K_HARD_NEGATIVE_TERMS = frozenset(
    {
        "Engine",
        "Idling",
        "Accelerating_and_revving_and_vroom",
        "Accelerating_and_revving",
        "Mechanical_fan",
        "Drill",
        "Tools",
        "Power_tool",
        "Wind",
        "Rain",
        "Thunder",
        "Thunderstorm",
        "Water",
        "Hiss",
        "Mechanisms",
    }
)

FSD50K_THREAT_TERMS = frozenset(
    {
        "Chainsaw",
        "Sawing",
        "Gunshot_and_gunfire",
        "Gunshot",
        "Gunfire",
        "Fire",
        "Crackle",
        "Explosion",
        "Fireworks",
    }
)


def select_fsd50k_hard_negative_candidates(
    metadata_csv: Path,
    *,
    target_rows: int,
    seed: int = 43,
    exclude_fnames: set[str] | None = None,
    metadata_split: str | None = "train",
) -> list[dict[str, str]]:
    exclude_fnames = exclude_fnames or set()
    candidates: list[dict[str, str]] = []
    with metadata_csv.open(newline="") as handle:
        for record in csv.DictReader(handle):
            fname = str(record.get("fname", "")).strip()
            if not fname or fname in exclude_fnames:
                continue
            if metadata_split and str(record.get("split", "")).strip().lower() != metadata_split:
                continue
            labels = fsd50k_labels(record)
            if not _is_hard_negative_labels(labels):
                continue
            candidates.append(
                {
                    "fname": fname,
                    "canopy_label": "background_unknown",
                    "labels": ",".join(labels),
                }
            )

    rng = random.Random(seed)
    rng.shuffle(candidates)
    return candidates[:target_rows]


def _is_hard_negative_labels(labels: list[str]) -> bool:
    label_set = set(labels)
    if label_set & FSD50K_THREAT_TERMS:
        return False
    return bool(label_set & FSD50K_HARD_NEGATIVE_TERMS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download FSD50K engine/tool/weather clips as background hard negatives.")
    parser.add_argument("--fsd50k-root", type=Path, default=Path("data/audio/raw/FSD50K"))
    parser.add_argument("--metadata-csv", type=Path)
    parser.add_argument("--target-rows", type=int, default=200)
    parser.add_argument("--hf-base-url", default="https://huggingface.co/datasets/Fhrozen/FSD50k/resolve/main/clips")
    parser.add_argument("--hf-split", choices=["dev", "eval"], default="dev")
    parser.add_argument("--metadata-split", choices=["train", "val", "test"], default="train")
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--curation-output",
        type=Path,
        default=Path("data/audio/curation/fsd50k_hard_negative_candidates.csv"),
    )
    parser.add_argument(
        "--split-overrides-output",
        type=Path,
        default=Path("data/audio/raw/FSD50K/FSD50K.hard_negative_splits.csv"),
    )
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    metadata_csv = args.metadata_csv or args.fsd50k_root / "FSD50K.ground_truth" / f"{args.hf_split}.csv"
    exclude = selected_override_fnames(args.split_overrides_output)
    selected_list = select_fsd50k_hard_negative_candidates(
        metadata_csv,
        target_rows=args.target_rows,
        seed=args.seed,
        exclude_fnames=exclude,
        metadata_split=args.metadata_split,
    )
    selected = {"background_unknown": selected_list}
    print(json.dumps({"selected": len(selected_list), "metadata_csv": str(metadata_csv)}, indent=2))

    if args.dry_run:
        return

    write_candidate_curation_sheet(
        args.curation_output,
        selected,
        audio_root=args.fsd50k_root,
        audio_split=args.hf_split,
        manifest_split="train",
    )
    write_split_overrides(
        args.split_overrides_output,
        selected,
        audio_split=args.hf_split,
        manifest_split="train",
    )
    download_selected_candidates(
        selected,
        output_root=args.fsd50k_root,
        hf_base_url=args.hf_base_url,
        hf_split=args.hf_split,
        insecure=args.insecure,
    )


if __name__ == "__main__":
    main()
