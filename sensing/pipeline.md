# TFN Sensing Pipeline — signal → filter → feature extraction → classification

## Overview

Pipeline для перетворення сирих сенсорних даних на тактичну розвідку.

```
[Сенсор] → [ADC] → [Filter] → [FFT] → [Features] → [Classify] → [Alert]
  п'єзо    ESP32   Kalman     1024pt   RMS, freq    Rule/ML    Telegram
  / DAS    / RPi   BandPass            peak freq
```

---

## Stage 1: Signal Acquisition

### Варіант A: П'єзо-сенсор + ESP32 (MVP)

```
П'єзо 27mm → LM358 amp → ADS1256 (24-bit, 30k SPS) → ESP32-S3 → WiFi/Fiber
```

| Параметр | Значення |
|----------|----------|
| ADC | ADS1256, 24-bit |
| Sample rate | 1000-10000 SPS |
| Frequency range | 0.1-500 Hz |
| Sensors per node | 4-8 (мультиплексор CD74HC4067) |

### Варіант B: DAS через φ-OTDR (повний)

```
Лазер 1550nm → Fiber → Backscatter → Photodetector → ADC → RPi
```

| Параметр | Значення |
|----------|----------|
| Spatial resolution | 1-5 м |
| Range | 5-40 км |
| Sample rate | 1000 Hz |
| Sensitivity | 10⁻⁶ рад фазового зсуву |

---

## Stage 2: Filtering

### 2.1 DC Removal

```python
def remove_dc(signal):
    return signal - np.mean(signal)
```

### 2.2 Band-pass filter (1-250 Hz)

```python
from scipy.signal import butter, filtfilt

def bandpass_filter(signal, lowcut=1.0, highcut=250.0, fs=1000, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)
```

### 2.3 Kalman filter (опціонально, для шуму)

```python
# Простий 1D Kalman для видалення випадкового шуму
# q = process noise, r = measurement noise
def kalman_1d(signal, q=0.01, r=0.1):
    x = signal[0]
    p = 1.0
    filtered = []
    for z in signal:
        p = p + q
        k = p / (p + r)
        x = x + k * (z - x)
        p = (1 - k) * p
        filtered.append(x)
    return np.array(filtered)
```

---

## Stage 3: FFT + Feature Extraction

### 3.1 FFT

```python
def compute_fft(signal, fs=1000):
    n = len(signal)
    window = np.hanning(n)
    fft_result = np.fft.fft(signal * window)
    freqs = np.fft.fftfreq(n, d=1/fs)
    magnitude = np.abs(fft_result[:n//2])
    freqs = freqs[:n//2]
    return freqs, magnitude
```

### 3.2 Feature extraction

```python
def extract_features(signal, fs=1000):
    freqs, magnitude = compute_fft(signal, fs)
    
    rms = np.sqrt(np.mean(signal**2))
    peak_freq = freqs[np.argmax(magnitude)]
    spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
    bandwidth = np.sqrt(np.sum(((freqs - spectral_centroid)**2) * magnitude) / np.sum(magnitude))
    zero_crossings = np.sum(np.diff(np.sign(signal)) != 0)
    
    # Frequency band energies
    bands = {
        'sub_hz': np.sum(magnitude[(freqs >= 0.1) & (freqs < 1)]),
        'footstep': np.sum(magnitude[(freqs >= 1) & (freqs < 5)]),
        'vehicle_low': np.sum(magnitude[(freqs >= 5) & (freqs < 20)]),
        'vehicle_high': np.sum(magnitude[(freqs >= 20) & (freqs < 80)]),
        'drone': np.sum(magnitude[(freqs >= 80) & (freqs < 250)]),
    }
    
    return {
        'rms': rms,
        'peak_freq': peak_freq,
        'spectral_centroid': spectral_centroid,
        'bandwidth': bandwidth,
        'zero_crossing_rate': zero_crossings / len(signal),
        **bands,
    }
```

---

## Stage 4: Classification

### 4.1 Rule-based (MVP — без ML)

```python
def classify_rule_based(features):
    footstep = features['footstep']
    vehicle_low = features['vehicle_low']
    vehicle_high = features['vehicle_high']
    drone = features['drone']
    rms = features['rms']
    
    if rms < 0.05:
        return 'silence', 0.0
    
    scores = {
        'infantry': footstep * 1.5 + features['zero_crossing_rate'] * 0.1,
        'wheeled': vehicle_low * 1.2 + vehicle_high * 0.5,
        'tracked': vehicle_low * 1.8 + features['sub_hz'] * 0.5,
        'drone': drone * 2.0,
        'artillery': rms * 3.0 if rms > 0.8 else 0,
        'digging': features['footstep'] * 0.5 + vehicle_low * 0.3 if features['zero_crossing_rate'] < 10 else 0,
    }
    
    best = max(scores, key=scores.get)
    confidence = min(scores[best] / (sum(scores.values()) + 0.01), 0.99)
    
    if confidence < 0.3:
        return 'unknown', confidence
    
    return best, confidence
```

### 4.2 ML-based (v0.2 — KNN / SVM)

```python
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler

class SignalClassifier:
    def __init__(self):
        self.model = SVC(kernel='rbf', probability=True)
        self.scaler = StandardScaler()
        self.trained = False
    
    def train(self, X_features, y_labels):
        X_scaled = self.scaler.fit_transform(X_features)
        self.model.fit(X_scaled, y_labels)
        self.trained = True
    
    def predict(self, features):
        if not self.trained:
            return 'unknown', 0.0
        X = self.scaler.transform([list(features.values())])
        proba = self.model.predict_proba(X)[0]
        idx = np.argmax(proba)
        return self.model.classes_[idx], proba[idx]
```

### 4.3 Neural network (v0.3 — Conv1D)

```python
# Для повного DAS з достатньою навчальною вибіркою
# Див. theory/CLOUD_STRATEGY.md для архітектури моделі
```

---

## Stage 5: Alert Generation

```python
THREAT_LEVELS = {
    'silence': 'none',
    'unknown': 'none',
    'infantry': 'medium',
    'wheeled': 'medium',
    'tracked': 'high',
    'artillery': 'critical',
    'drone': 'medium',
    'digging': 'low',
}

def generate_alert(classification, confidence, position_m, timestamp):
    threat = THREAT_LEVELS.get(classification, 'none')
    if threat == 'none':
        return None
    
    return {
        'timestamp': timestamp,
        'position_m': position_m,
        'target': classification,
        'threat': threat,
        'confidence': f"{confidence*100:.0f}%",
        'message': f"{classification.upper()} на {position_m}м ({confidence*100:.0f}%)"
    }
```

---

## Testing the Pipeline

```bash
# Симуляція (без заліза)
python -m simulation.das_simulator

# З п'єзо-сенсором (MVP)
python -m sensing.piezo_reader --port /dev/ttyUSB0 --duration 30
```

---

*Sensing Pipeline v1.0*
