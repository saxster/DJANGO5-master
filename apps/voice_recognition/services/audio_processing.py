"""Reusable audio processing utilities for voice biometrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, filtfilt, stft


@dataclass
class AudioSample:
    """Normalized mono audio sample."""

    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples) / self.sample_rate) if self.sample_rate else 0.0

    @classmethod
    def from_file(cls, path: str) -> "AudioSample":
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        sample_rate, data = wavfile.read(filepath)
        if data.ndim > 1:
            data = data.mean(axis=1)

        data = data.astype(np.float32)
        max_val = np.max(np.abs(data)) or 1.0
        normalized = data / max_val
        return cls(samples=normalized, sample_rate=sample_rate)


def compute_quality_metrics(sample: AudioSample) -> Dict[str, float]:
    """Estimate quality metrics such as SNR and energy stability."""
    if sample.samples.size == 0:
        return {
            'quality_score': 0.0,
            'snr_db': 0.0,
            'duration_seconds': 0.0,
            'issues': ['EMPTY_AUDIO'],
        }

    # Smooth signal to estimate baseline and noise components
    b, a = butter(3, 0.98)
    baseline = filtfilt(b, a, sample.samples)
    noise = sample.samples - baseline

    signal_power = np.mean(baseline ** 2) + 1e-9
    noise_power = np.mean(noise ** 2) + 1e-9
    snr_db = 10 * math.log10(signal_power / noise_power)

    rms = np.sqrt(signal_power)
    active_ratio = float(np.mean(np.abs(sample.samples) > 0.02))
    quality_score = max(0.0, min(1.0, (snr_db / 30.0) * 0.6 + active_ratio * 0.4))

    issues = []
    if snr_db < 12:
        issues.append('LOW_SNR')
    if sample.duration_seconds < 2.0:
        issues.append('TOO_SHORT')

    return {
        'quality_score': round(quality_score, 3),
        'snr_db': round(snr_db, 2),
        'duration_seconds': round(sample.duration_seconds, 2),
        'issues': issues,
    }


def detect_audio_spoof(sample: AudioSample, challenge: Optional[Dict[str, str]] = None) -> Dict[str, any]:
    """Lightweight liveness heuristics based on spectral analysis."""
    spectrum = np.abs(np.fft.rfft(sample.samples))
    total_energy = spectrum.sum() + 1e-9
    low_band = spectrum[: int(len(spectrum) * 0.1)].sum()
    high_band = spectrum[int(len(spectrum) * 0.6):].sum()

    flatness = float(high_band / total_energy)
    spoof_detected = flatness < 0.05 or high_band < low_band * 0.2

    fraud_indicators = []
    if spoof_detected:
        fraud_indicators.append('SPECTRAL_FLATNESS_LOW')

    challenge_ok = True
    if challenge:
        expected = challenge.get('expected_phrase')
        provided = challenge.get('spoken_text')
        if expected and provided:
            match_ratio = _sequence_similarity(expected.lower(), provided.lower())
            if match_ratio < 0.65:
                challenge_ok = False
                fraud_indicators.append('CHALLENGE_MISMATCH')

    return {
        'spoof_detected': spoof_detected or not challenge_ok,
        'liveness_score': round(flatness, 3),
        'fraud_indicators': fraud_indicators,
    }


def extract_embedding(sample: AudioSample, emb_dim: int = 256) -> np.ndarray:
    """Deterministic embedding using STFT statistics."""
    window = min(1024, max(256, sample.sample_rate // 8))
    _, _, zxx = stft(sample.samples, fs=sample.sample_rate, nperseg=window, noverlap=window // 2)
    magnitude = np.abs(zxx)

    spectral_mean = magnitude.mean(axis=1)
    spectral_std = magnitude.std(axis=1)
    vector = np.concatenate([spectral_mean, spectral_std])
    if vector.size < emb_dim:
        vector = np.pad(vector, (0, emb_dim - vector.size))
    else:
        vector = vector[:emb_dim]

    norm = np.linalg.norm(vector) or 1.0
    return (vector / norm).astype(np.float32)


def _sequence_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    matches = sum(1 for x, y in zip(a, b) if x == y)
    return matches / max(len(a), len(b))


__all__ = [
    'AudioSample',
    'compute_quality_metrics',
    'detect_audio_spoof',
    'extract_embedding',
]
