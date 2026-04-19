# TFN Detection Accuracy — Практичний Guide

> "50% accuracy — це не система, це рулетка. 80% — це інструмент."

---

## Поточний стан (MVP)

Поточна реалізація використовує **rule-based класифікацію** на основі frequency-band energies (див. `sensing/pipeline.md`).

```python
scores = {
    'infantry': footstep * 1.5 + zero_crossing_rate * 0.1,
    'wheeled':  vehicle_low * 1.2 + vehicle_high * 0.5,
    'tracked':  vehicle_low * 1.8 + sub_hz * 0.5,
    'drone':    drone * 2.0,
}
best = max(scores, key=scores.get)
```

### Оцінка точності

| Ціль | Поточна точність | Проблема |
|------|-----------------|----------|
| Піхота (кроки) | 50-65% | Плутає з копанням, вітром |
| Колісна техніка | 60-70% | Плутає з гусеничною |
| Гусенична техніка | 55-65% | Плутає з колісною |
| Дрон | 40-55% | Слабкий сигнал, багато шуму |
| Артилерія / вибух | 70-80% | Добре, але багато false alarms від грому |
| Копання | 45-55% | Плутає з кроками |

### Основні проблеми

1. **Жодного шумоочищення** — сирий сигнал + примітивний FFT
2. **Немає калібрування** — пороги стали, не адаптивні
3. **Немає multi-sensor fusion** — кожен сенсор працює окремо
4. **Немає трекінгу** — одиночне спрацьовування = алерт
5. **Немає адаптації до погоди** — вітер і дощ не фільтруються

---

## Цільові показники

| Метрика | Ціль (MVP+) | Ціль (v0.3) |
|---------|------------|-------------|
| Виявлення піхоти | 75-85% | 85-92% |
| Виявлення техніки | 85-90% | 90-97% |
| Виявлення артилерії | 90-95% | 95-99% |
| False alarm rate | < 5/год (ясно) | < 2/год (будь-яка погода) |
| Latency classificarion | < 100 мс | < 50 мс |
| Час до calibration | < 2 години | < 30 хвилин |

---

## Де втрачується точність

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Сигнал   │────→│ Фільтр   │────→│ Features │────→│ Classify │
│ 100%     │     │ -10%     │     │ -15%     │     │ -20%     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                   ↑                 ↑                 ↑
               Шум не        Немає ритму,     Rule-based
               відфільтровано  correlation    занадто простий

┌──────────┐     ┌──────────┐     ┌──────────┐
│ 1 Sensor │────→│ No Track │────→│ No Cal   │────→  ~55%
│ -5%      │     │ -10%     │     │ -10%     │
└──────────┘     └──────────┘     └──────────┘
  ↑                 ↑                 ↑
Один точковий   Немає руху      Пороги не
замір, не       вздовж          адаптовані
надійно         сегментів       до ґрунту
```

### Джерела втрат

| # | Джерело | Вплив | Виправлення |
|---|---------|-------|-------------|
| 1 | Environmental noise (вітер, дощ) | -15-25% | Adaptive thresholds (Step 6) |
| 2 | Variable soil/terrain | -10-15% | Per-site calibration (Step 6) |
| 3 | Non-standard targets (різні авто ≠ однакова сигнатура) | -10-15% | ML training data (Step 7) |
| 4 | Sensor quality (дешевий piezo = noisy) | -5-10% | Multi-sensor fusion (Step 4) |
| 5 | Installation variation (глибина, coupling) | -5-10% | Standardized protocol |
| 6 | Кількість сенсорів (1 шт замість 2-3) | -5-10% | Multi-sensor (Step 4) |

---

## Step-by-Step Improvement Plan

### Step 1: Clean Signal (Foundation)

**Без чистого сигналу нічого іншого не працюватиме.**

#### 1.1 DC Removal

```python
def remove_dc(signal):
    return signal - np.mean(signal)
```

Причина: ADC має offset, п'єзо може мати DC bias. Без видалення — FFT показує артефакти на 0 Гц.

#### 1.2 Low-pass filter: видалити > 200 Гц

```python
from scipy.signal import butter, filtfilt

