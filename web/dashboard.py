#!/usr/bin/env python3
"""
TFN Streamlit Dashboard — Tactical Fiber Network Visualization
================================================================

Run: streamlit run web/dashboard.py

Requires: pip install streamlit numpy folium
"""

import streamlit as st
import numpy as np
import json
import random
import math
import time
from datetime import datetime

try:
    import folium
    from folium.plugins import MeasureControl, Draw
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

try:
    import streamlit.components.v1 as components
    HAS_COMPONENTS = True
except ImportError:
    HAS_COMPONENTS = False

sys_import = __import__
sys = sys_import("sys")
sys.path.insert(0, ".")

from simulation.mesh_simulator import MeshSimulator, MeshNode, FiberLink, GeoCoord, NodeType, LinkState
from simulation.das_simulator import DASSimulator, TargetSignature, ThreatLevel, EnvironmentalCondition
from simulation.rf_detector import RFDetectorSimulator, RFSource, RFSourceType

NODE_COLORS = {
    NodeType.TRENCH: "green",
    NodeType.RELAY: "blue",
    NodeType.BASE_STATION: "red",
    NodeType.DAS_INTERROGATOR: "purple",
}

NODE_LABELS = {
    NodeType.TRENCH: "Trench Node",
    NodeType.RELAY: "Relay Node",
    NodeType.BASE_STATION: "Base Station",
    NodeType.DAS_INTERROGATOR: "DAS Interrogator",
}

LINK_COLORS = {
    LinkState.ACTIVE: "green",
    LinkState.DEGRADED: "orange",
    LinkState.BROKEN: "red",
}

ENV_OPTIONS = {
    "Clear": EnvironmentalCondition.CLEAR,
    "Light Wind": EnvironmentalCondition.LIGHT_WIND,
    "Strong Wind": EnvironmentalCondition.STRONG_WIND,
    "Light Rain": EnvironmentalCondition.LIGHT_RAIN,
    "Heavy Rain": EnvironmentalCondition.HEAVY_RAIN,
}

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
st.caption("Zero-Emission Tactical Fiber Network | Тактична Оптоволоконна Мережа | Real-time Simulation")

if "mesh_sim" not in st.session_state:
    st.session_state["mesh_sim"] = None
    st.session_state["mesh_routes"] = {}
    st.session_state["mesh_status"] = None
    st.session_state["last_strike"] = None
    st.session_state["strike_timeline"] = []
    st.session_state["das_results"] = None
    st.session_state["das_report"] = None
    st.session_state["rf_results"] = None
    st.session_state["rf_report"] = None
    st.session_state["live_sim_log"] = []
    st.session_state["live_health_history"] = []
    st.session_state["survivability_nodes"] = None
    st.session_state["survivability_events"] = []

tab_tmap, tab_mesh, tab_livesim, tab_das, tab_rf, tab_budget, tab_surv, tab_trophy = st.tabs([
    "🗺️ Tactical Map", "🌐 Mesh Network", "⚡ Live Sim",
    "👂 DAS Sensing", "📡 RF Detection", "📊 Link Budget",
    "🛡️ Survivability", "🏆 Trophy Intel",
])

