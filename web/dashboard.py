#!/usr/bin/env python3
"""
TFN Streamlit Dashboard — Tactical Fiber Network Visualization
================================================================

Run: streamlit run web/dashboard.py

Requires: pip install streamlit numpy
"""

import streamlit as st
import numpy as np
import json
import random
import math
from datetime import datetime

sys_import = __import__
sys = sys_import("sys")
sys.path.insert(0, ".")

from simulation.mesh_simulator import MeshSimulator, MeshNode, FiberLink, GeoCoord, NodeType, LinkState
from simulation.das_simulator import DASSimulator, TargetSignature, ThreatLevel
from simulation.rf_detector import RFDetectorSimulator, RFSource, RFSourceType


st.set_page_config(page_title="TFN SpiderLink Dashboard", layout="wide", page_icon="🕸️")

st.markdown("""
<style>
    .stApp { background: #0a0a0f; color: #e0e0f0; }
    .metric-card { background: #111118; border: 1px solid #1e1e2e; border-radius: 8px; padding: 16px; }
    h1, h2, h3 { color: #00ff88; }
    .stMetric { background: #111118; border-radius: 8px; padding: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🕸️ TFN SpiderLink — Tactical Dashboard")
st.caption("Zero-Emission Tactical Fiber Network | Real-time Simulation")

tab_mesh, tab_das, tab_rf, tab_budget, tab_trophy = st.tabs([
    "🌐 Mesh Network", "👂 DAS Sensing", "📡 RF Detection", "📊 Link Budget", "🏆 Trophy Intel"
])

with tab_mesh:
    st.header("Mesh Network Simulation")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Parameters")
        num_nodes = st.slider("Number of nodes", 3, 15, 8, key="mesh_nodes")
        area_km = st.slider("Area radius (km)", 1.0, 10.0, 3.0, key="mesh_area")
        max_link_km = st.slider("Max link distance (km)", 1.0, 10.0, 5.0, key="mesh_maxlink")

        if st.button("🚀 Deploy Network", key="deploy"):
            sim = MeshSimulator()
            sim.deploy_random_mesh(num_nodes=num_nodes, area_km=area_km)
            st.session_state["mesh_sim"] = sim
            st.session_state["mesh_routes"] = sim.compute_routing()
            st.session_state["mesh_status"] = sim.get_network_status()

        if st.button("💥 Artillery Strike", key="artillery") and "mesh_sim" in st.session_state:
            sim = st.session_state["mesh_sim"]
            nodes = list(sim.nodes.values())
            target = random.choice(nodes)
            result = sim.simulate_artillery_damage(
                target.position.lat + random.uniform(-0.003, 0.003),
                target.position.lon + random.uniform(-0.003, 0.003),
                blast_radius_m=100,
            )
            st.session_state["mesh_routes"] = sim.compute_routing()
            st.session_state["mesh_status"] = sim.get_network_status()
            st.session_state["last_strike"] = result

        if st.button("⏰ Simulate 24h", key="sim24") and "mesh_sim" in st.session_state:
            sim = st.session_state["mesh_sim"]
            for _ in range(24):
                sim.simulate_time_step(1.0)
            st.session_state["mesh_status"] = sim.get_network_status()

    with col2:
        if "mesh_sim" in st.session_state:
            sim = st.session_state["mesh_sim"]
            status = st.session_state.get("mesh_status", sim.get_network_status())

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Nodes Alive", f"{status['nodes_alive']}/{status['nodes_total']}")
            m2.metric("Active Links", f"{status['links_active']}/{status['links_total']}")
            m3.metric("Connectivity", f"{status['connectivity_pct']}%")
            m4.metric("Avg Battery", f"{status['avg_battery_hours']:.0f}h")

            st.subheader("Node Map (Simulated)")
            nodes = sim.nodes
            links = sim.links

            chart_data = {}
            node_positions = {}
            for nid, node in nodes.items():
                node_positions[nid] = (node.position.lat, node.position.lon)

            for nid, (lat, lon) in node_positions.items():
                st.text(f"  {nid}: ({lat:.4f}, {lon:.4f})")

            st.subheader("Link Analysis")
            for lid, link in links.items():
                state_icon = {"active": "🟢", "degraded": "🟡", "broken": "🔴"}.get(link.state.value, "❓")
                check = sim.check_link_feasibility(link)
                st.text(f"  {state_icon} {lid}: {link.length_m/1000:.1f}km, loss={check['total_loss_db']}dB, [{check['recommendation']}]")

            if "last_strike" in st.session_state:
                strike = st.session_state["last_strike"]
                st.subheader("Last Artillery Strike")
                st.json({
                    "links_damaged": strike["links_damaged"],
                    "blast_radius_m": strike["blast_radius_m"],
                })
        else:
            st.info("Click 'Deploy Network' to start simulation")

with tab_das:
    st.header("DAS — Distributed Acoustic Sensing")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Configuration")
        fiber_length = st.slider("Fiber length (m)", 1000, 20000, 5000, key="das_length")
        duration = st.slider("Duration (s)", 10, 300, 60, key="das_duration")

        st.subheader("Inject Events")
        events_to_inject = []
        for i, (sig, label) in enumerate([
            (TargetSignature.FOOTSTEP_GROUP, "Footstep Group"),
            (TargetSignature.WHEELED_VEHICLE, "Wheeled Vehicle"),
            (TargetSignature.TRACKED_VEHICLE, "Tracked Vehicle"),
            (TargetSignature.ARTILLERY_FIRE, "Artillery Fire"),
            (TargetSignature.EXPLOSION, "Explosion"),
            (TargetSignature.DRONE_HOVER, "Drone Hover"),
            (TargetSignature.EW_INTERFERENCE, "EW Interference"),
            (TargetSignature.DIGGING, "Digging"),
        ]):
            if st.checkbox(label, value=True, key=f"das_evt_{i}"):
                events_to_inject.append({
                    "time": random.uniform(2, duration - 5),
                    "position": random.uniform(200, fiber_length - 200),
                    "signature": sig,
                    "duration": random.uniform(1, 5),
                })

        if st.button("▶ Run DAS Simulation", key="run_das"):
            das = DASSimulator(fiber_length_m=fiber_length)
            das.auto_segment()
            detected = das.simulate_scenario(duration_s=duration, events=events_to_inject)
            st.session_state["das_results"] = das.get_alerts(ThreatLevel.LOW)
            st.session_state["das_report"] = das.generate_report()

    with col2:
        if "das_results" in st.session_state:
            alerts = st.session_state["das_results"]
            report = st.session_state.get("das_report", {})

            m1, m2, m3 = st.columns(3)
            m1.metric("Events Detected", report.get("events_detected", 0))
            m2.metric("High Threats", report.get("high_threat_events", 0))
            m3.metric("Fiber Length", f"{report.get('fiber_length_m', 0)}m")

            st.subheader("Alerts")
            for alert in alerts:
                threat = alert["threat"]
                color = {"none": "⚪", "low": "🟡", "medium": "🟠", "high": "🔴", "critical": "💥"}.get(threat, "❓")
                st.text(f"  {color} [{alert['target']}] {alert['position_m']}m — {alert['confidence']} ({threat})")

            st.subheader("Threat Breakdown")
            breakdown = report.get("threat_breakdown", {})
            if breakdown:
                st.bar_chart(breakdown)
        else:
            st.info("Configure and run DAS simulation")

with tab_rf:
    st.header("RF-Opto Hybrid Detection (Passive)")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("RF Sources to Detect")
        sources = []
        for src_type, label, default_power, default_freq, default_dist in [
            (RFSourceType.EW_STATION, "EW Station", 1000, 2.4e9, 10),
            (RFSourceType.RADAR, "Radar", 10000, 10e9, 50),
            (RFSourceType.FPV_CONTROL, "FPV Control", 0.5, 2.4e9, 5),
            (RFSourceType.FPV_VIDEO, "FPV Video", 0.2, 5.8e9, 3),
            (RFSourceType.TACTICAL_RADIO, "Tactical Radio", 5, 150e6, 15),
            (RFSourceType.CELL_TOWER, "Cell Tower", 100, 1.8e9, 30),
        ]:
            if st.checkbox(label, value=True, key=f"rf_{src_type.value}"):
                sources.append(RFSource(
                    source_type=src_type,
                    frequency_hz=default_freq,
                    power_w=default_power,
                    distance_to_fiber_m=default_dist,
                    position_m_on_fiber=random.uniform(200, 4800),
                ))

        if st.button("▶ Scan RF Sources", key="run_rf"):
            detector = RFDetectorSimulator(fiber_length_m=5000)
            results = detector.run_detection_sweep(sources)
            st.session_state["rf_results"] = results
            st.session_state["rf_report"] = detector.generate_report()

    with col2:
        if "rf_results" in st.session_state:
            results = st.session_state["rf_results"]
            report = st.session_state["rf_report"]

            m1, m2, m3 = st.columns(3)
            m1.metric("Scanned", report["total_sources_scanned"])
            m2.metric("Detected", report["detected"])
            m3.metric("Rate", report["detection_rate"])

            st.subheader("Detections")
            for r in results:
                icon = "✅" if r.detected else "❌"
                st.text(f"  {icon} {r.source_type.value}: "
                        f"{'φ=' + f'{r.phase_shift_rad:.2e}rad' if r.detected else 'below threshold'} "
                        f"{'SNR=' + f'{r.snr_db:.1f}dB' if r.detected else ''} "
                        f"[{r.method if r.detected else 'N/A'}]")

            if report.get("by_type"):
                st.subheader("Detections by Type")
                st.bar_chart(report["by_type"])
        else:
            st.info("Select RF sources and click 'Scan'")

with tab_budget:
    st.header("Optical Link Budget Calculator")

    col1, col2 = st.columns([1, 2])

    with col1:
        link_length = st.slider("Link length (km)", 0.5, 20.0, 5.0, key="budget_length")
        num_splices = st.slider("Number of splices", 0, 10, 3, key="budget_splices")
        splice_method = st.selectbox("Splice method", [
            "mechanical_good", "mechanical_avg", "fusion", "quick_connector", "field_emergency"
        ], index=0, key="budget_method")
        fiber_type = st.selectbox("Fiber type", ["G.657A2", "G.652D", "drone_spent"], key="budget_fiber")

    with col2:
        if st.button("📊 Calculate Budget", key="calc_budget"):
            sys.path.insert(0, ".")
            from calculator.fiber_budget import FiberBudgetCalculator, COMMON_SFP, SPLICE_TYPES

            calc = FiberBudgetCalculator(
                sfp=COMMON_SFP["generic_1310_20km"],
                fiber_type=fiber_type,
                link_length_km=link_length,
            )
            calc.add_fiber()
            calc.add_splice(splice_method, num_splices)
            calc.add_connector("SC_UPC", 2)
            calc.add_bend_loss(max(2, int(link_length * 2)))
            calc.add_environment_degradation(0.5 if fiber_type == "drone_spent" else 0.3)

            result = calc.calculate()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Loss", f"{result['total_loss_db']:.1f} dB")
            m2.metric("RX Power", f"{result['rx_power_dbm']:.1f} dBm")
            m3.metric("Margin", f"{result['margin_db']:.1f} dB")
            m4.metric("Status", result["status"])

            st.subheader("Loss Breakdown")
            comp_data = {c["name"]: c["total_loss_db"] for c in result["components"]}
            st.bar_chart(comp_data)

            st.subheader("Full Result")
            st.json(result)

with tab_trophy:
    st.header("Trophy Intelligence Simulation")

    st.markdown("""
    **Scenario:** Connect to enemy fiber optic cable found on neutral ground.

    1. Find enemy cable (broken by artillery)
    2. Strip + cleave + quick connector (3-5 min)
    3. Connect portable OTDR
    4. Read enemy activity along THEIR cable
    """)

    if st.button("🏆 Run Trophy Intel Mission", key="run_trophy"):
        das = DASSimulator(fiber_length_m=5000)
        das.auto_segment()

        enemy_events = [
            {"time": 5, "position": 1200, "signature": TargetSignature.FOOTSTEP_SINGLE, "duration": 3},
            {"time": 15, "position": 2500, "signature": TargetSignature.FOOTSTEP_GROUP, "duration": 8},
            {"time": 25, "position": 3200, "signature": TargetSignature.WHEELED_VEHICLE, "duration": 10},
            {"time": 35, "position": 3800, "signature": TargetSignature.TRACKED_VEHICLE, "duration": 8},
            {"time": 45, "position": 4000, "signature": TargetSignature.EW_INTERFERENCE, "duration": 5},
            {"time": 50, "position": 4200, "signature": TargetSignature.DIGGING, "duration": 7},
        ]

        detected = das.simulate_scenario(duration_s=60, events=enemy_events)
        alerts = das.get_alerts(ThreatLevel.LOW)
        report = das.generate_report()

        st.subheader("Mission Report")
        m1, m2, m3 = st.columns(3)
        m1.metric("Enemy Activity Points", report.get("events_detected", 0))
        m2.metric("High Threats", report.get("high_threat_events", 0))
        m3.metric("Cable Range", f"{report.get('fiber_length_m', 0)}m")

        st.subheader("Enemy Positions Detected")
        for alert in alerts:
            threat = alert["threat"]
            icon = {"low": "👤", "medium": "⚠️", "high": "🔴", "critical": "💥"}.get(threat, "❓")
            st.text(f"  {icon} {alert['target']} at {alert['position_m']}m from our position ({alert['confidence']})")

        st.subheader("Assessment")
        has_armor = any(a["target"] in ("tracked_vehicle", "wheeled_vehicle") for a in alerts)
        has_cp = any(a["target"] == "ew_interference" for a in alerts)
        has_troops = any(a["target"] in ("footstep_group", "footstep_single") for a in alerts)

        if has_cp:
            st.warning("Command Post detected (EW + generator signatures)")
        if has_armor:
            st.error("Armor units detected — possible defensive position")
        if has_troops:
            st.info(f"Troop movement detected — {'patrol activity' if not has_armor else 'defensive garrison'}")

        st.subheader("Threat Map")
        breakdown = report.get("threat_breakdown", {})
        if breakdown:
            st.bar_chart(breakdown)
