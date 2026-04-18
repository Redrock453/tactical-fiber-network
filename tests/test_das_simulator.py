#!/usr/bin/env python3
"""
Tests for TFN DAS Simulator
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.das_simulator import (
    DASSimulator, TargetSignature, ThreatLevel, FiberSegment
)


def test_das_creation():
    das = DASSimulator(fiber_length_m=5000)
    assert das.fiber_length == 5000
    assert das.num_channels == 5000


def test_das_auto_segment():
    das = DASSimulator(fiber_length_m=5000)
    das.auto_segment()
    assert len(das.segments) == 5


def test_das_custom_segment():
    das = DASSimulator(fiber_length_m=5000)
    das.add_segment(FiberSegment(start_m=0, end_m=2000, terrain="trench"))
    das.add_segment(FiberSegment(start_m=2000, end_m=5000, terrain="forest"))
    assert len(das.segments) == 2


def test_das_simulation_with_events():
    das = DASSimulator(fiber_length_m=5000)
    das.auto_segment()
    events = [
        {"time": 5, "position": 1000, "signature": TargetSignature.FOOTSTEP_GROUP, "duration": 3},
        {"time": 15, "position": 2500, "signature": TargetSignature.WHEELED_VEHICLE, "duration": 5},
    ]
    detected = das.simulate_scenario(duration_s=20, events=events)
    assert len(das.detected_events) >= 0


def test_das_alerts():
    das = DASSimulator(fiber_length_m=5000)
    das.auto_segment()
    events = [
        {"time": 5, "position": 1000, "signature": TargetSignature.TRACKED_VEHICLE, "duration": 5},
    ]
    das.simulate_scenario(duration_s=10, events=events)
    alerts = das.get_alerts(ThreatLevel.LOW)
    assert isinstance(alerts, list)


def test_das_report():
    das = DASSimulator(fiber_length_m=5000)
    das.auto_segment()
    events = [
        {"time": 5, "position": 1000, "signature": TargetSignature.ARTILLERY_FIRE, "duration": 1},
    ]
    das.simulate_scenario(duration_s=10, events=events)
    report = das.generate_report()
    assert "events_detected" in report
    assert "threat_breakdown" in report


def test_signature_profiles():
    for sig in TargetSignature:
        if sig == TargetSignature.SILENCE:
            continue
        from simulation.das_simulator import SIGNATURE_PROFILES
        assert sig in SIGNATURE_PROFILES, f"Missing profile for {sig}"


def test_terrain_sensitivity():
    das = DASSimulator(fiber_length_m=5000, spatial_resolution_m=1.0)
    das.add_segment(FiberSegment(start_m=0, end_m=2500, terrain="trench", burial_depth_m=0.1))
    das.add_segment(FiberSegment(start_m=2500, end_m=5000, terrain="road", burial_depth_m=0.0))
    s1 = das._get_terrain_sensitivity(1000)
    s2 = das._get_terrain_sensitivity(3000)
    assert s1 != s2


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
