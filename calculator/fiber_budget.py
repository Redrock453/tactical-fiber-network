#!/usr/bin/env python3
"""
TFN Optical Budget Calculator
===============================

Calculates the optical power budget for fiber links,
including all loss sources: fiber attenuation, splices,
connectors, bends, and margins.

Supports:
- Single-mode fiber (G.652, G.657)
- Multiple splice types (fusion, mechanical, field)
- Quick connectors
- Bend losses
- Environmental degradation margin
"""

import json
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class SFPModule:
    name: str
    wavelength_nm: int
    tx_power_dbm: float
    rx_sensitivity_dbm: float
    max_distance_km: float
    cost_usd: float

    @property
    def budget_db(self) -> float:
        return self.tx_power_dbm - self.rx_sensitivity_dbm


COMMON_SFP = {
    "GLC-LH-SM-40": SFPModule("Cisco GLC-LH-SM", 1310, -3.0, -28.0, 40, 35),
    "SFP-10G-LR": SFPModule("10G LR", 1310, -6.0, -20.0, 10, 25),
    "SFP-10G-ER": SFPModule("10G ER", 1550, -1.0, -22.0, 40, 60),
    "SFP-10G-ZR": SFPModule("10G ZR", 1550, 0.0, -24.0, 80, 120),
    "SFP-1G-LX": SFPModule("1G LX", 1310, -9.0, -22.0, 10, 10),
    "SFP-1G-LH": SFPModule("1G LH", 1550, -3.0, -28.0, 40, 30),
    "SFP-1G-EX": SFPModule("1G EX", 1550, -3.0, -32.0, 40, 45),
    "generic_1310_20km": SFPModule("Generic 1310nm 20km", 1310, -5.0, -25.0, 20, 8),
    "generic_1550_40km": SFPModule("Generic 1550nm 40km", 1550, -2.0, -28.0, 40, 15),
}

SPLICE_TYPES = {
    "fusion": {"loss_db": 0.05, "name": "Fusion splice", "time_min": 5, "cost_usd": 0},
    "mechanical_good": {"loss_db": 0.1, "name": "Mechanical splice (good cleave)", "time_sec": 30, "cost_usd": 10},
    "mechanical_avg": {"loss_db": 0.2, "name": "Mechanical splice (average)", "time_sec": 30, "cost_usd": 8},
    "mechanical_bad": {"loss_db": 0.5, "name": "Mechanical splice (bad cleave)", "time_sec": 30, "cost_usd": 8},
    "quick_connector": {"loss_db": 0.3, "name": "Quick connector (SC/FC)", "time_sec": 60, "cost_usd": 3},
    "field_emergency": {"loss_db": 1.0, "name": "Emergency field splice (tape)", "time_sec": 30, "cost_usd": 0},
}

CONNECTOR_TYPES = {
    "SC_UPC": {"loss_db": 0.25, "name": "SC/UPC"},
    "SC_APC": {"loss_db": 0.15, "name": "SC/APC"},
    "FC_UPC": {"loss_db": 0.3, "name": "FC/UPC"},
    "LC_UPC": {"loss_db": 0.15, "name": "LC/UPC"},
}

FIBER_TYPES = {
    "G.652D": {"attenuation_1310": 0.35, "attenuation_1550": 0.22, "name": "Standard SMF"},
    "G.657A1": {"attenuation_1310": 0.35, "attenuation_1550": 0.22, "name": "Bend-insensitive"},
    "G.657A2": {"attenuation_1310": 0.35, "attenuation_1550": 0.22, "name": "Bend-insensitive (enhanced)"},
    "drone_spent": {"attenuation_1310": 0.50, "attenuation_1550": 0.40, "name": "Spent FPV drone fiber (degraded)"},
}


@dataclass
class LinkComponent:
    name: str
    loss_db: float
    count: int
    cost_usd: float = 0.0
    notes: str = ""

    @property
    def total_loss(self) -> float:
        return self.loss_db * self.count

    @property
    def total_cost(self) -> float:
        return self.cost_usd * self.count


