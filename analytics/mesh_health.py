#!/usr/bin/env python3
"""
TFN Mesh Health Monitor
========================

Monitors the health of a deployed mesh network:
- Node status (battery, connectivity)
- Link quality (loss, degradation)
- Routing efficiency
- Alert generation
"""

import json
import random
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class NodeHealth:
    node_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    battery_percent: float = 100.0
    battery_hours_remaining: float = 100.0
    links_active: int = 0
    links_total: int = 0
    cpu_usage_percent: float = 10.0
    memory_usage_percent: float = 20.0
    temperature_c: float = 35.0
    last_heartbeat: Optional[str] = None
    issues: list = field(default_factory=list)

    def update_status(self):
        if self.battery_percent <= 0:
            self.status = HealthStatus.OFFLINE
        elif self.battery_percent < 10 or self.links_active == 0:
            self.status = HealthStatus.CRITICAL
        elif self.battery_percent < 25 or self.links_active < self.links_total * 0.5:
            self.status = HealthStatus.WARNING
        else:
            self.status = HealthStatus.HEALTHY


@dataclass
class LinkHealth:
    link_id: str
    node_a: str
    node_b: str
    status: HealthStatus = HealthStatus.HEALTHY
    rx_power_dbm: float = -15.0
    tx_power_dbm: float = -3.0
    loss_db: float = 5.0
    snr_db: float = 20.0
    ber: float = 0.0
    latency_ms: float = 0.5
    uptime_percent: float = 99.9
    issues: list = field(default_factory=list)

    def update_status(self, rx_sensitivity_dbm: float = -28.0):
        margin = self.rx_power_dbm - rx_sensitivity_dbm
        if self.rx_power_dbm == 0 and self.tx_power_dbm == 0:
            self.status = HealthStatus.OFFLINE
        elif margin < 3:
            self.status = HealthStatus.CRITICAL
            self.issues.append(f"Low margin: {margin:.1f}dB")
        elif margin < 6 or self.ber > 1e-6:
            self.status = HealthStatus.WARNING
        else:
            self.status = HealthStatus.HEALTHY