def lowpass_filter(signal, cutoff=200.0, fs=1000, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, cutoff / nyq, btype='low')
    return filtfilt(b, a, signal)
```

Причина: вище 200 Гц — тільки шум для п'єзо-сенсорів. Ціліальні сигнали: 0.5-150 Гц.

#### 1.3 Band-pass для конкретних цілей

```python
BANDPASS_PROFILES = {
    'footstep':  (1.0, 8.0),
    'vehicle':   (3.0, 80.0),
    'drone':     (30.0, 250.0),
    'artillery': (0.5, 20.0),
    'digging':   (2.0, 15.0),
}

def bandpass_filter(signal, lowcut, highcut, fs=1000, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, signal)
```

#### 1.4 Running average для noise floor tracking

```python
def noise_floor(signal, window=500):
    return np.convolve(np.abs(signal), np.ones(window)/window, mode='same')
```

Дозволяє адаптивно піднімати поріг при збільшенні фонового шуму.

**Очікуване покращення: +10% точності** (прибрано high-frequency noise та DC artifacts).

---

### Step 2: Feature Extraction

Поточний MVP використовує тільки band energies. Додаткові features значно покращують класифікацію.

#### 2.1 RMS Energy

```python
rms = np.sqrt(np.mean(signal**2))
```

Загальна енергія сигналу. Базовий індикатор: rms < поріг → тиша.

#### 2.2 Peak Frequency (FFT)

```python
freqs, magnitude = compute_fft(signal, fs)
peak_freq = freqs[np.argmax(magnitude)]
```

Головна частота сигналу. Найважливіший feature для розрізнення цілей.

#### 2.3 Spectral Centroid

```python
spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
```

"Центр ваги" спектра. Піхота: 2-5 Гц, техніка: 10-40 Гц, дрон: 50-150 Гц.

#### 2.4 Zero-Crossing Rate

```python
zcr = np.sum(np.diff(np.sign(signal)) != 0) / len(signal)
```

Швидкість зміни знаку. Високий ZCR = шум або високочастотний сигнал.

#### 2.5 Rhythm Score (автокореляція)

```python
def rhythm_score(signal, fs=1000):
    autocorr = np.correlate(signal, signal, mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    autocorr = autocorr / autocorr[0]
    peaks = np.where((autocorr[1:-1] > autocorr[:-2]) &
                     (autocorr[1:-1] > autocorr[2:]))[0] + 1
    if len(peaks) < 2:
        return 0.0
    return np.mean(autocorr[peaks[:5]])
```

**Критичний feature!** Кроки = ритмічний (rhythm_score > 0.5), техніка = безперервний (rhythm_score < 0.3), вибух = одиничний імпульс.

#### 2.6 Peak-to-RMS Ratio (імпульсне detection)

```python
peak_to_rms = np.max(np.abs(signal)) / (rms + 1e-10)
```

Висока ratio (> 10) = одиночний імпульс (постріл, вибух, удар).
Низька ratio (< 3) = безперервний сигнал (двигун, генератор).

#### 2.7 Повний feature vector

```python
def extract_features(signal, fs=1000):
    freqs, magnitude = compute_fft(signal, fs)

    rms = np.sqrt(np.mean(signal**2))
    peak_freq = freqs[np.argmax(magnitude)]
    spectral_centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)
    zcr = np.sum(np.diff(np.sign(signal)) != 0) / len(signal)
    rhythm = rhythm_score(signal, fs)
    p2r = np.max(np.abs(signal)) / (rms + 1e-10)

    bands = {
        'sub_hz':       np.sum(magnitude[(freqs >= 0.1) & (freqs < 1)]),
        'footstep':     np.sum(magnitude[(freqs >= 1) & (freqs < 5)]),
        'vehicle_low':  np.sum(magnitude[(freqs >= 5) & (freqs < 20)]),
        'vehicle_high': np.sum(magnitude[(freqs >= 20) & (freqs < 80)]),
        'drone':        np.sum(magnitude[(freqs >= 80) & (freqs < 250)]),
    }

    return {
        'rms': rms,
        'peak_freq': peak_freq,
        'spectral_centroid': spectral_centroid,
        'zero_crossing_rate': zcr,
        'rhythm_score': rhythm,
        'peak_to_rms': p2r,
        **bands,
    }
