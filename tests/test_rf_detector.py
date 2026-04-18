#!/usr/bin/env python3
"""
Tests for TFN RF Detector
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.rf_detector import RFDetectorSimulator, RFSource, RFSourceType


def test_rf_creation():
    det = RFDetectorSimulator(fiber_length_m=5000)
    assert det.fiber_length == 5000


def test_rf_ew_detection():
    det = RFDetectorSimulator(fiber_length_m=5000)
    source = RFSource(RFSourceType.EW_STATION, 2.4e9, 1000, 5, 1500)
    result = det.detect_source(source)
    assert result.detected
    assert result.phase_shift_rad > 0
    assert result.confidence > 0


def test_rf_weak_source():
    det = RFDetectorSimulator(fiber_length_m=5000)
    source = RFSource(RFSourceType.FPV_VIDEO, 5.8e9, 0.025, 50, 1000)
    result = det.detect_source(source)
    assert isinstance(result.detected, bool)


def test_rf_radar_detection():
    det = RFDetectorSimulator(fiber_length_m=5000)
    source = RFSource(RFSourceType.RADAR, 10e9, 10000, 10, 2000)
    result = det.detect_source(source)
    assert result.phase_shift_rad > 0


def test_rf_sweep():
    det = RFDetectorSimulator(fiber_length_m=5000)
    sources = [
        RFSource(RFSourceType.EW_STATION, 2.4e9, 1000, 10, 1000),
        RFSource(RFSourceType.FPV_CONTROL, 2.4e9, 0.5, 5, 2000),
    ]
    results = det.run_detection_sweep(sources)
    assert len(results) == 2


def test_rf_report():
    det = RFDetectorSimulator(fiber_length_m=5000)
    sources = det.generate_random_sources(5)
    det.run_detection_sweep(sources)
    report = det.generate_report()
    assert "total_sources_scanned" in report
    assert "detection_rate" in report


def test_electric_field_calculation():
    det = RFDetectorSimulator(fiber_length_m=5000)
    e = det._electric_field_at_fiber(1000, 10)
    assert e > 0


def test_kerr_phase_shift():
    det = RFDetectorSimulator(fiber_length_m=5000)
    e = det._electric_field_at_fiber(1000, 5)
    ps = det._kerr_phase_shift(e, 10)
    assert ps > 0


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
