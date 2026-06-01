from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio.merge_fsc22_manifest import merge_manifests
from research.audio.manifest import write_manifest
from research.audio.prepare_manifest import build_rows
from research.audio.report_manifest import build_manifest_report


def build_v5_manifest(
    *,
    esc50_root: Path,
    urbansound8k_root: Path | None,
    fsd50k_root: Path | None,
    hard_negative_manifests: list[Path],
    fsc22_manifest: Path | None,
    output: Path,
    report_output: Path | None = None,
    max_fsc22_per_class: int = 50,
    seed: int = 49,
) -> dict:
    rows = build_rows(
        esc50_root,
        urbansound8k_root,
        None,
        fsd50k_root,
        hard_negative_manifests,
    )
    base_output = output.with_name(output.stem + "_base.csv")
    write_manifest(base_output, rows)
    summary: dict = {
        "base_manifest": str(base_output),
        "base_rows": len(rows),
    }

    if fsc22_manifest and fsc22_manifest.exists():
        fsc22_summary = merge_manifests(
            base_manifest=base_output,
            fsc22_manifest=fsc22_manifest,
            output=output,
            max_fsc22_per_class=max_fsc22_per_class,
            seed=seed,
        )
        summary.update(fsc22_summary)
    else:
        write_manifest(output, rows)
        summary["output"] = str(output)
        summary["rows"] = len(rows)

    if report_output:
        report = build_manifest_report(output, min_test_support=100, experimental=True)
        report_output.write_text(json.dumps(report, indent=2))

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build expanded threat manifest v5: ESC-50 + UrbanSound8K + FSD50K + hard negatives + FSC22."
    )
    parser.add_argument("--esc50-root", type=Path, default=Path("data/audio/raw/ESC-50-master"))
    parser.add_argument("--urbansound8k-root", type=Path, default=Path("data/audio/raw/UrbanSound8K"))
    parser.add_argument("--fsd50k-root", type=Path, default=Path("data/audio/raw/FSD50K"))
    parser.add_argument("--hard-negative-manifest", type=Path, action="append", dest="hard_negative_manifests")
    parser.add_argument(
        "--fsc22-manifest",
        type=Path,
        default=Path("data/audio/manifests/fsc22_negatives_manifest.csv"),
    )
    parser.add_argument("--skip-fsc22", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/threat_manifest_expanded_v5.csv"))
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("data/audio/manifests/threat_manifest_expanded_v5_report.json"),
    )
    parser.add_argument("--max-fsc22-per-class", type=int, default=50)
    parser.add_argument("--seed", type=int, default=49)
    args = parser.parse_args()

    default_hard_negatives = [
        Path("data/audio/manifests/hard_negatives_expanded_hn_v3.csv"),
        Path("data/audio/manifests/dcase2020_machine_negatives_manifest.csv"),
    ]
    hard_negative_manifests = [
        path for path in (args.hard_negative_manifests or default_hard_negatives) if path.exists()
    ]
    fsc22_manifest = None if args.skip_fsc22 else args.fsc22_manifest
    urbansound_root = args.urbansound8k_root if args.urbansound8k_root.exists() else None
    fsd50k_root = args.fsd50k_root if args.fsd50k_root.exists() else None

    summary = build_v5_manifest(
        esc50_root=args.esc50_root,
        urbansound8k_root=urbansound_root,
        fsd50k_root=fsd50k_root,
        hard_negative_manifests=hard_negative_manifests,
        fsc22_manifest=fsc22_manifest,
        output=args.output,
        report_output=args.report_output,
        max_fsc22_per_class=args.max_fsc22_per_class,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