```

**Очікуване покращення: +5-10% точності** (ритм + імпульсність → краще розрізнення).

---

### Step 3: Rule-Based Classification (v2)

Покращене дерево рішень на основі розширених features.

```python
def classify_v2(f):
    if f['rms'] < 0.05:
        return 'silence', 0.95

    if f['peak_to_rms'] > 10:
        if f['rms'] > 0.5:
            return 'explosion', min(0.5 + f['rms'], 0.99)
        return 'impulse', 0.7

    if f['rhythm_score'] > 0.5 and f['peak_freq'] < 5:
        if f['rms'] > 0.1:
            return 'footstep_group', min(0.6 + f['rhythm_score'] * 0.3, 0.95)
        return 'footstep_single', min(0.5 + f['rhythm_score'] * 0.3, 0.90)

    if 8 < f['peak_freq'] < 50 and f['rhythm_score'] < 0.3:
        if f['vehicle_low'] > f['vehicle_high'] * 2:
            return 'tracked_vehicle', min(0.7 + f['rms'] * 0.2, 0.97)
        return 'wheeled_vehicle', min(0.7 + f['rms'] * 0.2, 0.95)

    if f['peak_freq'] > 80:
        return 'drone', min(0.5 + f['drone'] * 0.3, 0.85)

    if 2 < f['peak_freq'] < 8 and f['rhythm_score'] > 0.3 and f['rms'] < 0.3:
        return 'digging', min(0.5 + f['rhythm_score'] * 0.2, 0.85)

    if abs(f['peak_freq'] - 50) < 5 and f['rhythm_score'] < 0.1:
        return 'generator', 0.80

    return 'unknown', 0.3
```

#### Логіка дерева рішень

```
Signal → rms < 0.05? → YES: silence
       → peak_to_rms > 10? → YES: impulse/explosion
       → rhythm > 0.5 AND freq < 5? → YES: footstep
       → 8 < freq < 50 AND rhythm < 0.3? → YES: vehicle
           → low > high*2? → tracked
           → else → wheeled
       → freq > 80? → YES: drone
       → 2 < freq < 8 AND rhythm > 0.3? → YES: digging
       → freq ≈ 50 AND rhythm < 0.1? → YES: generator
       → else: unknown
```

**Очікуване покращення: +5-10% точності.**
**Ціль після Step 3: 70-75% точності.**

---

### Step 4: Multi-Sensor Fusion

Один сенсор — ненадійно. Два-три сенсори на сегмент — надійно.

#### Принцип

```
Сенсор CH0: infantry 82%  ──┐
Сенсор CH1: infantry 74%  ──┼──→ Fusion: infantry 89% ✓
Сенсор CH2: silence   95%  ──┘     (2/3 згодні, CH2 ошукався)
```

#### Правила fusion

```python
def fuse_sensors(detections):
    if len(detections) == 0:
        return 'silence', 0.0

    target_votes = {}
    for det in detections:
        t = det['target']
        c = det['confidence']
        if t not in target_votes:
            target_votes[t] = {'count': 0, 'total_conf': 0}
        target_votes[t]['count'] += 1
        target_votes[t]['total_conf'] += c

    best_target = max(target_votes, key=lambda t: target_votes[t]['count'])

    votes = target_votes[best_target]
    agreement = votes['count'] / len(detections)

    base_conf = votes['total_conf'] / votes['count']

    if agreement >= 0.6:
        fused_conf = min(base_conf + 0.2, 0.99)
    elif agreement >= 0.4:
        fused_conf = base_conf
    else:
        fused_conf = max(base_conf - 0.1, 0.1)

    strike_ready = (votes['count'] >= 2 and fused_conf >= 0.75)

    return best_target, fused_conf, strike_ready
