#!/usr/bin/env python3
"""
Tests for TFN Splice Loss Estimator
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator.splice_loss_estimator import (
    SpliceLossEstimator, SpliceMethod, CleaveQuality
)


def test_mechanical_splice_estimate():
    est = SpliceLossEstimator()
    result = est.estimate(SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD)
    assert result is not None
    assert result.typical_loss_db > 0
    assert result.field_viable


def test_fusion_splice_estimate():
    est = SpliceLossEstimator()
    result = est.estimate(SpliceMethod.FUSION, CleaveQuality.EXCELLENT)
    assert result is not None
    assert result.typical_loss_db < 0.1
    assert not result.field_viable


def test_link_estimation():
    est = SpliceLossEstimator()
    splices = [
        (SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD),
        (SpliceMethod.MECHANICAL_GEL, CleaveQuality.GOOD),
        (SpliceMethod.QUICK_CONNECTOR, CleaveQuality.AVERAGE),
    ]
    result = est.estimate_link(splices, fiber_length_km=5.0)
    assert result["total_loss_typical_db"] > 0
    assert result["total_loss_worst_db"] > result["total_loss_typical_db"]
    assert result["num_splices"] == 3


def test_recommendations():
    est = SpliceLossEstimator()
    recs = est.recommend_for_conditions(
        available_time_min=30, temperature_c=10, experience_level="basic", has_power=False
    )
    assert len(recs) > 0
    assert recs[0]["score"] > 0


def test_winter_recommendations():
    est = SpliceLossEstimator()
    recs = est.recommend_for_conditions(
        available_time_min=15, temperature_c=-15, has_power=False
    )
    for r in recs:
        assert r["method"] != "fusion"


def test_emergency_splice():
    est = SpliceLossEstimator()
    result = est.estimate(SpliceMethod.EMERGENCY_TAPE, CleaveQuality.AVERAGE)
    assert result is not None
    assert result.typical_loss_db > 1.0
    assert result.time_seconds < 30


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
