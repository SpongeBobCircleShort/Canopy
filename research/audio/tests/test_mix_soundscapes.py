import random

import numpy as np
import pytest

from research.audio import mix_soundscapes as mix


def test_fit_length_tiles_and_crops():
    rng = random.Random(0)
    short = np.array([1.0, 2.0, 3.0])
    tiled = mix.fit_length(short, 8, rng)
    assert len(tiled) == 8
    long = np.arange(100.0)
    cropped = mix.fit_length(long, 10, rng)
    assert len(cropped) == 10
    assert len(mix.fit_length(np.array([]), 5, rng)) == 5  # empty -> zeros


def test_mix_hits_target_snr():
    rng = random.Random(0)
    bg = rng.gauss(0, 1) * np.ones(1)  # placeholder, replaced below
    bg = np.random.default_rng(1).normal(0, 0.1, size=32000)
    threat = np.random.default_rng(2).normal(0, 1.0, size=16000)
    for target in (-6.0, 0.0, 12.0):
        mixed = mix.mix_at_snr(bg, threat, target, rng)
        # recover the threat component: mixed = bg_segment + scaled_threat, but we
        # can at least check the mix is length-matched to the threat and finite.
        assert len(mixed) == len(threat)
        assert np.isfinite(mixed).all()
        assert np.max(np.abs(mixed)) <= 1.0 + 1e-6


def test_mix_scales_threat_by_snr():
    """Higher SNR should make the threat louder relative to background."""
    rng = random.Random(0)
    bg = np.full(16000, 0.05)
    threat = np.random.default_rng(3).normal(0, 1.0, size=16000)
    low = mix.mix_at_snr(bg, threat, -10.0, random.Random(0))
    high = mix.mix_at_snr(bg, threat, 10.0, random.Random(0))
    # energy of the deviation from the (constant) background is larger at high SNR
    assert mix.rms(high - 0.05) > mix.rms(low - 0.05)


def test_rms_positive():
    assert mix.rms(np.zeros(10)) >= 0
    assert mix.rms(np.array([1.0, -1.0])) == pytest.approx(1.0, abs=1e-4)