```

#### Правила aggregation

| Кількість сенсорів згодних | Ефект |
|---------------------------|-------|
| 1 з 1 | Базовий confidence (ненадійно) |
| 2 з 2 | +0.15 confidence |
| 2 з 3 | +0.10 confidence |
| 1 з 3 | -0.10 confidence (ймовірно шум) |
| 3 з 3 | +0.20 confidence, strike_ready = true |

#### Мінімум для strike_ready

```
strike_ready = True ТОДІ І ТІЛЬКИ ТОДІ, коли:
  1. Мінімум 2 сенсори згодні
  2. Confidence ≥ 0.75
  3. Target ≠ 'unknown', 'silence'
```

**Очікуване покращення: +5-8% точності.**
**Ціль після Step 4: 75-83% точності.**

---

### Step 5: Time Correlation (Tracking)

Одиночне спрацьовування ≠ подія. Рухома ціль ≠ шум.

#### Принцип

```
Час T+0s:  seg_02 виявляє infantry 75%
Час T+5s:  seg_03 виявляє infantry 78%
Час T+10s: seg_04 виявляє infantry 72%

→ Це рухома ціль (track_id: trk_0042)
→ Напрямок: seg_02 → seg_03 → seg_04 (на південь)
→ Швидкість: ~15 км/год (відстань між seg / delta_t)
→ Confidence: 82% (середнє з 3 вимірів + бонус за послідовність)
```

#### Реалізація трекінгу

```python
SEGMENT_DISTANCE_M = {
    ('seg_01', 'seg_02'): 100,
    ('seg_02', 'seg_03'): 120,
    ('seg_03', 'seg_04'): 80,
}

class TargetTracker:
    def __init__(self, max_gap_s=30):
        self.tracks = {}
        self.next_id = 1
        self.max_gap = max_gap_s

    def update(self, segment_id, target, confidence, timestamp):
        best_track = None
        best_score = 0

        for tid, track in self.tracks.items():
            if track['target'] != target:
                continue
            if abs(track['last_time'] - timestamp) > self.max_gap:
                continue
            if track['last_segment'] == segment_id:
                score = confidence * 0.5
            elif self._adjacent(track['last_segment'], segment_id):
                score = confidence * 0.8
            else:
                score = confidence * 0.2
            if score > best_score:
                best_score = score
                best_track = tid

        if best_track:
            track = self.tracks[best_track]
            track['detections'].append({
                'segment': segment_id,
                'confidence': confidence,
                'timestamp': timestamp,
            })
            track['last_segment'] = segment_id
            track['last_time'] = timestamp

            if len(track['detections']) >= 2:
                d1 = track['detections'][-2]
                d2 = track['detections'][-1]
                dist = SEGMENT_DISTANCE_M.get(
                    (d1['segment'], d2['segment']), 150
                )
                dt = d2['timestamp'] - d1['timestamp']
                if dt > 0:
                    track['speed_kmh'] = (dist / dt) * 3.6
                track['direction'] = self._direction(
                    d1['segment'], d2['segment']
                )

            return best_track, track
        else:
            tid = f"trk_{self.next_id:04d}"
            self.next_id += 1
            self.tracks[tid] = {
                'target': target,
                'detections': [{
                    'segment': segment_id,
                    'confidence': confidence,
                    'timestamp': timestamp,
                }],
                'last_segment': segment_id,
                'last_time': timestamp,
                'speed_kmh': 0,
                'direction': 'unknown',
            }
            return tid, self.tracks[tid]

    def _adjacent(self, seg_a, seg_b):
        return (seg_a, seg_b) in SEGMENT_DISTANCE_M or \
               (seg_b, seg_a) in SEGMENT_DISTANCE_M

    def _direction(self, seg_a, seg_b):
        num_a = int(seg_a.split('_')[1])
        num_b = int(seg_b.split('_')[1])
        if num_b > num_a:
            return 'SW'
        return 'NE'