# ─────────────────────────────────────────────────────────────
# TAB: Tactical Map
# ─────────────────────────────────────────────────────────────
with tab_tmap:
    st.header("Tactical Map / Тактична Карта")

    if not HAS_FOLIUM:
        st.warning("Folium not installed. Install with: `pip install folium`")
        st.info("Falling back to text-based node listing.")

    sim = st.session_state.get("mesh_sim")

    if sim and HAS_FOLIUM:
        base_lat = np.mean([n.position.lat for n in sim.nodes.values()])
        base_lon = np.mean([n.position.lon for n in sim.nodes.values()])

        fmap = folium.Map(location=[base_lat, base_lon], zoom_start=13, tiles="OpenStreetMap")
        try:
            fmap.add_child(MeasureControl())
            fmap.add_child(Draw())
        except Exception:
            pass

        for nid, node in sim.nodes.items():
            color = NODE_COLORS.get(node.node_type, "gray")
            icon_html = f"""
            <div style="font-size:12px;color:white;background:{color};
                        border-radius:50%;width:28px;height:28px;text-align:center;
                        line-height:28px;font-weight:bold;">{nid[-3:]}</div>
            """
            popup_text = (
                f"<b>{nid}</b><br>Type: {NODE_LABELS.get(node.node_type, node.node_type.value)}<br>"
                f"Lat: {node.position.lat:.5f}<br>Lon: {node.position.lon:.5f}<br>"
                f"Battery: {node.battery_current_wh:.1f}/{node.battery_capacity_wh:.1f} Wh<br>"
                f"Alive: {'✅' if node.is_alive else '❌'}"
            )
            folium.Marker(
                location=[node.position.lat, node.position.lon],
                popup=folium.Popup(popup_text, max_width=250),
                icon=folium.DivIcon(html=icon_html),
                tooltip=f"{nid} ({NODE_LABELS.get(node.node_type, '')})",
            ).add_to(fmap)

        for lid, link in sim.links.items():
            na = sim.nodes.get(link.node_a)
            nb = sim.nodes.get(link.node_b)
            if na and nb:
                color = LINK_COLORS.get(link.state, "gray")
                weight = 4 if link.state == LinkState.ACTIVE else 2
                dash = "5,5" if link.state == LinkState.BROKEN else None
                folium.PolyLine(
                    locations=[
                        [na.position.lat, na.position.lon],
                        [nb.position.lat, nb.position.lon],
                    ],
                    color=color,
                    weight=weight,
                    opacity=0.8,
                    dash_array=dash,
                    popup=f"<b>{lid}</b><br>State: {link.state.value}<br>"
                          f"Length: {link.length_m/1000:.2f} km<br>Loss: {link.total_loss_db:.1f} dB",
                    tooltip=f"{link.state.value}: {link.length_m/1000:.1f}km",
                ).add_to(fmap)

                if link.has_das and link.state != LinkState.BROKEN:
                    mid_lat = (na.position.lat + nb.position.lat) / 2
                    mid_lon = (na.position.lon + nb.position.lon) / 2
                    folium.CircleMarker(
                        location=[mid_lat, mid_lon],
                        radius=4,
                        color="purple",
                        fill=True,
                        fill_opacity=0.6,
                        popup=f"DAS sensor on {lid}",
                        tooltip="DAS Sensor",
                    ).add_to(fmap)

        for event in sim.events:
            if event.get("type") == "artillery_impact":
                pos = event.get("position", {})
                lat_e = pos.get("lat", base_lat)
                lon_e = pos.get("lon", base_lon)
                blast = event.get("blast_radius_m", 100)
                folium.Circle(
                    location=[lat_e, lon_e],
                    radius=blast,
                    color="red",
                    fill=True,
                    fill_opacity=0.25,
                    popup=f"Artillery Impact<br>Blast: {blast}m<br>Links damaged: {event.get('links_damaged', 0)}",
                    tooltip="Artillery Impact",
                ).add_to(fmap)
                folium.Marker(
                    location=[lat_e, lon_e],
                    icon=folium.Icon(color="red", icon="explosion", prefix="fa"),
                    popup=f"Impact at ({lat_e:.4f}, {lon_e:.4f})",
                ).add_to(fmap)

        map_html = fmap.get_root().render()
        if HAS_COMPONENTS:
            components.html(map_html, height=600)
        else:
            st.components.v1.html(map_html, height=600)

        st.subheader("Map Legend / Легенда карти")
        lc1, lc2, lc3, lc4 = st.columns(4)
        lc1.markdown("🟢 **Trench Node**")
        lc2.markdown("🔵 **Relay Node**")
        lc3.markdown("🔴 **Base Station**")
        lc4.markdown("🟣 **DAS Interrogator**")

    elif sim and not HAS_FOLIUM:
        st.subheader("Node Positions (text fallback)")
        for nid, node in sim.nodes.items():
            st.text(f"  {nid} ({NODE_LABELS.get(node.node_type, '')}): "
                    f"({node.position.lat:.4f}, {node.position.lon:.4f}) "
                    f"Battery: {node.battery_current_wh:.1f}Wh")
    else:
        st.info("Deploy a mesh network first (Mesh Network tab) to see the tactical map.")

