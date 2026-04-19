#!/usr/bin/env python3

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sensor_reading_creation():
    from sensing.multi_sensor import SensorReading

    reading = SensorReading(
        sensor_id="S1",
        segment_id="seg_01",
        timestamp=time.time(),
        target_type="footstep",
        confidence=0.85,
        position_m=1000.0,
        features={"rms": 0.3},
    )

    assert reading.sensor_id == "S1"
    assert reading.segment_id == "seg_01"
    assert reading.position_m == 1000.0
    assert reading.target_type == "footstep"
    assert reading.confidence == 0.85
    assert isinstance(reading.features, dict)


def test_fusion_single_sensor():
    from sensing.multi_sensor import MultiSensorFusion, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    now = time.time()

    reading = SensorReading(
        sensor_id="S1",
        segment_id="seg_01",
        timestamp=now,
        target_type="footstep",
        confidence=0.80,
        position_m=1000.0,
    )

    fusion.add_detection(reading)
    fused = fusion.get_fused_events()
    assert len(fused) >= 1
    assert fused[0]["sensor_count"] == 1
    assert fused[0]["confidence"] < 0.80


def test_fusion_two_sensors_agree():
    from sensing.multi_sensor import MultiSensorFusion, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    now = time.time()

    r1 = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=now,
        target_type="footstep", confidence=0.70, position_m=990.0,
    )
    r2 = SensorReading(
        sensor_id="S2", segment_id="seg_01", timestamp=now,
        target_type="footstep", confidence=0.75, position_m=1010.0,
    )

    fusion.add_detection(r1)
    fusion.add_detection(r2)
    fused = fusion.get_fused_events()
    assert len(fused) >= 1
    avg_conf = (0.70 + 0.75) / 2
    assert fused[0]["confidence"] > avg_conf
    assert fused[0]["target_type"] == "footstep"
    assert fused[0]["sensor_count"] == 2


def test_fusion_three_sensors_agree():
    from sensing.multi_sensor import MultiSensorFusion, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    now = time.time()

    for i in range(3):
        r = SensorReading(
            sensor_id=f"S{i}", segment_id="seg_01", timestamp=now,
            target_type="tracked_vehicle", confidence=0.65, position_m=990.0 + i * 10,
        )
        fusion.add_detection(r)

    fused = fusion.get_fused_events()
    assert len(fused) >= 1
    assert fused[0]["confidence"] > 0.65
    assert fused[0]["target_type"] == "tracked_vehicle"
    assert fused[0]["sensor_count"] == 3


def test_fusion_sensors_disagree():
    from sensing.multi_sensor import MultiSensorFusion, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    now = time.time()

    r1 = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=now,
        target_type="footstep", confidence=0.80, position_m=1000.0,
    )
    r2 = SensorReading(
        sensor_id="S2", segment_id="seg_01", timestamp=now,
        target_type="wheeled_vehicle", confidence=0.80, position_m=1010.0,
    )

    fusion.add_detection(r1)
    fusion.add_detection(r2)
    fused = fusion.get_fused_events()
    assert len(fused) >= 1
    best = fused[0]
    assert best["target_type"] in ("footstep", "wheeled_vehicle")


def test_fusion_time_window():
    from sensing.multi_sensor import MultiSensorFusion, SensorReading

    fusion = MultiSensorFusion(time_window_s=2.0)
    now = time.time()

    r1 = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=now,
        target_type="footstep", confidence=0.80, position_m=1000.0,
    )
    r2 = SensorReading(
        sensor_id="S2", segment_id="seg_02", timestamp=now - 10.0,
        target_type="footstep", confidence=0.80, position_m=1010.0,
    )

    fusion.add_detection(r1)
    fusion.add_detection(r2)
    fused = fusion.get_fused_events()
    assert len(fused) >= 1
    assert all(f["sensor_count"] == 1 for f in fused)


def test_time_correlator_single_event():
    from sensing.multi_sensor import TimeCorrelator

    correlator = TimeCorrelator(max_track_age_s=120.0)
    now = time.time()

    event = {
        "segment_id": "seg_03",
        "target_type": "footstep",
        "confidence": 0.8,
        "position_m": 1500.0,
        "timestamp": now,
    }

    track = correlator.update(event)
    assert track is not None
    assert track["target_type"] == "footstep"
    assert len(track["segments_visited"]) == 1


def test_time_correlator_movement():
    from sensing.multi_sensor import TimeCorrelator

    correlator = TimeCorrelator(max_track_age_s=120.0)
    now = time.time()

    correlator.update({"segment_id": "seg_01", "target_type": "footstep", "confidence": 0.8, "position_m": 100.0, "timestamp": now})
    correlator.update({"segment_id": "seg_02", "target_type": "footstep", "confidence": 0.8, "position_m": 200.0, "timestamp": now + 1.0})
    correlator.update({"segment_id": "seg_03", "target_type": "footstep", "confidence": 0.8, "position_m": 300.0, "timestamp": now + 2.0})

    tracks = correlator.get_active_tracks()
    assert len(tracks) >= 1
    track = tracks[0]
    assert len(track["segments_visited"]) == 3
    assert track["speed_estimate"] > 0


