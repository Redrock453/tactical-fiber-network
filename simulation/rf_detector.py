#!/usr/bin/env python3
"""
TFN RF-Opto Hybrid Detector Simulator
========================================

Simulates detection of RF emissions via fiber optic cable
using Kerr effect and thermo-optic response.

Models:
- EW station detection (high power, 100W-1kW)
- Drone RF control link detection (low power, 0.1-5W)
- Radar detection (pulsed, high power)
- FPV video transmitter detection

All detection is PASSIVE - no RF emission from the sensor.
"""

import math
import random
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RFSourceType(Enum):
    EW_STATION = "ew_station"
    RADAR = "radar"
    FPV_CONTROL = "fpv_control"
    FPV_VIDEO = "fpv_video"
    TACTICAL_RADIO = "tactical_radio"
    SATELLITE_UPLINK = "satellite_uplink"
    CELL_TOWER = "cell_tower"


@dataclass
class RFSource:
    source_type: RFSourceType
    frequency_hz: float
    power_w: float
    distance_to_fiber_m: float
    position_m_on_fiber: float
    modulation: str = "continuous"
    bandwidth_hz: float = 1e6


RF_PROFILES = {
    RFSourceType.EW_STATION: {
        "freq_range": (100e6, 6e9),
        "power_range": (100, 5000),
        "typical_distance": (5, 50),
        "modulation": ["noise", "sweep", "tone"],
    },
    RFSourceType.RADAR: {
        "freq_range": (1e9, 18e9),
        "power_range": (1000, 50000),
        "typical_distance": (10, 200),
        "modulation": ["pulsed", "fm chirp"],
    },
    RFSourceType.FPV_CONTROL: {
        "freq_range": (2.4e9, 2.5e9),
        "power_range": (0.1, 2),
        "typical_distance": (1, 30),
        "modulation": ["fhss", "dsss"],
    },
    RFSourceType.FPV_VIDEO: {
        "freq_range": (5.7e9, 5.9e9),
        "power_range": (0.025, 1),
        "typical_distance": (0.5, 15),
        "modulation": ["ofdm", "analog"],
    },
    RFSourceType.TACTICAL_RADIO: {
        "freq_range": (30e6, 512e6),
        "power_range": (1, 50),
        "typical_distance": (2, 50),
        "modulation": ["fm", "nfm", "dmr"],
    },
    RFSourceType.SATELLITE_UPLINK: {
        "freq_range": (14e9, 14.5e9),
        "power_range": (10, 500),
        "typical_distance": (20, 200),
        "modulation": ["qpsk", "8psk"],
    },
    RFSourceType.CELL_TOWER: {
        "freq_range": (700e6, 3.5e9),
        "power_range": (20, 200),
        "typical_distance": (10, 100),
        "modulation": ["ofdm", "lte"],
    },
}


@dataclass
class DetectionResult:
    timestamp_s: float
    source_type: RFSourceType
    position_m: float
    detected: bool
    phase_shift_rad: float
    snr_db: float
    confidence: float
    distance_estimate_m: float
    power_estimate_w: float
    frequency_estimate_hz: float
    method: str


