from pathlib import Path

import pytest

from research.audio.labels import canonical_label
from research.audio.manifest import ManifestRow, read_manifest, validate_manifest_rows, write_manifest
from research.audio.prepare_manifest import assign_balanced_splits


def test_label_aliases_map_to_canopy_taxonomy() -> None:
    assert canonical_label("gun_shot") == "gunshot"
    assert canonical_label("crackling fire") == "fire_crackle"
    assert canonical_label("engine_idling") == "vehicle"
    with pytest.raises(ValueError, match="Unsupported audio label"):
        canonical_label("birdsong")


def test_manifest_round_trip_and_validation(tmp_path: Path) -> None:
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"not-real-audio")
    manifest_path = tmp_path / "manifest.csv"

    write_manifest(
        manifest_path,
        [
            ManifestRow(
                path=str(audio_file),
                label="gun_shot",
                source="unit",
                split="train",
                duration_seconds=1.2,
                license="test",
                notes="synthetic",
            )
        ],
    )

    rows = read_manifest(manifest_path)
    assert rows[0]["label"] == "gunshot"
    assert rows[0]["split"] == "train"


def test_manifest_rejects_bad_split() -> None:
    with pytest.raises(ValueError, match="split must be one of"):
        validate_manifest_rows(
            [
                {
                    "path": "missing.wav",
                    "label": "chainsaw",
                    "source": "unit",
                    "split": "holdout",
                    "duration_seconds": "",
                    "license": "",
                    "notes": "",
                }
            ],
            require_files=False,
        )


def test_balanced_split_assigner_covers_each_label() -> None:
    rows = []
    for label in ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]:
        for index in range(10):
            rows.append(ManifestRow(path=f"/tmp/{label}-{index}.wav", label=label, source="unit", split="train"))

    split_rows = assign_balanced_splits(rows, seed=1, val_fraction=0.2, test_fraction=0.2)
    observed = {(row.label, row.split) for row in split_rows}

    for label in ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]:
        assert (label, "train") in observed
        assert (label, "val") in observed
        assert (label, "test") in observed
