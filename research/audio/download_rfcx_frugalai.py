from __future__ import annotations

import argparse
import csv
from pathlib import Path

CURATION_COLUMNS = [
    "path",
    "label",
    "split",
    "source_recording_id",
    "site_id",
    "license",
    "reviewer",
    "decision",
    "notes",
]

RFCX_LABELS = {
    0: "chainsaw",
    1: "background_unknown",
    "0": "chainsaw",
    "1": "background_unknown",
    "chainsaw": "chainsaw",
    "environment": "background_unknown",
}


def download_rfcx_frugalai(
    *,
    output_root: Path,
    dataset_name: str,
    splits: list[str],
    max_chainsaw_per_split: int,
    max_background_per_split: int,
) -> list[dict[str, str]]:
    try:
        from datasets import Audio, load_dataset
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to use the RFCx downloader") from exc

    rows = []
    for split in splits:
        dataset = load_dataset(dataset_name, split=split, streaming=True)
        dataset = dataset.cast_column("audio", Audio(decode=False))
        counts = {"chainsaw": 0, "background_unknown": 0}
        for sample in dataset:
            label = RFCX_LABELS.get(sample["label"])
            if label is None:
                continue
            if label == "chainsaw" and counts[label] >= max_chainsaw_per_split:
                continue
            if label == "background_unknown" and counts[label] >= max_background_per_split:
                continue
            audio = sample["audio"]
            path = Path(audio.get("path") or f"rfcx-{split}-{label}-{counts[label]}.wav")
            audio_bytes = audio.get("bytes")
            if not audio_bytes:
                continue
            output_path = output_root / split / label / path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)
            counts[label] += 1
            rows.append(
                {
                    "path": str(output_path),
                    "label": label,
                    "split": "test" if split == "test" else "train",
                    "source_recording_id": output_path.stem,
                    "site_id": "",
                    "license": "CC BY-NC 4.0",
                    "reviewer": "",
                    "decision": "needs_review",
                    "notes": f"rfcx_split={split}; original_label={sample['label']}",
                }
            )
            print(f"downloaded split={split} label={label} path={output_path}", flush=True)
            if counts["chainsaw"] >= max_chainsaw_per_split and counts["background_unknown"] >= max_background_per_split:
                break
    return rows


def write_curation_sheet(output: Path, rows: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CURATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download selected RFCx FrugalAI chainsaw/background clips.")
    parser.add_argument("--output-root", type=Path, default=Path("data/audio/raw/RFCx-FrugalAI"))
    parser.add_argument("--dataset-name", default="rfcx/frugalai")
    parser.add_argument("--splits", nargs="+", default=["train", "test"])
    parser.add_argument("--max-chainsaw-per-split", type=int, default=250)
    parser.add_argument("--max-background-per-split", type=int, default=250)
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/rfcx_frugalai_candidates.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(
            "RFCx FrugalAI is gated on Hugging Face. Accept the dataset conditions, set HF_TOKEN if needed, "
            "then rerun without --dry-run."
        )
        return

    rows = download_rfcx_frugalai(
        output_root=args.output_root,
        dataset_name=args.dataset_name,
        splits=args.splits,
        max_chainsaw_per_split=args.max_chainsaw_per_split,
        max_background_per_split=args.max_background_per_split,
    )
    write_curation_sheet(args.curation_output, rows)
    print(f"wrote {len(rows)} rows to {args.curation_output}")


if __name__ == "__main__":
    main()
