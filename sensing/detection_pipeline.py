#!/usr/bin/env python3
"""
TFN ISR Detection Pipeline
===========================

Real-time signal processing pipeline for edge nodes.
Processes raw sensor data through filtering, feature extraction,
and rule-based classification to produce classified events.

No external dependencies — uses only Python standard library.
"""

import math
import random
import time
import uuid
from typing import Optional

try:
    from simulation.das_simulator import SIGNATURE_PROFILES, TargetSignature
    _HAS_PROFILES = True
except ImportError:
    _HAS_PROFILES = False


class SignalBuffer:
    """Circular buffer for raw sensor samples."""

    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.buffer: list[float] = []

    def push(self, sample: float):
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)
        self.buffer.append(sample)

    def get_recent(self, n: int) -> list[float]:
        if n <= 0:
            return []
        if n >= len(self.buffer):
            return list(self.buffer)
        return self.buffer[-n:]

    def clear(self):
        self.buffer.clear()

    @property
    def size(self) -> int:
        return len(self.buffer)


class SignalFilter:
    """Simple digital filters for signal conditioning."""

    @staticmethod
    def low_pass(data: list[float], cutoff_ratio: float = 0.1) -> list[float]:
        if not data:
            return []
        alpha = max(0.001, min(cutoff_ratio, 1.0))
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(alpha * data[i] + (1.0 - alpha) * result[-1])
        return result

    @staticmethod
    def band_pass(data: list[float], low_ratio: float = 0.01,
                  high_ratio: float = 0.1) -> list[float]:
        if not data:
            return []
        high_passed = SignalFilter.low_pass(data, high_ratio)
        low_component = SignalFilter.low_pass(high_passed, low_ratio)
        return [h - l for h, l in zip(high_passed, low_component)]

    @staticmethod
    def remove_dc(data: list[float]) -> list[float]:
        if not data:
            return []
        mean = sum(data) / len(data)
        return [s - mean for s in data]


