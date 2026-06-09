"""Open-set acoustic anomaly inference: audio clip -> anomaly score + likelihoods.

This is the torch-backed wrapper. It loads a fitted anomaly artifact, embeds a
clip with the CNN embedder (reusing ``AudioInferenceService.embed``), and scores
it with the numpy core in ``research.audio.anomaly``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.audio import anomaly
from research.audio.infer import AudioInferenceService


class AnomalyDetector:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.artifact = anomaly.load_artifact(self.model_dir)
        self.model_version = self.artifact.get("model_version", anomaly.ARTIFACT_VERSION)
        embedder_dir = self.artifact.get("embedder", {}).get("model_dir")
        if not embedder_dir:
            raise ValueError(
                f"Anomaly artifact at {self.model_dir} has no embedder.model_dir; "
                "re-fit with research.audio.fit_anomaly."
            )
        self._embedder = AudioInferenceService(Path(embedder_dir))

    def score(self, audio_path: Path) -> dict:
        embedding = self._embedder.embed(Path(audio_path))
        result = anomaly.score_embedding(embedding, self.artifact)
        result["model_version"] = self.model_version
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a clip with a Canopy open-set anomaly detector.")
    parser.add_argument("--model", type=Path, required=True, help="Anomaly artifact directory")
    parser.add_argument("--audio", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(AnomalyDetector(args.model).score(args.audio), indent=2))


if __name__ == "__main__":
    main()
