from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from research.audio.manifest import MANIFEST_COLUMNS, write_manifest


DEFAULT_RFCX_CURATION = Path("data/audio/curation/rfcx_frugalai_candidates.csv")
DEFAULT_OUTPUT = Path("data/audio/manifests/threat_manifest_forest_v1.csv")
DEFAULT_REPORT_OUTPUT = Path("data/audio/manifests/threat_manifest_forest_v1_report.json")


def build_forest_manifest(
    *,
    rfcx_curation: Path,
    fsc22_manifest: Path | None,
    kaggle_chainsaw_manifest: Path | None,
    kaggle_fire_manifest: Path | None,
    kaggle_gunshot_manifest: Path | None,
    kaggle_vehicle_manifest: Path | None,
    output: Path,
    report_output: Path | None = None,
    rfcx_val_fraction: float = 0.2,
    rfcx_chainsaw_max_per_site: int | None = None,
    rfcx_background_max_per_site: int | None = None,
    rfcx_heldout_site: str | None = None,
    chainsaw_background_only: bool = False,
    kaggle_chainsaw_train_rows: int = 300,
    kaggle_fire_rows_per_split: int | None = None,
    kaggle_gunshot_rows_per_split: int | None = 160,
    kaggle_vehicle_rows_per_split: int | None = 220,
    fsc22_rows_per_class: int | None = 50,
    seed: int = 56,
) -> dict:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []

    rfcx_rows, rfcx_report = _rfcx_rows(
        rfcx_curation,
        val_fraction=rfcx_val_fraction,
        chainsaw_max_per_site=rfcx_chainsaw_max_per_site,
        background_max_per_site=rfcx_background_max_per_site,
        heldout_site=rfcx_heldout_site,
        seed=seed,
    )
    rows.extend(rfcx_rows)

    if fsc22_manifest and fsc22_manifest.exists():
        fsc22_rows = _read_rows(fsc22_manifest)
        if chainsaw_background_only:
            fsc22_rows = [row for row in fsc22_rows if row.get("label") == "background_unknown"]
        rows.extend(
            _train_only_rows(
                _sample_fsc22_by_class(fsc22_rows, rows_per_class=fsc22_rows_per_class, rng=rng),
                source_note="forest_v1=train_only; forest_background_negative=true",
            )
        )
    if kaggle_chainsaw_manifest and kaggle_chainsaw_manifest.exists():
        rows.extend(
            _train_only_rows(
                _sample_groups(_read_rows(kaggle_chainsaw_manifest), target_rows=kaggle_chainsaw_train_rows, rng=rng),
                source_note=f"forest_v1=train_only; kaggle_chainsaw_train_rows={kaggle_chainsaw_train_rows}",
            )
        )
    if not chainsaw_background_only and kaggle_fire_manifest and kaggle_fire_manifest.exists():
        rows.extend(_sample_by_split(_read_rows(kaggle_fire_manifest), rows_per_split=kaggle_fire_rows_per_split, rng=rng))
    if not chainsaw_background_only and kaggle_gunshot_manifest and kaggle_gunshot_manifest.exists():
        rows.extend(_sample_by_split(_read_rows(kaggle_gunshot_manifest), rows_per_split=kaggle_gunshot_rows_per_split, rng=rng))
    if not chainsaw_background_only and kaggle_vehicle_manifest and kaggle_vehicle_manifest.exists():
        rows.extend(_sample_by_split(_read_rows(kaggle_vehicle_manifest), rows_per_split=kaggle_vehicle_rows_per_split, rng=rng))

    rows = [_normalize_row(row) for row in rows]
    write_manifest(output, rows)
    report = _manifest_report(
        rows,
        rfcx_report=rfcx_report,
        seed=seed,
        chainsaw_background_only=chainsaw_background_only,
    )
    if report_output:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(report, indent=2) + "\n")
    return {"output": str(output), "rows": len(rows), "report_output": str(report_output) if report_output else None, **report}


