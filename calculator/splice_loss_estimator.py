#!/usr/bin/env python3
"""
TFN Splice Loss Estimator
===========================

Estimates optical losses for different field splicing methods
and provides recommendations for combat conditions.

Models:
- Mechanical splice quality vs cleave quality
- Quick connector performance
- Environmental effects on splice quality
- Cumulative loss for multi-splice links
"""

import json
import random
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CleaveQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    EMERGENCY = "emergency"


class SpliceMethod(Enum):
    FUSION = "fusion"
    MECHANICAL_GEL = "mechanical_gel"
    MECHANICAL_DRY = "mechanical_dry"
    QUICK_CONNECTOR = "quick_connector"
    EMERGENCY_TAPE = "emergency_tape"
    UV_GLUE = "uv_glue"


@dataclass
class SpliceEstimate:
    method: SpliceMethod
    cleave: CleaveQuality
    typical_loss_db: float
    best_case_db: float
    worst_case_db: float
    confidence_90pct_db: float
    time_seconds: int
    cost_usd: float
    requires_power: bool
    temperature_range: tuple
    reliability_months: int
    field_viable: bool
    notes: str


SPLICE_DATA = {
    (SpliceMethod.FUSION, CleaveQuality.EXCELLENT): SpliceEstimate(
        SpliceMethod.FUSION, CleaveQuality.EXCELLENT,
        0.02, 0.01, 0.05, 0.03, 180, 0, True, (-10, 50), 120, False, "Lab/professional only"
    ),
    (SpliceMethod.FUSION, CleaveQuality.GOOD): SpliceEstimate(
        SpliceMethod.FUSION, CleaveQuality.GOOD,
        0.03, 0.02, 0.08, 0.05, 180, 0, True, (-10, 50), 120, False, "Lab/professional only"
    ),
    (SpliceMethod.MECHANICAL_GEL, CleaveQuality.EXCELLENT): SpliceEstimate(
        SpliceMethod.MECHANICAL_GEL, CleaveQuality.EXCELLENT,
        0.07, 0.03, 0.15, 0.10, 30, 10, False, (-20, 60), 18, True, "Best field option"
    ),
    (SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD): SpliceEstimate(
        SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD,
        0.12, 0.05, 0.25, 0.18, 30, 10, False, (-20, 60), 18, True, "Good field option"
    ),
    (SpliceMethod.MECHANICAL_GEL, CleaveQuality.AVERAGE): SpliceEstimate(
        SpliceMethod.MECHANICAL_GEL, CleaveQuality.AVERAGE,
        0.20, 0.10, 0.40, 0.30, 30, 10, False, (-20, 60), 18, True, "Acceptable"
    ),
    (SpliceMethod.MECHANICAL_GEL, CleaveQuality.POOR): SpliceEstimate(
        SpliceMethod.MECHANICAL_GEL, CleaveQuality.POOR,
        0.40, 0.20, 0.80, 0.60, 30, 10, False, (-20, 60), 12, True, "Marginal"
    ),
    (SpliceMethod.MECHANICAL_DRY, CleaveQuality.GOOD): SpliceEstimate(
        SpliceMethod.MECHANICAL_DRY, CleaveQuality.GOOD,
        0.10, 0.05, 0.20, 0.15, 25, 15, False, (-30, 70), 24, True, "No gel needed"
    ),
    (SpliceMethod.MECHANICAL_DRY, CleaveQuality.AVERAGE): SpliceEstimate(
        SpliceMethod.MECHANICAL_DRY, CleaveQuality.AVERAGE,
        0.18, 0.08, 0.35, 0.25, 25, 15, False, (-30, 70), 24, True, "No gel needed"
    ),
    (SpliceMethod.QUICK_CONNECTOR, CleaveQuality.GOOD): SpliceEstimate(
        SpliceMethod.QUICK_CONNECTOR, CleaveQuality.GOOD,
        0.20, 0.10, 0.40, 0.30, 60, 3, False, (-10, 60), 12, True, "Fastest end termination"
    ),
    (SpliceMethod.QUICK_CONNECTOR, CleaveQuality.AVERAGE): SpliceEstimate(
        SpliceMethod.QUICK_CONNECTOR, CleaveQuality.AVERAGE,
        0.35, 0.15, 0.60, 0.50, 60, 3, False, (-10, 60), 12, True, "Fastest end termination"
    ),
    (SpliceMethod.QUICK_CONNECTOR, CleaveQuality.POOR): SpliceEstimate(
        SpliceMethod.QUICK_CONNECTOR, CleaveQuality.POOR,
        0.55, 0.25, 1.20, 0.80, 60, 3, False, (-10, 60), 6, True, "Marginal"
    ),
    (SpliceMethod.EMERGENCY_TAPE, CleaveQuality.AVERAGE): SpliceEstimate(
        SpliceMethod.EMERGENCY_TAPE, CleaveQuality.AVERAGE,
        2.0, 1.0, 5.0, 3.5, 20, 0, False, (-10, 40), 1, True, "LAST RESORT ONLY"
    ),
    (SpliceMethod.UV_GLUE, CleaveQuality.GOOD): SpliceEstimate(
        SpliceMethod.UV_GLUE, CleaveQuality.GOOD,
        0.30, 0.10, 0.80, 0.50, 45, 5, False, (-5, 50), 6, True, "Needs UV light"
    ),
    (SpliceMethod.UV_GLUE, CleaveQuality.AVERAGE): SpliceEstimate(
        SpliceMethod.UV_GLUE, CleaveQuality.AVERAGE,
        0.60, 0.20, 1.50, 1.00, 45, 5, False, (-5, 50), 6, True, "Needs UV light"
    ),
}


