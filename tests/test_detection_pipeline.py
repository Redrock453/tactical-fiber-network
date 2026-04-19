#!/usr/bin/env python3

import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_signal_buffer():
    from sensing.detection_pipeline import SignalBuffer

    buf = SignalBuffer(capacity=5)
    assert buf.size == 0
    assert len(buf.get_recent(10)) == 0

    for i in range(3):
        buf.push(float(i))
    assert buf.size == 3
    assert buf.get_recent(3) == [0.0, 1.0, 2.0]

    for i in range(3, 8):
        buf.push(float(i))
    assert buf.size == 5
    assert buf.get_recent(5) == [3.0, 4.0, 5.0, 6.0, 7.0]
    assert buf.get_recent(3) == [5.0, 6.0, 7.0]

    buf.clear()
    assert buf.size == 0


def test_signal_filter_lowpass():
    from sensing.detection_pipeline import SignalFilter

    data = [math.sin(2.0 * math.pi * 10.0 * i / 1000) for i in range(1000)]
    data += [0.8 * math.sin(2.0 * math.pi * 400.0 * i / 1000) for i in range(1000)]

    filtered = SignalFilter.low_pass(data, cutoff_ratio=0.1)
    assert len(filtered) == len(data)

    rms_orig = math.sqrt(sum(s * s for s in data) / len(data))
    rms_filt = math.sqrt(sum(s * s for s in filtered) / len(filtered))
    assert rms_filt < rms_orig


def test_signal_filter_bandpass():
    from sensing.detection_pipeline import SignalFilter

    data = [math.sin(2.0 * math.pi * 20.0 * i / 1000) for i in range(1000)]
    filtered = SignalFilter.band_pass(data, low_ratio=0.01, high_ratio=0.1)
    assert len(filtered) == len(data)

    empty = SignalFilter.band_pass([], low_ratio=0.01, high_ratio=0.1)
    assert empty == []


def test_signal_filter_remove_dc():
    from sensing.detection_pipeline import SignalFilter

    data = [101.0, 102.0, 103.0, 104.0, 105.0]
    result = SignalFilter.remove_dc(data)
    assert len(result) == 5
    assert abs(sum(result) / len(result)) < 1e-10

    empty = SignalFilter.remove_dc([])
    assert empty == []


def test_feature_extraction_rms():
    from sensing.detection_pipeline import FeatureExtractor

    signal = [1.0, -1.0, 1.0, -1.0]
    rms = FeatureExtractor.compute_rms(signal)
    assert abs(rms - 1.0) < 1e-10

    assert FeatureExtractor.compute_rms([]) == 0.0
    assert FeatureExtractor.compute_rms([0.0] * 100) == 0.0


def test_feature_extraction_zero_crossing():
    from sensing.detection_pipeline import FeatureExtractor

    signal = [1.0, -1.0, 1.0, -1.0, 1.0]
    zcr = FeatureExtractor.compute_zero_crossing_rate(signal)
    assert zcr > 0

    zcr_flat = FeatureExtractor.compute_zero_crossing_rate([1.0] * 100)
    assert zcr_flat == 0.0

    zcr_short = FeatureExtractor.compute_zero_crossing_rate([1.0])
    assert zcr_short == 0.0


def test_feature_extraction_fft_peak():
    from sensing.detection_pipeline import FeatureExtractor

    fs = 1000
    target_freq = 50.0
    signal = [math.sin(2.0 * math.pi * target_freq * i / fs) for i in range(256)]
    peak_freq, peak_mag = FeatureExtractor.compute_fft_peak(signal, fs)
    assert peak_freq > 0
    assert abs(peak_freq - target_freq) < 5.0
    assert peak_mag > 0


def test_feature_extraction_spectral_centroid():
    from sensing.detection_pipeline import FeatureExtractor

    fs = 1000
    low_signal = [math.sin(2.0 * math.pi * 10.0 * i / fs) for i in range(256)]
    high_signal = [math.sin(2.0 * math.pi * 200.0 * i / fs) for i in range(256)]

    centroid_low = FeatureExtractor.compute_spectral_centroid(low_signal, fs)
    centroid_high = FeatureExtractor.compute_spectral_centroid(high_signal, fs)
    assert centroid_low < centroid_high