def _rfcx_rows(
    curation_path: Path,
    *,
    val_fraction: float,
    chainsaw_max_per_site: int | None,
    background_max_per_site: int | None,
    heldout_site: str | None,
    seed: int,
) -> tuple[list[dict[str, str]], dict]:
    heldout_site = heldout_site.strip() if heldout_site else None
    source_rows = _read_rows(curation_path)
    parsed = []
    for row in source_rows:
        site_id, recording_id = _rfcx_site_and_recording_id(row["path"])
        split = row.get("split", "train")
        parsed.append((row, site_id, recording_id, split))

    source_chainsaw_sites = Counter(site_id for row, site_id, _, _ in parsed if row.get("label") == "chainsaw")
    parsed, site_cap_report = _apply_rfcx_site_caps(
        parsed,
        chainsaw_max_per_site=chainsaw_max_per_site,
        background_max_per_site=background_max_per_site,
        uncapped_sites={heldout_site} if heldout_site else set(),
        seed=seed,
    )

    test_recording_ids = {
        recording_id
        for _, site_id, recording_id, split in parsed
        if split == "test" and (heldout_site is None or site_id == heldout_site)
    }
    train_rows_by_label: dict[str, dict[str, list[tuple[dict[str, str], str, str, str]]]] = defaultdict(lambda: defaultdict(list))
    output_rows: list[dict[str, str]] = []
    dropped_overlap = 0

    for row, site_id, recording_id, split in parsed:
        if heldout_site and site_id == heldout_site:
            output_rows.append(
                _rfcx_manifest_row(
                    row,
                    split="test",
                    site_id=site_id,
                    recording_id=recording_id,
                    heldout_site=heldout_site,
                )
            )
        elif split == "test" and heldout_site is None:
            output_rows.append(_rfcx_manifest_row(row, split="test", site_id=site_id, recording_id=recording_id))
        elif recording_id in test_recording_ids:
            dropped_overlap += 1
        else:
            train_rows_by_label[row["label"]][recording_id].append((row, site_id, recording_id, split))

    rng = random.Random(seed)
    for label, groups in sorted(train_rows_by_label.items()):
        group_items = list(groups.items())
        rng.shuffle(group_items)
        val_group_count = max(1, round(len(group_items) * val_fraction)) if group_items else 0
        val_recordings = {recording_id for recording_id, _ in group_items[:val_group_count]}
        for recording_id, group_rows in group_items:
            split = "val" if recording_id in val_recordings else "train"
            for row, site_id, _, _ in group_rows:
                output_rows.append(_rfcx_manifest_row(row, split=split, site_id=site_id, recording_id=recording_id))

    chainsaw_sites = Counter(site_id for row, site_id, _, _ in parsed if row.get("label") == "chainsaw")
    report = {
        "rfcx_source_rows": len(source_rows),
        "rfcx_rows": len(output_rows),
        "rfcx_heldout_site": heldout_site or "",
        "rfcx_heldout_rows": sum(1 for row in output_rows if f"site_id={heldout_site}" in row.get("notes", "") and row["split"] == "test")
        if heldout_site
        else 0,
        "rfcx_heldout_label_counts": dict(
            sorted(
                Counter(
                    row["label"]
                    for row in output_rows
                    if heldout_site and f"site_id={heldout_site}" in row.get("notes", "") and row["split"] == "test"
                ).items()
            )
        ),
        "rfcx_dropped_train_val_overlap_with_test": dropped_overlap,
        "rfcx_source_chainsaw_unique_inferred_sites": len(source_chainsaw_sites),
        "rfcx_source_chainsaw_inferred_site_counts": dict(source_chainsaw_sites.most_common()),
        "rfcx_selected_chainsaw_unique_inferred_sites": len(chainsaw_sites),
        "rfcx_selected_chainsaw_inferred_site_counts": dict(chainsaw_sites.most_common()),
        **site_cap_report,
    }
    return output_rows, report


