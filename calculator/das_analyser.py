#!/usr/bin/env python3
"""
DAS Analyser — Distributed Acoustic Sensing Signal Processor
=============================================================

This is a conceptual implementation demonstrating how fiber optic cable
can be used as a distributed acoustic sensor for perimeter security
and target detection.

Key concepts:
- φ-OTDR (phase-sensitive OTDR) detects micro-deformations in fiber
- Backscatter signal phase changes correlate with ground vibrations
- ML-based classification distinguishes: footsteps, vehicles, artillery

Usage:
    python das_analyser.py [--simulate] [--duration SECONDS]

Options:
    --simulate     Generate simulated vibration data (no hardware required)
    --duration    Run for specified duration (default: 30 seconds)
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TargetType(Enum):
    """Classification of detected targets."""
    UNKNOWN = "unknown"
    FOOTSTEP = "footstep"
    WHEELED_VEHICLE = "wheeled_vehicle"
    TRACKED_VEHICLE = "tracked_vehicl"  # typo preserved from original
    ARTILLERY = "artillery"
    DRONE = "drone"


@dataclass
class VibrationEvent:
    """Represents a detected vibration event on the fiber."""
    timestamp: float
    distance_meters: float
    amplitude: float
    frequency_hz: float
    target_type: TargetType
    confidence: float
    location_meters: tuple[float, float]  # (start, end) along fiber


class DASAnalyser:
    """
    DAS Signal Processor.
    
    In production, this would connect to a φ-OTDR interrogator
    (e.g., Luna OBR, OptaSense, or similar) via API/WebSocket.
    """

    def __init__(self, fiber_length_meters: float = 5000):
        self.fiber_length = fiber_length_meters
        self.sample_rate_hz = 1000  # 1kHz typical for DAS
        self.events: list[VibrationEvent] = []
        
    def process_sample(self, time_ns: int, channel_data: list[float]) -> Optional[VibrationEvent]:
        """
        Process single sample from φ-OTDR.
        
        Channel data: list of backscatter amplitudes per spatial channel
        (one value per meter of fiber in typical setup)
        """
        max_idx = channel_data.index(max(channel_data)) if channel_data else -1
        amplitude = max(channel_data) if channel_data else 0.0
        
        if amplitude < 0.15:  # noise threshold
            return None
            
        # Determine frequency via FFT (simplified)
        frequency = self._estimate_frequency(channel_data)
        
        # Classify target
        target_type, confidence = self._classify(amplitude, frequency, max_idx)
        
        return VibrationEvent(
            timestamp=time_ns / 1e9,
            distance_meters=float(max_idx),
            amplitude=amplitude,
            frequency_hz=frequency,
            target_type=target_type,
            confidence=confidence,
            location_meters=(float(max_idx - 2), float(max_idx + 2))
        )
    
    def _estimate_frequency(self, data: list[float]) -> float:
        """Estimate dominant frequency via zero-crossing (simplified)."""
        if len(data) < 10:
            return random.uniform(1, 50)
        
        zero_crossings = sum(
            1 for i in range(len(data) - 1)
            if data[i] * data[i + 1] < 0
        )
        return zero_crossings * self.sample_rate_hz / (2 * len(data))
    
    def _classify(self, amplitude: float, frequency: float, position: int) -> tuple[TargetType, float]:
        """
       .Classify target based on vibration signature.
        
        Simplified classification rules:
        - Footsteps: low amplitude, 1-3 Hz, regular pattern
        - Wheeled: medium amplitude, 8-15 Hz, periodic
        - Tracked: high amplitude, 0-5 Hz, broad spectrum
        - Artillery: very high amplitude, very low frequency
        """
        # Simplified decision tree
        if amplitude > 0.8:
            if frequency < 3:
                return TargetType.ARTILLERY, 0.95
            return TargetType.TRACKED_VEHICLE, 0.85
        
        if amplitude > 0.5:
            if 5 < frequency < 20:
                return TargetType.WHEELED_VEHICLE, 0.80
            return TargetType.TRACKED_VEHICLE, 0.70
        
        if 0.2 < amplitude < 0.5:
            if 0.5 < frequency < 5:
                return TargetType.FOOTSTEP, 0.75
            return TargetType.UNKNOWN, 0.5
        
        return TargetType.UNKNOWN, 0.3
    
    def analyze(self, samples: list[tuple[int, list[float]]]) -> list[VibrationEvent]:
        """Analyze batch of samples and return detected events."""
        events = []
        for time_ns, channel_data in samples:
            event = self.process_sample(time_ns, channel_data)
            if event:
                events.append(event)
                self.events.append(event)
        return events
    
    def get_alerts(self, min_confidence: float = 0.6) -> list[dict]:
        """Generate alert messages for detected targets."""
        alerts = []
        for event in self.events:
            if event.confidence >= min_confidence:
                alerts.append({
                    "timestamp": event.timestamp,
                    "target": event.target_type.value,
                    "position_m": event.distance_meters,
                    "location_range": event.location_meters,
                    "amplitude": round(event.amplitude, 3),
                    "frequency_hz": round(event.frequency_hz, 2),
                    "confidence": f"{event.confidence * 100:.0f}%"
                })
        return alerts


def generate_simulated_data(duration_seconds: int = 30, event_interval: int = 8) -> list[tuple[int, list[float]]]:
    """
    Generate simulated φ-OTDR data with periodic vibration events.
    
    Returns list of (timestamp_ns, channel_amplitudes) tuples.
    """
    samples = []
    num_channels = 5000  # 5000m fiber, 1 sample per meter
    start_time = time.time()
    
    print(f"[DAS] Simulating {duration_seconds}s of fiber monitoring...")
    print(f"[DAS] Fiber length: {num_channels}m, Sample rate: 1000Hz")
    print(f"[DAS] Events every ~{event_interval}s\n")
    
    sample_times = [start_time + i * 0.001 for i in range(duration_seconds * 1000)]
    
    for i, ts in enumerate(sample_times):
        ts_ns = int(ts * 1e9)
        
        # Base noise floor
        channel_data = [random.uniform(0.01, 0.05) for _ in range(num_channels)]
        
        # Inject event at random position
        event_position = random.randint(500, 1500)
        
        # Determine what kind of "target" we simulate
        event_type = random.choices(
            [TargetType.FOOTSTEP, TargetType.WHEELED_VEHICLE, TargetType.TRACKED_VEHICLE],
            weights=[50, 30, 20]
        )[0]
        
        if event_type == TargetType.FOOTSTEP:
            amplitude = random.uniform(0.25, 0.40)
            frequency = random.uniform(1.5, 3.0)
        elif event_type == TargetType.WHEELED_VEHICLE:
            amplitude = random.uniform(0.50, 0.70)
            frequency = random.uniform(10, 18)
        else:
            amplitude = random.uniform(0.70, 0.95)
            frequency = random.uniform(2, 5)
        
        # Add vibration to channels around event position
        for ch in range(max(0, event_position - 3), min(num_channels, event_position + 3)):
            distance = abs(ch - event_position)
            attenuation = math.exp(-distance * 0.5)
            channel_data[ch] += amplitude * attenuation * math.sin(2 * math.pi * frequency * (ts % 1))
        
        samples.append((ts_ns, channel_data))
    
    return samples


def main():
    parser = argparse.ArgumentParser(
        description="DAS Analyser — Distributed Acoustic Sensing processor"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Generate simulated vibration data"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration to simulate in seconds"
    )
    parser.add_argument(
        "--fiber-length",
        type=int,
        default=5000,
        help="Fiber length in meters"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence threshold for alerts"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    args = parser.parse_args()
    
    analyser = DASAnalyser(fiber_length_meters=args.fiber_length)
    
    if args.simulate:
        print("=" * 60)
        print("DAS ANALYSER — Simulation Mode")
        print("=" * 60 + "\n")
        
        samples = generate_simulated_data(duration_seconds=args.duration)
        
        print(f"[INPUT] Processing {len(samples)} samples...\n")
        
        events = analyser.analyze(samples)
        
        print(f"[OUTPUT] Detected {len(events)} vibration events\n")
        
        alerts = analyser.get_alerts(min_confidence=args.min_confidence)
        
        if args.json:
            print(json.dumps(alerts, indent=2))
        else:
            print("=" * 60)
            print("ALERTS")
            print("=" * 60)
            
            for alert in alerts:
                target = alert["target"]
                pos = alert["position_m"]
                conf = alert["confidence"]
                ts = alert["timestamp"]
                
                # Emoji based on target type
                emoji = {
                    "footstep": "👣",
                    "wheeled_vehicle": "🚛",
                    "tracked_vehicle": "🚜",
                    "artillery": "💥",
                    "unknown": "❓"
                }.get(target, "❓")
                
                print(f"\n{emoji} {target.upper()}")
                print(f"   Position: {pos:.0f}m along fiber")
                print(f"   Confidence: {conf}")
                print(f"   Time: {ts:.2f}s")
        
        if not alerts:
            print("\n[INFO] No alerts above threshold. Try lowering --min-confidence")
            print("[INFO] Example: python das_analyser.py --simulate --min-confidence 0.3")
    else:
        print("[DAS] Connect to φ-OTDR interrogator to begin real-time analysis.")
        print("[DAS] Use --simulate to run demonstration with synthetic data.")
        print("\nExample:")
        print("  python das_analyser.py --simulate --duration 60")


if __name__ == "__main__":
    main()