```

#### Правило: "Одиночне detection ≠ event"

```python
def should_alert(track):
    det = track['detections']
    if len(det) < 2:
        return False, "single_detection_log_only"
    if len(det) == 2:
        dt = det[1]['timestamp'] - det[0]['timestamp']
        if dt > 30:
            return False, "gap_too_large"
    return True, "confirmed_track"
```

**Очікуване покращення: +3-5% точності.**
**Ціль після Step 5: 80-88% точності.**

---

### Step 6: Calibration (Критичний крок!)

**Без калібрування нічого з переліченого не працює добре.** Кожна ділянка має свій ґрунт, свою акустику, свій рівень шуму.

#### Процедура калібрування для ділянки розгортання

```
КАЛІБРУВАННЯ — ~2 години на ділянку

Етап 1: Baseline (30 хвилин)
[ ] Записати 30 хв тиші на всіх каналах
[ ] Обчислити: mean_rms, std_rms, noise_floor per channel
[ ] Зберегти як baseline_profile.json

Етап 2: Піхота (20 хвилин)
[ ] 1 людина проходить вздовж кожного сегмента (5м від сенсора)
[ ] 1 людина проходить (10м від сенсора)
[ ] Група 3 людини проходить (5м)
[ ] Група 3 людини проходить (10м)
[ ] Записати всі проходи з timestamps та labels

Етап 3: Техніка (20 хвилин)
[ ] Легкий автомобіль (10м, 20м, 50м від сенсора)
[ ] Важкий автомобіль / БТР (якщо є)
[ ] Записати всі проходи з timestamps та labels

Етап 4: Умови (20 хвилин)
[ ] Записати вітер (якщо є) — 10 хв
[ ] Записати дощ (якщо є) — 10 хв
[ ] Записати фоновий шум (генератор, дорога)

Етап 5: Обробка
[ ] Для кожного типу: обчислити середні features
[ ] Встановити пороги:
    - silence_threshold = baseline_mean + 2 * baseline_std
    - footstep_threshold = footstep_mean_rms * 0.7
    - vehicle_threshold = vehicle_mean_rms * 0.7
[ ] Зберегти як calibration_profile.json
```

#### Формат calibration profile

```json
{
  "site_id": "frontline_sector_07",
  "calibrated_at": "2026-04-19T14:30:00Z",
  "baseline": {
    "CH0": {"mean_rms": 0.012, "std_rms": 0.004, "noise_floor": 0.008},
    "CH1": {"mean_rms": 0.015, "std_rms": 0.005, "noise_floor": 0.010},
    "CH2": {"mean_rms": 0.011, "std_rms": 0.003, "noise_floor": 0.007},
    "CH3": {"mean_rms": 0.013, "std_rms": 0.004, "noise_floor": 0.009}
  },
  "thresholds": {
    "silence_rms": 0.025,
    "footstep_rms_min": 0.04,
    "vehicle_rms_min": 0.10,
    "artillery_rms_min": 0.50
  },
  "reference_features": {
    "footstep_5m":  {"rms": 0.08, "peak_freq": 2.5, "rhythm": 0.65},
    "footstep_10m": {"rms": 0.04, "peak_freq": 2.2, "rhythm": 0.55},
    "vehicle_10m":  {"rms": 0.25, "peak_freq": 15.0, "rhythm": 0.15},
    "vehicle_50m":  {"rms": 0.12, "peak_freq": 12.0, "rhythm": 0.10}
  },
  "weather_adjustments": {
    "wind_light":  {"threshold_multiplier": 1.3},
    "wind_strong": {"threshold_multiplier": 1.8},
    "rain_light":  {"threshold_multiplier": 1.5},
    "rain_heavy":  {"threshold_multiplier": 2.5}
  }
}
```

**Калібрування не є опціональним — це обов'язковий крок. Без нього все інше марно.**

---

### Step 7: ML (Майбутнє, НЕ перший крок!)

ML запускається **тільки після** збору 200+ розмічених записів і налагодження steps 1-6.

#### Мінімум даних для ML

| Клас | Мінімум записів | Джерело |
|------|----------------|---------|
| Піхота одиночна | 30 | Польовий запис |
| Піхота група | 30 | Польовий запис |
| Колісна техніка | 30 | Польовий запис |
| Гусенична техніка | 20 | Польовий запис (або симуляція) |
| Артилерія / вибух | 15 | Польовий запис |
| Копання | 20 | Польовий запис |
| Дрон | 20 | Польовий запис + симуляція |
| Тиша | 50 | Baseline |
| Вітер / дощ | 20 | Польовий запис |
| **РАЗОМ** | **235** | |

#### Алгоритм вибору

| Алгоритм | Переваги | Недоліки | Коли |
|----------|----------|----------|------|
| **KNN (k=5)** | Простий, швидкий, працює з малою вибіркою | Погано з високорозмірними features | Перша спроба, 200+ записів |
| **Random Forest** | Робіт стійкий, не потребує scaling | Довший inference | 500+ записів |
| **SVM (RBF)** | Добре з малими вибірками | Чутливий до параметрів | 300+ записів, конкретний сайт |
| **Conv1D NN** | Найкраща точність, працює з raw FFT | Потребує 2000+ записів, GPU для тренування | Production, 2000+ записів |

#### KNN implementation (перший ML-крок)

```python
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
import joblib