# ─────────────────────────────────────────────────────────────
# TAB: Mesh Network (enhanced)
# ─────────────────────────────────────────────────────────────
with tab_mesh:
    st.header("Mesh Network Simulation / Симуляція Мережі")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Parameters / Параметри")
        num_nodes = st.slider("Number of nodes", 3, 15, 8, key="mesh_nodes")
        area_km = st.slider("Area radius (km)", 1.0, 10.0, 3.0, key="mesh_area")
        max_link_km = st.slider("Max link distance (km)", 1.0, 10.0, 5.0, key="mesh_maxlink")

        if st.button("🚀 Deploy Network", key="deploy"):
            sim = MeshSimulator()
            sim.deploy_random_mesh(num_nodes=num_nodes, area_km=area_km)
            st.session_state["mesh_sim"] = sim
            st.session_state["mesh_routes"] = sim.compute_routing()
            st.session_state["mesh_status"] = sim.get_network_status()
            st.session_state["last_strike"] = None
            st.session_state["strike_timeline"] = []

        if st.button("💥 Artillery Strike", key="artillery") and st.session_state["mesh_sim"]:
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
            timeline = st.session_state.get("strike_timeline", [])
            timeline.append({
                "time": datetime.utcnow().isoformat(),
                "connectivity": sim.get_network_status()["connectivity_pct"],
                "links_active": sim.get_network_status()["links_active"],
                "links_total": sim.get_network_status()["links_total"],
            })
            st.session_state["strike_timeline"] = timeline

        if st.button("⏰ Simulate 24h", key="sim24") and st.session_state["mesh_sim"]:
            sim = st.session_state["mesh_sim"]
            for _ in range(24):
                sim.simulate_time_step(1.0)
            st.session_state["mesh_status"] = sim.get_network_status()

    with col2:
        sim = st.session_state["mesh_sim"]
        if sim:
            status = st.session_state.get("mesh_status", sim.get_network_status())

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Nodes Alive", f"{status['nodes_alive']}/{status['nodes_total']}")
            m2.metric("Active Links", f"{status['links_active']}/{status['links_total']}")
            m3.metric("Connectivity", f"{status['connectivity_pct']}%")
            m4.metric("Avg Battery", f"{status['avg_battery_hours']:.0f}h")

            health_score = status["connectivity_pct"] * (status["nodes_alive"] / max(status["nodes_total"], 1))
            health_color = "🟢" if health_score >= 70 else ("🟡" if health_score >= 40 else "🔴")
            st.subheader(f"Network Health Score: {health_color} {health_score:.1f}/100")

            st.subheader("Node Power Status / Статус живлення вузлів")
            for nid, node in sim.nodes.items():
                batt_pct = (node.battery_current_wh / node.battery_capacity_wh * 100) if node.battery_capacity_wh > 0 else 0
                batt_icon = "🔋" if batt_pct > 60 else ("🪫" if batt_pct > 20 else "☠️")
                state_str = "ONLINE" if node.is_alive else "OFFLINE"
                st.text(f"  {batt_icon} {nid} ({NODE_LABELS.get(node.node_type, '')}): "
                        f"{batt_pct:.0f}% ({node.battery_current_wh:.1f}Wh) | {state_str} | "
                        f"{node.battery_hours:.1f}h remaining")

            st.subheader("Link Analysis / Аналіз з'єднань")
            for lid, link in sim.links.items():
                state_icon = {"active": "🟢", "degraded": "🟡", "broken": "🔴"}.get(link.state.value, "❓")
                check = sim.check_link_feasibility(link)
                bw_est = max(0.1, 10.0 - link.total_loss_db * 0.3) if link.state != LinkState.BROKEN else 0
                lat_est = (link.length_m / 200000) + (0.5 if link.state == LinkState.DEGRADED else 0.1)
                st.text(f"  {state_icon} {lid}: {link.length_m/1000:.1f}km, "
                        f"loss={check['total_loss_db']}dB, BW≈{bw_est:.1f}Gbps, "
                        f"lat≈{lat_est:.2f}ms [{check['recommendation']}]")

            routes = st.session_state.get("mesh_routes", {})
            if routes:
                st.subheader("Routes & Backup Paths / Маршрути та резервні шляхи")
                for key, route in list(routes.items())[:10]:
                    path_str = " → ".join(route["path"])
                    hops = route["hops"]
                    cost = route["total_cost"]
                    bw_route = max(0.1, 10.0 - cost * 0.3)
                    lat_route = hops * 0.15 + cost * 0.01
                    st.text(f"  {key}: {path_str} ({hops} hops, "
                            f"cost={cost:.1f}, BW≈{bw_route:.1f}Gbps, lat≈{lat_route:.2f}ms)")

            if st.session_state.get("last_strike"):
                strike = st.session_state["last_strike"]
                st.subheader("Last Artillery Strike / Останній артобстріл")
                st.json({
                    "links_damaged": strike["links_damaged"],
                    "blast_radius_m": strike["blast_radius_m"],
                })

            timeline = st.session_state.get("strike_timeline", [])
            if len(timeline) > 1:
                st.subheader("Degradation Timeline / Часова шкала деградації")
                timeline_data = {t["time"][-8:]: t["connectivity"] for t in timeline}
                st.line_chart(timeline_data)
        else:
            st.info("Click 'Deploy Network' to start simulation / Натисніть 'Deploy Network'")

