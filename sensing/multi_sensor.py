#!/usr/bin/env python3
"""
TFN Multi-Sensor Fusion & Time Correlation
============================================

Fuses detections from multiple sensors, tracks target movement
across segments, and provides edge autonomy for disconnected ops.

No external dependencies — uses only Python standard library.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SensorReading:
    """Single sensor detection."""
    sensor_id: str
    segment_id: str
    timestamp: float
    target_type: str
    confidence: float
    position_m: float
    features: dict = field(default_factory=dict)


def _threat_rank(target_type: str) -> int:
    ranks = {
        "unknown": 0,
        "wind_noise": 0,
        "rain_noise": 0,
        "footstep": 1,
        "digging": 1,
        "group": 2,
        "wheeled_vehicle": 2,
        "drone": 2,
        "tracked_vehicle": 3,
        "artillery": 4,
        "explosion": 4,
    }
    return ranks.get(target_type, 0)


class MultiSensorFusion:
    """Fuse detections from multiple sensors to improve accuracy.

    Rules:
    1. If 2+ sensors on same segment agree -> confidence boost (+0.2)
    2. If 1 sensor only -> confidence penalty (-0.1)
    3. Minimum 2 sensors for "strike_ready" action
    """

    def __init__(self, time_window_s: float = 5.0):
        self.time_window = time_window_s
        self.recent_detections: list[SensorReading] = []
        self._segment_spacing_m = 2000.0

    def add_detection(self, reading: SensorReading):
        self.recent_detections.append(reading)
        now = time.time()
        cutoff = now - self.time_window * 3
        self.recent_detections = [
            d for d in self.recent_detections if d.timestamp > cutoff
        ]

    def get_fused_events(self) -> list[dict]:
        if not self.recent_detections:
            return []

        now = time.time()
        recent = [
            d for d in self.recent_detections
            if now - d.timestamp < self.time_window
        ]
        if not recent:
            return []

        groups: dict[str, list[SensorReading]] = {}
        for d in recent:
            key = d.segment_id
            if key not in groups:
                groups[key] = []
            groups[key].append(d)

        fused: list[dict] = []
        for seg_id, detections in groups.items():
            type_counts: dict[str, int] = {}
            for d in detections:
                type_counts[d.target_type] = type_counts.get(d.target_type, 0) + 1

            best_type = max(type_counts, key=type_counts.get)
            agreeing = [d for d in detections if d.target_type == best_type]
            agreeing_sensors = len(set(d.sensor_id for d in agreeing))

            avg_confidence = sum(d.confidence for d in agreeing) / len(agreeing)
            boosted = self._boost_confidence(avg_confidence, agreeing_sensors)
            avg_position = sum(d.position_m for d in detections) / len(detections)

            fused.append({
                "segment_id": seg_id,
                "target_type": best_type,
                "confidence": round(min(boosted, 0.99), 3),
                "position_m": round(avg_position, 1),
                "sensor_count": len(detections),
                "agreeing_sensors": agreeing_sensors,
                "timestamp": now,
                "features": detections[0].features if detections else {},
            })

        return fused

    def _boost_confidence(self, base_confidence: float,
                          agreeing_sensors: int) -> float:
        if agreeing_sensors >= 2:
            return base_confidence + 0.2 * (agreeing_sensors - 1)
        return max(base_confidence - 0.1, 0.0)


class TimeCorrelator:
    """Track target movement across segments.

    If event moves segment_1 -> segment_2 -> segment_3 over time,
    it's a real moving target, not noise.
    """

    def __init__(self, max_track_age_s: float = 120.0,
                 segment_spacing_m: float = 2000.0):
        self.max_track_age = max_track_age_s
        self.segment_spacing = segment_spacing_m
        self.tracks: dict[int, dict] = {}
        self.next_track_id = 1

    def update(self, fused_event: dict) -> Optional[dict]:
        seg_id = fused_event.get("segment_id", "")
        ts = fused_event.get("timestamp", time.time())
        target_type = fused_event.get("target_type", "unknown")
        confidence = fused_event.get("confidence", 0.0)
        position_m = fused_event.get("position_m", 0.0)

        best_track_id: Optional[int] = None
        best_track_score = 0.0

        for tid, track in list(self.tracks.items()):
            if track.get("target_type") != target_type:
                continue
            age = ts - track["last_seen"]
            if age > self.max_track_age:
                continue
            last_seg = (track["segments_visited"][-1]
                        if track["segments_visited"] else "")
            seg_dist = abs(self._seg_num(seg_id) - self._seg_num(last_seg))
            if seg_dist > 5:
                continue
            score = confidence * (1.0 / (1.0 + seg_dist))
            if score > best_track_score:
                best_track_score = score
                best_track_id = tid

        if best_track_id is not None:
            track = self.tracks[best_track_id]
            track["segments_visited"].append(seg_id)
            track["segment_times"].append(ts)
            track["last_seen"] = ts
            track["confidence"] = max(track["confidence"], confidence)
            track["speed_estimate"] = self._estimate_speed(
                track["segments_visited"], track["segment_times"]
            )
            track["heading"] = self._estimate_heading(track["segments_visited"])
            track["behavior"] = self._classify_track(track)
            track["position_m"] = position_m
            return dict(track)

        tid = self.next_track_id
        self.next_track_id += 1
        track = {
            "track_id": tid,
            "target_type": target_type,
            "segments_visited": [seg_id],
            "segment_times": [ts],
            "last_seen": ts,
            "confidence": confidence,
            "speed_estimate": 0.0,
            "heading": "static",
            "behavior": "static",
            "position_m": position_m,
        }
        self.tracks[tid] = track
        return dict(track)

    def get_active_tracks(self) -> list[dict]:
        now = time.time()
        active: list[dict] = []
        for track in self.tracks.values():
            if now - track["last_seen"] < self.max_track_age:
                active.append(dict(track))
        return active

    def _seg_num(self, seg_id: str) -> int:
        try:
            return int(seg_id.split("_")[-1])
        except (ValueError, IndexError):
            return 0

    def _estimate_speed(self, segments: list[str],
                        times: list[float]) -> float:
        if len(segments) < 2:
            return 0.0
        total_dist = 0.0
        total_time = 0.0
        for i in range(1, len(segments)):
            d = (abs(self._seg_num(segments[i]) - self._seg_num(segments[i - 1]))
                 * self.segment_spacing)
            dt = times[i] - times[i - 1]
            if dt > 0:
                total_dist += d
                total_time += dt
        if total_time == 0:
            return 0.0
        return total_dist / total_time

    def _estimate_heading(self, segments: list[str]) -> str:
        if len(segments) < 2:
            return "static"
        recent = segments[-3:] if len(segments) >= 3 else segments
        diffs = [
            self._seg_num(recent[i]) - self._seg_num(recent[i - 1])
            for i in range(1, len(recent))
        ]
        avg_diff = sum(diffs) / len(diffs)
        if abs(avg_diff) < 0.3:
            return "lateral"
        if avg_diff > 0:
            return "towards_front"
        return "towards_rear"

    def _classify_track(self, track: dict) -> str:
        speed = track.get("speed_estimate", 0.0)
        heading = track.get("heading", "static")

        if speed < 0.5:
            return "static"
        if heading == "lateral" and speed < 5.0:
            return "patrol"
        if heading == "towards_rear":
            return "approach"
        if heading == "towards_front":
            return "retreat"
        return "movement"


class EdgeAutonomy:
    """Local decision logic for when C2 is unreachable.

    Rules:
    - If confidence > 0.8 AND threat >= "high" -> local alert + auto-log
    - If confidence > 0.9 AND threat == "critical" -> emergency beacon
    - Otherwise: queue for C2 upload when available
    """

    def __init__(self, fusion: MultiSensorFusion, correlator: TimeCorrelator):
        self.fusion = fusion
        self.correlator = correlator
        self.local_alerts: list[dict] = []
        self.c2_queue: list[dict] = []
        self.c2_connected: bool = True

    def process_detection(self, reading: SensorReading) -> Optional[dict]:
        self.fusion.add_detection(reading)
        fused_events = self.fusion.get_fused_events()

        result = None
        for event in fused_events:
            track = self.correlator.update(event)
            if track is None:
                continue

            action = self._decide(event, track)
            result = {
                "event": event,
                "track": track,
                "action": action,
            }

            if self.c2_connected:
                self.c2_queue.append(result)
            else:
                conf = event.get("confidence", 0.0)
                threat = _threat_rank(event.get("target_type", "unknown"))

                if conf > 0.9 and threat >= 4:
                    self.local_alerts.append({
                        **result,
                        "emergency_beacon": True,
                    })
                    self.c2_queue.append(result)
                elif conf > 0.8 and threat >= 3:
                    self.local_alerts.append(result)
                    self.c2_queue.append(result)
                else:
                    self.c2_queue.append(result)

        return result

    def set_c2_status(self, connected: bool):
        self.c2_connected = connected

    def flush_queue(self) -> list[dict]:
        pending = list(self.c2_queue)
        self.c2_queue.clear()
        return pending

    def _decide(self, event: dict, track: dict) -> str:
        conf = event.get("confidence", 0.0)
        threat = _threat_rank(event.get("target_type", "unknown"))
        sensors = event.get("agreeing_sensors", 1)

        if conf > 0.8 and threat >= 4 and sensors >= 2:
            return "strike_ready"
        if conf > 0.7 and threat >= 3:
            return "investigate"
        if threat >= 2:
            return "monitor"
        return "log_only"
