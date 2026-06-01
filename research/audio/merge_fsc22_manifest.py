from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from research.audio.manifest import MANIFEST_COLUMNS, write_manifest


def merge_manifests(
    *,
    base_manifest: Path,
    fsc22_manifest: Path,
    output: Path,
    max_fsc22_per_class: int | None = None,
    seed: int = 48,
) -> dict:
    rows = _read_rows(base_manifest)
    fsc22_rows = _sample_fsc22_rows(_read_rows(fsc22_manifest), max_per_class=max_fsc22_per_class, seed=seed)
    for row in fsc22_rows:
        row["notes"] = f"{row.get('notes', '')}; merged_fsc22_negatives=true".strip("; ")
    rows.extend(fsc22_rows)
    write_manifest(output, rows)
    return {
        "output": str(output),
        "rows": len(rows),
        "base_rows": len(rows) - len(fsc22_rows),
        "fsc22_rows": len(fsc22_rows),
        "max_fsc22_per_class": max_fsc22_per_class,
    }


def _sample_fsc22_rows(rows: list[dict[str, str]], *, max_per_class: int | None, seed: int) -> list[dict[str, str]]:
    if max_per_class is None:
        return rows
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_fsc22_class(row)].append(row)
    rng = random.Random(seed)
    selected: list[dict[str, str]] = []
    for class_name in sorted(grouped):
        class_rows = sorted(grouped[class_name], key=lambda row: row["path"])
        rng.shuffle(class_rows)
        selected.extend(class_rows[:max_per_class])
    return selected


def _fsc22_class(row: dict[str, str]) -> str:
    marker = "fsc22_class="
    notes = row.get("notes", "")
    if marker in notes:
        return notes.split(marker, 1)[1].split(";", 1)[0]
    return row.get("label", "unknown")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge train-only FSC22 negatives into a Canopy audio manifest.")
    parser.add_argument("--base-manifest", type=Path, default=Path("data/audio/manifests/threat_manifest_expanded_v5_base.csv"))
    parser.add_argument("--fsc22-manifest", type=Path, default=Path("data/audio/manifests/fsc22_negatives_manifest.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/threat_manifest_expanded_v5.csv"))
    parser.add_argument("--max-fsc22-per-class", type=int, default=50)
    parser.add_argument("--seed", type=int, default=48)
    args = parser.parse_args()

    summary = merge_manifests(
        base_manifest=args.base_manifest,
        fsc22_manifest=args.fsc22_manifest,
        output=args.output,
        max_fsc22_per_class=args.max_fsc22_per_class,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