# ─────────────────────────────────────────────────────────────
# TAB: Live Simulation
# ─────────────────────────────────────────────────────────────
with tab_livesim:
    st.header("Live Simulation / Симуляція в реальному часі")

    st.markdown("""
    **Scenario:** Auto-deploy mesh → sustained artillery fire → observe degradation.
    
    **Сценарій:** Автоматичне розгортання мережі → масований артобстріл → спостереження деградації.
    """)

    lc1, lc2 = st.columns([1, 3])

    with lc1:
        live_nodes = st.slider("Nodes for live sim", 4, 12, 8, key="live_nodes")
        live_strikes = st.slider("Artillery strikes", 1, 15, 5, key="live_strikes")
        live_speed = st.selectbox("Animation speed", ["Fast", "Normal", "Slow"], index=1, key="live_speed")

        if st.button("▶ Start Live Simulation", key="start_live"):
            sim = MeshSimulator()
            sim.deploy_random_mesh(num_nodes=live_nodes, area_km=3.0)
            st.session_state["mesh_sim"] = sim
            st.session_state["mesh_routes"] = sim.compute_routing()
            st.session_state["mesh_status"] = sim.get_network_status()
            st.session_state["live_sim_log"] = []
            st.session_state["live_health_history"] = [sim.get_network_status()["connectivity_pct"]]

            delay_map = {"Fast": 0.1, "Normal": 0.3, "Slow": 0.8}
            delay = delay_map.get(live_speed, 0.3)

            nodes = list(sim.nodes.values())

            log_placeholder = st.empty()
            health_placeholder = st.empty()
            metrics_placeholder = st.empty()

            log_entries = []
            health_history = [sim.get_network_status()["connectivity_pct"]]

            for i in range(live_strikes):
                target = random.choice(nodes)
                result = sim.simulate_artillery_damage(
                    target.position.lat + random.uniform(-0.005, 0.005),
                    target.position.lon + random.uniform(-0.005, 0.005),
                    blast_radius_m=random.uniform(50, 200),
                )
                status = sim.get_network_status()
                health_history.append(status["connectivity_pct"])

                log_entries.append(
                    f"Strike #{i+1}: {result['links_damaged']} links damaged | "
                    f"Connectivity: {status['connectivity_pct']}% | "
                    f"Alive: {status['nodes_alive']}/{status['nodes_total']}"
                )

                with metrics_placeholder.container():
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Strike", f"#{i+1}/{live_strikes}")
                    mc2.metric("Connectivity", f"{status['connectivity_pct']}%")
                    mc3.metric("Links Active", f"{status['links_active']}/{status['links_total']}")
                    mc4.metric("Nodes Alive", f"{status['nodes_alive']}/{status['nodes_total']}")

                with health_placeholder.container():
                    st.subheader("Network Health Over Time")
                    st.line_chart({"Connectivity %": health_history})

                with log_placeholder.container():
                    st.subheader("Strike Log")
                    for entry in log_entries:
                        if "0 links" in entry:
                            st.text(f"  💨 {entry}")
                        elif "connectivity" in entry.lower() and float(entry.split("Connectivity: ")[1].split("%")[0]) < 40:
                            st.text(f"  💥 {entry}")
                        else:
                            st.text(f"  🔥 {entry}")

                time.sleep(delay)

            st.session_state["live_sim_log"] = log_entries
            st.session_state["live_health_history"] = health_history
            st.session_state["mesh_routes"] = sim.compute_routing()
            st.session_state["mesh_status"] = sim.get_network_status()
            st.session_state["strike_timeline"] = [
                {"time": f"Strike {i+1}", "connectivity": h,
                 "links_active": 0, "links_total": 0}
                for i, h in enumerate(health_history)
            ]

    with lc2:
        log_entries = st.session_state.get("live_sim_log", [])
        health_history = st.session_state.get("live_health_history", [])
        sim = st.session_state.get("mesh_sim")

        if log_entries:
            st.subheader("Last Run Summary")
            if health_history:
                st.line_chart({"Connectivity %": health_history})
            for entry in log_entries:
                st.text(f"  {entry}")

            if sim:
                final = sim.get_network_status()
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Final Connectivity", f"{final['connectivity_pct']}%")
                sc2.metric("Surviving Nodes", f"{final['nodes_alive']}/{final['nodes_total']}")
                sc3.metric("Mesh Healthy", "✅" if final["mesh_healthy"] else "❌")
        elif sim:
            st.info("Run a live simulation above to see real-time degradation.")
        else:
            st.info("No mesh deployed yet. Click 'Start Live Simulation'.")

