#!/usr/bin/env python3
"""
TFN DAS (Distributed Acoustic Sensing) Simulator
==================================================

Simulates φ-OTDR interrogation of fiber optic cable for:
- Footstep detection
- Vehicle detection (wheeled / tracked)
- Artillery fire detection
- Drone flyover detection
- EW interference detection

Generates realistic synthetic backscatter signals with noise,
multi-target events, and produces classification reports.
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


SIGNATURE_PROFILES = {
    TargetSignature.SILENCE: {
        "freq_range": (0.1, 0.3),
        "amplitude_range": (0.01, 0.05),
        "duration_s": (0.5, 2.0),
        "pattern": "continuous",
    },
    TargetSignature.FOOTSTEP_SINGLE: {
        "freq_range": (1.5, 3.0),
        "amplitude_range": (0.15, 0.35),
        "duration_s": (0.1, 0.3),
        "pattern": "periodic",
        "period_hz": 2.0,
    },
    TargetSignature.FOOTSTEP_GROUP: {
        "freq_range": (1.0, 4.0),
        "amplitude_range": (0.25, 0.55),
        "duration_s": (0.15, 0.4),
        "pattern": "periodic",
        "period_hz": 3.5,
    },
    TargetSignature.WHEELED_VEHICLE: {
        "freq_range": (8.0, 20.0),
        "amplitude_range": (0.40, 0.70),
        "duration_s": (1.0, 5.0),
        "pattern": "continuous",
    },
    TargetSignature.TRACKED_VEHICLE: {
        "freq_range": (2.0, 8.0),
        "amplitude_range": (0.60, 0.90),
        "duration_s": (2.0, 8.0),
        "pattern": "continuous",
    },
    TargetSignature.ARTILLERY_FIRE: {
        "freq_range": (0.5, 3.0),
        "amplitude_range": (0.85, 1.0),
        "duration_s": (0.05, 0.2),
        "pattern": "impulse",
    },
    TargetSignature.EXPLOSION: {
        "freq_range": (0.1, 15.0),
        "amplitude_range": (0.90, 1.0),
        "duration_s": (0.3, 1.5),
        "pattern": "impulse",
    },
    TargetSignature.DRONE_HOVER: {
        "freq_range": (40.0, 80.0),
        "amplitude_range": (0.10, 0.25),
        "duration_s": (5.0, 30.0),
        "pattern": "continuous",
    },
    TargetSignature.DRONE_FLYBY: {
        "freq_range": (30.0, 100.0),
        "amplitude_range": (0.15, 0.35),
        "duration_s": (2.0, 8.0),
        "pattern": "sweep",
    },
    TargetSignature.EW_INTERFERENCE: {
        "freq_range": (100.0, 2000.0),
        "amplitude_range": (0.30, 0.60),
        "duration_s": (1.0, 10.0),
        "pattern": "continuous",
    },
    TargetSignature.DIGGING: {
        "freq_range": (3.0, 12.0),
        "amplitude_range": (0.20, 0.50),
        "duration_s": (0.2, 1.0),
        "pattern": "periodic",
        "period_hz": 1.5,
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
                 spatial_resolution_m: float = 1.0, noise_floor_db: float = -60.0):
        self.fiber_length = fiber_length_m
        self.sample_rate = sample_rate_hz
        self.spatial_resolution = spatial_resolution_m
        self.noise_floor = noise_floor_db
        self.num_channels = int(fiber_length_m / spatial_resolution_m)
        self.segments: list[FiberSegment] = []
        self.detected_events: list[DASEvent] = []
        self.backscatter_data: list[list[float]] = []

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

        confidence = min(best_score * 1.2, 0.99)

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

    def simulate_scenario(self, duration_s: float = 60.0,
                          events: Optional[list[dict]] = None) -> list[DASEvent]:
        if not self.segments:
            self.auto_segment()

        if events is None:
            events = self._generate_random_events(duration_s)

        self.detected_events.clear()
        num_samples = int(duration_s)

        for sample_idx in range(num_samples):
            t = float(sample_idx)
            channel_data = self._generate_backscatter()

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
    print(f"Segments: {len(sim.segments)}")
    for seg in sim.segments:
        print(f"  {seg.start_m:.0f}-{seg.end_m:.0f}m: {seg.terrain} "
              f"(depth={seg.burial_depth_m:.2f}m, atten={seg.attenuation_db_km:.2f}dB/km)")

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

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