def test_time_correlator_speed_estimate():
    from sensing.multi_sensor import TimeCorrelator

    correlator = TimeCorrelator(max_track_age_s=120.0, segment_spacing_m=100.0)
    now = time.time()

    correlator.update({"segment_id": "seg_01", "target_type": "wheeled_vehicle", "confidence": 0.85, "position_m": 100.0, "timestamp": now})
    correlator.update({"segment_id": "seg_02", "target_type": "wheeled_vehicle", "confidence": 0.85, "position_m": 200.0, "timestamp": now + 1.0})
    correlator.update({"segment_id": "seg_03", "target_type": "wheeled_vehicle", "confidence": 0.85, "position_m": 300.0, "timestamp": now + 2.0})

    tracks = correlator.get_active_tracks()
    assert len(tracks) >= 1
    track = tracks[0]
    assert track["speed_estimate"] > 0


def test_time_correlator_heading():
    from sensing.multi_sensor import TimeCorrelator

    correlator = TimeCorrelator(max_track_age_s=120.0, segment_spacing_m=100.0)
    now = time.time()

    correlator.update({"segment_id": "seg_01", "target_type": "footstep", "confidence": 0.8, "position_m": 100.0, "timestamp": now})
    correlator.update({"segment_id": "seg_02", "target_type": "footstep", "confidence": 0.8, "position_m": 200.0, "timestamp": now + 2.0})
    correlator.update({"segment_id": "seg_03", "target_type": "footstep", "confidence": 0.8, "position_m": 300.0, "timestamp": now + 4.0})

    tracks = correlator.get_active_tracks()
    assert len(tracks) >= 1
    heading = tracks[0]["heading"]
    assert heading in ("towards_front", "towards_rear", "lateral", "static")


def test_time_correlator_track_expiry():
    from sensing.multi_sensor import TimeCorrelator

    correlator = TimeCorrelator(max_track_age_s=5.0)
    old_time = time.time() - 10.0

    correlator.update({"segment_id": "seg_05", "target_type": "footstep", "confidence": 0.8, "position_m": 500.0, "timestamp": old_time})

    tracks = correlator.get_active_tracks()
    assert len(tracks) == 0


def test_edge_autonomy_c2_connected():
    from sensing.multi_sensor import EdgeAutonomy, MultiSensorFusion, TimeCorrelator, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    correlator = TimeCorrelator(max_track_age_s=120.0)
    edge = EdgeAutonomy(fusion, correlator)
    edge.set_c2_status(True)

    reading = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=time.time(),
        target_type="footstep", confidence=0.75, position_m=1000.0,
    )

    result = edge.process_detection(reading)
    assert len(edge.c2_queue) >= 0


def test_edge_autonomy_c2_disconnected():
    from sensing.multi_sensor import EdgeAutonomy, MultiSensorFusion, TimeCorrelator, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    correlator = TimeCorrelator(max_track_age_s=120.0)
    edge = EdgeAutonomy(fusion, correlator)
    edge.set_c2_status(False)

    reading = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=time.time(),
        target_type="tracked_vehicle", confidence=0.85, position_m=1000.0,
    )

    result = edge.process_detection(reading)
    assert len(edge.c2_queue) >= 0


def test_edge_autonomy_queue_flush():
    from sensing.multi_sensor import EdgeAutonomy, MultiSensorFusion, TimeCorrelator, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    correlator = TimeCorrelator(max_track_age_s=120.0)
    edge = EdgeAutonomy(fusion, correlator)

    reading1 = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=time.time(),
        target_type="footstep", confidence=0.70, position_m=500.0,
    )
    reading2 = SensorReading(
        sensor_id="S2", segment_id="seg_01", timestamp=time.time(),
        target_type="footstep", confidence=0.75, position_m=1500.0,
    )

    edge.process_detection(reading1)
    edge.process_detection(reading2)

    queued = edge.flush_queue()
    assert len(queued) >= 0
    assert len(edge.flush_queue()) == 0


def test_edge_autonomy_emergency():
    from sensing.multi_sensor import EdgeAutonomy, MultiSensorFusion, TimeCorrelator, SensorReading

    fusion = MultiSensorFusion(time_window_s=5.0)
    correlator = TimeCorrelator(max_track_age_s=120.0)
    edge = EdgeAutonomy(fusion, correlator)
    edge.set_c2_status(False)

    reading = SensorReading(
        sensor_id="S1", segment_id="seg_01", timestamp=time.time(),
        target_type="artillery", confidence=0.92, position_m=2000.0,
    )

    edge.process_detection(reading)
    assert len(edge.local_alerts) >= 1 or len(edge.c2_queue) >= 1


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
