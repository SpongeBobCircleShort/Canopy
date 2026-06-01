from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from research.audio.manifest import MANIFEST_COLUMNS, write_manifest


def build_manifest(
    *,
    base_manifest: Path,
    kaggle_chainsaw_manifest: Path,
    kaggle_gunshot_manifest: Path | None,
    kaggle_fire_manifest: Path | None,
    kaggle_vehicle_manifest: Path,
    output: Path,
    chainsaw_target_rows: int = 300,
    gunshot_target_rows: int = 500,
    fire_target_rows: int = 500,
    vehicle_target_rows: int = 1400,
    seed: int = 45,
) -> dict:
    rows = _read_rows(base_manifest)
    chainsaw_rows = _sample_groups(_read_rows(kaggle_chainsaw_manifest), target_rows=chainsaw_target_rows, seed=seed + 1)
    gunshot_rows = _sample_groups(_read_rows(kaggle_gunshot_manifest), target_rows=gunshot_target_rows, seed=seed + 2) if kaggle_gunshot_manifest else []
    fire_rows = _sample_groups(_read_rows(kaggle_fire_manifest), target_rows=fire_target_rows, seed=seed + 3) if kaggle_fire_manifest else []
    vehicle_rows = _sample_vehicle_groups(
        _read_rows(kaggle_vehicle_manifest),
        target_rows=vehicle_target_rows,
        seed=seed,
    )
    rows.extend(_train_only_rows(chainsaw_rows, source_note=f"kaggle_balanced_v2=train_only; chainsaw_target_rows={chainsaw_target_rows}"))
    rows.extend(_train_only_rows(gunshot_rows, source_note=f"kaggle_balanced_v2=train_only; gunshot_target_rows={gunshot_target_rows}"))
    rows.extend(_train_only_rows(fire_rows, source_note=f"kaggle_balanced_v2=train_only; fire_target_rows={fire_target_rows}"))
    rows.extend(_train_only_rows(vehicle_rows, source_note=f"kaggle_balanced_v2=train_only; vehicle_target_rows={vehicle_target_rows}"))
    write_manifest(output, rows)
    return {
        "output": str(output),
        "rows": len(rows),
        "base_manifest": str(base_manifest),
        "kaggle_chainsaw_rows": len(chainsaw_rows),
        "kaggle_gunshot_rows": len(gunshot_rows),
        "kaggle_fire_rows": len(fire_rows),
        "kaggle_vehicle_rows": len(vehicle_rows),
        "chainsaw_target_rows": chainsaw_target_rows,
        "gunshot_target_rows": gunshot_target_rows,
        "fire_target_rows": fire_target_rows,
        "vehicle_target_rows": vehicle_target_rows,
        "seed": seed,
    }


def _sample_vehicle_groups(rows: list[dict[str, str]], *, target_rows: int, seed: int) -> list[dict[str, str]]:
    by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_category[_relative_category(row)].append(row)
    if len(by_category) > 1:
        return _round_robin_categories(by_category, target_rows=target_rows, seed=seed)
    return _sample_groups(rows, target_rows=target_rows, seed=seed)


def _sample_groups(rows: list[dict[str, str]], *, target_rows: int, seed: int) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[_note_value(row["notes"], "source_recording_id") or Path(row["path"]).stem].append(row)

    rng = random.Random(seed)
    shuffled = list(groups.items())
    rng.shuffle(shuffled)
    selected: list[dict[str, str]] = []
    for _, group_rows in shuffled:
        if len(selected) >= target_rows:
            break
        selected.extend(sorted(group_rows, key=lambda row: row["path"]))
    return selected[:target_rows]


def _round_robin_categories(by_category: dict[str, list[dict[str, str]]], *, target_rows: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    category_groups = []
    for category, rows in sorted(by_category.items()):
        sampled_groups = defaultdict(list)
        for row in rows:
            sampled_groups[_note_value(row["notes"], "source_recording_id") or Path(row["path"]).stem].append(row)
        groups = [sorted(group_rows, key=lambda row: row["path"]) for group_rows in sampled_groups.values()]
        rng.shuffle(groups)
        category_groups.append((category, groups))

    selected: list[dict[str, str]] = []
    exhausted = set()
    while len(selected) < target_rows and len(exhausted) < len(category_groups):
        for index, (_, groups) in enumerate(category_groups):
            if index in exhausted:
                continue
            if not groups:
                exhausted.add(index)
                continue
            selected.extend(groups.pop(0))
            if len(selected) >= target_rows:
                break
    rng.shuffle(selected)
    return selected[:target_rows]


def _train_only_rows(rows: list[dict[str, str]], *, source_note: str) -> list[dict[str, str]]:
    train_rows = []
    for row in rows:
        updated = {column: row.get(column, "") for column in MANIFEST_COLUMNS}
        original_split = updated["split"]
        updated["split"] = "train"
        updated["notes"] = f"{updated['notes']}; original_split={original_split}; {source_note}".strip("; ")
        train_rows.append(updated)
    return train_rows


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _note_value(notes: str, key: str) -> str:
    marker = f"{key}="
    if marker not in notes:
        return ""
    return notes.split(marker, 1)[1].split(";", 1)[0].strip()


def _relative_category(row: dict[str, str]) -> str:
    relative_path = _note_value(row.get("notes", ""), "relative_path")
    if relative_path:
        return relative_path.split("/", 1)[0]
    return Path(row["path"]).parent.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a train-only capped Kaggle-balanced audio manifest.")
    parser.add_argument("--base-manifest", type=Path, default=Path("data/audio/manifests/threat_manifest_expanded_hn_v4.csv"))
    parser.add_argument("--kaggle-chainsaw-manifest", type=Path, default=Path("data/audio/manifests/kaggle_chainsaw_manifest.csv"))
    parser.add_argument("--kaggle-gunshot-manifest", type=Path, default=Path("data/audio/manifests/kaggle_gunshot_manifest.csv"))
    parser.add_argument("--kaggle-fire-manifest", type=Path, default=Path("data/audio/manifests/kaggle_forest_wildfire_manifest.csv"))
    parser.add_argument("--kaggle-vehicle-manifest", type=Path, default=Path("data/audio/manifests/kaggle_vehicle_janboubiabderrahim_manifest.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/threat_manifest_kaggle_balanced_v2.csv"))
    parser.add_argument("--chainsaw-target-rows", type=int, default=300)
    parser.add_argument("--gunshot-target-rows", type=int, default=500)
    parser.add_argument("--fire-target-rows", type=int, default=500)
    parser.add_argument("--vehicle-target-rows", type=int, default=1400)
    parser.add_argument("--seed", type=int, default=45)
    args = parser.parse_args()

    summary = build_manifest(
        base_manifest=args.base_manifest,
        kaggle_chainsaw_manifest=args.kaggle_chainsaw_manifest,
        kaggle_gunshot_manifest=args.kaggle_gunshot_manifest if args.kaggle_gunshot_manifest.exists() else None,
        kaggle_fire_manifest=args.kaggle_fire_manifest if args.kaggle_fire_manifest.exists() else None,
        kaggle_vehicle_manifest=args.kaggle_vehicle_manifest,
        output=args.output,
        chainsaw_target_rows=args.chainsaw_target_rows,
        gunshot_target_rows=args.gunshot_target_rows,
        fire_target_rows=args.fire_target_rows,
        vehicle_target_rows=args.vehicle_target_rows,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