class MeshHealthMonitor:
    def __init__(self, rx_sensitivity_dbm: float = -28.0):
        self.rx_sensitivity = rx_sensitivity_dbm
        self.nodes: dict[str, NodeHealth] = {}
        self.links: dict[str, LinkHealth] = {}
        self.alerts: list[dict] = []
        self.history: list[dict] = []

    def add_node(self, node_id: str, battery_percent: float = 100.0,
                 links_total: int = 3):
        node = NodeHealth(
            node_id=node_id,
            battery_percent=battery_percent,
            battery_hours_remaining=battery_percent * 2,
            links_active=links_total,
            links_total=links_total,
        )
        self.nodes[node_id] = node

    def add_link(self, link_id: str, node_a: str, node_b: str,
                 rx_power: float = -15.0, loss_db: float = 5.0):
        link = LinkHealth(
            link_id=link_id, node_a=node_a, node_b=node_b,
            rx_power_dbm=rx_power, loss_db=loss_db,
        )
        self.links[link_id] = link

    def update(self, node_updates: Optional[dict] = None,
               link_updates: Optional[dict] = None):
        if node_updates:
            for nid, updates in node_updates.items():
                if nid in self.nodes:
                    node = self.nodes[nid]
                    for k, v in updates.items():
                        if hasattr(node, k):
                            setattr(node, k, v)
                    node.update_status()

        if link_updates:
            for lid, updates in link_updates.items():
                if lid in self.links:
                    link = self.links[lid]
                    for k, v in updates.items():
                        if hasattr(link, k):
                            setattr(link, k, v)
                    link.update_status(self.rx_sensitivity)

        self._generate_alerts()
        self._record_snapshot()

    def _generate_alerts(self):
        for nid, node in self.nodes.items():
            if node.status == HealthStatus.OFFLINE:
                self.alerts.append({
                    "timestamp": datetime.now().isoformat(),
                    "severity": "critical",
                    "type": "node_offline",
                    "node": nid,
                    "message": f"Node {nid} is OFFLINE (battery={node.battery_percent:.0f}%)",
                })
            elif node.status == HealthStatus.CRITICAL:
                self.alerts.append({
                    "timestamp": datetime.now().isoformat(),
                    "severity": "critical",
                    "type": "node_critical",
                    "node": nid,
                    "message": f"Node {nid} CRITICAL: battery={node.battery_percent:.0f}%, links={node.links_active}/{node.links_total}",
                })
            elif node.status == HealthStatus.WARNING:
                if node.battery_percent < 25:
                    self.alerts.append({
                        "timestamp": datetime.now().isoformat(),
                        "severity": "warning",
                        "type": "battery_low",
                        "node": nid,
                        "message": f"Node {nid} battery low: {node.battery_percent:.0f}% ({node.battery_hours_remaining:.0f}h)",
                    })

        for lid, link in self.links.items():
            if link.status == HealthStatus.OFFLINE:
                self.alerts.append({
                    "timestamp": datetime.now().isoformat(),
                    "severity": "critical",
                    "type": "link_down",
                    "link": lid,
                    "message": f"Link {lid} ({link.node_a}↔{link.node_b}) is DOWN",
                })

    def _record_snapshot(self):
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "nodes_healthy": sum(1 for n in self.nodes.values() if n.status == HealthStatus.HEALTHY),
            "nodes_total": len(self.nodes),
            "links_active": sum(1 for l in self.links.values() if l.status != HealthStatus.OFFLINE),
            "links_total": len(self.links),
            "avg_battery": sum(n.battery_percent for n in self.nodes.values()) / max(len(self.nodes), 1),
        }
        self.history.append(snapshot)

    def get_dashboard(self) -> dict:
        return {
            "summary": {
                "nodes_healthy": sum(1 for n in self.nodes.values() if n.status == HealthStatus.HEALTHY),
                "nodes_warning": sum(1 for n in self.nodes.values() if n.status == HealthStatus.WARNING),
                "nodes_critical": sum(1 for n in self.nodes.values() if n.status == HealthStatus.CRITICAL),
                "nodes_offline": sum(1 for n in self.nodes.values() if n.status == HealthStatus.OFFLINE),
                "links_healthy": sum(1 for l in self.links.values() if l.status == HealthStatus.HEALTHY),
                "links_offline": sum(1 for l in self.links.values() if l.status == HealthStatus.OFFLINE),
                "avg_battery": round(sum(n.battery_percent for n in self.nodes.values()) / max(len(self.nodes), 1), 1),
            },
            "nodes": {
                nid: {
                    "status": n.status.value,
                    "battery": f"{n.battery_percent:.0f}%",
                    "hours_left": f"{n.battery_hours_remaining:.0f}h",
                    "links": f"{n.links_active}/{n.links_total}",
                }
                for nid, n in self.nodes.items()
            },
            "links": {
                lid: {
                    "status": l.status.value,
                    "rx_power": f"{l.rx_power_dbm:.1f}dBm",
                    "loss": f"{l.loss_db:.1f}dB",
                    "latency": f"{l.latency_ms:.1f}ms",
                    "uptime": f"{l.uptime_percent:.1f}%",
                }
                for lid, l in self.links.items()
            },
            "recent_alerts": self.alerts[-10:],
            "mesh_healthy": all(
                n.status in (HealthStatus.HEALTHY, HealthStatus.WARNING)
                for n in self.nodes.values()
            ),
        }


def demo():
    mon = MeshHealthMonitor()

    nodes = ["CP", "POS-A", "POS-B", "POS-C", "RELAY", "OBS-1"]
    for nid in nodes:
        mon.add_node(nid, battery_percent=random.uniform(50, 100), links_total=3)

    links = [
        ("CP↔POS-A", "CP", "POS-A"), ("CP↔RELAY", "CP", "RELAY"),
        ("POS-A↔POS-B", "POS-A", "POS-B"), ("POS-B↔POS-C", "POS-B", "POS-C"),
        ("POS-C↔OBS-1", "POS-C", "OBS-1"), ("RELAY↔POS-B", "RELAY", "POS-B"),
    ]
    for lid, a, b in links:
        mon.add_link(lid, a, b, rx_power=random.uniform(-20, -8), loss_db=random.uniform(2, 8))

    print("=" * 60)
    print("TFN MESH HEALTH MONITOR")
    print("=" * 60)

    dashboard = mon.get_dashboard()
    s = dashboard["summary"]
    print(f"\nNodes: {s['nodes_healthy']} healthy, {s['nodes_warning']} warning, "
          f"{s['nodes_critical']} critical, {s['nodes_offline']} offline")
    print(f"Links: {s['links_healthy']} healthy, {s['links_offline']} offline")
    print(f"Avg battery: {s['avg_battery']}%")
    print(f"Mesh healthy: {dashboard['mesh_healthy']}")

    mon.update(
        node_updates={"POS-B": {"battery_percent": 5, "battery_hours_remaining": 10}},
        link_updates={"POS-B↔POS-C": {"rx_power_dbm": -30}},
    )

    print(f"\n--- After degradation ---")
    for alert in mon.alerts:
        print(f"  [{alert['severity'].upper()}] {alert['message']}")

    dashboard2 = mon.get_dashboard()
    print(f"\nMesh healthy: {dashboard2['mesh_healthy']}")

    print(json.dumps(dashboard2, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo()