def test_feature_extraction_rhythm():
    from sensing.detection_pipeline import FeatureExtractor

    fs = 1000
    periodic = [0.0] * (2 * fs)
    for beat_idx in range(0, 2 * fs, fs // 2):
        for j in range(min(20, 2 * fs - beat_idx)):
            periodic[beat_idx + j] = 1.0

    noise = [random.gauss(0, 0.1) for _ in range(2 * fs)]

    rhythm_periodic = FeatureExtractor.compute_rhythm_score(periodic, fs)
    rhythm_noise = FeatureExtractor.compute_rhythm_score(noise, fs)
    assert rhythm_periodic >= rhythm_noise


def test_classifier_footstep():
    from sensing.detection_pipeline import TargetClassifier

    classifier = TargetClassifier()
    features = {
        "fft_peak_freq": 3.0,
        "rms": 0.15,
        "peak_amp": 0.3,
        "zcr": 0.02,
        "rhythm_score": 0.7,
        "peak_to_rms": 2.0,
        "spectral_centroid": 5.0,
    }
    target_type, confidence, threat = classifier.classify(features)
    assert target_type in ("footstep", "group", "digging")
    assert confidence > 0.0
    assert threat in ("low", "medium", "none")


def test_classifier_vehicle():
    from sensing.detection_pipeline import TargetClassifier

    classifier = TargetClassifier()
    features = {
        "fft_peak_freq": 20.0,
        "rms": 0.45,
        "peak_amp": 0.8,
        "zcr": 0.03,
        "rhythm_score": 0.05,
        "peak_to_rms": 1.8,
        "spectral_centroid": 25.0,
    }
    target_type, confidence, threat = classifier.classify(features)
    assert target_type in ("wheeled_vehicle", "tracked_vehicle", "drone", "explosion")
    assert confidence > 0.0


def test_classifier_rejection():
    from sensing.detection_pipeline import TargetClassifier

    classifier = TargetClassifier()
    features = {
        "fft_peak_freq": 1000.0,
        "rms": 0.001,
        "peak_amp": 0.001,
        "zcr": 0.01,
        "rhythm_score": 0.01,
        "peak_to_rms": 1.0,
        "spectral_centroid": 900.0,
    }
    target_type, confidence, threat = classifier.classify_with_rejection(features, min_confidence=0.95)
    assert target_type == "unknown" or confidence < 0.95


def test_pipeline_full():
    from sensing.detection_pipeline import DetectionPipeline, generate_test_signal

    pipe = DetectionPipeline(sample_rate=1000, window_size=1024)
    signal = generate_test_signal("footstep", duration_s=1.0, sample_rate=1000)

    event = pipe.process_window(signal)
    if event is not None:
        assert "target_type" in event
        assert 0.0 <= event["confidence"] <= 1.0
        assert "threat_level" in event
        assert "action_recommended" in event


def test_pipeline_rejection():
    from sensing.detection_pipeline import DetectionPipeline

    pipe = DetectionPipeline(sample_rate=1000, window_size=1024)
    noise = [random.gauss(0, 0.001) for _ in range(1024)]
    event = pipe.process_window(noise)
    assert event is None


def test_generate_test_signal():
    from sensing.detection_pipeline import generate_test_signal

    target_types = ["footstep", "wheeled_vehicle", "tracked_vehicle", "drone", "artillery", "digging"]
    for target_type in target_types:
        signal = generate_test_signal(target_type, duration_s=1.0, sample_rate=1000)
        assert len(signal) == 1000
        rms = math.sqrt(sum(s * s for s in signal) / len(signal))
        assert rms > 0, f"Signal for {target_type} should not be all zeros"


def test_pipeline_action_recommendation():
    from sensing.detection_pipeline import DetectionPipeline, generate_test_signal

    pipe = DetectionPipeline(sample_rate=1000, window_size=1024)

    artillery_signal = generate_test_signal("artillery", duration_s=1.0, sample_rate=1000)
    event = pipe.process_window(artillery_signal)

    if event is not None:
        assert "action_recommended" in event
        assert isinstance(event["action_recommended"], str)

    low_signal = generate_test_signal("digging", duration_s=1.0, sample_rate=1000)
    event_low = pipe.process_window(low_signal)

    if event_low is not None:
        assert "action_recommended" in event_low


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
