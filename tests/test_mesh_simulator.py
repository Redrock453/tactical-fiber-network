#!/usr/bin/env python3
"""
Tests for TFN Mesh Simulator
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.mesh_simulator import (
    MeshSimulator, MeshNode, FiberLink, GeoCoord,
    NodeType, LinkState
)


def test_geo_distance():
    a = GeoCoord(lat=48.5, lon=36.3)
    b = GeoCoord(lat=48.51, lon=36.31)
    dist = a.distance_to(b)
    assert 1000 < dist < 2000, f"Expected ~1.3km, got {dist}"


def test_fiber_link_loss():
    link = FiberLink(
        id="test", node_a="a", node_b="b",
        length_m=5000, attenuation_db_km=0.35,
        splice_count=2, connector_loss_db=0.5,
    )
    assert link.total_loss_db > 0
    assert link.is_usable


def test_fiber_link_broken():
    link = FiberLink(
        id="test", node_a="a", node_b="b",
        length_m=5000, state=LinkState.BROKEN,
    )
    assert link.total_loss_db == float("inf")
    assert not link.is_usable


def test_mesh_deploy():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=5, area_km=2.0)
    assert len(sim.nodes) == 5
    assert len(sim.links) > 0


def test_mesh_routing():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=5, area_km=2.0)
    routes = sim.compute_routing()
    assert len(routes) > 0


def test_mesh_status():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=5, area_km=2.0)
    status = sim.get_network_status()
    assert status["nodes_total"] == 5
    assert status["connectivity_pct"] > 0


def test_link_feasibility():
    sim = MeshSimulator()
    n1 = MeshNode(id="a", node_type=NodeType.TRENCH, position=GeoCoord(48.5, 36.3))
    n2 = MeshNode(id="b", node_type=NodeType.TRENCH, position=GeoCoord(48.51, 36.31))
    sim.add_node(n1)
    sim.add_node(n2)
    link = FiberLink(id="l1", node_a="a", node_b="b", length_m=1500)
    sim.add_link(link)
    check = sim.check_link_feasibility(link)
    assert "feasible" in check


def test_artillery_damage():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=6, area_km=2.0, base_lat=48.5, base_lon=36.3)
    initial_active = sum(1 for l in sim.links.values() if l.state == LinkState.ACTIVE)
    node = list(sim.nodes.values())[0]
    sim.simulate_artillery_damage(
        node.position.lat, node.position.lon, blast_radius_m=200
    )
    after_active = sum(1 for l in sim.links.values() if l.state == LinkState.ACTIVE)
    assert after_active <= initial_active


def test_battery_drain():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=3, area_km=1.0)
    node = list(sim.nodes.values())[0]
    initial_battery = node.battery_current_wh
    sim.simulate_time_step(10.0)
    assert node.battery_current_wh < initial_battery


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