class TFNClassifier:
    def __init__(self, k=5):
        self.model = KNeighborsClassifier(n_neighbors=k, weights='distance')
        self.scaler = StandardScaler()
        self.trained = False
        self.feature_names = [
            'rms', 'peak_freq', 'spectral_centroid', 'zero_crossing_rate',
            'rhythm_score', 'peak_to_rms',
            'sub_hz', 'footstep', 'vehicle_low', 'vehicle_high', 'drone'
        ]

    def train(self, features_list, labels):
        X = [[f[name] for name in self.feature_names] for f in features_list]
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, labels)
        self.trained = True

    def predict(self, features):
        if not self.trained:
            return 'unknown', 0.0
        x = [[features[name] for name in self.feature_names]]
        x_scaled = self.scaler.transform(x)
        proba = self.model.predict_proba(x_scaled)[0]
        idx = np.argmax(proba)
        return self.model.classes_[idx], proba[idx]

    def save(self, path):
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
        }, path)

    def load(self, path):
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.trained = True
```

**Очікуване покращення з ML: +5-10% точності.**
**Ціль після Step 7: 85-92% точності.**

---

## Anti-False-Alarm Rules

Хибні спрацьовування (false alarms) вбивають довіру оператора. Краще пропустити подію, ніж постійно кричати "вовк".

### Правило 1: Одиночне detection = тільки log

```python
if detection_count == 1:
    action = 'log_only'
    alert = False
```

Одиночне спрацьовування одного сенсора — майже завжди шум. Log для подальшого аналізу, але не турбувати оператора.

### Правило 2: Немає руху = ймовірно шум

```python
if not has_movement_across_segments(detection, last_5_minutes):
    confidence *= 0.5
```

Справжня ціль рухається. Станонарне спрацьовування = вітер, тварина, settle.

### Правило 3: Вітер = дуже регулярний

```python
def is_wind_pattern(features):
    wind_spectral_signature = (
        features['spectral_centroid'] < 3.0 and
        features['rhythm_score'] < 0.15 and
        features['rms'] < 0.15 and
        features['peak_to_rms'] < 5
    )
    return wind_spectral_signature
```

Вітер дає дуже регулярний, низькочастотний, безперервний сигнал. Навчитися розпізнавати і пригнічувати.

### Правило 4: Дощ = wideband

```python
def is_rain_noise(features):
    all_bands_elevated = all([
        features['footstep'] > baseline * 2,
        features['vehicle_low'] > baseline * 2,
        features['vehicle_high'] > baseline * 1.5,
    ])
    return all_bands_elevated
