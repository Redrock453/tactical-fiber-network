#!/usr/bin/env python3
"""
TFN Break Locator — OTDR-based Fiber Break Detection
=====================================================

Locates breaks and degradation points in fiber optic cable
using OTDR (Optical Time-Domain Reflectometer) analysis.

Supports:
- Single break detection
- Multiple break detection (artillery damage)
- Degradation hotspot identification
- Break position estimation with confidence intervals
"""

import math
import random
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class OTDRPoint:
    distance_m: float
    power_dbm: float
    is_event: bool = False
    event_type: str = ""


@dataclass
class BreakInfo:
    position_m: float
    confidence: float
    return_loss_db: float
    event_type: str
    severity: str


class BreakLocator:
    def __init__(self, fiber_length_m: float = 10000,
                 pulse_width_ns: float = 100,
                 noise_floor_dbm: float = -60):
        self.fiber_length = fiber_length_m
        self.pulse_width_ns = pulse_width_ns
        self.noise_floor = noise_floor_dbm
        self.spatial_resolution = 0.15 * pulse_width_ns / 10
        self.points: list[OTDRPoint] = []

    def generate_otdr_trace(self, breaks: Optional[list[dict]] = None,
                            splices: Optional[list[dict]] = None,
                            attenuation_db_km: float = 0.35) -> list[OTDRPoint]:
        points = []
        step = self.spatial_resolution
        tx_power = 0.0

        breaks_at = {}
        if breaks:
            for b in breaks:
                breaks_at[int(b["position_m"] / step)] = b

        splices_at = {}
        if splices:
            for s in splices:
                splices_at[int(s["position_m"] / step)] = s

        num_points = int(self.fiber_length / step)
        current_power = tx_power

        for i in range(num_points):
            dist = i * step
            current_power -= attenuation_db_km * step / 1000

            if i in splices_at:
                splice = splices_at[i]
                current_power -= splice.get("loss_db", 0.2)
                points.append(OTDRPoint(
                    distance_m=dist, power_dbm=current_power,
                    is_event=True, event_type="splice",
                ))
            elif i in breaks_at:
                brk = breaks_at[i]
                current_power -= brk.get("return_loss_db", 14.0)
                points.append(OTDRPoint(
                    distance_m=dist, power_dbm=current_power,
                    is_event=True, event_type="break",
                ))
                for j in range(i + 1, min(i + int(50 / step), num_points)):
                    d = j * step
                    noise = random.gauss(self.noise_floor, 2)
                    points.append(OTDRPoint(distance_m=d, power_dbm=noise))
                break
            else:
                noise = random.gauss(0, 0.05)
                points.append(OTDRPoint(distance_m=dist, power_dbm=current_power + noise))

        self.points = points
        return points

    def locate_breaks(self) -> list[BreakInfo]:
        breaks = []
        for i in range(1, len(self.points)):
            prev = self.points[i - 1]
            curr = self.points[i]

            if prev.power_dbm - curr.power_dbm > 5.0:
                confidence = min((prev.power_dbm - curr.power_dbm) / 20.0, 0.99)
                return_loss = prev.power_dbm - curr.power_dbm

                severity = "complete" if return_loss > 10 else "partial"

                breaks.append(BreakInfo(
                    position_m=round(curr.distance_m, 1),
                    confidence=round(confidence, 3),
                    return_loss_db=round(return_loss, 1),
                    event_type=curr.event_type or "sudden_drop",
                    severity=severity,
                ))

        return breaks

    def locate_degradation(self, window_m: float = 100) -> list[dict]:
        step = self.spatial_resolution
        window_samples = int(window_m / step)
        hotspots = []

        for i in range(window_samples, len(self.points) - window_samples):
            window = self.points[i - window_samples:i + window_samples]
            if len(window) < window_samples:
                continue

            before = self.points[i - window_samples:i]
            after = self.points[i:i + window_samples]

            avg_before = sum(p.power_dbm for p in before) / len(before)
            avg_after = sum(p.power_dbm for p in after) / len(after)

            expected_loss = 0.35 * window_m * 2 / 1000
            actual_loss = avg_before - avg_after
            excess = actual_loss - expected_loss

            if excess > 0.5:
                hotspots.append({
                    "position_m": round(self.points[i].distance_m, 1),
                    "expected_loss_db": round(expected_loss, 2),
                    "actual_loss_db": round(actual_loss, 2),
                    "excess_loss_db": round(excess, 2),
                    "severity": "high" if excess > 2 else "medium" if excess > 1 else "low",
                })

        merged = []
        for h in hotspots:
            if not merged or h["position_m"] - merged[-1]["position_m"] > window_m:
                merged.append(h)

        return merged

    def generate_report(self) -> dict:
        breaks = self.locate_breaks()
        degradation = self.locate_degradation()

        trace_ok = len(self.points) > 0 and not any(b.severity == "complete" for b in breaks)

        return {
            "fiber_length_m": self.fiber_length,
            "spatial_resolution_m": round(self.spatial_resolution, 2),
            "trace_points": len(self.points),
            "breaks_found": len(breaks),
            "breaks": [
                {
                    "position_m": b.position_m,
                    "confidence": f"{b.confidence * 100:.0f}%",
                    "return_loss_db": b.return_loss_db,
                    "type": b.event_type,
                    "severity": b.severity,
                }
                for b in breaks
            ],
            "degradation_hotspots": len(degradation),
            "hotspots": degradation[:10],
            "fiber_status": "OK" if trace_ok and not breaks else
                           "DEGRADED" if not breaks else "BROKEN",
            "usable_length_m": round(
                breaks[0].position_m if breaks else self.fiber_length, 1
            ),
        }


def demo():
    print("=" * 60)
    print("TFN BREAK LOCATOR — OTDR Analysis")
    print("=" * 60)

    scenarios = [
        {
            "name": "Healthy fiber (no breaks)",
            "breaks": None,
            "splices": [{"position_m": 2500, "loss_db": 0.15}, {"position_m": 5000, "loss_db": 0.15}],
        },
        {
            "name": "Single break at 3500m (artillery)",
            "breaks": [{"position_m": 3500, "return_loss_db": 15}],
            "splices": [{"position_m": 2000, "loss_db": 0.2}],
        },
        {
            "name": "Multiple breaks (heavy shelling)",
            "breaks": [{"position_m": 1200, "return_loss_db": 12}, {"position_m": 3800, "return_loss_db": 18}],
            "splices": [{"position_m": 2500, "loss_db": 0.2}],
        },
    ]

    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        locator = BreakLocator(fiber_length_m=10000)
        locator.generate_otdr_trace(
            breaks=scenario["breaks"],
            splices=scenario["splices"],
        )
        report = locator.generate_report()
        print(f"  Status: {report['fiber_status']}")
        print(f"  Usable length: {report['usable_length_m']}m")
        print(f"  Breaks: {report['breaks_found']}")
        for b in report["breaks"]:
            print(f"    → {b['position_m']}m, loss={b['return_loss_db']}dB, [{b['severity']}]")
        if report["hotspots"]:
            print(f"  Degradation hotspots: {report['degradation_hotspots']}")
            for h in report["hotspots"][:5]:
                print(f"    → {h['position_m']}m, excess={h['excess_loss_db']}dB [{h['severity']}]")


if __name__ == "__main__":
    demo()