class SpliceLossEstimator:
    def __init__(self):
        self.results: list[dict] = []

    def estimate(self, method: SpliceMethod, cleave: CleaveQuality) -> Optional[SpliceEstimate]:
        return SPLICE_DATA.get((method, cleave))

    def estimate_link(self, splices: list[tuple[SpliceMethod, CleaveQuality]],
                      fiber_length_km: float = 5.0,
                      fiber_attenuation_db_km: float = 0.35) -> dict:
        total_splice_loss = 0.0
        worst_case_total = 0.0
        splice_details = []

        for method, cleave in splices:
            est = self.estimate(method, cleave)
            if est is None:
                continue
            total_splice_loss += est.typical_loss_db
            worst_case_total += est.worst_case_db
            splice_details.append({
                "method": method.value,
                "cleave": cleave.value,
                "typical_loss_db": est.typical_loss_db,
                "worst_case_db": est.worst_case_db,
                "time_seconds": est.time_seconds,
                "field_viable": est.field_viable,
                "notes": est.notes,
            })

        fiber_loss = fiber_length_km * fiber_attenuation_db_km
        total_typical = total_splice_loss + fiber_loss
        total_worst = worst_case_total + fiber_loss

        return {
            "fiber_length_km": fiber_length_km,
            "fiber_loss_db": round(fiber_loss, 2),
            "num_splices": len(splices),
            "splice_loss_typical_db": round(total_splice_loss, 2),
            "splice_loss_worst_db": round(worst_case_total, 2),
            "total_loss_typical_db": round(total_typical, 2),
            "total_loss_worst_db": round(total_worst, 2),
            "total_time_seconds": sum(d["time_seconds"] for d in splice_details),
            "budget_required_db": round(total_worst + 6, 2),
            "details": splice_details,
        }

    def recommend_for_conditions(self, available_time_min: int = 30,
                                  temperature_c: int = 10,
                                  experience_level: str = "basic",
                                  has_power: bool = False) -> list[dict]:
        recommendations = []
        for (method, cleave), est in SPLICE_DATA.items():
            if not est.field_viable:
                continue
            if est.time_seconds > available_time_min * 60:
                continue
            if temperature_c < est.temperature_range[0] or temperature_c > est.temperature_range[1]:
                continue
            if est.requires_power and not has_power:
                continue
            score = (
                (1.0 - est.typical_loss_db / 2.0) * 0.4 +
                (1.0 - est.time_seconds / 180) * 0.3 +
                est.reliability_months / 24.0 * 0.2 +
                (1.0 - est.cost_usd / 20) * 0.1
            )
            recommendations.append({
                "method": method.value,
                "cleave_quality": cleave.value,
                "loss_db": est.typical_loss_db,
                "time_seconds": est.time_seconds,
                "score": round(score, 3),
                "notes": est.notes,
            })

        return sorted(recommendations, key=lambda x: x["score"], reverse=True)

    def compare_all_methods(self) -> None:
        print("=" * 70)
        print("TFN SPLICE LOSS ESTIMATOR — METHOD COMPARISON")
        print("=" * 70)

        print("\n--- All Methods (sorted by typical loss) ---\n")
        all_methods = sorted(SPLICE_DATA.values(), key=lambda s: s.typical_loss_db)
        print(f"{'Method':<25} {'Cleave':<12} {'Loss(dB)':>9} {'Best':>6} {'Worst':>6} "
              f"{'Time':>6} {'Field':>6} {'Note'}")
        print("-" * 100)
        for s in all_methods:
            if s.field_viable:
                marker = "FIELD"
            else:
                marker = "lab"
            print(f"  {s.method.value:<23} {s.cleave.value:<12} "
                  f"{s.typical_loss_db:>8.2f} {s.best_case_db:>5.2f} {s.worst_case_db:>5.2f} "
                  f"{s.time_seconds:>5}s {marker:>5}  {s.notes}")

        print("\n--- Typical Field Link: 5km, 3 splices ---\n")
        scenarios = [
            ("Best field (mech+gel, good cleave)",
             [(SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD)] * 3),
            ("Average field (mech+gel, avg cleave)",
             [(SpliceMethod.MECHANICAL_GEL, CleaveQuality.AVERAGE)] * 3),
            ("Dry splice, good cleave",
             [(SpliceMethod.MECHANICAL_DRY, CleaveQuality.GOOD)] * 3),
            ("Quick connectors only",
             [(SpliceMethod.QUICK_CONNECTOR, CleaveQuality.AVERAGE)] * 3),
            ("Mixed: 1 mech + 2 quick",
             [(SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD),
              (SpliceMethod.QUICK_CONNECTOR, CleaveQuality.GOOD)] * 2)[:3],
            ("Emergency (tape splice)",
             [(SpliceMethod.EMERGENCY_TAPE, CleaveQuality.AVERAGE)] * 3),
        ]

        for name, splices in scenarios:
            actual = splices[:3]
            result = self.estimate_link(actual, fiber_length_km=5.0)
            status = "OK" if result["total_loss_worst_db"] < 20 else "MARGINAL" if result["total_loss_worst_db"] < 25 else "FAIL"
            print(f"  {name:<35} "
                  f"typical={result['total_loss_typical_db']:.1f}dB  "
                  f"worst={result['total_loss_worst_db']:.1f}dB  "
                  f"time={result['total_time_seconds']}s  "
                  f"[{status}]")

        print("\n--- Recommendations for conditions ---\n")
        conditions = [
            ("Normal (10°C, 30min, basic)", 30, 10, "basic", False),
            ("Winter (-15°C, 15min)", 15, -15, "basic", False),
            ("Under fire (5min, stress)", 5, 20, "basic", False),
            ("Night operation (10°C, 20min)", 20, 10, "basic", False),
            ("Rear base (has power)", 60, 20, "experienced", True),
        ]

        for name, time_min, temp, level, power in conditions:
            print(f"  {name}:")
            recs = self.recommend_for_conditions(time_min, temp, level, power)
            for r in recs[:3]:
                print(f"    {r['method']:<25} loss={r['loss_db']:.2f}dB  "
                      f"time={r['time_seconds']}s  score={r['score']:.2f}")
            print()

        print("\n--- Monte Carlo: Link reliability simulation ---\n")
        print("  Simulating 1000 links, 5km, 3 mechanical splices (good cleave)...")
        losses = []
        for _ in range(1000):
            link_loss = 5.0 * 0.35
            for _ in range(3):
                base = 0.12
                variation = random.gauss(0, 0.03)
                link_loss += max(0.02, base + variation)
            losses.append(link_loss)

        losses.sort()
        p50 = losses[500]
        p90 = losses[900]
        p99 = losses[990]
        ok_count = sum(1 for l in losses if l < 22)

        print(f"  P50 loss: {p50:.2f} dB")
        print(f"  P90 loss: {p90:.2f} dB")
        print(f"  P99 loss: {p99:.2f} dB")
        print(f"  Links with margin > 3dB (budget=25dB): {ok_count}/1000 = {ok_count/10:.0f}%")

        print("\n" + "=" * 70)
        print("ESTIMATION COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    estimator = SpliceLossEstimator()
    estimator.compare_all_methods()