# ─────────────────────────────────────────────────────────────
# TAB: DAS Sensing (enhanced)
# ─────────────────────────────────────────────────────────────
with tab_das:
    st.header("DAS — Distributed Acoustic Sensing / Розподілене акустичне зондування")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Configuration / Конфігурація")
        fiber_length = st.slider("Fiber length (m)", 1000, 20000, 5000, key="das_length")
        duration = st.slider("Duration (s)", 10, 300, 60, key="das_duration")

        env_label = st.selectbox(
            "Environmental Condition / Умови середовища",
            list(ENV_OPTIONS.keys()),
            index=0,
            key="das_env",
        )
        env_cond = ENV_OPTIONS[env_label]

        st.subheader("Inject Events / Вставити події")
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
            das = DASSimulator(fiber_length_m=fiber_length, env_condition=env_cond)
            das.auto_segment()
            detected = das.simulate_scenario(duration_s=duration, events=events_to_inject)
            st.session_state["das_results"] = das.get_alerts(ThreatLevel.LOW)
            st.session_state["das_report"] = das.generate_report()
            st.session_state["das_env"] = env_cond

        if st.button("📈 Generate FFT Waveform", key="gen_fft"):
            das_tmp = DASSimulator(fiber_length_m=fiber_length, env_condition=env_cond)
            sig_type = random.choice([
                TargetSignature.FOOTSTEP_GROUP,
                TargetSignature.TRACKED_VEHICLE,
                TargetSignature.ARTILLERY_FIRE,
                TargetSignature.DRONE_HOVER,
                TargetSignature.DIGGING,
            ])
            waveform = das_tmp.generate_fft_signature(sig_type, duration_s=0.1, sample_rate=1000)
            st.session_state["das_fft"] = waveform
            st.session_state["das_fft_label"] = sig_type.value

    with col2:
        if st.session_state.get("das_results"):
            alerts = st.session_state["das_results"]
            report = st.session_state.get("das_report", {})

            m1, m2, m3 = st.columns(3)
            m1.metric("Events Detected", report.get("events_detected", 0))
            m2.metric("High Threats", report.get("high_threat_events", 0))
            m3.metric("Fiber Length", f"{report.get('fiber_length_m', 0)}m")

            active_env = st.session_state.get("das_env", EnvironmentalCondition.CLEAR)
            if isinstance(active_env, EnvironmentalCondition):
                das_tmp = DASSimulator(env_condition=active_env)
                far = das_tmp.get_false_alarm_rate()
                st.subheader(f"False Alarm Rate ({active_env.value})")
                fc1, fc2, fc3, fc4 = st.columns(4)
                fc1.metric("Wind noise/h", far["wind_noise_per_h"])
                fc2.metric("Rain noise/h", far["rain_noise_per_h"])
                fc3.metric("Traffic/h", far["distant_traffic_per_h"])
                fc4.metric("Total/h", far["total_per_h"])

            st.subheader("Alerts / Тривоги (with SNR)")
            for alert in alerts:
                threat = alert["threat"]
                color = {"none": "⚪", "low": "🟡", "medium": "🟠", "high": "🔴", "critical": "💥"}.get(threat, "❓")
                st.text(
                    f"  {color} [{alert['target']}] {alert['position_m']}m — "
                    f"{alert['confidence']} ({threat}) SNR={alert.get('snr_db', 'N/A')}dB"
                )

            st.subheader("Threat Breakdown")
            breakdown = report.get("threat_breakdown", {})
            if breakdown:
                st.bar_chart(breakdown)

            fft_data = st.session_state.get("das_fft")
            if fft_data:
                st.subheader(f"FFT Waveform: {st.session_state.get('das_fft_label', 'unknown')}")
                st.line_chart(fft_data)
        else:
            st.info("Configure and run DAS simulation / Налаштуйте та запустіть DAS симуляцію")

