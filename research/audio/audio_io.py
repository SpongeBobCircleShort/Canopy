from __future__ import annotations

from pathlib import Path


def load_and_preprocess_audio(path: str | Path, *, sample_rate: int, clip_seconds: float):
    torch, torchaudio = _torch_modules()
    try:
        waveform, source_rate = torchaudio.load(str(path))
    except RuntimeError:
        waveform, source_rate = _load_audio_fallback(path, torch)
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


def augment_waveform(
    waveform,
    *,
    gain_min: float = 0.85,
    gain_max: float = 1.15,
    noise_std: float = 0.003,
    max_shift_fraction: float = 0.08,
):
    torch, _ = _torch_modules()
    if gain_max > 0 and gain_min > 0:
        gain = torch.empty(1).uniform_(gain_min, gain_max).item()
        waveform = waveform * gain
    if max_shift_fraction > 0:
        max_shift = int(waveform.shape[1] * max_shift_fraction)
        if max_shift > 0:
            shift = int(torch.randint(-max_shift, max_shift + 1, (1,)).item())
            waveform = torch.roll(waveform, shifts=shift, dims=1)
    if noise_std > 0:
        waveform = waveform + torch.randn_like(waveform) * noise_std
    return waveform.clamp(-1.0, 1.0)


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


def apply_spec_augment(log_mel, *, max_time_mask_frames: int = 12, max_freq_mask_bins: int = 8):
    torch, _ = _torch_modules()
    augmented = log_mel.clone()
    if max_freq_mask_bins > 0 and augmented.shape[1] > 1:
        width = int(torch.randint(0, min(max_freq_mask_bins, augmented.shape[1]) + 1, (1,)).item())
        if width > 0:
            start = int(torch.randint(0, augmented.shape[1] - width + 1, (1,)).item())
            augmented[:, start : start + width, :] = 0
    if max_time_mask_frames > 0 and augmented.shape[2] > 1:
        width = int(torch.randint(0, min(max_time_mask_frames, augmented.shape[2]) + 1, (1,)).item())
        if width > 0:
            start = int(torch.randint(0, augmented.shape[2] - width + 1, (1,)).item())
            augmented[:, :, start : start + width] = 0
    return augmented


def load_log_mel(
    path: str | Path,
    *,
    sample_rate: int,
    clip_seconds: float,
    n_mels: int,
    augment: bool = False,
    augmentation: dict | None = None,
):
    waveform = load_and_preprocess_audio(path, sample_rate=sample_rate, clip_seconds=clip_seconds)
    augmentation = augmentation or {}
    if augment:
        waveform = augment_waveform(
            waveform,
            gain_min=float(augmentation.get("gain_min", 0.85)),
            gain_max=float(augmentation.get("gain_max", 1.15)),
            noise_std=float(augmentation.get("noise_std", 0.003)),
            max_shift_fraction=float(augmentation.get("max_shift_fraction", 0.08)),
        )
    log_mel = waveform_to_log_mel(waveform, sample_rate=sample_rate, n_mels=n_mels)
    if augment:
        log_mel = apply_spec_augment(
            log_mel,
            max_time_mask_frames=int(augmentation.get("max_time_mask_frames", 12)),
            max_freq_mask_bins=int(augmentation.get("max_freq_mask_bins", 8)),
        )
    return log_mel


def _torch_modules():
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to use audio model code") from exc
    return torch, torchaudio


def _load_audio_fallback(path: str | Path, torch):
    try:
        return _load_with_soundfile(path, torch)
    except (ImportError, RuntimeError):
        return _load_wav_with_scipy(path, torch)


def _load_with_soundfile(path: str | Path, torch):
    try:
        import soundfile as sf
    except ImportError as exc:
        raise ImportError("soundfile is not installed") from exc

    data, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    tensor = torch.as_tensor(data).transpose(0, 1).contiguous()
    return tensor, sample_rate


def _load_wav_with_scipy(path: str | Path, torch):
    try:
        from scipy.io import wavfile
    except ImportError as exc:
        raise RuntimeError("Install scipy or a torchaudio backend that can decode WAV files") from exc

    sample_rate, data = wavfile.read(str(path))
    tensor = torch.as_tensor(data)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    else:
        tensor = tensor.transpose(0, 1)
    if tensor.dtype.is_floating_point:
        waveform = tensor.float()
    else:
        info = torch.iinfo(tensor.dtype)
        scale = max(abs(info.min), info.max)
        waveform = tensor.float() / scale
    return waveform, sample_rate
