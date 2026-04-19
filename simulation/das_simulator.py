#!/usr/bin/env python3
"""
TFN DAS (Distributed Acoustic Sensing) Simulator
==================================================

Simulates phi-OTDR interrogation of fiber optic cable for:
- Footstep detection
- Vehicle detection (wheeled / tracked)
- Artillery fire detection
- Drone flyover detection
- EW interference detection

Generates realistic synthetic backscatter signals with noise,
multi-target events, and produces classification reports.

Physics model:
- Fiber: G.657.A2, alpha = 0.35 dB/km
- SNR(d) = P_launch - alpha*L - 10*log10(d) - NF
- Detection: logistic P_detect(SNR) with threshold at 3 dB
"""

import math
import random
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThreatLevel(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TargetSignature(Enum):
    SILENCE = "silence"
    FOOTSTEP_SINGLE = "footstep_single"
    FOOTSTEP_GROUP = "footstep_group"
    WHEELED_VEHICLE = "wheeled_vehicle"
    TRACKED_VEHICLE = "tracked_vehicle"
    ARTILLERY_FIRE = "artillery_fire"
    EXPLOSION = "explosion"
    DRONE_HOVER = "drone_hover"
    DRONE_FLYBY = "drone_flyby"
    EW_INTERFERENCE = "ew_interference"
    DIGGING = "digging"


class EnvironmentalCondition(Enum):
    CLEAR = "clear"
    LIGHT_WIND = "light_wind"
    STRONG_WIND = "strong_wind"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"


SIGNATURE_PROFILES = {
    TargetSignature.SILENCE: {
        "freq_range": (0.1, 0.3),
        "amplitude_range": (0.01, 0.05),
        "duration_s": (0.5, 2.0),
        "pattern": "continuous",
        "harmonics": [],
        "bandwidth_hz": 0.2,
        "temporal_pattern": "continuous",
        "decay_time_s": 0.0,
    },
    TargetSignature.FOOTSTEP_SINGLE: {
        "freq_range": (1.0, 4.0),
        "amplitude_range": (0.15, 0.35),
        "duration_s": (0.1, 0.3),
        "pattern": "periodic",
        "period_hz": 2.0,
        "harmonics": [(2.0, 0.5), (3.0, 0.25)],
        "bandwidth_hz": 3.0,
        "temporal_pattern": "periodic",
        "decay_time_s": 0.15,
    },
    TargetSignature.FOOTSTEP_GROUP: {
        "freq_range": (1.0, 4.0),
        "amplitude_range": (0.25, 0.55),
        "duration_s": (0.15, 0.4),
        "pattern": "periodic",
        "period_hz": 3.5,
        "harmonics": [(2.0, 0.5), (3.0, 0.25)],
        "bandwidth_hz": 3.0,
        "temporal_pattern": "periodic",
        "decay_time_s": 0.15,
    },
    TargetSignature.WHEELED_VEHICLE: {
        "freq_range": (2.0, 50.0),
        "amplitude_range": (0.40, 0.70),
        "duration_s": (1.0, 5.0),
        "pattern": "continuous",
        "harmonics": [(2.0, 0.6), (3.0, 0.3), (4.0, 0.15)],
        "bandwidth_hz": 48.0,
        "temporal_pattern": "continuous",
        "decay_time_s": 0.0,
    },
    TargetSignature.TRACKED_VEHICLE: {
        "freq_range": (8.0, 30.0),
        "amplitude_range": (0.60, 0.90),
        "duration_s": (2.0, 8.0),
        "pattern": "continuous",
        "harmonics": [(2.0, 0.7), (3.0, 0.5), (4.0, 0.3)],
        "bandwidth_hz": 82.0,
        "temporal_pattern": "continuous",
        "decay_time_s": 0.0,
    },
    TargetSignature.ARTILLERY_FIRE: {
        "freq_range": (0.0, 500.0),
        "amplitude_range": (0.85, 1.0),
        "duration_s": (0.05, 0.2),
        "pattern": "impulse",
        "harmonics": [(2.0, 0.8), (3.0, 0.6), (5.0, 0.3)],
        "bandwidth_hz": 500.0,
        "temporal_pattern": "impulse",
        "decay_time_s": 0.05,
    },
    TargetSignature.EXPLOSION: {
        "freq_range": (0.1, 15.0),
        "amplitude_range": (0.90, 1.0),
        "duration_s": (0.3, 1.5),
        "pattern": "impulse",
        "harmonics": [(2.0, 0.7), (3.0, 0.4)],
        "bandwidth_hz": 15.0,
        "temporal_pattern": "impulse",
        "decay_time_s": 0.5,
    },
    TargetSignature.DRONE_HOVER: {
        "freq_range": (80.0, 200.0),
        "amplitude_range": (0.10, 0.25),
        "duration_s": (5.0, 30.0),
        "pattern": "continuous",
        "harmonics": [(2.0, 0.8), (3.0, 0.6), (4.0, 0.4)],
        "bandwidth_hz": 120.0,
        "temporal_pattern": "continuous",
        "decay_time_s": 0.0,
    },
    TargetSignature.DRONE_FLYBY: {
        "freq_range": (80.0, 200.0),
        "amplitude_range": (0.15, 0.35),
        "duration_s": (2.0, 8.0),
        "pattern": "sweep",
        "harmonics": [(2.0, 0.8), (3.0, 0.6), (4.0, 0.4)],
        "bandwidth_hz": 120.0,
        "temporal_pattern": "sweep",
        "decay_time_s": 0.0,
    },
    TargetSignature.EW_INTERFERENCE: {
        "freq_range": (100.0, 2000.0),
        "amplitude_range": (0.30, 0.60),
        "duration_s": (1.0, 10.0),
        "pattern": "continuous",
        "harmonics": [(2.0, 0.5), (3.0, 0.3)],
        "bandwidth_hz": 1900.0,
        "temporal_pattern": "continuous",
        "decay_time_s": 0.0,
    },
    TargetSignature.DIGGING: {
        "freq_range": (2.0, 8.0),
        "amplitude_range": (0.20, 0.50),
        "duration_s": (0.2, 1.0),
        "pattern": "periodic",
        "period_hz": 1.5,
        "harmonics": [(2.0, 0.4), (3.0, 0.2)],
        "bandwidth_hz": 6.0,
        "temporal_pattern": "periodic",
        "decay_time_s": 0.0,
    },
}


@dataclass
class DASEvent:
    timestamp_s: float
    position_m: float
    target_type: TargetSignature
    amplitude: float
    frequency_hz: float
    confidence: float
    threat_level: ThreatLevel
    snr_db: float
    description: str


@dataclass
class FiberSegment:
    start_m: float
    end_m: float
    attenuation_db_km: float = 0.35
    burial_depth_m: float = 0.0
    terrain: str = "ground"


class DASSimulator:
    def __init__(self, fiber_length_m: float = 10000, sample_rate_hz: int = 1000,
                 spatial_resolution_m: float = 1.0, noise_floor_db: float = -60.0,
                 launch_power_dbm: float = 0.0, noise_figure_db: float = 5.0,
                 env_condition: EnvironmentalCondition = EnvironmentalCondition.CLEAR):
        self.fiber_length = fiber_length_m
        self.sample_rate = sample_rate_hz
        self.spatial_resolution = spatial_resolution_m
        self.noise_floor = noise_floor_db
        self.num_channels = int(fiber_length_m / spatial_resolution_m)
        self.segments: list[FiberSegment] = []
        self.detected_events: list[DASEvent] = []
        self.backscatter_data: list[list[float]] = []
        self.launch_power_dbm = launch_power_dbm
        self.noise_figure_db = noise_figure_db
        self.env_condition = env_condition
        self._fiber_attenuation_db_km = 0.35
        self._snr_steepness = 0.5
        self._snr_threshold_db = 3.0

    def add_segment(self, segment: FiberSegment):
        self.segments.append(segment)

    def auto_segment(self):
        segment_length = self.fiber_length / 5
        terrains = ["ground", "road", "field", "forest", "trench"]
        for i in range(5):
            self.add_segment(FiberSegment(
                start_m=i * segment_length,
                end_m=(i + 1) * segment_length,
                attenuation_db_km=0.35 + random.uniform(-0.05, 0.1),
                burial_depth_m=random.uniform(0, 0.3),
                terrain=terrains[i],
            ))

    def compute_snr(self, position_m: float, target_distance_m: float) -> float:
        if target_distance_m <= 0.0:
            target_distance_m = 0.1
        fiber_length_km = position_m / 1000.0
        fiber_loss = self._fiber_attenuation_db_km * fiber_length_km
        geometric_loss = 10.0 * math.log10(target_distance_m)
        snr = self.launch_power_dbm - fiber_loss - geometric_loss - self.noise_figure_db
        return snr

    def _compute_detection_probability(self, snr_db: float) -> float:
        exponent = -self._snr_steepness * (snr_db - self._snr_threshold_db)
        return 1.0 / (1.0 + math.exp(exponent))

    def _generate_backscatter(self) -> list[float]:
        data = []
        for ch in range(self.num_channels):
            pos = ch * self.spatial_resolution
            base = -20.0 + random.gauss(0, 2.0)
            attenuation = 0.35 * (pos / 1000.0)
            data.append(base - attenuation)
        return data

    def _inject_target(self, channel_data: list[float], position_m: float,
                       signature: TargetSignature, time_s: float) -> list[float]:
        profile = SIGNATURE_PROFILES[signature]
        center_ch = int(position_m / self.spatial_resolution)
        amplitude = random.uniform(*profile["amplitude_range"])
        freq = random.uniform(*profile["freq_range"])
        spread = max(3, int(amplitude * 10))

        for offset in range(-spread, spread + 1):
            ch = center_ch + offset
            if 0 <= ch < len(channel_data):
                distance_factor = math.exp(-abs(offset) * 0.5)
                terrain_factor = self._get_terrain_sensitivity(ch)
                phase = 2 * math.pi * freq * time_s
                signal = amplitude * distance_factor * terrain_factor * math.sin(phase)
                noise = random.gauss(0, 0.02)
                channel_data[ch] += signal + noise

        return channel_data

    def _inject_environmental_noise(self, channel_data: list[float],
                                    time_s: float) -> list[float]:
        cond = self.env_condition

        if cond == EnvironmentalCondition.CLEAR:
            return channel_data

        for ch in range(len(channel_data)):
            pos = ch * self.spatial_resolution

            if cond in (EnvironmentalCondition.LIGHT_WIND, EnvironmentalCondition.STRONG_WIND):
                wind_strength = 0.3 if cond == EnvironmentalCondition.LIGHT_WIND else 1.0
                wind_freq = random.uniform(0.5, 3.0)
                wind_noise = wind_strength * random.gauss(0, 0.05) * math.sin(
                    2 * math.pi * wind_freq * time_s + ch * 0.01
                )
                channel_data[ch] += wind_noise

            elif cond in (EnvironmentalCondition.LIGHT_RAIN, EnvironmentalCondition.HEAVY_RAIN):
                rain_strength = 0.2 if cond == EnvironmentalCondition.LIGHT_RAIN else 0.8
                rain_freq = random.uniform(10.0, 100.0)
                rain_noise = rain_strength * random.gauss(0, 0.03) * math.sin(
                    2 * math.pi * rain_freq * time_s + ch * 0.005
                )
                channel_data[ch] += rain_noise

        return channel_data

    def _get_terrain_sensitivity(self, channel: int) -> float:
        pos = channel * self.spatial_resolution
        for seg in self.segments:
            if seg.start_m <= pos < seg.end_m:
                multipliers = {
                    "ground": 1.0,
                    "road": 0.7,
                    "field": 1.2,
                    "forest": 0.5,
                    "trench": 1.5,
                }
                depth_factor = 1.0 + seg.burial_depth_m * 2.0
                return multipliers.get(seg.terrain, 1.0) / depth_factor
        return 1.0

    def _classify_event(self, amplitude: float, frequency: float,
                        position_m: float) -> tuple[TargetSignature, float, ThreatLevel]:
        target_distance_m = max(1.0, 10.0 / max(amplitude, 0.01))
        snr = self.compute_snr(position_m, target_distance_m)

        if snr < -3.0:
            return TargetSignature.SILENCE, 0.0, ThreatLevel.NONE

        p_detect = self._compute_detection_probability(snr)

        best_match = TargetSignature.SILENCE
        best_score = 0.0

        for sig_type, profile in SIGNATURE_PROFILES.items():
            if sig_type == TargetSignature.SILENCE:
                continue
            f_min, f_max = profile["freq_range"]
            a_min, a_max = profile["amplitude_range"]

            freq_score = 1.0 - min(abs(frequency - (f_min + f_max) / 2) / ((f_max - f_min) / 2 + 1), 1.0)
            amp_score = 1.0 - min(abs(amplitude - (a_min + a_max) / 2) / ((a_max - a_min) / 2 + 0.1), 1.0)
            score = (freq_score + amp_score) / 2.0

            if score > best_score:
                best_score = score
                best_match = sig_type

        confidence = min(p_detect * best_score * 1.2, 0.99)

        threat_map = {
            TargetSignature.SILENCE: ThreatLevel.NONE,
            TargetSignature.FOOTSTEP_SINGLE: ThreatLevel.LOW,
            TargetSignature.FOOTSTEP_GROUP: ThreatLevel.MEDIUM,
            TargetSignature.WHEELED_VEHICLE: ThreatLevel.MEDIUM,
            TargetSignature.TRACKED_VEHICLE: ThreatLevel.HIGH,
            TargetSignature.ARTILLERY_FIRE: ThreatLevel.CRITICAL,
            TargetSignature.EXPLOSION: ThreatLevel.CRITICAL,
            TargetSignature.DRONE_HOVER: ThreatLevel.MEDIUM,
            TargetSignature.DRONE_FLYBY: ThreatLevel.MEDIUM,
            TargetSignature.EW_INTERFERENCE: ThreatLevel.HIGH,
            TargetSignature.DIGGING: ThreatLevel.LOW,
        }

        return best_match, confidence, threat_map.get(best_match, ThreatLevel.NONE)

    def get_false_alarm_rate(self) -> dict:
        base_rate = {
            EnvironmentalCondition.CLEAR: {
                "wind_noise_per_h": 0.0,
                "rain_noise_per_h": 0.0,
                "distant_traffic_per_h": 0.5,
                "total_per_h": 0.5,
            },
            EnvironmentalCondition.LIGHT_WIND: {
                "wind_noise_per_h": 1.0,
                "rain_noise_per_h": 0.0,
                "distant_traffic_per_h": 0.5,
                "total_per_h": 1.5,
            },
            EnvironmentalCondition.STRONG_WIND: {
                "wind_noise_per_h": 5.0,
                "rain_noise_per_h": 0.0,
                "distant_traffic_per_h": 0.5,
                "total_per_h": 5.5,
            },
            EnvironmentalCondition.LIGHT_RAIN: {
                "wind_noise_per_h": 0.0,
                "rain_noise_per_h": 2.0,
                "distant_traffic_per_h": 0.5,
                "total_per_h": 2.5,
            },
            EnvironmentalCondition.HEAVY_RAIN: {
                "wind_noise_per_h": 2.0,
                "rain_noise_per_h": 8.0,
                "distant_traffic_per_h": 0.3,
                "total_per_h": 10.3,
            },
        }
        return base_rate.get(self.env_condition, base_rate[EnvironmentalCondition.CLEAR])

    def _inject_false_alarms(self, events: list[dict], duration_s: float) -> list[dict]:
        far = self.get_false_alarm_rate()
        total_rate = far["total_per_h"]
        expected_count = total_rate * duration_s / 3600.0
        num_false = int(expected_count)
        if random.random() < (expected_count - num_false):
            num_false += 1

        cond = self.env_condition

        for _ in range(num_false):
            t = random.uniform(0, duration_s)
            position = random.uniform(100, self.fiber_length - 100)

            if cond in (EnvironmentalCondition.LIGHT_WIND, EnvironmentalCondition.STRONG_WIND):
                freq = random.uniform(0.5, 3.0)
                signature = TargetSignature.FOOTSTEP_SINGLE
                duration = random.uniform(0.5, 2.0)
                description_extra = "wind"
            elif cond in (EnvironmentalCondition.LIGHT_RAIN, EnvironmentalCondition.HEAVY_RAIN):
                freq = random.uniform(10.0, 100.0)
                signature = TargetSignature.WHEELED_VEHICLE
                duration = random.uniform(1.0, 3.0)
                description_extra = "rain"
            else:
                freq = random.uniform(2.0, 8.0)
                signature = TargetSignature.WHEELED_VEHICLE
                duration = random.uniform(2.0, 5.0)
                description_extra = "distant_traffic"

            events.append({
                "time": t,
                "position": position,
                "signature": signature,
                "duration": duration,
                "false_alarm": True,
                "false_alarm_source": description_extra,
            })

        return events

    def simulate_scenario(self, duration_s: float = 60.0,
                          events: Optional[list[dict]] = None) -> list[DASEvent]:
        if not self.segments:
            self.auto_segment()

        if events is None:
            events = self._generate_random_events(duration_s)

        events = self._inject_false_alarms(events, duration_s)

        self.detected_events.clear()
        num_samples = int(duration_s)

        for sample_idx in range(num_samples):
            t = float(sample_idx)
            channel_data = self._generate_backscatter()

            channel_data = self._inject_environmental_noise(channel_data, t)

            for event in events:
                if abs(t - event["time"]) < event.get("duration", 1.0):
                    self._inject_target(
                        channel_data, event["position"],
                        event["signature"], t
                    )

            max_idx = max(range(len(channel_data)), key=lambda i: channel_data[i])
            max_val = channel_data[max_idx]

            if max_val > self.noise_floor / 10:
                position = max_idx * self.spatial_resolution
                amplitude_norm = min((max_val - self.noise_floor / 10) / 30.0, 1.0)
                freq = self._estimate_freq_from_channel(channel_data, max_idx)

                target, conf, threat = self._classify_event(amplitude_norm, freq, position)

                if target != TargetSignature.SILENCE and conf > 0.3:
                    das_event = DASEvent(
                        timestamp_s=t,
                        position_m=round(position, 1),
                        target_type=target,
                        amplitude=round(amplitude_norm, 3),
                        frequency_hz=round(freq, 2),
                        confidence=round(conf, 3),
                        threat_level=threat,
                        snr_db=round(max_val - self.noise_floor, 1),
                        description=self._describe_event(target, position, conf),
                    )
                    self.detected_events.append(das_event)

            if sample_idx % 10 == 0:
                self.backscatter_data.append(channel_data[:])

        return self.detected_events

    def _generate_random_events(self, duration_s: float) -> list[dict]:
        events = []
        num_events = random.randint(3, int(duration_s / 10))

        for _ in range(num_events):
            sig = random.choices(
                list(TargetSignature),
                weights=[5, 15, 10, 12, 8, 3, 2, 5, 4, 3, 8],
            )[0]
            events.append({
                "time": random.uniform(0, duration_s),
                "position": random.uniform(100, self.fiber_length - 100),
                "signature": sig,
                "duration": random.uniform(0.5, 5.0),
            })

        return sorted(events, key=lambda e: e["time"])

    def _estimate_freq_from_channel(self, data: list[float], center: int) -> float:
        window = data[max(0, center - 50):center + 50]
        if len(window) < 10:
            return 0.0
        crossings = sum(1 for i in range(len(window) - 1) if window[i] * window[i + 1] < 0)
        return crossings * self.sample_rate / (2 * len(window))

    def _describe_event(self, target: TargetSignature, position: float,
                        confidence: float) -> str:
        descs = {
            TargetSignature.FOOTSTEP_SINGLE: f"Single pedestrian at {position:.0f}m",
            TargetSignature.FOOTSTEP_GROUP: f"Group movement at {position:.0f}m",
            TargetSignature.WHEELED_VEHICLE: f"Wheeled vehicle at {position:.0f}m",
            TargetSignature.TRACKED_VEHICLE: f"Tracked vehicle (armor?) at {position:.0f}m",
            TargetSignature.ARTILLERY_FIRE: f"ARTILLERY FIRE detected at {position:.0f}m",
            TargetSignature.EXPLOSION: f"EXPLOSION at {position:.0f}m",
            TargetSignature.DRONE_HOVER: f"Hovering drone at {position:.0f}m",
            TargetSignature.DRONE_FLYBY: f"Drone flyby at {position:.0f}m",
            TargetSignature.EW_INTERFERENCE: f"EW interference at {position:.0f}m",
            TargetSignature.DIGGING: f"Digging activity at {position:.0f}m",
            TargetSignature.SILENCE: "",
        }
        desc = descs.get(target, f"Unknown at {position:.0f}m")
        return f"[{confidence * 100:.0f}%] {desc}"

    def generate_fft_signature(self, target: TargetSignature, duration_s: float,
                               sample_rate: int = 1000) -> list[float]:
        if target == TargetSignature.SILENCE:
            return [0.0] * int(duration_s * sample_rate)

        profile = SIGNATURE_PROFILES[target]
        freq_min, freq_max = profile["freq_range"]
        amp_min, amp_max = profile["amplitude_range"]
        harmonics = profile.get("harmonics", [])
        temporal_pattern = profile.get("temporal_pattern", "continuous")
        decay_time = profile.get("decay_time_s", 0.0)
        period_hz = profile.get("period_hz", 1.0)

        num_samples = int(duration_s * sample_rate)
        fundamental_freq = (freq_min + freq_max) / 2.0
        amplitude = (amp_min + amp_max) / 2.0

        signal = []
        for i in range(num_samples):
            t = i / sample_rate
            sample = 0.0

            sample += amplitude * math.sin(2 * math.pi * fundamental_freq * t)

            for mult, rel_amp in harmonics:
                harmonic_freq = fundamental_freq * mult
                sample += amplitude * rel_amp * math.sin(2 * math.pi * harmonic_freq * t)

            if temporal_pattern == "impulse" and decay_time > 0:
                decay = math.exp(-t / decay_time)
                sample *= decay
            elif temporal_pattern == "periodic":
                envelope = 0.5 + 0.5 * math.sin(2 * math.pi * period_hz * t)
                sample *= envelope
            elif temporal_pattern == "sweep":
                sweep_factor = 0.5 + 0.5 * (t / duration_s)
                sample *= sweep_factor

            sample += random.gauss(0, 0.02 * amplitude)
            signal.append(sample)

        return signal

    def get_alerts(self, min_threat: ThreatLevel = ThreatLevel.MEDIUM) -> list[dict]:
        threat_order = [ThreatLevel.NONE, ThreatLevel.LOW, ThreatLevel.MEDIUM,
                        ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        min_idx = threat_order.index(min_threat)

        alerts = []
        for evt in self.detected_events:
            if threat_order.index(evt.threat_level) >= min_idx:
                alerts.append({
                    "timestamp_s": evt.timestamp_s,
                    "position_m": evt.position_m,
                    "target": evt.target_type.value,
                    "threat": evt.threat_level.value,
                    "confidence": f"{evt.confidence * 100:.0f}%",
                    "snr_db": evt.snr_db,
                    "description": evt.description,
                })
        return alerts

    def generate_report(self) -> dict:
        threat_counts = {}
        for evt in self.detected_events:
            key = evt.target_type.value
            threat_counts[key] = threat_counts.get(key, 0) + 1

        positions = [e.position_m for e in self.detected_events]
        return {
            "fiber_length_m": self.fiber_length,
            "events_detected": len(self.detected_events),
            "threat_breakdown": threat_counts,
            "position_range": {
                "min": min(positions) if positions else 0,
                "max": max(positions) if positions else 0,
            },
            "high_threat_events": sum(
                1 for e in self.detected_events
                if e.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
            ),
        }


def main():
    print("=" * 60)
    print("TFN DAS SIMULATOR")
    print("=" * 60)

    sim = DASSimulator(fiber_length_m=5000, spatial_resolution_m=1.0)
    sim.auto_segment()

    print(f"\nFiber: {sim.fiber_length}m, Channels: {sim.num_channels}")
    print(f"Launch power: {sim.launch_power_dbm} dBm, Noise figure: {sim.noise_figure_db} dB")
    print(f"Segments: {len(sim.segments)}")
    for seg in sim.segments:
        print(f"  {seg.start_m:.0f}-{seg.end_m:.0f}m: {seg.terrain} "
              f"(depth={seg.burial_depth_m:.2f}m, atten={seg.attenuation_db_km:.2f}dB/km)")

    print("\n--- SNR Analysis ---")
    test_positions = [500, 1000, 2000, 3500, 4500]
    test_distances = [5, 10, 50, 100, 500]
    for pos in test_positions:
        for dist in test_distances:
            snr = sim.compute_snr(pos, dist)
            p_det = sim._compute_detection_probability(snr)
            print(f"  pos={pos:>5}m, dist={dist:>4}m -> SNR={snr:>6.1f}dB, P_detect={p_det:.3f}")

    print("\n--- Environmental Conditions & False Alarm Rates ---")
    for cond in EnvironmentalCondition:
        sim.env_condition = cond
        far = sim.get_false_alarm_rate()
        print(f"  {cond.value:>12s}: {far['total_per_h']:.1f} false alarms/hour "
              f"(wind={far['wind_noise_per_h']:.1f}, rain={far['rain_noise_per_h']:.1f}, "
              f"traffic={far['distant_traffic_per_h']:.1f})")

    sim.env_condition = EnvironmentalCondition.CLEAR

    custom_events = [
        {"time": 5, "position": 800, "signature": TargetSignature.FOOTSTEP_GROUP, "duration": 3},
        {"time": 12, "position": 2200, "signature": TargetSignature.WHEELED_VEHICLE, "duration": 8},
        {"time": 20, "position": 3500, "signature": TargetSignature.TRACKED_VEHICLE, "duration": 10},
        {"time": 30, "position": 1200, "signature": TargetSignature.ARTILLERY_FIRE, "duration": 0.5},
        {"time": 35, "position": 4000, "signature": TargetSignature.EXPLOSION, "duration": 1},
        {"time": 40, "position": 500, "signature": TargetSignature.DRONE_HOVER, "duration": 15},
        {"time": 50, "position": 3000, "signature": TargetSignature.EW_INTERFERENCE, "duration": 5},
        {"time": 55, "position": 1800, "signature": TargetSignature.DIGGING, "duration": 4},
    ]

    print(f"\n--- Running scenario ({len(custom_events)} injected events) ---\n")
    events = sim.simulate_scenario(duration_s=60, events=custom_events)

    print(f"Detected events: {len(events)}\n")

    alerts = sim.get_alerts(min_threat=ThreatLevel.MEDIUM)
    print("--- ALERTS (MEDIUM+ threat) ---")
    for alert in alerts:
        icon = {"low": ".", "medium": "!", "high": "!!", "critical": "!!!"}.get(alert["threat"], "?")
        print(f"  [{icon}] {alert['description']}")
        print(f"       Position: {alert['position_m']}m, SNR: {alert['snr_db']}dB")

    report = sim.generate_report()
    print("\n--- REPORT ---")
    print(json.dumps(report, indent=2))

    print("\n--- FFT Signature Generation ---")
    for target in [TargetSignature.FOOTSTEP_GROUP, TargetSignature.TRACKED_VEHICLE,
                   TargetSignature.ARTILLERY_FIRE, TargetSignature.DRONE_HOVER,
                   TargetSignature.DIGGING]:
        sig = sim.generate_fft_signature(target, duration_s=0.1, sample_rate=1000)
        peak = max(abs(s) for s in sig) if sig else 0
        profile = SIGNATURE_PROFILES[target]
        print(f"  {target.value:>20s}: {len(sig)} samples, peak={peak:.3f}, "
              f"bandwidth={profile['bandwidth_hz']:.0f}Hz, "
              f"pattern={profile['temporal_pattern']}, "
              f"harmonics={len(profile['harmonics'])}")

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
