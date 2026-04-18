#!/usr/bin/env python3
"""
Tests for TFN Fiber Budget Calculator
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator.fiber_budget import (
    FiberBudgetCalculator, COMMON_SFP, FIBER_TYPES, SPLICE_TYPES
)


def test_sfp_budget():
    sfp = COMMON_SFP["generic_1310_20km"]
    assert sfp.budget_db == sfp.tx_power_dbm - sfp.rx_sensitivity_dbm


def test_simple_link():
    calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["generic_1310_20km"],
        fiber_type="G.657A2",
        link_length_km=5.0,
    )
    calc.add_fiber()
    calc.add_splice("mechanical_good", 2)
    calc.add_connector("SC_UPC", 2)
    result = calc.calculate()
    assert result["feasible"]
    assert result["total_loss_db"] > 0
    assert result["rx_power_dbm"] > -28


def test_long_link():
    calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["generic_1310_20km"],
        fiber_type="drone_spent",
        link_length_km=20.0,
    )
    calc.add_fiber()
    calc.add_splice("mechanical_avg", 5)
    calc.add_connector("SC_UPC", 2)
    calc.add_bend_loss(20)
    calc.add_environment_degradation(1.0)
    result = calc.calculate()
    assert result["total_loss_db"] > 5


def test_max_distance():
    calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["SFP-10G-ZR"],
        fiber_type="G.657A2",
        link_length_km=1.0,
    )
    calc.add_fiber()
    calc.add_splice("fusion", 2)
    calc.add_connector("LC_UPC", 2)
    result = calc.calculate()
    assert result["max_distance_estimate_km"] > 20


def test_emergency_link():
    calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["generic_1310_20km"],
        fiber_type="drone_spent",
        link_length_km=5.0,
    )
    calc.add_fiber()
    calc.add_splice("field_emergency", 3)
    calc.add_connector("SC_UPC", 2)
    result = calc.calculate()
    assert result["total_loss_db"] > 5


def test_all_fiber_types():
    for ftype in FIBER_TYPES:
        calc = FiberBudgetCalculator(fiber_type=ftype, link_length_km=5.0)
        calc.add_fiber()
        result = calc.calculate()
        assert result["total_loss_db"] > 0, f"Failed for {ftype}"


def test_all_sfp_modules():
    for name, sfp in COMMON_SFP.items():
        assert sfp.budget_db > 0, f"Invalid budget for {name}"


def test_cost_calculation():
    calc = FiberBudgetCalculator(
        sfp=COMMON_SFP["generic_1310_20km"],
        link_length_km=5.0,
    )
    calc.add_fiber()
    calc.add_splice("mechanical_good", 3)
    result = calc.calculate()
    assert result["cost_usd"] > 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} tests...")
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