def _apply_rfcx_site_caps(
    parsed: list[tuple[dict[str, str], str, str, str]],
    *,
    chainsaw_max_per_site: int | None,
    background_max_per_site: int | None,
    uncapped_sites: set[str],
    seed: int,
) -> tuple[list[tuple[dict[str, str], str, str, str]], dict]:
    caps = {"chainsaw": chainsaw_max_per_site, "background_unknown": background_max_per_site}
    if all(value is None for value in caps.values()):
        return parsed, {
            "rfcx_site_caps": {},
            "rfcx_site_cap_dropped_rows": 0,
            "rfcx_site_cap_dropped_by_label": {},
        }

    rng = random.Random(seed)
    selected: list[tuple[dict[str, str], str, str, str]] = []
    dropped_by_label: Counter[str] = Counter()
    by_label_site: dict[tuple[str, str], list[tuple[dict[str, str], str, str, str]]] = defaultdict(list)
    uncapped: list[tuple[dict[str, str], str, str, str]] = []
    for item in parsed:
        row, site_id, _, _ = item
        cap = caps.get(row.get("label", ""))
        if cap is None or site_id in uncapped_sites:
            uncapped.append(item)
        else:
            by_label_site[(row["label"], site_id)].append(item)

    selected.extend(uncapped)
    for (label, _), site_rows in sorted(by_label_site.items()):
        shuffled = list(site_rows)
        rng.shuffle(shuffled)
        cap = caps[label]
        assert cap is not None
        selected.extend(shuffled[:cap])
        dropped_by_label[label] += max(0, len(shuffled) - cap)

    return selected, {
        "rfcx_site_caps": {label: cap for label, cap in caps.items() if cap is not None},
        "rfcx_site_cap_dropped_rows": sum(dropped_by_label.values()),
        "rfcx_site_cap_dropped_by_label": dict(sorted(dropped_by_label.items())),
    }


def _rfcx_manifest_row(
    row: dict[str, str],
    *,
    split: str,
    site_id: str,
    recording_id: str,
    heldout_site: str | None = None,
) -> dict[str, str]:
    notes = row.get("notes", "")
    heldout_note = f"; heldout_site={heldout_site}" if heldout_site else ""
    notes = (
        f"{notes}; source_recording_id={recording_id}; site_id={site_id}; "
        f"forest_domain_v1=true; original_split={row.get('split', '')}{heldout_note}"
    ).strip("; ")
    return {
        "path": str(Path(row["path"]).resolve()),
        "label": row["label"],
        "source": "rfcx_frugalai",
        "split": split,
        "duration_seconds": "3",
        "license": row.get("license", "CC BY-NC 4.0"),
        "notes": notes,
    }


def _rfcx_site_and_recording_id(path: str) -> tuple[str, str]:
    stem = Path(path).stem
    match = re.search(r"_(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})_", stem)
    if not match:
        return "unknown", stem
    prefix = stem[: match.start()]
    site_id = re.sub(r"_(?:19|20)\d{2}$", "", prefix) or "unknown"
    return site_id, f"{site_id}_{match.group('uuid')}"


def _sample_by_split(rows: list[dict[str, str]], *, rows_per_split: int | None, rng: random.Random) -> list[dict[str, str]]:
    if rows_per_split is None:
        return rows
    selected: list[dict[str, str]] = []
    by_split: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
    for split in ("train", "val", "test"):
        selected.extend(_sample_groups(by_split.get(split, []), target_rows=rows_per_split, rng=rng))
    return selected


def _sample_fsc22_by_class(rows: list[dict[str, str]], *, rows_per_class: int | None, rng: random.Random) -> list[dict[str, str]]:
    if rows_per_class is None:
        return rows
    by_class: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_class[_note_value(row.get("notes", ""), "fsc22_class") or row["label"]].append(row)
    selected: list[dict[str, str]] = []
    for class_name in sorted(by_class):
        class_rows = sorted(by_class[class_name], key=lambda item: item["path"])
        rng.shuffle(class_rows)
        selected.extend(class_rows[:rows_per_class])
    return selected


def _sample_groups(rows: list[dict[str, str]], *, target_rows: int, rng: random.Random) -> list[dict[str, str]]:
    if target_rows <= 0 or len(rows) <= target_rows:
        return rows
    by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_group[_note_value(row.get("notes", ""), "source_recording_id") or Path(row["path"]).stem].append(row)
    groups = list(by_group.values())
    rng.shuffle(groups)
    selected: list[dict[str, str]] = []
    for group_rows in groups:
        if len(selected) >= target_rows:
            break
        selected.extend(sorted(group_rows, key=lambda item: item["path"]))
    return selected[:target_rows]