# ─────────────────────────────────────────────────────────────
# TAB: RF Detection
# ─────────────────────────────────────────────────────────────
with tab_rf:
    st.header("RF-Opto Hybrid Detection (Passive) / Радіо-Оптичне Виявлення")

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
        if st.session_state.get("rf_results"):
            results = st.session_state["rf_results"]
            report = st.session_state["rf_report"]

            m1, m2, m3 = st.columns(3)
            m1.metric("Scanned", report["total_sources_scanned"])
            m2.metric("Detected", report["detected"])
            m3.metric("Rate", report["detection_rate"])

            st.subheader("Detections / Виявлення")
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
            st.info("Select RF sources and click 'Scan' / Виберіть джерела та натисніть 'Scan'")

# ─────────────────────────────────────────────────────────────
# TAB: Link Budget
# ─────────────────────────────────────────────────────────────
with tab_budget:
    st.header("Optical Link Budget Calculator / Калькулятор оптичного бюджету")

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

# ─────────────────────────────────────────────────────────────
# TAB: Survivability
# ─────────────────────────────────────────────────────────────
with tab_surv:
    st.header("Survivability / Живучість мережі")

    sc1, sc2 = st.columns([1, 2])

    with sc1:
        st.subheader("Node Concealment Checklist / Контроль маскування")
        concealment_items = [
            ("Visual concealment (camo net/earth)", "Візуальне маскування", True),
            ("Thermal signature suppression", "Придушення теплової сигнатури", False),
            ("Pattern disruption (break straight lines)", "Порушення геометричних ліній", True),
            ("Cable burial depth ≥ 30cm", "Глибина закладення кабелю ≥ 30см", False),
            ("EM silent (no RF emissions)", "ЕМ мовчання (немає радіовипромінювання)", True),
            ("IR signature minimal", "ІЧ сигнатура мінімальна", False),
        ]
        for eng, ukr, default in concealment_items:
            checked = st.checkbox(eng, value=default, key=f"conceal_{eng[:20]}")
            if not checked:
                st.caption(f"  ⚠️ {ukr} — NOT CHECKED")

        st.subheader("Cable Deployment Guidelines")
        st.markdown("""
        **Рекомендації з прокладання кабелю:**
        - 🟢 Use existing terrain features (trenches, ditches)
        - 🟢 Avoid straight lines — use zigzag patterns
        - 🟢 Burial depth: 30-50cm minimum
        - 🟡 Avoid roads (vehicle damage risk)
        - 🔴 Never cross open ground without burial
        - 🔴 Mark cable routes for friendly forces only
        """)

        st.subheader("Pre-built Scenario")
        if st.button("🎯 Run 10-Node Sustained Fire Scenario", key="run_surv_scenario"):
            sim = MeshSimulator()
            sim.deploy_random_mesh(num_nodes=10, area_km=4.0, base_lat=48.5, base_lon=36.3)

            timeline_data = []
            initial = sim.get_network_status()
            timeline_data.append({"step": "Deploy", "connectivity": initial["connectivity_pct"],
                                  "nodes": initial["nodes_alive"], "event": "Initial deployment"})

            for wave in range(8):
                nodes = list(sim.nodes.values())
                target = random.choice(nodes)
                sim.simulate_artillery_damage(
                    target.position.lat + random.uniform(-0.005, 0.005),
                    target.position.lon + random.uniform(-0.005, 0.005),
                    blast_radius_m=random.uniform(60, 180),
                )
                sim.simulate_time_step(1.0)
                status = sim.get_network_status()
                timeline_data.append({
                    "step": f"Strike {wave+1}",
                    "connectivity": status["connectivity_pct"],
                    "nodes": status["nodes_alive"],
                    "event": f"Artillery wave {wave+1}",
                })

            final = sim.get_network_status()
            timeline_data.append({"step": "Final", "connectivity": final["connectivity_pct"],
                                  "nodes": final["nodes_alive"], "event": "Assessment"})

            st.session_state["survivability_nodes"] = sim
            st.session_state["survivability_events"] = timeline_data
            st.session_state["mesh_sim"] = sim
            st.session_state["mesh_status"] = final

        st.subheader("🎯 Find the Node Challenge")
        st.markdown("""
        Try to find a hidden node. Click a position on the map to check
        if a concealed node would be visible from that angle.
        / Спробуйте знайти прихований вузол.
        """)
        guess_lat = st.number_input("Guess latitude offset", value=0.001, step=0.001, key="surv_guess_lat", format="%.4f")
        guess_lon = st.number_input("Guess longitude offset", value=0.001, step=0.001, key="surv_guess_lon", format="%.4f")

        if st.button("🔍 Check Visibility", key="check_vis"):
            sim_s = st.session_state.get("survivability_nodes") or st.session_state.get("mesh_sim")
            if sim_s:
                base_node = list(sim_s.nodes.values())[0]
                guess_pos = GeoCoord(
                    lat=base_node.position.lat + guess_lat,
                    lon=base_node.position.lon + guess_lon,
                )
                found = False
                for nid, node in sim_s.nodes.items():
                    dist = guess_pos.distance_to(node.position)
                    if dist < 200:
                        st.success(f"✅ Node {nid} found! Distance: {dist:.0f}m")
                        found = True
                        break
                if not found:
                    nearest = min(sim_s.nodes.values(), key=lambda n: guess_pos.distance_to(n.position))
                    nearest_dist = guess_pos.distance_to(nearest.position)
                    st.error(f"❌ No node within 200m. Nearest: {nearest.id} at {nearest_dist:.0f}m")
            else:
                st.warning("Deploy a network first.")

    with sc2:
        timeline_data = st.session_state.get("survivability_events", [])
        if timeline_data:
            st.subheader("Degradation Timeline / Шкала деградації")
            conn_data = {t["step"]: t["connectivity"] for t in timeline_data}
            st.line_chart(conn_data)

            st.subheader("Event Log")
            for entry in timeline_data:
                icon = "🟢" if entry["connectivity"] >= 70 else ("🟡" if entry["connectivity"] >= 40 else "🔴")
                st.text(f"  {icon} {entry['step']}: Connectivity={entry['connectivity']}%, "
                        f"Nodes={entry['nodes']}, {entry['event']}")

            st.subheader("Survivability Assessment")
            final_conn = timeline_data[-1]["connectivity"]
            initial_conn = timeline_data[0]["connectivity"]
            degradation = initial_conn - final_conn
            if final_conn >= 70:
                st.success(f"Network highly survivable. Only {degradation:.1f}% connectivity loss under sustained fire.")
            elif final_conn >= 40:
                st.warning(f"Network partially degraded. {degradation:.1f}% connectivity loss. Consider adding relay nodes.")
            else:
                st.error(f"Network severely degraded. {degradation:.1f}% connectivity loss. Redundancy needed.")
        else:
            st.info("Run the sustained fire scenario to see survivability analysis.")

