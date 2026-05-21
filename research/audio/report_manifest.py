from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from research.audio.labels import LABELS
from research.audio.manifest import read_manifest

SOURCE_RECORDING_KEYS = ("source_recording_id", "recording_id", "source_recording", "source_file", "site_id", "video_id", "clip_id")


def build_manifest_report(
    manifest: Path,
    *,
    min_test_support: int = 100,
    experimental: bool = False,
    test_fraction: float = 0.15,
) -> dict:
    rows = read_manifest(manifest)
    by_label = Counter(row["label"] for row in rows)
    by_split = Counter(row["split"] for row in rows)
    by_source = Counter(row["source"] for row in rows)
    by_label_split: dict[str, Counter] = defaultdict(Counter)
    by_source_label: dict[str, Counter] = defaultdict(Counter)
    by_original_class: dict[str, Counter] = defaultdict(Counter)
    splits_by_source_recording: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        by_label_split[row["label"]][row["split"]] += 1
        by_source_label[row["source"]][row["label"]] += 1
        original_class = _original_class(row["notes"])
        if original_class:
            by_original_class[row["source"]][original_class] += 1
        source_recording = _source_recording_key(row)
        if source_recording:
            splits_by_source_recording[source_recording].add(row["split"])

    test_support = {label: by_label_split[label]["test"] for label in LABELS}
    collection_targets = _collection_targets(test_support, min_test_support=min_test_support, test_fraction=test_fraction)
    split_leaks = {
        source_recording: sorted(splits)
        for source_recording, splits in sorted(splits_by_source_recording.items())
        if len(splits) > 1
    }
    failures = []
    if not experimental:
        failures = [f"{label} has {count} test rows, expected >= {min_test_support}" for label, count in test_support.items() if count < min_test_support]
        failures.extend(f"source recording appears in multiple splits: {key} -> {splits}" for key, splits in split_leaks.items())

    return {
        "manifest": str(manifest),
        "rows": len(rows),
        "counts": {
            "by_label": dict(by_label),
            "by_split": dict(by_split),
            "by_source": dict(by_source),
            "by_label_split": {label: dict(counter) for label, counter in sorted(by_label_split.items())},
            "by_source_label": {source: dict(counter) for source, counter in sorted(by_source_label.items())},
            "by_original_class": {source: dict(counter.most_common()) for source, counter in sorted(by_original_class.items())},
            "source_recording_split_leaks": split_leaks,
        },
        "validation": {
            "experimental": experimental,
            "min_test_support": min_test_support,
            "test_support": test_support,
            "collection_targets": collection_targets,
            "passed": not failures,
            "failures": failures,
        },
    }


def _original_class(notes: str) -> str:
    for key in ("esc50_category", "urbansound_class", "fsd50k_labels", "canopy_subcategory", "predicted"):
        marker = f"{key}="
        if marker not in notes:
            continue
        value = notes.split(marker, 1)[1].split(";", 1)[0].strip()
        if value:
            return f"{key}:{value}"
    return ""


def _source_recording_key(row: dict[str, str]) -> str:
    for key in SOURCE_RECORDING_KEYS:
        value = _note_value(row["notes"], key)
        if value:
            return f"{row['source']}:{key}:{value}"
    return ""


def _note_value(notes: str, key: str) -> str:
    marker = f"{key}="
    if marker not in notes:
        return ""
    return notes.split(marker, 1)[1].split(";", 1)[0].strip()


def _collection_targets(test_support: dict[str, int], *, min_test_support: int, test_fraction: float) -> dict[str, dict[str, int]]:
    safe_test_fraction = max(test_fraction, 1e-9)
    targets = {}
    for label in LABELS:
        additional_test_rows = max(0, min_test_support - int(test_support.get(label, 0)))
        targets[label] = {
            "additional_verified_test_rows_needed": additional_test_rows,
            "estimated_additional_total_rows_needed_with_balanced_split": math.ceil(additional_test_rows / safe_test_fraction)
            if additional_test_rows
            else 0,
        }
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Report and validate Canopy audio manifest quality.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-test-support", type=int, default=100)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--experimental", action="store_true")
    args = parser.parse_args()

    report = build_manifest_report(
        args.manifest,
        min_test_support=args.min_test_support,
        experimental=args.experimental,
        test_fraction=args.test_fraction,
    )
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
    if not report["validation"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