class FiberBudgetCalculator:
    def __init__(self, sfp: Optional[SFPModule] = None,
                 fiber_type: str = "G.657A2",
                 link_length_km: float = 5.0):
        self.sfp = sfp or COMMON_SFP["generic_1310_20km"]
        self.fiber_type = fiber_type
        self.link_length_km = link_length_km
        self.components: list[LinkComponent] = []
        self.environment_margin_db = 3.0
        self.safety_margin_db = 3.0

    def add_fiber(self, length_km: Optional[float] = None):
        length = length_km or self.link_length_km
        fiber = FIBER_TYPES[self.fiber_type]
        wavelength = self.sfp.wavelength_nm
        if wavelength == 1310:
            atten = fiber["attenuation_1310"]
        else:
            atten = fiber["attenuation_1550"]
        self.components.append(LinkComponent(
            name=f"Fiber ({fiber['name']})",
            loss_db=round(atten * length, 2),
            count=1,
            notes=f"{atten} dB/km × {length} km, λ={wavelength}nm",
        ))

    def add_splice(self, splice_type: str, count: int = 1):
        info = SPLICE_TYPES[splice_type]
        self.components.append(LinkComponent(
            name=info["name"],
            loss_db=info["loss_db"],
            count=count,
            cost_usd=info.get("cost_usd", 0),
            notes=f"{info['loss_db']} dB × {count}",
        ))

    def add_connector(self, connector_type: str, count: int = 2):
        info = CONNECTOR_TYPES[connector_type]
        self.components.append(LinkComponent(
            name=info["name"],
            loss_db=info["loss_db"],
            count=count,
            notes=f"{info['loss_db']} dB × {count}",
        ))

    def add_bend_loss(self, num_bends: int = 5, loss_per_bend_db: float = 0.1):
        self.components.append(LinkComponent(
            name="Bend losses",
            loss_db=loss_per_bend_db,
            count=num_bends,
            notes=f"~{num_bends} bends × {loss_per_bend_db} dB",
        ))

    def add_environment_degradation(self, extra_loss_db: float = 0.5):
        self.components.append(LinkComponent(
            name="Environmental degradation",
            loss_db=extra_loss_db,
            count=1,
            notes="Dirt, moisture, micro-cracks in spent fiber",
        ))

    def calculate(self) -> dict:
        total_loss = sum(c.total_loss for c in self.components)
        budget = self.sfp.budget_db
        margin = budget - total_loss - self.safety_margin_db
        rx_power = self.sfp.tx_power_dbm - total_loss
        feasible = rx_power >= self.sfp.rx_sensitivity_dbm + self.environment_margin_db

        return {
            "sfp": {
                "name": self.sfp.name,
                "wavelength_nm": self.sfp.wavelength_nm,
                "tx_power_dbm": self.sfp.tx_power_dbm,
                "rx_sensitivity_dbm": self.sfp.rx_sensitivity_dbm,
                "budget_db": budget,
            },
            "link_length_km": self.link_length_km,
            "fiber_type": self.fiber_type,
            "components": [
                {
                    "name": c.name,
                    "loss_db": c.loss_db,
                    "count": c.count,
                    "total_loss_db": round(c.total_loss, 3),
                    "notes": c.notes,
                }
                for c in self.components
            ],
            "total_loss_db": round(total_loss, 3),
            "rx_power_dbm": round(rx_power, 2),
            "margin_db": round(margin, 2),
            "safety_margin_db": self.safety_margin_db,
            "feasible": feasible,
            "status": "OK" if feasible else ("MARGINAL" if margin >= 0 else "UNUSABLE"),
            "max_distance_estimate_km": round(self._estimate_max_distance(budget - self.safety_margin_db), 1),
            "cost_usd": round(sum(c.total_cost for c in self.components) + self.sfp.cost_usd * 2, 2),
        }

    def _estimate_max_distance(self, available_budget: float) -> float:
        non_fiber_loss = sum(
            c.total_loss for c in self.components
            if "Fiber" not in c.name
        )
        fiber_budget = available_budget - non_fiber_loss
        if fiber_budget <= 0:
            return 0.0
        fiber = FIBER_TYPES[self.fiber_type]
        wavelength = self.sfp.wavelength_nm
        atten = fiber["attenuation_1310" if wavelength == 1310 else "attenuation_1550"]
        return fiber_budget / atten


