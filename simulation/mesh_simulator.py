#!/usr/bin/env python3
"""
TFN Mesh Network Simulator
===========================

Simulates a tactical fiber mesh network with:
- Node deployment via UAV fiber drops
- Dynamic routing (B.A.T.M.A.N.-like) with OSPF-like rerouting
- Realistic artillery damage model with probabilistic P_break
- Battery/power model with solar recharge and degradation
- Link failure recovery with alternative paths
- Traffic simulation
- DAS event injection along fiber paths
- Network health scoring and graceful degradation timeline
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


class ArtilleryCaliber(Enum):
    MORTAR_82mm = 15
    HOWITZER_152mm = 30
    MLRS = 50

    @property
    def characteristic_radius_m(self) -> float:
        return float(self.value)


class PowerState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    DEGRADED = "degraded"


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
    burial_depth_cm: float = 30.0

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
    power_state: PowerState = PowerState.ACTIVE
    solar_panel_w: float = 0.0
    charge_cycles: int = 0
    last_traffic_time: float = 0.0
    _total_charged_wh: float = field(default=0.0, repr=False)
    _battery_critical_alerted: bool = field(default=False, repr=False)

    @property
    def battery_hours(self) -> float:
        effective_power = self._effective_power_consumption()
        if effective_power <= 0:
            return float("inf")
        return self.battery_current_wh / effective_power

    @property
    def optical_budget_db(self) -> float:
        return self.tx_power_dbm - self.rx_sensitivity_dbm

    @property
    def effective_capacity_wh(self) -> float:
        return self.battery_capacity_wh * max(0.0, 1.0 - 0.001 * self.charge_cycles)

    def _effective_power_consumption(self) -> float:
        if self.power_state == PowerState.IDLE:
            return 2.0
        elif self.power_state == PowerState.DEGRADED:
            return 3.0
        return self.power_consumption_w

    def get_power_status(self) -> dict:
        effective_power = self._effective_power_consumption()
        hours_remaining = (
            self.battery_current_wh / effective_power if effective_power > 0 else float("inf")
        )
        capacity = self.effective_capacity_wh
        battery_pct = min(100.0, self.battery_current_wh / capacity * 100) if capacity > 0 else 0
        solar_prod = _compute_solar_production(self.solar_panel_w, None)
        is_charging = solar_prod > effective_power and self.solar_panel_w > 0

        return {
            "node_id": self.id,
            "power_state": self.power_state.value,
            "battery_current_wh": round(self.battery_current_wh, 2),
            "battery_capacity_wh": self.battery_capacity_wh,
            "effective_capacity_wh": round(capacity, 2),
            "battery_pct": round(battery_pct, 2),
            "hours_remaining": round(hours_remaining, 2),
            "power_consumption_w": round(effective_power, 2),
            "solar_panel_w": self.solar_panel_w,
            "is_charging": is_charging,
            "charge_cycles": self.charge_cycles,
            "critical": battery_pct < 20,
        }


def _get_solar_factor(hour: int) -> float:
    if hour < 6 or hour > 18:
        return 0.0
    return 0.8 * math.sin(math.pi * (hour - 6) / 12)


def _compute_solar_production(solar_panel_w: float, hour: Optional[int]) -> float:
    if solar_panel_w <= 0:
        return 0.0
    if hour is None:
        hour = 12
    factor = _get_solar_factor(hour)
    efficiency = 0.2
    return solar_panel_w * efficiency * factor


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
        node_types = ([NodeType.TRENCH] * (num_nodes - 2)
                      + [NodeType.BASE_STATION, NodeType.DAS_INTERROGATOR])
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
                last_traffic_time=self.simulation_time,
            )
            self.add_node(node)

        node_ids = list(self.nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                dist = self.nodes[node_ids[i]].position.distance_to(
                    self.nodes[node_ids[j]].position
                )
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

    # ------------------------------------------------------------------
    # Artillery damage (enhanced probabilistic model)
    # ------------------------------------------------------------------

    def simulate_artillery_damage(self, impact_lat: float, impact_lon: float,
                                  blast_radius_m: float = 50.0,
                                  caliber: Optional[ArtilleryCaliber] = None):
        impact_pos = GeoCoord(lat=impact_lat, lon=impact_lon)
        R = caliber.characteristic_radius_m if caliber else blast_radius_m
        num_samples = 12
        damaged_links = []

        for link_id, link in self.links.items():
            if link.state == LinkState.BROKEN:
                continue
            node_a = self.nodes[link.node_a]
            node_b = self.nodes[link.node_b]

            closest_dist = float("inf")
            closest_frac = 0.5
            link_broken = False

            for i in range(1, num_samples + 1):
                frac = i / (num_samples + 1)
                point_lat = node_a.position.lat + frac * (node_b.position.lat - node_a.position.lat)
                point_lon = node_a.position.lon + frac * (node_b.position.lon - node_a.position.lon)
                point = GeoCoord(lat=point_lat, lon=point_lon)
                dist = point.distance_to(impact_pos)

                if dist < closest_dist:
                    closest_dist = dist
                    closest_frac = frac

                if R > 0:
                    p_break = math.exp(-dist / R)
                else:
                    p_break = 1.0 if dist == 0 else 0.0

                if p_break > random.random():
                    link_broken = True

            if link_broken:
                link.state = LinkState.BROKEN
                link.break_position_m = link.length_m * closest_frac
                damaged_links.append({
                    "link_id": link_id,
                    "break_position_m": round(link.break_position_m, 1),
                    "distance_to_impact_m": round(closest_dist, 1),
                })

        event = {
            "timestamp": self.simulation_time,
            "type": "artillery_impact",
            "position": {"lat": impact_lat, "lon": impact_lon},
            "blast_radius_m": blast_radius_m,
            "caliber": caliber.name if caliber else None,
            "characteristic_radius_m": R,
            "links_damaged": len(damaged_links),
            "details": damaged_links,
        }
        self.events.append(event)
        return event

    def simulate_vehicle_crossing(self, vehicle_path: list,
                                  vehicle_type: str = "heavy"):
        damaged_links = []

        for link_id, link in self.links.items():
            if link.state == LinkState.BROKEN:
                continue
            node_a = self.nodes[link.node_a]
            node_b = self.nodes[link.node_b]

            for path_point in vehicle_path:
                hit = False
                for i in range(1, 11):
                    frac = i / 11
                    fiber_lat = node_a.position.lat + frac * (node_b.position.lat - node_a.position.lat)
                    fiber_lon = node_a.position.lon + frac * (node_b.position.lon - node_a.position.lon)
                    fiber_point = GeoCoord(lat=fiber_lat, lon=fiber_lon)
                    dist = fiber_point.distance_to(path_point)

                    if dist < 5.0:
                        p_break = 0.3 if link.burial_depth_cm < 5 else 0.05
                        if random.random() < p_break:
                            link.state = LinkState.BROKEN
                            link.break_position_m = link.length_m * frac
                            damaged_links.append({
                                "link_id": link_id,
                                "break_position_m": round(link.break_position_m, 1),
                                "vehicle_distance_m": round(dist, 1),
                                "burial_depth_cm": link.burial_depth_cm,
                            })
                            hit = True
                            break
                if hit:
                    break

        event = {
            "timestamp": self.simulation_time,
            "type": "vehicle_crossing",
            "vehicle_type": vehicle_type,
            "path_points": len(vehicle_path),
            "links_damaged": len(damaged_links),
            "details": damaged_links,
        }
        self.events.append(event)
        return event

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------

    def _build_adjacency(self) -> dict:
        alive_nodes = {nid for nid, n in self.nodes.items() if n.is_alive}
        adj: dict[str, dict[str, float]] = {nid: {} for nid in alive_nodes}
        for link in self.links.values():
            if not link.is_usable:
                continue
            if link.node_a in alive_nodes and link.node_b in alive_nodes:
                cost = link.total_loss_db + link.length_m * 0.001
                adj[link.node_a][link.node_b] = cost
                adj[link.node_b][link.node_a] = cost
        return adj

    def _dijkstra(self, adj: dict, src: str) -> tuple[dict, dict]:
        dist = {n: float("inf") for n in adj}
        prev = {n: None for n in adj}
        dist[src] = 0.0
        visited = set()
        while len(visited) < len(adj):
            u = min(
                (n for n in adj if n not in visited),
                key=lambda n: dist[n],
                default=None,
            )
            if u is None or dist[u] == float("inf"):
                break
            visited.add(u)
            for v, w in adj[u].items():
                new_dist = dist[u] + w
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
        return dist, prev

    def _reconstruct_path(self, prev: dict, src: str, dst: str) -> list[str]:
        path: list[str] = []
        cur = dst
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        if len(path) > 1 and path[0] == src:
            return path
        return []

    # ------------------------------------------------------------------
    # Routing (backward-compatible + enhanced)
    # ------------------------------------------------------------------

    def compute_routing(self) -> dict:
        adj = self._build_adjacency()
        alive_nodes = {nid for nid, n in self.nodes.items() if n.is_alive}
        paths: dict = {}
        for src in alive_nodes:
            dist, prev = self._dijkstra(adj, src)
            for dst in alive_nodes:
                if dst == src:
                    continue
                path = self._reconstruct_path(prev, src, dst)
                if path:
                    paths[f"{src}->{dst}"] = {
                        "path": path,
                        "hops": len(path) - 1,
                        "total_cost": round(dist[dst], 2),
                    }
            self.nodes[src].routing_table = paths
        return paths

    def compute_alternative_routes(self) -> dict:
        adj = self._build_adjacency()
        alive_nodes = sorted(nid for nid, n in self.nodes.items() if n.is_alive)
        routes: dict = {}

        for src in alive_nodes:
            for dst in alive_nodes:
                if src == dst:
                    continue
                key = f"{src}->{dst}"

                dist1, prev1 = self._dijkstra(adj, src)
                primary = self._reconstruct_path(prev1, src, dst)

                if not primary:
                    routes[key] = {"primary": None, "backup": None}
                    continue

                primary_links: set[str] = set()
                for k in range(len(primary) - 1):
                    a, b = primary[k], primary[k + 1]
                    for lid, link in self.links.items():
                        if ((link.node_a == a and link.node_b == b)
                                or (link.node_a == b and link.node_b == a)):
                            primary_links.add(lid)

                adj_backup: dict[str, dict[str, float]] = {
                    nid: dict(neighbors) for nid, neighbors in adj.items()
                }
                for lid in primary_links:
                    lk = self.links[lid]
                    adj_backup[lk.node_a].pop(lk.node_b, None)
                    adj_backup[lk.node_b].pop(lk.node_a, None)

                dist2, prev2 = self._dijkstra(adj_backup, src)
                backup = self._reconstruct_path(prev2, src, dst)

                routes[key] = {
                    "primary": {
                        "path": primary,
                        "hops": len(primary) - 1,
                        "total_cost": round(dist1[dst], 2),
                    },
                    "backup": (
                        {
                            "path": backup,
                            "hops": len(backup) - 1,
                            "total_cost": round(dist2[dst], 2),
                        }
                        if backup else None
                    ),
                }

        return routes

    def estimate_path_bandwidth(self, path: list) -> float:
        if len(path) < 2:
            return 0.0
        num_hops = len(path) - 1
        base_gbps = 1.0
        overhead_per_hop = 0.05
        return round(base_gbps * ((1 - overhead_per_hop) ** num_hops), 4)

    def estimate_path_latency(self, path: list) -> float:
        if len(path) < 2:
            return 0.0
        total_latency_ms = 0.0
        for i in range(len(path) - 1):
            node_a = self.nodes.get(path[i])
            node_b = self.nodes.get(path[i + 1])
            if not node_a or not node_b:
                continue
            dist_km = node_a.position.distance_to(node_b.position) / 1000.0
            fiber_latency_ms = dist_km * 0.005
            hop_processing_ms = 0.5
            total_latency_ms += fiber_latency_ms + hop_processing_ms
        return round(total_latency_ms, 4)

    def estimate_failover_time(self, broken_link_id: str) -> float:
        base_failover = 4.0
        if broken_link_id in self.links:
            link = self.links[broken_link_id]
            adjacent_active = 0
            for l in self.links.values():
                if not l.is_usable:
                    continue
                if l.node_a in (link.node_a, link.node_b) or l.node_b in (link.node_a, link.node_b):
                    adjacent_active += 1
            if adjacent_active > 2:
                base_failover -= 0.5
            elif adjacent_active <= 1:
                base_failover += 1.0
        return round(base_failover + random.uniform(-0.5, 0.5), 2)

    # ------------------------------------------------------------------
    # Network status (backward-compatible)
    # ------------------------------------------------------------------

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
            avg_battery = sum(
                n.battery_hours for n in self.nodes.values() if n.is_alive
            ) / alive_nodes

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

    # ------------------------------------------------------------------
    # Time step (enhanced with power states, solar, degradation)
    # ------------------------------------------------------------------

    def simulate_time_step(self, dt_hours: float = 1.0):
        self.simulation_time += dt_hours * 3600
        current_hour = int((self.simulation_time / 3600) % 24)
        idle_threshold_s = 300.0

        for node in self.nodes.values():
            if not node.is_alive:
                continue

            time_since_traffic = self.simulation_time - node.last_traffic_time
            if time_since_traffic > idle_threshold_s and node.power_state == PowerState.ACTIVE:
                node.power_state = PowerState.IDLE

            effective_power = node._effective_power_consumption()
            drain_wh = effective_power * dt_hours
            node.battery_current_wh -= drain_wh

            if node.solar_panel_w > 0:
                solar_wh = _compute_solar_production(node.solar_panel_w, current_hour) * dt_hours
                node.battery_current_wh = min(
                    node.effective_capacity_wh,
                    node.battery_current_wh + solar_wh,
                )
                node._total_charged_wh += solar_wh
                while node._total_charged_wh >= node.battery_capacity_wh:
                    node._total_charged_wh -= node.battery_capacity_wh
                    node.charge_cycles += 1

            if node.battery_current_wh <= 0:
                node.battery_current_wh = 0
                node.is_alive = False
                node._battery_critical_alerted = False
                self.events.append({
                    "timestamp": self.simulation_time,
                    "type": "node_died",
                    "node_id": node.id,
                    "reason": "battery_depleted",
                })
            elif node.battery_current_wh < node.effective_capacity_wh * 0.2:
                if not node._battery_critical_alerted:
                    node._battery_critical_alerted = True
                    self.events.append({
                        "timestamp": self.simulation_time,
                        "type": "battery_critical",
                        "node_id": node.id,
                        "battery_pct": round(
                            node.battery_current_wh / node.effective_capacity_wh * 100, 1
                        ),
                    })
            else:
                node._battery_critical_alerted = False

        for link in self.links.values():
            if link.state == LinkState.ACTIVE and random.random() < 0.002 * dt_hours:
                link.state = LinkState.DEGRADED
                self.events.append({
                    "timestamp": self.simulation_time,
                    "type": "link_degraded",
                    "link_id": link.id,
                    "reason": "environmental_stress",
                })

    # ------------------------------------------------------------------
    # Network health scoring
    # ------------------------------------------------------------------

    def compute_network_health(self) -> dict:
        total_links = len(self.links)
        active_links = sum(1 for l in self.links.values() if l.state == LinkState.ACTIVE)
        alive_nodes = sum(1 for n in self.nodes.values() if n.is_alive)
        total_nodes = len(self.nodes)

        connectivity_score = (active_links / total_links * 100) if total_links > 0 else 0
        coverage_score = (alive_nodes / total_nodes * 100) if total_nodes > 0 else 0

        alt_routes = self.compute_alternative_routes()
        total_pairs = 0
        pairs_with_backup = 0
        for route in alt_routes.values():
            if route["primary"] is not None:
                total_pairs += 1
                if route["backup"] is not None:
                    pairs_with_backup += 1
        redundancy_score = (pairs_with_backup / total_pairs * 100) if total_pairs > 0 else 0

        alive_list = [n for n in self.nodes.values() if n.is_alive]
        if alive_list:
            avg_battery_pct = sum(
                n.battery_current_wh / n.effective_capacity_wh * 100 for n in alive_list
            ) / len(alive_list)
        else:
            avg_battery_pct = 0
        battery_score = min(100.0, max(0.0, avg_battery_pct))

        overall = (
            connectivity_score * 0.30
            + coverage_score * 0.20
            + redundancy_score * 0.30
            + battery_score * 0.20
        )

        if overall >= 90:
            rating = "EXCELLENT"
        elif overall >= 70:
            rating = "GOOD"
        elif overall >= 50:
            rating = "FAIR"
        elif overall >= 30:
            rating = "POOR"
        else:
            rating = "CRITICAL"

        return {
            "connectivity_score": round(connectivity_score, 1),
            "coverage_score": round(coverage_score, 1),
            "redundancy_score": round(redundancy_score, 1),
            "battery_score": round(battery_score, 1),
            "overall_score": round(overall, 1),
            "rating": rating,
        }

    # ------------------------------------------------------------------
    # Graceful degradation timeline
    # ------------------------------------------------------------------

    def simulate_degradation(self, artillery_events: list) -> list:
        timeline: list[dict] = []

        for i, event in enumerate(artillery_events):
            t = event.get("time_s", i * 600)
            lat = event.get("lat", 0)
            lon = event.get("lon", 0)
            caliber_name = event.get("caliber")
            blast_radius = event.get("blast_radius_m", 50.0)

            self.simulation_time = t

            caliber = None
            if caliber_name:
                try:
                    caliber = ArtilleryCaliber[caliber_name]
                except KeyError:
                    pass

            damage_event = self.simulate_artillery_damage(lat, lon, blast_radius, caliber)

            routes = self.compute_routing()
            health = self.compute_network_health()

            active_routes = sum(1 for r in routes.values() if r["hops"] >= 1)
            avg_hops = (
                sum(r["hops"] for r in routes.values()) / len(routes) if routes else 0
            )

            total_bw = sum(self.estimate_path_bandwidth(r["path"]) for r in routes.values())
            avg_bw = total_bw / len(routes) if routes else 0

            total_lat = sum(self.estimate_path_latency(r["path"]) for r in routes.values())
            avg_lat = total_lat / len(routes) if routes else 0

            timeline.append({
                "time_s": t,
                "event_index": i,
                "links_damaged": damage_event["links_damaged"],
                "total_links_broken": sum(
                    1 for l in self.links.values() if l.state == LinkState.BROKEN
                ),
                "active_routes": active_routes,
                "avg_hops": round(avg_hops, 2),
                "avg_bandwidth_gbps": round(avg_bw, 4),
                "avg_latency_ms": round(avg_lat, 4),
                "health": health,
            })

        return timeline


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

    print("\n--- Alternative Routes (OSPF-like) ---")
    alt_routes = sim.compute_alternative_routes()
    backup_count = sum(1 for r in alt_routes.values() if r["backup"] is not None)
    print(f"  Total pairs: {len(alt_routes)}, with backup: {backup_count}")
    for key, route in list(alt_routes.items())[:5]:
        primary = route["primary"]
        backup = route["backup"]
        if primary:
            pstr = f"primary {primary['hops']} hops"
            bstr = f", backup {backup['hops']} hops" if backup else ", no backup"
            print(f"  {key}: {pstr}{bstr}")

    print("\n--- Bandwidth & Latency Estimates ---")
    for key, route in list(routes.items())[:5]:
        bw = sim.estimate_path_bandwidth(route["path"])
        lat_ms = sim.estimate_path_latency(route["path"])
        print(f"  {key}: {bw} Gbps, {lat_ms} ms")

    print("\n--- Simulating Artillery Strike (P_break model) ---")
    node_list = list(sim.nodes.values())
    target = random.choice(node_list)
    impact = sim.simulate_artillery_damage(
        target.position.lat + random.uniform(-0.005, 0.005),
        target.position.lon + random.uniform(-0.005, 0.005),
        caliber=ArtilleryCaliber.HOWITZER_152mm,
    )
    print(f"  Impact near {target.id} ({ArtilleryCaliber.HOWITZER_152mm.name}): "
          f"{impact['links_damaged']} links damaged")
    for d in impact["details"]:
        print(f"    {d['link_id']}: break at {d['break_position_m']}m "
              f"(dist {d['distance_to_impact_m']}m)")

    if impact["details"]:
        broken_id = impact["details"][0]["link_id"]
        failover = sim.estimate_failover_time(broken_id)
        print(f"  Estimated failover time: {failover}s")

    status_after = sim.get_network_status()
    print(f"\n--- Post-Strike Status ---")
    print(f"  Connectivity: {status_after['connectivity_pct']}%")
    print(f"  Active links: {status_after['links_active']}/{status_after['links_total']}")
    print(f"  Mesh healthy: {status_after['mesh_healthy']}")

    print("\n--- Recomputing Routes ---")
    routes_after = sim.compute_routing()
    rerouted = sum(1 for r in routes_after.values() if r["hops"] > 1)
    print(f"  Active routes: {len(routes_after)}, multi-hop: {rerouted}")

    print("\n--- Power Status ---")
    for nid, node in sim.nodes.items():
        ps = node.get_power_status()
        charging = " [CHARGING]" if ps["is_charging"] else ""
        critical = " [CRITICAL]" if ps["critical"] else ""
        print(f"  {nid}: {ps['power_state']}, {ps['battery_pct']:.1f}% "
              f"({ps['hours_remaining']:.1f}h remaining){charging}{critical}")

    print("\n--- Network Health Score ---")
    health = sim.compute_network_health()
    print(f"  Connectivity: {health['connectivity_score']}")
    print(f"  Coverage: {health['coverage_score']}")
    print(f"  Redundancy: {health['redundancy_score']}")
    print(f"  Battery: {health['battery_score']}")
    print(f"  Overall: {health['overall_score']} ({health['rating']})")

    print("\n--- Degradation Timeline ---")
    for link in sim.links.values():
        if link.state == LinkState.BROKEN:
            link.state = LinkState.ACTIVE
            link.break_position_m = None

    degradation_events = [
        {"time_s": 0, "lat": target.position.lat, "lon": target.position.lon,
         "caliber": "HOWITZER_152mm"},
        {"time_s": 600, "lat": target.position.lat + 0.005,
         "lon": target.position.lon + 0.005, "caliber": "MLRS"},
        {"time_s": 1200, "lat": target.position.lat - 0.003,
         "lon": target.position.lon - 0.003, "caliber": "MORTAR_82mm"},
    ]
    timeline = sim.simulate_degradation(degradation_events)
    for entry in timeline:
        print(f"  T+{entry['time_s']}s: {entry['links_damaged']} damaged, "
              f"{entry['active_routes']} routes, "
              f"bw={entry['avg_bandwidth_gbps']} Gbps, "
              f"lat={entry['avg_latency_ms']} ms, "
              f"health={entry['health']['overall_score']} "
              f"({entry['health']['rating']})")

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