class RFDetectorSimulator:
    N2_KERR = 3.2e-20
    WAVELENGTH = 1550e-9
    N_FIBER = 1.47
    MIN_DETECTABLE_PHASE_SHIFT = 1e-6

    def __init__(self, fiber_length_m: float = 10000,
                 spatial_resolution_m: float = 1.0,
                 tx_power_dbm: float = 0.0,
                 rx_sensitivity_dbm: float = -30.0):
        self.fiber_length = fiber_length_m
        self.spatial_resolution = spatial_resolution_m
        self.tx_power_dbm = tx_power_dbm
        self.rx_sensitivity_dbm = rx_sensitivity_dbm
        self.detections: list[DetectionResult] = []

    def _electric_field_at_fiber(self, power_w: float, distance_m: float) -> float:
        if distance_m <= 0:
            distance_m = 0.1
        power_density = power_w / (4 * math.pi * distance_m ** 2)
        impedance = 377.0
        e_field = math.sqrt(2 * power_density * impedance)
        return e_field

    def _kerr_phase_shift(self, e_field: float, fiber_length_exposed_m: float) -> float:
        delta_n = self.N2_KERR * e_field ** 2
        phase_shift = (2 * math.pi / self.WAVELENGTH) * delta_n * fiber_length_exposed_m
        return phase_shift

    def _thermo_optic_phase_shift(self, power_w: float, distance_m: float,
                                   exposure_time_s: float = 1.0) -> float:
        absorption_coeff = 1e-6
        if distance_m <= 0:
            distance_m = 0.1
        heat_deposited = power_w * absorption_coeff / (distance_m ** 2) * exposure_time_s
        dn_dT = 1.1e-5
        delta_T = heat_deposited * 0.01
        delta_n = dn_dT * delta_T
        phase_shift = (2 * math.pi / self.WAVELENGTH) * delta_n * 0.1
        return phase_shift

    def _estimate_snr(self, phase_shift: float) -> float:
        noise_level = 1e-7
        if phase_shift <= 0:
            return -100.0
        snr = 10 * math.log10(phase_shift / noise_level)
        return snr

    def detect_source(self, source: RFSource, timestamp_s: float = 0.0) -> DetectionResult:
        e_field = self._electric_field_at_fiber(source.power_w, source.distance_to_fiber_m)
        exposed_length = min(50.0, self.fiber_length * 0.01)

        kerr_shift = self._kerr_phase_shift(e_field, exposed_length)
        thermo_shift = self._thermo_optic_phase_shift(source.power_w, source.distance_to_fiber_m)

        total_phase_shift = kerr_shift + thermo_shift
        dominant_method = "kerr" if kerr_shift > thermo_shift else "thermo_optic"

        snr = self._estimate_snr(total_phase_shift)
        detected = total_phase_shift > self.MIN_DETECTABLE_PHASE_SHIFT and snr > 3.0

        confidence = min(abs(snr) / 20.0, 0.99) if detected else 0.0

        dist_estimate = source.distance_to_fiber_m * random.uniform(0.7, 1.3) if detected else -1
        power_estimate = source.power_w * random.uniform(0.5, 2.0) if detected else -1
        freq_estimate = source.frequency_hz * random.uniform(0.98, 1.02) if detected else -1

        result = DetectionResult(
            timestamp_s=timestamp_s,
            source_type=source.source_type,
            position_m=source.position_m_on_fiber,
            detected=detected,
            phase_shift_rad=total_phase_shift,
            snr_db=round(snr, 2),
            confidence=round(confidence, 3),
            distance_estimate_m=round(dist_estimate, 1),
            power_estimate_w=round(power_estimate, 2),
            frequency_estimate_hz=round(freq_estimate, 0),
            method=dominant_method,
        )
        self.detections.append(result)
        return result

    def run_detection_sweep(self, sources: list[RFSource]) -> list[DetectionResult]:
        results = []
        for i, source in enumerate(sources):
            result = self.detect_source(source, timestamp_s=float(i))
            results.append(result)
        return results

    def generate_random_sources(self, count: int = 10) -> list[RFSource]:
        sources = []
        for _ in range(count):
            src_type = random.choices(
                list(RFSourceType),
                weights=[5, 3, 20, 15, 10, 2, 5],
            )[0]
            profile = RF_PROFILES[src_type]
            freq = random.uniform(*profile["freq_range"])
            power = random.uniform(*profile["power_range"])
            distance = random.uniform(*profile["typical_distance"])
            position = random.uniform(100, self.fiber_length - 100)
            modulation = random.choice(profile["modulation"])

            sources.append(RFSource(
                source_type=src_type,
                frequency_hz=freq,
                power_w=power,
                distance_to_fiber_m=distance,
                position_m_on_fiber=position,
                modulation=modulation,
            ))
        return sources

    def generate_report(self) -> dict:
        total = len(self.detections)
        detected = sum(1 for d in self.detections if d.detected)
        by_type = {}
        for d in self.detections:
            if d.detected:
                key = d.source_type.value
                by_type[key] = by_type.get(key, 0) + 1

        return {
            "total_sources_scanned": total,
            "detected": detected,
            "detection_rate": f"{(detected / total * 100):.1f}%" if total > 0 else "0%",
            "by_type": by_type,
            "min_snr_detected": min((d.snr_db for d in self.detections if d.detected), default=0),
            "methods_used": list(set(d.method for d in self.detections if d.detected)),
        }