def _train_only_rows(rows: list[dict[str, str]], *, source_note: str) -> list[dict[str, str]]:
    output = []
    for row in rows:
        updated = _normalize_row(row)
        original_split = updated["split"]
        updated["split"] = "train"
        updated["notes"] = f"{updated['notes']}; original_split={original_split}; {source_note}".strip("; ")
        output.append(updated)
    return output


def _manifest_report(rows: list[dict[str, str]], *, rfcx_report: dict, seed: int, chainsaw_background_only: bool) -> dict:
    return {
        "seed": seed,
        "chainsaw_background_only": chainsaw_background_only,
        "label_counts": dict(sorted(Counter(row["label"] for row in rows).items())),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "source_counts": dict(sorted(Counter(row["source"] for row in rows).items())),
        "split_label_counts": {
            f"{split}/{label}": count
            for (split, label), count in sorted(Counter((row["split"], row["label"]) for row in rows).items())
        },
        **rfcx_report,
    }


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {column: str(row.get(column, "")) for column in MANIFEST_COLUMNS}


def _note_value(notes: str, key: str) -> str:
    marker = f"{key}="
    if marker not in notes:
        return ""
    return notes.split(marker, 1)[1].split(";", 1)[0].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the forest-domain v1 Canopy audio manifest.")
    parser.add_argument("--rfcx-curation", type=Path, default=DEFAULT_RFCX_CURATION)
    parser.add_argument("--fsc22-manifest", type=Path, default=Path("data/audio/manifests/fsc22_negatives_manifest.csv"))
    parser.add_argument("--kaggle-chainsaw-manifest", type=Path, default=Path("data/audio/manifests/kaggle_chainsaw_manifest.csv"))
    parser.add_argument("--kaggle-fire-manifest", type=Path, default=Path("data/audio/manifests/kaggle_forest_wildfire_manifest.csv"))
    parser.add_argument("--kaggle-gunshot-manifest", type=Path, default=Path("data/audio/manifests/kaggle_gunshot_manifest.csv"))
    parser.add_argument("--kaggle-vehicle-manifest", type=Path, default=Path("data/audio/manifests/kaggle_vehicle_manifest.csv"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--rfcx-val-fraction", type=float, default=0.2)
    parser.add_argument("--rfcx-chainsaw-max-per-site", type=int)
    parser.add_argument("--rfcx-background-max-per-site", type=int)
    parser.add_argument("--rfcx-heldout-site", help="Reserve all RFCx rows from this inferred site as the only test split.")
    parser.add_argument("--chainsaw-background-only", action="store_true", help="Build a chainsaw/background-only manifest.")
    parser.add_argument("--kaggle-chainsaw-train-rows", type=int, default=300)
    parser.add_argument("--kaggle-gunshot-rows-per-split", type=int, default=160)
    parser.add_argument("--kaggle-vehicle-rows-per-split", type=int, default=220)
    parser.add_argument("--fsc22-rows-per-class", type=int, default=50)
    parser.add_argument("--seed", type=int, default=56)
    args = parser.parse_args()

    summary = build_forest_manifest(
        rfcx_curation=args.rfcx_curation,
        fsc22_manifest=args.fsc22_manifest,
        kaggle_chainsaw_manifest=args.kaggle_chainsaw_manifest,
        kaggle_fire_manifest=args.kaggle_fire_manifest,
        kaggle_gunshot_manifest=args.kaggle_gunshot_manifest,
        kaggle_vehicle_manifest=args.kaggle_vehicle_manifest,
        output=args.output,
        report_output=args.report_output,
        rfcx_val_fraction=args.rfcx_val_fraction,
        rfcx_chainsaw_max_per_site=args.rfcx_chainsaw_max_per_site,
        rfcx_background_max_per_site=args.rfcx_background_max_per_site,
        rfcx_heldout_site=args.rfcx_heldout_site,
        chainsaw_background_only=args.chainsaw_background_only,
        kaggle_chainsaw_train_rows=args.kaggle_chainsaw_train_rows,
        kaggle_gunshot_rows_per_split=args.kaggle_gunshot_rows_per_split,
        kaggle_vehicle_rows_per_split=args.kaggle_vehicle_rows_per_split,
        fsc22_rows_per_class=args.fsc22_rows_per_class,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