# ─────────────────────────────────────────────────────────────
# TAB: Trophy Intel
# ─────────────────────────────────────────────────────────────
with tab_trophy:
    st.header("Trophy Intelligence Simulation / Трофейна Розвідка")

    st.markdown("""
    **Scenario:** Connect to enemy fiber optic cable found on neutral ground.
    **Сценарій:** Підключення до ворожого оптоволоконного кабелю знайденого на нейтральній смузі.

    1. Find enemy cable (broken by artillery) / Знайти ворожий кабель (зруйнований артилерією)
    2. Strip + cleave + quick connector (3-5 min)
    3. Connect portable OTDR / Підключити портативний OTDR
    4. Read enemy activity along THEIR cable / Зчитати ворожу активність вздовж ЇХНЬОГО кабелю
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

        st.subheader("Mission Report / Звіт місії")
        m1, m2, m3 = st.columns(3)
        m1.metric("Enemy Activity Points", report.get("events_detected", 0))
        m2.metric("High Threats", report.get("high_threat_events", 0))
        m3.metric("Cable Range", f"{report.get('fiber_length_m', 0)}m")

        st.subheader("Enemy Positions Detected / Виявлені позиції ворога")
        for alert in alerts:
            threat = alert["threat"]
            icon = {"low": "👤", "medium": "⚠️", "high": "🔴", "critical": "💥"}.get(threat, "❓")
            st.text(f"  {icon} {alert['target']} at {alert['position_m']}m from our position ({alert['confidence']})")

        st.subheader("Assessment / Оцінка")
        has_armor = any(a["target"] in ("tracked_vehicle", "wheeled_vehicle") for a in alerts)
        has_cp = any(a["target"] == "ew_interference" for a in alerts)
        has_troops = any(a["target"] in ("footstep_group", "footstep_single") for a in alerts)

        if has_cp:
            st.warning("Command Post detected (EW + generator signatures) / Виявлено командний пункт")
        if has_armor:
            st.error("Armor units detected — possible defensive position / Виявлено бронетехніку")
        if has_troops:
            st.info(f"Troop movement detected — {'patrol activity' if not has_armor else 'defensive garrison'} / Рух особового складу")

        st.subheader("Threat Map / Карта загроз")
        breakdown = report.get("threat_breakdown", {})
        if breakdown:
            st.bar_chart(breakdown)

# ─────────────────────────────────────────────────────────────
# PDF / JSON Export
# ─────────────────────────────────────────────────────────────
st.divider()

ec1, ec2, ec3 = st.columns([1, 1, 1])

with ec1:
    st.subheader("Export Report")

with ec2:
    if st.button("📄 Generate Report", key="gen_report"):
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "type": "TFN SpiderLink Dashboard Report",
        }

        sim = st.session_state.get("mesh_sim")
        if sim:
            status = st.session_state.get("mesh_status") or sim.get_network_status()
            report["mesh"] = {
                "status": status,
                "nodes": {
                    nid: {
                        "type": node.node_type.value,
                        "position": {"lat": node.position.lat, "lon": node.position.lon},
                        "battery_pct": round(node.battery_current_wh / node.battery_capacity_wh * 100, 1) if node.battery_capacity_wh > 0 else 0,
                        "alive": node.is_alive,
                        "battery_hours": round(node.battery_hours, 1),
                    }
                    for nid, node in sim.nodes.items()
                },
                "links": {
                    lid: {
                        "state": link.state.value,
                        "length_km": round(link.length_m / 1000, 2),
                        "loss_db": link.total_loss_db,
                    }
                    for lid, link in sim.links.items()
                },
                "events_count": len(sim.events),
            }

        if st.session_state.get("das_results"):
            report["das"] = {
                "alerts": st.session_state["das_results"],
                "report": st.session_state.get("das_report", {}),
            }

        if st.session_state.get("rf_results"):
            report["rf"] = {
                "detections": [
                    {
                        "type": r.source_type.value,
                        "detected": r.detected,
                        "snr_db": r.snr_db,
                        "method": r.method,
                    }
                    for r in st.session_state["rf_results"]
                ],
                "report": st.session_state.get("rf_report", {}),
            }

        timeline = st.session_state.get("strike_timeline", [])
        if timeline:
            report["strike_timeline"] = timeline

        health_history = st.session_state.get("live_health_history", [])
        if health_history:
            report["live_health_history"] = health_history

        survivability_events = st.session_state.get("survivability_events", [])
        if survivability_events:
            report["survivability"] = survivability_events

        st.session_state["export_report"] = report

with ec3:
    report = st.session_state.get("export_report")
    if report:
        st.download_button(
            "⬇️ Download Report (JSON)",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name=f"tfn_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="download_report",
        )
    else:
        st.caption("Click 'Generate Report' first.")
