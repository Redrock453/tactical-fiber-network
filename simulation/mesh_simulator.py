#!/usr/bin/env python3
"""
TFN Mesh Network Simulator
===========================

Simulates a tactical fiber mesh network with:
- Node deployment via UAV fiber drops
- Dynamic routing (B.A.T.M.A.N.-like)
- Link failure recovery
- Traffic simulation
- DAS event injection along fiber paths
"""

import json
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LinkState(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    BROKEN = "broken"


class NodeType(Enum):
    TRENCH = "trench"
    RELAY = "relay"
    BASE_STATION = "base_station"
    DAS_INTERROGATOR = "das_interrogator"


@dataclass
class GeoCoord:
    lat: float
    lon: float

    def distance_to(self, other: "GeoCoord") -> float:
        R = 6371000
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(self.lat)) * math.cos(math.radians(other.lat)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class FiberLink:
    id: str
    node_a: str
    node_b: str
    length_m: float
    attenuation_db_km: float = 0.35
    splice_count: int = 0
    splice_loss_db: float = 0.1
    connector_loss_db: float = 0.5
    state: LinkState = LinkState.ACTIVE
    fiber_type: str = "G.657.A2"
    wavelength_nm: int = 1550
    has_das: bool = False
    break_position_m: Optional[float] = None

    @property
    def total_loss_db(self) -> float:
        if self.state == LinkState.BROKEN:
            return float("inf")
        fiber_loss = (self.length_m / 1000) * self.attenuation_db_km
        splice_loss = self.splice_count * self.splice_loss_db
        connector_loss = self.connector_loss_db * 2
        total = fiber_loss + splice_loss + connector_loss
        if self.state == LinkState.DEGRADED:
            total += random.uniform(3, 10)
        return round(total, 2)

    @property
    def is_usable(self) -> bool:
        return self.state != LinkState.BROKEN


@dataclass
class MeshNode:
    id: str
    node_type: NodeType
    position: GeoCoord
    tx_power_dbm: float = -3.0
    rx_sensitivity_dbm: float = -28.0
    sfp_wavelength: int = 1550
    sfp_max_distance_km: float = 20.0
    battery_capacity_wh: float = 100.0
    battery_current_wh: float = 100.0
    power_consumption_w: float = 5.0
    is_alive: bool = True
    routing_table: dict = field(default_factory=dict)

    @property
    def battery_hours(self) -> float:
        if self.power_consumption_w <= 0:
            return float("inf")
        return self.battery_current_wh / self.power_consumption_w

    @property
    def optical_budget_db(self) -> float:
        return self.tx_power_dbm - self.rx_sensitivity_dbm


class MeshSimulator:
    def __init__(self):
        self.nodes: dict[str, MeshNode] = {}
        self.links: dict[str, FiberLink] = {}
        self.events: list[dict] = []
        self.simulation_time: float = 0.0

    def add_node(self, node: MeshNode):
        self.nodes[node.id] = node

    def add_link(self, link: FiberLink):
        self.links[link.id] = link

    def deploy_random_mesh(self, num_nodes: int = 6, area_km: float = 5.0,
                           base_lat: float = 48.0, base_lon: float = 37.0):
        node_types = [NodeType.TRENCH] * (num_nodes - 2) + [NodeType.BASE_STATION, NodeType.DAS_INTERROGATOR]
        random.shuffle(node_types)

        for i in range(num_nodes):
            lat = base_lat + random.uniform(-area_km / 111, area_km / 111)
            lon = base_lon + random.uniform(-area_km / 80, area_km / 80)
            ntype = node_types[i]
            node = MeshNode(
                id=f"node_{i:03d}",
                node_type=ntype,
                position=GeoCoord(lat=lat, lon=lon),
                battery_capacity_wh=random.uniform(50, 200),
                battery_current_wh=random.uniform(40, 200),
                power_consumption_w=random.uniform(3, 10),
            )
            self.add_node(node)

        node_ids = list(self.nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                dist = self.nodes[node_ids[i]].position.distance_to(self.nodes[node_ids[j]].position)
                if dist < area_km * 1000 * 0.8 or random.random() < 0.3:
                    link_id = f"link_{node_ids[i]}_{node_ids[j]}"
                    link = FiberLink(
                        id=link_id,
                        node_a=node_ids[i],
                        node_b=node_ids[j],
                        length_m=dist,
                        splice_count=max(1, int(dist / 2000)),
                        has_das=random.random() < 0.4,
                    )
                    self.add_link(link)

    def check_link_feasibility(self, link: FiberLink) -> dict:
        if link.node_a not in self.nodes or link.node_b not in self.nodes:
            return {"feasible": False, "reason": "nodes not found"}

        node_a = self.nodes[link.node_a]
        node_b = self.nodes[link.node_b]
        total_loss = link.total_loss_db
        budget = min(node_a.optical_budget_db, node_b.optical_budget_db)
        margin = budget - total_loss

        return {
            "link_id": link.id,
            "feasible": margin >= 3.0,
            "total_loss_db": total_loss,
            "budget_db": budget,
            "margin_db": round(margin, 2),
            "rx_power_dbm": round(node_a.tx_power_dbm - total_loss, 2),
            "length_km": round(link.length_m / 1000, 2),
            "recommendation": "OK" if margin >= 3.0 else (
                "ADD AMPLIFIER" if margin >= 0 else "UNUSABLE"
            ),
        }

    def simulate_artillery_damage(self, impact_lat: float, impact_lon: float,
                                  blast_radius_m: float = 50.0):
        impact_pos = GeoCoord(lat=impact_lat, lon=impact_lon)
        damaged_links = []
        for link_id, link in self.links.items():
            if link.state == LinkState.BROKEN:
                continue
            node_a = self.nodes[link.node_a]
            node_b = self.nodes[link.node_b]
            for frac in [0.25, 0.5, 0.75]:
                point_lat = node_a.position.lat + frac * (node_b.position.lat - node_a.position.lat)
                point_lon = node_a.position.lon + frac * (node_b.position.lon - node_a.position.lon)
                point = GeoCoord(lat=point_lat, lon=point_lon)
                dist = point.distance_to(impact_pos)
                if dist < blast_radius_m:
                    link.state = LinkState.BROKEN
                    link.break_position_m = link.length_m * frac
                    damaged_links.append({
                        "link_id": link_id,
                        "break_position_m": round(link.break_position_m, 1),
                        "distance_to_impact_m": round(dist, 1),
                    })
                    break

        event = {
            "timestamp": self.simulation_time,
            "type": "artillery_impact",
            "position": {"lat": impact_lat, "lon": impact_lon},
            "blast_radius_m": blast_radius_m,
            "links_damaged": len(damaged_links),
            "details": damaged_links,
        }
        self.events.append(event)
        return event

    def compute_routing(self) -> dict:
        alive_nodes = {nid: n for nid, n in self.nodes.items() if n.is_alive}
        active_links = {lid: l for lid, l in self.links.items() if l.is_usable}

        adj = {nid: {} for nid in alive_nodes}
        for link in active_links.values():
            if link.node_a in alive_nodes and link.node_b in alive_nodes:
                cost = link.total_loss_db + link.length_m * 0.001
                adj[link.node_a][link.node_b] = cost
                adj[link.node_b][link.node_a] = cost

        paths = {}
        for src in alive_nodes:
            dist = {n: float("inf") for n in alive_nodes}
            prev = {n: None for n in alive_nodes}
            dist[src] = 0.0
            visited = set()
            while len(visited) < len(alive_nodes):
                u = min((n for n in alive_nodes if n not in visited), key=lambda n: dist[n], default=None)
                if u is None or dist[u] == float("inf"):
                    break
                visited.add(u)
                for v, w in adj[u].items():
                    new_dist = dist[u] + w
                    if new_dist < dist[v]:
                        dist[v] = new_dist
                        prev[v] = u

            for dst in alive_nodes:
                if dst == src:
                    continue
                path = []
                cur = dst
                while cur is not None:
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
                if len(path) > 1 and path[0] == src:
                    paths[f"{src}->{dst}"] = {
                        "path": path,
                        "hops": len(path) - 1,
                        "total_cost": round(dist[dst], 2),
                    }
            self.nodes[src].routing_table = paths

        return paths

    def get_network_status(self) -> dict:
        total_links = len(self.links)
        active_links = sum(1 for l in self.links.values() if l.state == LinkState.ACTIVE)
        broken_links = sum(1 for l in self.links.values() if l.state == LinkState.BROKEN)
        degraded_links = sum(1 for l in self.links.values() if l.state == LinkState.DEGRADED)
        alive_nodes = sum(1 for n in self.nodes.values() if n.is_alive)

        connectivity = 0.0
        if total_links > 0:
            connectivity = (active_links / total_links) * 100

        avg_battery = 0.0
        if alive_nodes > 0:
            avg_battery = sum(n.battery_hours for n in self.nodes.values() if n.is_alive) / alive_nodes

        return {
            "simulation_time_s": self.simulation_time,
            "nodes_total": len(self.nodes),
            "nodes_alive": alive_nodes,
            "links_total": total_links,
            "links_active": active_links,
            "links_broken": broken_links,
            "links_degraded": degraded_links,
            "connectivity_pct": round(connectivity, 1),
            "avg_battery_hours": round(avg_battery, 1),
            "total_events": len(self.events),
            "mesh_healthy": connectivity >= 60 and alive_nodes >= len(self.nodes) * 0.5,
        }

    def simulate_time_step(self, dt_hours: float = 1.0):
        self.simulation_time += dt_hours * 3600
        for node in self.nodes.values():
            if node.is_alive:
                node.battery_current_wh -= node.power_consumption_w * dt_hours
                if node.battery_current_wh <= 0:
                    node.battery_current_wh = 0
                    node.is_alive = False
                    self.events.append({
                        "timestamp": self.simulation_time,
                        "type": "node_died",
                        "node_id": node.id,
                        "reason": "battery_depleted",
                    })

        for link in self.links.values():
            if link.state == LinkState.ACTIVE and random.random() < 0.002 * dt_hours:
                link.state = LinkState.DEGRADED
                self.events.append({
                    "timestamp": self.simulation_time,
                    "type": "link_degraded",
                    "link_id": link.id,
                    "reason": "environmental_stress",
                })


def run_simulation():
    sim = MeshSimulator()
    sim.deploy_random_mesh(num_nodes=8, area_km=3.0, base_lat=48.5, base_lon=36.3)

    print("=" * 60)
    print("TFN MESH NETWORK SIMULATOR")
    print("=" * 60)

    status = sim.get_network_status()
    print(f"\nDeployed: {status['nodes_total']} nodes, {status['links_total']} links")
    print(f"Connectivity: {status['connectivity_pct']}%")

    print("\n--- Link Feasibility Analysis ---")
    for lid, link in sim.links.items():
        check = sim.check_link_feasibility(link)
        marker = "OK" if check["feasible"] else "FAIL"
        print(f"  {lid}: {check['length_km']}km, loss={check['total_loss_db']}dB, "
              f"margin={check['margin_db']}dB [{marker}]")

    print("\n--- Routing Table Computation ---")
    routes = sim.compute_routing()
    for key, route in list(routes.items())[:10]:
        print(f"  {key}: {' -> '.join(route['path'])} ({route['hops']} hops)")

    print("\n--- Simulating Artillery Strike ---")
    node_list = list(sim.nodes.values())
    target = random.choice(node_list)
    impact = sim.simulate_artillery_damage(
        target.position.lat + random.uniform(-0.005, 0.005),
        target.position.lon + random.uniform(-0.005, 0.005),
        blast_radius_m=80,
    )
    print(f"  Impact near {target.id}: {impact['links_damaged']} links damaged")

    status_after = sim.get_network_status()
    print(f"\n--- Post-Strike Status ---")
    print(f"  Connectivity: {status_after['connectivity_pct']}%")
    print(f"  Active links: {status_after['links_active']}/{status_after['links_total']}")
    print(f"  Mesh healthy: {status_after['mesh_healthy']}")

    print("\n--- Recomputing Routes ---")
    routes_after = sim.compute_routing()
    rerouted = sum(1 for r in routes_after.values() if r["hops"] > 1)
    print(f"  Active routes: {len(routes_after)}, multi-hop: {rerouted}")

    print("\n--- 24h Battery Simulation ---")
    for h in range(24):
        sim.simulate_time_step(dt_hours=1.0)
    final = sim.get_network_status()
    print(f"  Alive nodes: {final['nodes_alive']}/{final['nodes_total']}")
    print(f"  Avg battery: {final['avg_battery_hours']}h remaining")

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)

    return {
        "initial_status": status,
        "post_strike_status": status_after,
        "final_status": final,
        "events": len(sim.events),
    }


if __name__ == "__main__":
    result = run_simulation()
    print(f"\nTotal events logged: {result['events']}")