```

Дощ піднімає ВСІ frequency bands одночасно. Справжня ціль — тільки конкретні bands.

### Правило 5: "Distant traffic" = низький SNR + continuous

```python
def is_distant_traffic(features):
    return (
        features['rms'] < 0.08 and
        features['vehicle_low'] > features['footstep'] * 3 and
        features['rhythm_score'] < 0.1 and
        features['peak_to_rms'] < 3
    )
```

Віддалений рух на шосе — постійний слабкий сигнал у vehicle_low band. Позначити як "possible_noise", не alert.

---

## Environmental Adaptation

Пороги системи повинні адаптуватися до погодних умов.

| Умова | Threshold Multiplier | Notes |
|-------|---------------------|-------|
| Ясно, тихо | 1.0 | Baseline — стандартні пороги |
| Легкий вітер (3-5 м/с) | 1.3 | Трохи вищий поріг, зберігає чутливість |
| Сильний вітер (>8 м/с) | 1.8 | Ігнорувати footstep-level events |
| Легкий дощ | 1.5 | Зменшити чутливість, зберегти vehicle detection |
| Сильний дощ | 2.5 | Система майже сліпа, позначити в status |
| Сніг / мороз | 1.2 | Ґрунт твердий → краща передача вібрацій |
| Мокрий ґрунт | 0.8 | Ґрунт м'який → гірша передача, але менше шуму |

### Реалізація adaptive thresholds

```python
class AdaptiveThreshold:
    def __init__(self, calibration):
        self.base = calibration['thresholds']
        self.weather_mult = 1.0
        self.auto_noise_mult = 1.0

    def update_weather(self, condition):
        self.weather_mult = WEATHER_MULTIPLIERS.get(condition, 1.0)

    def update_auto_noise(self, recent_rms_values):
        recent_mean = np.mean(recent_rms_values[-100:])
        baseline = self.base['silence_rms']
        if recent_mean > baseline * 2:
            self.auto_noise_mult = min(recent_mean / baseline, 3.0)
        else:
            self.auto_noise_mult = 1.0

    @property
    def effective_mult(self):
        return max(self.weather_mult, self.auto_noise_mult)

    @property
    def silence_threshold(self):
        return self.base['silence_rms'] * self.effective_mult

    @property
    def footstep_threshold(self):
        return self.base['footstep_rms_min'] * self.effective_mult

    @property
    def vehicle_threshold(self):
        return self.base['vehicle_rms_min'] * self.effective_mult
```

### Моніторинг погодних умов

```python
def detect_weather_from_signal(signal_history, fs=1000):
    features = extract_features(signal_history[-10*fs:], fs)

    if features['rms'] > 0.2 and features['rhythm_score'] < 0.1:
        if features['zero_crossing_rate'] > 50:
            return 'rain_heavy'
        return 'wind_strong'

    if features['rms'] > 0.1 and features['rhythm_score'] < 0.2:
        if features['zero_crossing_rate'] > 30:
            return 'rain_light'
        return 'wind_light'

    return 'clear'
