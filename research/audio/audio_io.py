from __future__ import annotations

from pathlib import Path


def load_and_preprocess_audio(path: str | Path, *, sample_rate: int, clip_seconds: float):
    torch, torchaudio = _torch_modules()
    waveform, source_rate = torchaudio.load(str(path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if source_rate != sample_rate:
        waveform = torchaudio.functional.resample(waveform, source_rate, sample_rate)
    target_frames = int(sample_rate * clip_seconds)
    current_frames = waveform.shape[1]
    if current_frames < target_frames:
        waveform = torch.nn.functional.pad(waveform, (0, target_frames - current_frames))
    elif current_frames > target_frames:
        waveform = waveform[:, :target_frames]
    return waveform


def waveform_to_log_mel(waveform, *, sample_rate: int, n_mels: int):
    torch, torchaudio = _torch_modules()
    transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=sample_rate,
        n_fft=1024,
        hop_length=320,
        n_mels=n_mels,
        power=2.0,
    )
    mel = transform(waveform)
    log_mel = torch.log(mel + 1e-6)
    mean = log_mel.mean()
    std = log_mel.std().clamp_min(1e-6)
    return (log_mel - mean) / std


def load_log_mel(path: str | Path, *, sample_rate: int, clip_seconds: float, n_mels: int):
    waveform = load_and_preprocess_audio(path, sample_rate=sample_rate, clip_seconds=clip_seconds)
    return waveform_to_log_mel(waveform, sample_rate=sample_rate, n_mels=n_mels)


def _torch_modules():
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to use audio model code") from exc
    return torch, torchaudio
