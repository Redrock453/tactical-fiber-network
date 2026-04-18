#!/usr/bin/env python3
"""
Tests for TFN Topology Planner
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator.topology_planner import TopologyPlanner, TacticalPosition


def test_add_position():
    planner = TopologyPlanner()
    planner.add_position(TacticalPosition(id="a", name="Test", lat=48.5, lon=36.3))
    assert len(planner.positions) == 1


def test_mst_single():
    planner = TopologyPlanner()
    planner.add_position(TacticalPosition(id="a", name="A", lat=48.50, lon=36.30))
    planner.add_position(TacticalPosition(id="b", name="B", lat=48.51, lon=36.31))
    mst = planner.plan_minimum_spanning_tree()
    assert len(mst) == 1


def test_mst_triangle():
    planner = TopologyPlanner(max_fiber_length_km=10.0)
    planner.add_position(TacticalPosition(id="a", name="A", lat=48.50, lon=36.30))
    planner.add_position(TacticalPosition(id="b", name="B", lat=48.51, lon=36.31))
    planner.add_position(TacticalPosition(id="c", name="C", lat=48.52, lon=36.30))
    mst = planner.plan_minimum_spanning_tree()
    assert len(mst) == 2


def test_deployment_plan():
    planner = TopologyPlanner()
    positions = [
        TacticalPosition(id="a", name="A", lat=48.50, lon=36.30, priority=5),
        TacticalPosition(id="b", name="B", lat=48.51, lon=36.31, priority=7),
        TacticalPosition(id="c", name="C", lat=48.52, lon=36.32, priority=5),
        TacticalPosition(id="d", name="D", lat=48.53, lon=36.30, priority=8),
    ]
    for p in positions:
        planner.add_position(p)
    plan = planner.generate_deployment_plan()
    assert plan["nodes"] == 4
    assert plan["total_links"] >= 3
    assert "deployment_instructions" in plan
    assert "equipment_needed" in plan


def test_distance_calculation():
    pos_a = TacticalPosition(id="a", name="A", lat=48.5, lon=36.3)
    pos_b = TacticalPosition(id="b", name="B", lat=48.5, lon=36.301)
    dist = pos_a.distance_to(pos_b)
    assert 50 < dist < 200


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