```

---

## Recording Protocol

Як збирати навчальні дані в польових умовах.

### Setup

```
[П'єзо-сенсор] → [ADS1256] → [ESP32] → [RPi] → [SD Card / Fiber → C2]
                                          │
                                     raw_recorder.py
                                     (без класифікації,
                                      тільки запис)
```

### Процедура запису

```
1. Встановити сенсор на місці
2. Запустити raw_recorder.py:
   python sensing/raw_recorder.py --channels 0,1,2,3 --duration 60 --label "footstep_5m"
3. Виконати дію (пройти кроками на відстані 5м)
4. Маркувати timestamps:
   [14:23:15] — початок проходу
   [14:23:45] — кінець проходу
5. Зберегти як JSON:
```

### Формат запису

```json
{
  "recording_id": "rec_20260419_142315",
  "site_id": "frontline_sector_07",
  "timestamp": "2026-04-19T14:23:15Z",
  "label": "footstep_group",
  "metadata": {
    "distance_m": 5,
    "target_count": 3,
    "soil_type": "loam",
    "weather": "clear",
    "temperature_c": 18,
    "wind_mps": 2.5
  },
  "channels": {
    "CH0": {
      "samples": [0.012, 0.014, 0.013, ...],
      "sample_rate": 1000,
      "num_samples": 60000
    },
    "CH1": {
      "samples": [0.008, 0.009, 0.010, ...],
      "sample_rate": 1000,
      "num_samples": 60000
    }
  },
  "events": [
    {"time_s": 5.2, "description": "first footstep detected"},
    {"time_s": 6.8, "description": "second footstep"},
    {"time_s": 8.1, "description": "third footstep"}
  ]
}
```

### Мінімальний набір записів

| Категорія | Записів | Тривалість | Примітка |
|-----------|---------|-----------|----------|
| Тиша (baseline) | 10 × 5 хв | 50 хв | Різний час доби |
| Кроки одиночні (5м) | 10 × 1 хв | 10 хв | |
| Кроки одиночні (10м) | 10 × 1 хв | 10 хв | |
| Кроки група (5м) | 10 × 1 хв | 10 хв | 2-5 людей |
| Колісна техніка (10м) | 10 × 1 хв | 10 хв | Різні авто |
| Колісна техніка (30м) | 5 × 1 хв | 5 хв | |
| Гусенична техніка | 5 × 1 хв | 5 хв | Якщо є можливість |
| Артилерія / вибух | 5 × 30 сек | 2.5 хв | По можливості |
| Копання | 10 × 2 хв | 20 хв | |
| Вітер | 5 × 5 хв | 25 хв | Різна сила |
| Дощ | 5 × 5 хв | 25 хв | Різна інтенсивність |
| Дрон | 5 × 1 хв | 5 хв | |
| **РАЗОМ** | **95 записів** | **~3 години** | |

### Зберігання

- Формат: JSON ( один файл на запис)
- Розмір: ~120KB за 1 хв (4 канали × 1000 SPS × 60 сек × float)
- 95 записів × ~120KB = ~11MB
- Зберігати на SD картці edge-вузла
- При можливості — завантажити на C2 для централізованого ML-тренування

---

## Зведена таблиця покращень

| Step | Що робимо | Покращення | Накопичувана точність |
|------|----------|-----------|----------------------|
| 0 (MVP) | Rule-based, band energies | — | ~50-60% |
| 1 | Clean signal (filters, DC removal) | +10% | 60-70% |
| 2 | Extended features (rhythm, p2r, centroid) | +5-10% | 65-80% |
| 3 | Rule-based v2 (decision tree) | +5-10% | **70-75%** |
| 4 | Multi-sensor fusion (2-3 сенсори) | +5-8% | **75-83%** |
| 5 | Time correlation / tracking | +3-5% | **80-88%** |
| 6 | Calibration (обов'язкове!) | Критичне | Без нього все гірше на 10-20% |
| 7 | ML (KNN / Random Forest) | +5-10% | **85-92%** |

### Порядок впровадження

```
Тиждень 1: Steps 1-3 (filters + features + rules v2) → 70-75%
Тиждень 2: Step 6 (calibration) + Step 4 (multi-sensor) → 80-83%
Тиждень 3: Step 5 (tracking) → 83-88%
Тиждень 4+: Step 7 (ML, після збору 200+ записів) → 85-92%
```

---

## Зв'язок з іншими документами

| Документ | Зв'язок |
|----------|---------|
| `sensing/pipeline.md` | Signal processing pipeline, FFT, базова класифікація |
| `sensing/pseudo_das_mvp.md` | Piezo + ESP32 реалізація |
| `docs/ISR_ARCHITECTURE.md` | Повна архітектура ISR системи |
| `docs/ISR_INTELLIGENCE_GUIDE.md` | Характеристики виявлення по типах цілей |
| `configs/alert_rules.yaml` | Правила алертів та escalation |
| `architecture/node_v2.md` | Специфікація edge-вузла |

---

*Detection Accuracy Guide v1.0 — SpiderLink*
*Ревізія: 2026-04-19*