def compare_scenarios():
    print("=" * 70)
    print("TFN OPTICAL BUDGET CALCULATOR — SCENARIO COMPARISON")
    print("=" * 70)

    scenarios = [
        ("Ideal 5km (fusion splices)", "G.657A2", 5.0, "fusion", 2, "SC_UPC"),
        ("Field 5km (mechanical splices)", "G.657A2", 5.0, "mechanical_good", 3, "SC_UPC"),
        ("Spent fiber 3km (field conditions)", "drone_spent", 3.0, "mechanical_avg", 4, "quick_connector"),
        ("Long range 10km (field)", "G.657A2", 10.0, "mechanical_good", 5, "SC_UPC"),
        ("Emergency 2km (tape splice)", "drone_spent", 2.0, "field_emergency", 3, "quick_connector"),
        ("Spent fiber 5km (degraded)", "drone_spent", 5.0, "mechanical_avg", 3, "SC_UPC"),
    ]

    results = []
    for name, fiber, length, splice, splice_count, conn in scenarios:
        calc = FiberBudgetCalculator(
            sfp=COMMON_SFP["generic_1310_20km"],
            fiber_type=fiber,
            link_length_km=length,
        )
        calc.add_fiber()
        calc.add_splice(splice, splice_count)
        calc.add_connector(conn, 2)
        calc.add_bend_loss(num_bends=max(2, int(length * 2)))
        calc.add_environment_degradation(0.5 if fiber == "drone_spent" else 0.3)

        result = calc.calculate()
        result["scenario"] = name
        results.append(result)

    print(f"\n{'Scenario':<40} {'Length':>6} {'Loss':>6} {'Margin':>7} {'RX':>7} {'Status':>8}")
    print("-" * 80)
    for r in results:
        print(f"{r['scenario']:<40} {r['link_length_km']:>5.1f}km "
              f"{r['total_loss_db']:>5.1f}dB "
              f"{r['margin_db']:>6.1f}dB "
              f"{r['rx_power_dbm']:>6.1f}dBm "
              f"{r['status']:>8}")

    print(f"\n--- Detailed: Field 5km scenario ---\n")
    field_calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["generic_1310_20km"],
        fiber_type="G.657A2",
        link_length_km=5.0,
    )
    field_calc.add_fiber()
    field_calc.add_splice("mechanical_good", 3)
    field_calc.add_connector("SC_UPC", 2)
    field_calc.add_bend_loss(10, 0.1)
    field_calc.add_environment_degradation(0.3)

    detail = field_calc.calculate()
    print(json.dumps(detail, indent=2))

    print(f"\n--- Max Distance Estimates ---\n")
    for sfp_name, sfp in COMMON_SFP.items():
        calc = FiberBudgetCalculator(sfp=sfp, fiber_type="G.657A2", link_length_km=1.0)
        calc.add_fiber()
        calc.add_splice("mechanical_good", 3)
        calc.add_connector("SC_UPC", 2)
        calc.add_bend_loss(10)
        calc.add_environment_degradation(0.3)
        result = calc.calculate()
        print(f"  {sfp_name:<25} budget={sfp.budget_db:.0f}dB  "
              f"max_dist={result['max_distance_estimate_km']:.1f}km  "
              f"cost=${result['cost_usd']:.0f}")


if __name__ == "__main__":
    compare_scenarios()
