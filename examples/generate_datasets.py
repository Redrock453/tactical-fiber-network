#!/usr/bin/env python3
"""
TFN Example Dataset Generator
===============================

Generates synthetic datasets for testing and training:
1. DAS vibration signatures (11 target types)
2. RF-Opto detection samples
3. Mesh network event logs
4. OTDR traces with breaks

Run: python3 examples/generate_datasets.py
Output: examples/data/ (JSON files)
"""

import json
import math
import random
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.das_simulator import (
    DASSimulator, TargetSignature, ThreatLevel, FiberSegment
)
from simulation.rf_detector import RFDetectorSimulator, RFSource, RFSourceType
from simulation.mesh_simulator import MeshSimulator, NodeType

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")


def generate_das_dataset(num_samples=500):
    print(f"  Generating DAS dataset ({num_samples} samples)...")
    samples = []

    target_types = [t for t in TargetSignature if t != TargetSignature.SILENCE]

    for i in range(num_samples):
        target = random.choice(target_types)
        fiber_length = random.uniform(2000, 10000)
        position = random.uniform(100, fiber_length - 100)

        das = DASSimulator(fiber_length_m=fiber_length, spatial_resolution_m=1.0)
        das.add_segment(FiberSegment(
            start_m=0, end_m=fiber_length / 2,
            terrain=random.choice(["ground", "trench", "field"]),
            burial_depth_m=random.uniform(0, 0.3),
        ))
        das.add_segment(FiberSegment(
            start_m=fiber_length / 2, end_m=fiber_length,
            terrain=random.choice(["road", "forest", "ground"]),
            burial_depth_m=random.uniform(0, 0.2),
        ))

        events = [{
            "time": random.uniform(2, 30),
            "position": position,
            "signature": target,
            "duration": random.uniform(0.5, 5.0),
        }]

        detected = das.simulate_scenario(duration_s=35, events=events)

        sample = {
            "id": f"das_{i:04d}",
            "target_type": target.value,
            "fiber_length_m": fiber_length,
            "position_m": position,
            "events_detected": len(detected),
            "alerts": das.get_alerts(ThreatLevel.LOW),
            "report": das.generate_report(),
        }
        samples.append(sample)

    return samples


def generate_rf_dataset(num_samples=300):
    print(f"  Generating RF-Opto dataset ({num_samples} samples)...")
    samples = []

    for i in range(num_samples):
        src_type = random.choice(list(RFSourceType))
        from simulation.rf_detector import RF_PROFILES
        profile = RF_PROFILES[src_type]

        freq = random.uniform(*profile["freq_range"])
        power = random.uniform(*profile["power_range"])
        distance = random.uniform(*profile["typical_distance"])
        position = random.uniform(100, 4900)

        source = RFSource(
            source_type=src_type,
            frequency_hz=freq,
            power_w=power,
            distance_to_fiber_m=distance,
            position_m_on_fiber=position,
            modulation=random.choice(profile["modulation"]),
        )

        detector = RFDetectorSimulator(fiber_length_m=5000)
        result = detector.detect_source(source)

        sample = {
            "id": f"rf_{i:04d}",
            "source_type": src_type.value,
            "frequency_hz": freq,
            "power_w": power,
            "distance_m": distance,
            "position_m": position,
            "detected": result.detected,
            "phase_shift_rad": result.phase_shift_rad,
            "snr_db": result.snr_db,
            "method": result.method,
        }
        samples.append(sample)

    return samples


def generate_mesh_dataset(num_networks=50):
    print(f"  Generating mesh event dataset ({num_networks} networks)...")
    all_events = []

    for i in range(num_networks):
        sim = MeshSimulator()
        num_nodes = random.randint(4, 12)
        sim.deploy_random_mesh(num_nodes=num_nodes, area_km=random.uniform(2, 8))

        initial = sim.get_network_status()

        num_strikes = random.randint(0, 3)
        for _ in range(num_strikes):
            target = random.choice(list(sim.nodes.values()))
            sim.simulate_artillery_damage(
                target.position.lat + random.uniform(-0.005, 0.005),
                target.position.lon + random.uniform(-0.005, 0.005),
                blast_radius_m=random.uniform(30, 150),
            )

        sim.compute_routing()
        final = sim.get_network_status()

        all_events.append({
            "id": f"mesh_{i:04d}",
            "num_nodes": num_nodes,
            "initial_connectivity": initial["connectivity_pct"],
            "strikes": num_strikes,
            "final_connectivity": final["connectivity_pct"],
            "links_broken": initial["links_active"] - final["links_active"],
            "mesh_healthy": final["mesh_healthy"],
            "events_logged": len(sim.events),
        })

    return all_events


def generate_otdr_dataset(num_traces=100):
    print(f"  Generating OTDR trace dataset ({num_traces} traces)...")
    from analytics.break_locator import BreakLocator

    samples = []

    for i in range(num_traces):
        locator = BreakLocator(fiber_length_m=random.uniform(2000, 15000))
        num_breaks = random.choices([0, 1, 2, 3], weights=[30, 40, 20, 10])[0]
        num_splices = random.randint(1, 5)

        breaks = [{"position_m": random.uniform(500, locator.fiber_length - 500),
                    "return_loss_db": random.uniform(8, 20)} for _ in range(num_breaks)]
        splices = [{"position_m": random.uniform(200, locator.fiber_length - 200),
                     "loss_db": random.uniform(0.05, 0.3)} for _ in range(num_splices)]

        locator.generate_otdr_trace(
            breaks=breaks if breaks else None,
            splices=splices,
            attenuation_db_km=random.uniform(0.2, 0.5),
        )

        report = locator.generate_report()

        samples.append({
            "id": f"otdr_{i:04d}",
            "fiber_length_m": locator.fiber_length,
            "num_breaks_injected": num_breaks,
            "num_splices_injected": num_splices,
            "breaks_found": report["breaks_found"],
            "fiber_status": report["fiber_status"],
            "usable_length_m": report["usable_length_m"],
        })

    return samples


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("TFN DATASET GENERATOR")
    print("=" * 60)
    print()

    datasets = {
        "das_signatures.json": generate_das_dataset(500),
        "rf_detections.json": generate_rf_dataset(300),
        "mesh_events.json": generate_mesh_dataset(50),
        "otdr_traces.json": generate_otdr_dataset(100),
    }

    for filename, data in datasets.items():
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {path} ({len(data)} samples)")

    print()

    stats = {}
    for filename, data in datasets.items():
        stats[filename] = len(data)

    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_samples": sum(stats.values()),
            "datasets": stats,
        }, f, indent=2)

    print(f"  Summary: {summary_path}")
    print(f"  Total samples: {sum(stats.values())}")
    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