class FeatureExtractor:
    """Extract features from filtered signal for classification."""

    @staticmethod
    def _compute_spectrum(data: list[float], sample_rate: int = 1000,
                          max_n: int = 256) -> list[tuple[float, float]]:
        N = min(max_n, len(data))
        if N < 4:
            return [(0.0, 0.0)]
        x = data[:N]
        spectrum: list[tuple[float, float]] = []
        half = N // 2
        for k in range(half):
            re = 0.0
            im = 0.0
            for n in range(N):
                angle = 2.0 * math.pi * k * n / N
                re += x[n] * math.cos(angle)
                im -= x[n] * math.sin(angle)
            mag = math.sqrt(re * re + im * im) / N
            freq = k * sample_rate / N
            spectrum.append((freq, mag))
        return spectrum

    @staticmethod
    def compute_rms(data: list[float]) -> float:
        if not data:
            return 0.0
        return math.sqrt(sum(s * s for s in data) / len(data))

    @staticmethod
    def compute_peak_amplitude(data: list[float]) -> float:
        if not data:
            return 0.0
        return max(abs(s) for s in data)

    @staticmethod
    def compute_zero_crossing_rate(data: list[float]) -> float:
        if len(data) < 2:
            return 0.0
        crossings = sum(
            1 for i in range(len(data) - 1) if data[i] * data[i + 1] < 0
        )
        return crossings / (len(data) - 1)

    @staticmethod
    def compute_fft_peak(data: list[float],
                         sample_rate: int = 1000) -> tuple[float, float]:
        spectrum = FeatureExtractor._compute_spectrum(data, sample_rate)
        best_freq = 0.0
        best_mag = 0.0
        for freq, mag in spectrum[1:]:
            if mag > best_mag:
                best_mag = mag
                best_freq = freq
        return (best_freq, best_mag)

    @staticmethod
    def compute_spectral_centroid(data: list[float],
                                  sample_rate: int = 1000) -> float:
        spectrum = FeatureExtractor._compute_spectrum(data, sample_rate)
        total_mag = sum(mag for _, mag in spectrum[1:])
        if total_mag < 1e-12:
            return 0.0
        weighted = sum(freq * mag for freq, mag in spectrum[1:])
        return weighted / total_mag

    @staticmethod
    def compute_rhythm_score(data: list[float], sample_rate: int = 1000) -> float:
        if len(data) < 10:
            return 0.0
        N = len(data)
        mean = sum(data) / N
        centered = [s - mean for s in data]
        energy = sum(s * s for s in centered)
        if energy < 1e-12:
            return 0.0

        min_lag = max(1, int(0.05 * sample_rate))
        max_lag = min(int(2.0 * sample_rate), N - 1)
        if max_lag <= min_lag:
            return 0.0

        step = max(1, (max_lag - min_lag) // 200)
        best_corr = 0.0
        for lag in range(min_lag, max_lag, step):
            overlap = N - lag
            corr = sum(centered[i] * centered[i + lag] for i in range(overlap))
            corr /= energy
            if corr > best_corr:
                best_corr = corr

        return max(0.0, min(1.0, best_corr))

    @staticmethod
    def extract_all(data: list[float], sample_rate: int = 1000) -> dict:
        spectrum = FeatureExtractor._compute_spectrum(data, sample_rate)

        fft_peak_freq = 0.0
        fft_peak_amp = 0.0
        for freq, mag in spectrum[1:]:
            if mag > fft_peak_amp:
                fft_peak_amp = mag
                fft_peak_freq = freq

        total_mag = sum(mag for _, mag in spectrum[1:])
        spectral_centroid = 0.0
        if total_mag > 1e-12:
            spectral_centroid = (
                sum(freq * mag for freq, mag in spectrum[1:]) / total_mag
            )

        rms = math.sqrt(sum(s * s for s in data) / len(data)) if data else 0.0
        peak_amp = max(abs(s) for s in data) if data else 0.0

        zcr = 0.0
        if len(data) >= 2:
            crossings = sum(
                1 for i in range(len(data) - 1) if data[i] * data[i + 1] < 0
            )
            zcr = crossings / (len(data) - 1)

        rhythm = FeatureExtractor.compute_rhythm_score(data, sample_rate)

        peak_to_rms = peak_amp / rms if rms > 1e-9 else 0.0

        return {
            "rms": rms,
            "peak_amp": peak_amp,
            "zcr": zcr,
            "fft_peak_freq": fft_peak_freq,
            "fft_peak_amp": fft_peak_amp,
            "spectral_centroid": spectral_centroid,
            "rhythm_score": rhythm,
            "peak_to_rms": peak_to_rms,
        }


class TargetClassifier:
    """Rule-based classifier — no ML needed for MVP.

    Classification rules (based on real acoustic signatures):
    - FOOTSTEP: freq 1-4 Hz, rhythm > 0.5, moderate amplitude
    - GROUP: freq 1-4 Hz, rhythm > 0.3, high amplitude, wider spectrum
    - WHEELED_VEHICLE: freq 8-50 Hz, continuous (rhythm < 0.3), high amplitude
    - TRACKED_VEHICLE: freq 5-30 Hz + harmonics, very high amplitude
    - DRONE: freq 80-200 Hz, continuous, moderate amplitude
    - ARTILLERY: impulse (very high peak/rms ratio), freq 0-500 Hz
    - EXPLOSION: similar to artillery but longer decay
    - DIGGING: freq 2-8 Hz, rhythmic with pauses
    - WIND_NOISE: freq 0.5-3 Hz, very regular, low amplitude
    - RAIN_NOISE: wideband 10-100 Hz, very regular
    - UNKNOWN: doesn't match anything well
    """

    def __init__(self):
        self.rules = self._build_rules()

    def _build_rules(self) -> list[dict]:
        return [
            {
                "name": "footstep",
                "conditions": [
                    ("fft_peak_freq", 0.5, 8.0),
                    ("rms", 0.05, 0.25),
                    ("peak_amp", 0.08, 0.5),
                    ("zcr", 0.0, 0.08),
                ],
                "weight": 1.0,
            },
            {
                "name": "group",
                "conditions": [
                    ("fft_peak_freq", 0.5, 8.0),
                    ("rms", 0.10, 0.70),
                    ("peak_amp", 0.3, 1.0),
                    ("rhythm_score", 0.25, 1.0),
                ],
                "weight": 1.0,
            },
            {
                "name": "wheeled_vehicle",
                "conditions": [
                    ("fft_peak_freq", 8.0, 40.0),
                    ("rms", 0.20, 0.60),
                    ("peak_amp", 0.3, 1.2),
                ],
                "weight": 1.0,
            },
            {
                "name": "tracked_vehicle",
                "conditions": [
                    ("fft_peak_freq", 10.0, 40.0),
                    ("rms", 0.55, 2.0),
                    ("peak_amp", 1.0, 5.0),
                ],
                "weight": 1.05,
            },
            {
                "name": "drone",
                "conditions": [
                    ("fft_peak_freq", 80.0, 300.0),
                    ("zcr", 0.10, 0.60),
                ],
                "weight": 1.0,
            },
            {
                "name": "artillery",
                "conditions": [
                    ("peak_to_rms", 3.0, 50.0),
                    ("rms", 0.03, 0.30),
                    ("rhythm_score", 0.0, 0.40),
                    ("fft_peak_freq", 15.0, 300.0),
                    ("zcr", 0.0, 0.15),
                ],
                "weight": 1.1,
            },
            {
                "name": "explosion",
                "conditions": [
                    ("fft_peak_freq", 5.0, 20.0),
                    ("peak_to_rms", 1.5, 50.0),
                    ("rms", 0.10, 0.60),
                ],
                "weight": 1.0,
            },
            {
                "name": "digging",
                "conditions": [
                    ("fft_peak_freq", 2.0, 15.0),
                    ("rms", 0.05, 0.55),
                    ("rhythm_score", 0.25, 0.85),
                    ("zcr", 0.0, 0.10),
                ],
                "weight": 1.0,
            },
            {
                "name": "wind_noise",
                "conditions": [
                    ("fft_peak_freq", 0.3, 5.0),
                    ("rms", 0.003, 0.04),
                    ("peak_amp", 0.01, 0.07),
                    ("zcr", 0.0, 0.10),
                ],
                "weight": 1.0,
            },
            {
                "name": "rain_noise",
                "conditions": [
                    ("fft_peak_freq", 30.0, 120.0),
                    ("zcr", 0.15, 0.85),
                    ("rms", 0.005, 0.18),
                    ("peak_amp", 0.01, 0.12),
                ],
                "weight": 0.95,
            },
        ]

    def _condition_score(self, value: float, min_val: float,
                         max_val: float) -> float:
        if min_val <= value <= max_val:
            return 1.0
        margin = max((max_val - min_val) * 0.5, 0.01)
        if value < min_val:
            return max(0.0, 1.0 - (min_val - value) / margin)
        return max(0.0, 1.0 - (value - max_val) / margin)

    def classify(self, features: dict) -> tuple[str, float, str]:
        best_name = "unknown"
        best_score = 0.0

        for rule in self.rules:
            scores: list[float] = []
            for feat_name, min_val, max_val in rule["conditions"]:
                val = features.get(feat_name, 0.0)
                scores.append(self._condition_score(val, min_val, max_val))
            avg_score = sum(scores) / len(scores) if scores else 0.0
            total = avg_score * rule.get("weight", 1.0)
            if total > best_score:
                best_score = total
                best_name = rule["name"]

        threat_map = {
            "footstep": "low",
            "group": "medium",
            "wheeled_vehicle": "medium",
            "tracked_vehicle": "high",
            "drone": "medium",
            "artillery": "critical",
            "explosion": "critical",
            "digging": "low",
            "wind_noise": "none",
            "rain_noise": "none",
            "unknown": "none",
        }

        confidence = min(max(best_score, 0.0), 0.99)
        threat = threat_map.get(best_name, "none")
        return (best_name, confidence, threat)

    def classify_with_rejection(self, features: dict,
                                min_confidence: float = 0.4) -> tuple[str, float, str]:
        target_type, confidence, threat = self.classify(features)
        if confidence < min_confidence:
            return ("unknown", 0.0, "none")
        return (target_type, confidence, threat)


class DetectionPipeline:
    """Full pipeline: raw signal -> filtered -> features -> classification -> event."""

    def __init__(self, sample_rate: int = 1000, window_size: int = 1024):
        self.sample_rate = sample_rate
        self.window_size = window_size
        self.buffer = SignalBuffer(capacity=window_size * 10)
        self.filter = SignalFilter()
        self.extractor = FeatureExtractor()
        self.classifier = TargetClassifier()
        self.detection_count = 0
        self._hop_size = max(1, window_size // 2)
        self._sample_counter = 0

    def feed_sample(self, sample: float) -> Optional[dict]:
        self.buffer.push(sample)
        self._sample_counter += 1
        if (self._sample_counter >= self._hop_size
                and self.buffer.size >= self.window_size):
            self._sample_counter = 0
            data = self.buffer.get_recent(self.window_size)
            return self.process_window(data)
        return None

    def process_window(self, data: list[float]) -> Optional[dict]:
        if len(data) < 64:
            return None

        dc_removed = self.filter.remove_dc(data)
        filtered = self.filter.band_pass(dc_removed, 0.001, 0.45)

        features = self.extractor.extract_all(filtered, self.sample_rate)

        if features["rms"] < 0.005:
            return None

        target_type, confidence, threat_level = \
            self.classifier.classify_with_rejection(features)

        if target_type == "unknown":
            return None

        self.detection_count += 1
        action = self._determine_action(target_type, confidence, threat_level)

        return {
            "event_id": str(uuid.uuid4())[:8],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target_type": target_type,
            "confidence": round(confidence, 3),
            "threat_level": threat_level,
            "features": {k: round(v, 4) for k, v in features.items()},
            "segment_id": "seg_00",
            "position_m": 0.0,
            "source": "piezo_sensor",
            "action_recommended": action,
        }

    def _determine_action(self, target_type: str, confidence: float,
                          threat_level: str) -> str:
        if threat_level == "critical" and confidence >= 0.8:
            return "strike_ready"
        if threat_level in ("high", "critical"):
            return "investigate"
        if threat_level == "medium":
            return "monitor"
        return "log_only"


_SIGNATURE_MAP = {
    "footstep": "FOOTSTEP_SINGLE",
    "group": "FOOTSTEP_GROUP",
    "wheeled_vehicle": "WHEELED_VEHICLE",
    "tracked_vehicle": "TRACKED_VEHICLE",
    "drone": "DRONE_HOVER",
    "artillery": "ARTILLERY_FIRE",
    "explosion": "EXPLOSION",
    "digging": "DIGGING",
}

_FALLBACK_PROFILES: dict[str, dict] = {
    "footstep": {
        "freq": 2.5, "amp": 0.25,
        "harmonics": [(2.0, 0.5), (3.0, 0.25)],
        "pattern": "periodic", "period_hz": 2.0, "decay": 0.15,
    },
    "group": {
        "freq": 2.5, "amp": 0.40,
        "harmonics": [(2.0, 0.5), (3.0, 0.25)],
        "pattern": "periodic", "period_hz": 3.5, "decay": 0.15,
    },
    "wheeled_vehicle": {
        "freq": 25.0, "amp": 0.55,
        "harmonics": [(2.0, 0.6), (3.0, 0.3)],
        "pattern": "continuous", "period_hz": 0, "decay": 0.0,
    },
    "tracked_vehicle": {
        "freq": 15.0, "amp": 0.75,
        "harmonics": [(2.0, 0.7), (3.0, 0.5), (4.0, 0.3)],
        "pattern": "continuous", "period_hz": 0, "decay": 0.0,
    },
    "drone": {
        "freq": 140.0, "amp": 0.18,
        "harmonics": [(2.0, 0.8), (3.0, 0.6)],
        "pattern": "continuous", "period_hz": 0, "decay": 0.0,
    },
    "artillery": {
        "freq": 50.0, "amp": 0.92,
        "harmonics": [(2.0, 0.8), (3.0, 0.6)],
        "pattern": "impulse", "period_hz": 0, "decay": 0.05,
    },
    "explosion": {
        "freq": 7.0, "amp": 0.95,
        "harmonics": [(2.0, 0.7), (3.0, 0.4)],
        "pattern": "impulse", "period_hz": 0, "decay": 0.5,
    },
    "digging": {
        "freq": 5.0, "amp": 0.35,
        "harmonics": [(2.0, 0.4), (3.0, 0.2)],
        "pattern": "periodic", "period_hz": 1.5, "decay": 0.0,
    },
    "wind": {
        "freq": 1.5, "amp": 0.04,
        "harmonics": [],
        "pattern": "continuous", "period_hz": 0, "decay": 0.0,
    },
    "rain": {
        "freq": 50.0, "amp": 0.06,
        "harmonics": [(2.0, 0.3)],
        "pattern": "continuous", "period_hz": 0, "decay": 0.0,
    },
}


def generate_test_signal(target_type: str, duration_s: float = 1.0,
                         sample_rate: int = 1000,
                         noise_level: float = 0.05) -> list[float]:
    """Generate synthetic test signals for validation.

    Uses harmonic composition from SIGNATURE_PROFILES if available,
    otherwise falls back to built-in approximation profiles.
    """
    num_samples = int(duration_s * sample_rate)
    profile = None

    if _HAS_PROFILES and target_type in _SIGNATURE_MAP:
        sig_name = _SIGNATURE_MAP[target_type]
        for ts in TargetSignature:
            if ts.value == sig_name:
                profile = SIGNATURE_PROFILES[ts]
                break

    if profile is not None:
        freq_min, freq_max = profile["freq_range"]
        amp_min, amp_max = profile["amplitude_range"]
        fundamental = (freq_min + freq_max) / 2.0
        amplitude = (amp_min + amp_max) / 2.0
        harmonics = profile.get("harmonics", [])
        temporal = profile.get("temporal_pattern", "continuous")
        decay = profile.get("decay_time_s", 0.0)
        period_hz = profile.get("period_hz", 1.0)
    elif target_type in _FALLBACK_PROFILES:
        fp = _FALLBACK_PROFILES[target_type]
        fundamental = fp["freq"]
        amplitude = fp["amp"]
        harmonics = fp["harmonics"]
        temporal = fp["pattern"]
        decay = fp["decay"]
        period_hz = fp["period_hz"]
    else:
        fundamental = 10.0
        amplitude = 0.3
        harmonics = []
        temporal = "continuous"
        decay = 0.0
        period_hz = 0.0

    signal: list[float] = []
    for i in range(num_samples):
        t = i / sample_rate
        sample = amplitude * math.sin(2.0 * math.pi * fundamental * t)

        for mult, rel_amp in harmonics:
            hf = fundamental * mult
            sample += amplitude * rel_amp * math.sin(2.0 * math.pi * hf * t)

        if temporal == "impulse" and decay > 0:
            sample *= math.exp(-t / decay)
        elif temporal == "periodic":
            envelope = 0.5 + 0.5 * math.sin(2.0 * math.pi * period_hz * t)
            sample *= envelope
        elif temporal == "sweep":
            sample *= 0.5 + 0.5 * (t / max(duration_s, 0.001))

        sample += random.gauss(0, noise_level * max(amplitude, 0.01))
        signal.append(sample)

    return signal