def main():
    print("=" * 60)
    print("TFN RF-OPTO HYBRID DETECTOR SIMULATOR")
    print("=" * 60)

    detector = RFDetectorSimulator(fiber_length_m=5000)

    test_sources = [
        RFSource(RFSourceType.EW_STATION, 2.4e9, 1000, 10, 1500, "noise"),
        RFSource(RFSourceType.RADAR, 10e9, 10000, 50, 3000, "pulsed"),
        RFSource(RFSourceType.FPV_CONTROL, 2.4e9, 0.5, 5, 800, "fhss"),
        RFSource(RFSourceType.FPV_VIDEO, 5.8e9, 0.2, 3, 1200, "analog"),
        RFSource(RFSourceType.TACTICAL_RADIO, 150e6, 5, 15, 2500, "fm"),
        RFSource(RFSourceType.EW_STATION, 900e6, 500, 25, 4000, "sweep"),
        RFSource(RFSourceType.FPV_CONTROL, 2.4e9, 0.1, 20, 600, "dsss"),
        RFSource(RFSourceType.SATELLITE_UPLINK, 14e9, 100, 100, 3500, "qpsk"),
    ]

    print(f"\nFiber: {detector.fiber_length}m")
    print(f"Scanning {len(test_sources)} RF sources...\n")
    print("-" * 60)

    results = detector.run_detection_sweep(test_sources)

    for r in results:
        status = "DETECTED" if r.detected else "MISSED"
        print(f"\n  [{status}] {r.source_type.value}")
        print(f"    Frequency: {r.frequency_estimate_hz / 1e6:.1f} MHz" if r.detected else "    Not detected")
        if r.detected:
            print(f"    Phase shift: {r.phase_shift_rad:.2e} rad")
            print(f"    SNR: {r.snr_db:.1f} dB")
            print(f"    Confidence: {r.confidence * 100:.0f}%")
            print(f"    Est. distance: {r.distance_estimate_m:.0f}m")
            print(f"    Est. power: {r.power_estimate_w:.1f}W")
            print(f"    Method: {r.method}")
            print(f"    Position on fiber: {r.position_m:.0f}m")

    report = detector.generate_report()
    print("\n" + "=" * 60)
    print("DETECTION REPORT")
    print("=" * 60)
    print(json.dumps(report, indent=2))

    print("\n--- Sensitivity Analysis ---")
    print("Min detectable phase shift: 1e-6 rad")
    print("Kerr coefficient (n2): 3.2e-20 m^2/V^2")
    print(f"Wavelength: {detector.WAVELENGTH * 1e9:.0f}nm")

    print("\n--- Theoretical Detection Ranges ---")
    for power_dbm in [10, 20, 30, 40, 50]:
        power_w = 10 ** ((power_dbm - 30) / 10)
        for dist in [1, 5, 10, 50, 100]:
            e = detector._electric_field_at_fiber(power_w, dist)
            ps = detector._kerr_phase_shift(e, 10)
            detectable = "YES" if ps > detector.MIN_DETECTABLE_PHASE_SHIFT else "no"
            if dist in [1, 10, 100]:
                print(f"  {power_w:.1f}W @ {dist}m: delta_phi={ps:.2e} rad [{detectable}]")

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
