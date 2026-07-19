"""BirdNET embedding backbone for the open-set detector.

Swaps the weak from-scratch CNN embedder for BirdNET V2.4 (1024-d), which
generalizes far better across sites and sound types than a classifier trained
from scratch on public/urban audio. Runs through birdnetlib on the LiteRT
(ai-edge-litert) runtime, so no full TensorFlow install is required: we shim
``tensorflow.lite.Interpreter`` to LiteRT and preserve intermediate tensors so
the embedding layer is readable.

Exposes the same surface the fitting code expects from ``AudioInferenceService``:
``embed(path) -> np.ndarray``, plus ``checkpoint`` and ``model_config`` dicts.
"""
from __future__ import annotations

import sys
import types
import warnings
from pathlib import Path

import numpy as np

BIRDNET_DIM = 1024
BIRDNET_VERSION = "birdnet-v2.4"


def _install_litert_shim() -> None:
    """Make ``from tensorflow import lite`` resolve to LiteRT with tensor
    preservation, so birdnetlib runs without TensorFlow installed."""
    if "tensorflow" in sys.modules:
        return
    import ai_edge_litert.interpreter as litert

    class _PreservingInterpreter(litert.Interpreter):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("experimental_preserve_all_tensors", True)
            super().__init__(*args, **kwargs)

    tf_mod = types.ModuleType("tensorflow")
    lite_mod = types.ModuleType("tensorflow.lite")
    lite_mod.Interpreter = _PreservingInterpreter
    tf_mod.lite = lite_mod
    sys.modules["tensorflow"] = tf_mod
    sys.modules["tensorflow.lite"] = lite_mod


class BirdNETEmbedder:
    """BirdNET V2.4 embedder (mean-pooled over the 3-second analysis windows)."""

    def __init__(self) -> None:
        warnings.filterwarnings("ignore")
        _install_litert_shim()
        from birdnetlib.analyzer import Analyzer

        self._analyzer = Analyzer()
        # Compatibility surface with AudioInferenceService (read by fit_anomaly).
        self.checkpoint = {"artifact": {"model_version": BIRDNET_VERSION, "labels": []}}
        self.model_config = {"architecture": "birdnet", "embedding_dim": BIRDNET_DIM}

    _SR = 48000
    _WIN = 3  # BirdNET analysis window (seconds)

    def _extract(self, source: str) -> np.ndarray | None:
        from birdnetlib import Recording

        recording = Recording(self._analyzer, source, min_conf=0.0)
        recording.extract_embeddings()
        segments = [np.asarray(e["embeddings"], dtype=np.float64) for e in recording.embeddings]
        return np.mean(segments, axis=0) if segments else None

    def embed(self, path: str | Path) -> np.ndarray:
        pooled = self._extract(str(path))
        if pooled is not None:
            return pooled
        # BirdNET yields nothing for clips shorter than one 3s window; pad and retry.
        import tempfile

        import librosa
        import soundfile as sf

        waveform, _ = librosa.load(str(path), sr=self._SR, mono=True)
        need = self._SR * self._WIN
        if len(waveform) < need:
            waveform = np.pad(waveform, (0, need - len(waveform)))
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            sf.write(tmp.name, waveform, self._SR)
            pooled = self._extract(tmp.name)
        if pooled is None:
            raise ValueError(f"BirdNET produced no embedding for {path}")
        return pooled
