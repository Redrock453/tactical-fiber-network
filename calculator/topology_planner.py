#!/usr/bin/env python3
"""
TFN Topology Planner
=====================

Plans optimal fiber mesh topology based on:
- Node positions (GPS coordinates)
- Available fiber lengths from UAV drops
- Terrain considerations
- Redundancy requirements

Outputs deployment plan with specific instructions.
"""

import json
import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TacticalPosition:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: float = 0
    position_type: str = "trench"
    priority: int = 5
    has_power: bool = False

    def distance_to(self, other: "TacticalPosition") -> float:
        R = 6371000
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(self.lat)) * math.cos(math.radians(other.lat)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class FiberDrop:
    id: str
    from_node: str
    to_node: str
    fiber_length_m: float
    actual_distance_m: float
    slack_ratio: float = 1.15
    is_redundant: bool = False
    drone_type: str = "FPV"
    deployment_method: str = "uav"

    @property
    def usable_length_m(self) -> float:
        return self.fiber_length_m / self.slack_ratio


class TopologyPlanner:
    def __init__(self, max_fiber_length_km: float = 10.0,
                 min_redundancy: int = 1,
                 fiber_type: str = "G.657A2"):
        self.max_fiber_length_m = max_fiber_length_km * 1000
        self.min_redundancy = min_redundancy
        self.fiber_type = fiber_type
        self.positions: dict[str, TacticalPosition] = {}
        self.planned_drops: list[FiberDrop] = {}

    def add_position(self, pos: TacticalPosition):
        self.positions[pos.id] = pos

    def add_positions_from_recon(self, positions: list[dict]):
        for p in positions:
            self.add_position(TacticalPosition(**p))

    def compute_all_distances(self) -> dict[str, dict[str, float]]:
        dist = {}
        for id_a, pos_a in self.positions.items():
            dist[id_a] = {}
            for id_b, pos_b in self.positions.items():
                if id_a != id_b:
                    dist[id_a][id_b] = pos_a.distance_to(pos_b)
        return dist

    def plan_minimum_spanning_tree(self) -> list[FiberDrop]:
        if not self.positions:
            return []

        distances = self.compute_all_distances()
        nodes = list(self.positions.keys())
        in_tree = {nodes[0]}
        edges = []

        while len(in_tree) < len(nodes):
            best_edge = None
            best_dist = float("inf")
            for u in in_tree:
                for v in nodes:
                    if v not in in_tree and v in distances.get(u, {}):
                        d = distances[u][v]
                        if d < best_dist and d <= self.max_fiber_length_m:
                            best_dist = d
                            best_edge = (u, v, d)
            if best_edge is None:
                break
            u, v, d = best_edge
            in_tree.add(v)
            edges.append(FiberDrop(
                id=f"drop_{len(edges):03d}",
                from_node=u,
                to_node=v,
                fiber_length_m=d * 1.15,
                actual_distance_m=d,
            ))
        return edges

    def add_redundancy(self, mst_edges: list[FiberDrop]) -> list[FiberDrop]:
        distances = self.compute_all_distances()
        node_connectivity = {}
        for e in mst_edges:
            node_connectivity[e.from_node] = node_connectivity.get(e.from_node, 0) + 1
            node_connectivity[e.to_node] = node_connectivity.get(e.to_node, 0) + 1

        redundant = []
        nodes = list(self.positions.keys())

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                already_connected = any(
                    (e.from_node == u and e.to_node == v) or
                    (e.from_node == v and e.to_node == u)
                    for e in mst_edges + redundant
                )
                if not already_connected:
                    d = distances.get(u, {}).get(v, float("inf"))
                    if d <= self.max_fiber_length_m:
                        min_conn = min(
                            node_connectivity.get(u, 0),
                            node_connectivity.get(v, 0),
                        )
                        if min_conn < self.min_redundancy + 1:
                            drop = FiberDrop(
                                id=f"drop_red_{len(redundant):03d}",
                                from_node=u,
                                to_node=v,
                                fiber_length_m=d * 1.15,
                                actual_distance_m=d,
                                is_redundant=True,
                            )
                            redundant.append(drop)
                            node_connectivity[u] = node_connectivity.get(u, 0) + 1
                            node_connectivity[v] = node_connectivity.get(v, 0) + 1

        return mst_edges + redundant

    def generate_deployment_plan(self) -> dict:
        mst = self.plan_minimum_spanning_tree()
        all_drops = self.add_redundancy(mst)

        total_fiber_m = sum(d.fiber_length_m for d in all_drops)
        primary_drops = [d for d in all_drops if not d.is_redundant]
        redundant_drops = [d for d in all_drops if d.is_redundant]

        connectivity = {}
        for d in all_drops:
            connectivity[d.from_node] = connectivity.get(d.from_node, 0) + 1
            connectivity[d.to_node] = connectivity.get(d.to_node, 0) + 1

        drop_instructions = []
        for d in all_drops:
            pos_a = self.positions[d.from_node]
            pos_b = self.positions[d.to_node]
            drop_instructions.append({
                "drop_id": d.id,
                "from": {"id": d.from_node, "name": pos_a.name,
                         "coords": f"{pos_a.lat:.5f}, {pos_a.lon:.5f}"},
                "to": {"id": d.to_node, "name": pos_b.name,
                       "coords": f"{pos_b.lat:.5f}, {pos_b.lon:.5f}"},
                "fiber_needed_m": round(d.fiber_length_m, 0),
                "actual_distance_m": round(d.actual_distance_m, 0),
                "type": "redundant" if d.is_redundant else "primary",
                "splices_needed": max(1, int(d.fiber_length_m / 2000)),
                "status": "pending",
            })

        return {
            "topology": "mesh" if redundant_drops else "tree",
            "nodes": len(self.positions),
            "primary_links": len(primary_drops),
            "redundant_links": len(redundant_drops),
            "total_links": len(all_drops),
            "total_fiber_m": round(total_fiber_m, 0),
            "total_fiber_km": round(total_fiber_m / 1000, 1),
            "min_connectivity": min(connectivity.values()) if connectivity else 0,
            "max_connectivity": max(connectivity.values()) if connectivity else 0,
            "fiber_type": self.fiber_type,
            "max_single_link_m": round(max(d.fiber_length_m for d in all_drops), 0) if all_drops else 0,
            "deployment_instructions": drop_instructions,
            "equipment_needed": self._estimate_equipment(all_drops),
        }

    def _estimate_equipment(self, drops: list[FiberDrop]) -> dict:
        total_splices = sum(max(1, int(d.fiber_length_m / 2000)) for d in drops)
        return {
            "sfp_modules": len(self.positions) * 2,
            "media_converters": len(self.positions),
            "mechanical_splices": total_splices * 2,
            "quick_connectors": len(drops) * 2,
            "splice_cost_usd": total_splices * 2 * 10,
            "connector_cost_usd": len(drops) * 2 * 3,
            "sfp_cost_usd": len(self.positions) * 2 * 15,
            "total_cost_usd": (total_splices * 2 * 10 + len(drops) * 2 * 3 + len(self.positions) * 2 * 15),
        }


def demo_deployment():
    print("=" * 70)
    print("TFN TOPOLOGY PLANNER — DEMO DEPLOYMENT")
    print("=" * 70)

    planner = TopologyPlanner(max_fiber_length_km=8.0, min_redundancy=1)

    positions = [
        {"id": "cp", "name": "Command Post", "lat": 48.5120, "lon": 36.3400,
         "elevation_m": 180, "position_type": "bunker", "priority": 10, "has_power": True},
        {"id": "pos_1", "name": "Position Alpha", "lat": 48.5145, "lon": 36.3430,
         "elevation_m": 165, "position_type": "trench", "priority": 7},
        {"id": "pos_2", "name": "Position Bravo", "lat": 48.5160, "lon": 36.3480,
         "elevation_m": 155, "position_type": "trench", "priority": 7},
        {"id": "pos_3", "name": "Position Charlie", "lat": 48.5130, "lon": 36.3520,
         "elevation_m": 160, "position_type": "trench", "priority": 6},
        {"id": "obs_1", "name": "Observation Post 1", "lat": 48.5180, "lon": 36.3450,
         "elevation_m": 195, "position_type": "observation", "priority": 8},
        {"id": "relay_1", "name": "Relay Node", "lat": 48.5155, "lon": 36.3355,
         "elevation_m": 175, "position_type": "relay", "priority": 5},
        {"id": "rear_1", "name": "Rear Base", "lat": 48.5090, "lon": 36.3350,
         "elevation_m": 190, "position_type": "base", "priority": 9, "has_power": True},
    ]

    planner.add_positions_from_recon(positions)
    plan = planner.generate_deployment_plan()

    print(f"\nTopology: {plan['topology'].upper()}")
    print(f"Nodes: {plan['nodes']}")
    print(f"Links: {plan['primary_links']} primary + {plan['redundant_links']} redundant = {plan['total_links']} total")
    print(f"Total fiber: {plan['total_fiber_km']} km")
    print(f"Connectivity: {plan['min_connectivity']}-{plan['max_connectivity']} links/node")

    print(f"\n--- Deployment Instructions ---\n")
    for instr in plan["deployment_instructions"]:
        link_type = "↔" if instr["type"] == "primary" else "↔↔"
        print(f"  {link_type} {instr['from']['name']} → {instr['to']['name']}")
        print(f"     Distance: {instr['actual_distance_m']:.0f}m, Fiber: {instr['fiber_needed_m']:.0f}m")
        print(f"     Splices: {instr['splices_needed']}, Type: {instr['type']}")

    equip = plan["equipment_needed"]
    print(f"\n--- Equipment Summary ---")
    print(f"  SFP modules: {equip['sfp_modules']} (${equip['sfp_cost_usd']})")
    print(f"  Mechanical splices: {equip['mechanical_splices']} (${equip['splice_cost_usd']})")
    print(f"  Quick connectors: {equip['quick_connectors']} (${equip['connector_cost_usd']})")
    print(f"  TOTAL COST: ${equip['total_cost_usd']}")

    print(f"\n--- Full Plan (JSON) ---")
    print(json.dumps(plan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_deployment()
