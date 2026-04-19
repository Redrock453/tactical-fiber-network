# SpiderLink TFN — Повний опис проєкту

## Версія 1.0 — Квітень 2026

---

## 1. Що це таке

**SpiderLink TFN (Tactical Fiber Network)** — польова система прихованого спостереження та зв'язку на базі оптоволоконних кабелів.

Принцип: відпрацьовані оптоволоконні кабелі від FPV-дронів (безкоштовний матеріал) укладаються в землю вздовж лінії фронту. До них підключаються дешеві обчислювальні вузли ($169-243 кожен). Система утворює mesh-мережу, яка:

- **Невидима для РЕР** — нульова RF-емісія, радіорозвідка противника не здатна виявити мережу
- **Виявляє цілі** — п'єзо-сенсори вздовж кабеля фіксують кроки, техніку, артилерію, дрони
- **Передає дані** — волоконно-оптичний канал зв'язку, латентність < 1 мс/км
- **Працює під обстрілом** — ring-топологія з резервними маршрутами, вузли — витратний матеріал (<$200, заміна за 2 хвилини)

Репозиторій: https://github.com/Redrock453/tactical-fiber-network

---

## 2. Як це працює (загальна схема)

```
[Сенсори] → [Edge Node] → [Fiber Mesh] → [C2 Server] → [Оператор]
  piezo       фільтрація     BATMAN-adv     FastAPI       Browser
  ADS1256     класифікація   WireGuard      WebSocket     Strike btn
              event JSON     ring route     events DB     Audio alert
```

Чотири рівні:

| Рівень | Компонент | Завдання |
|--------|-----------|----------|
| **Sensor Layer** | Piezo + ADS1256 ADC + ESP32 | Захоплення акустичного сигналу |
| **Edge Nodes** | Banana Pi BPI-R3 + SFP | Фільтрація, класифікація, маршрутизація |
| **Backbone Fiber** | G.657.A2 (відпрацьований БПЛА) | Передача даних, нульова RF-емісія |
| **C2 Core** | Ноутбук / mini PC | Агрегація, візуалізація, прийняття рішень |

---

## 3. Структура репозиторію

### 3.1. Симулятори

Усі симулятори написані на чистому Python (без numpy), працюють автономно.

**`simulation/das_simulator.py`** — DAS (Distributed Acoustic Sensing) симулятор

Імітує φ-OTDR interrogation оптоволоконного кабелю. Виявляє та класифікує 11 типів цілей:

| Тип цілі | Частоти | Рівень загрози |
|----------|---------|----------------|
| Одиничний пішохід | 1-4 Hz, гармоніки 2x, 3x | LOW |
| Група людей | 1-4 Hz, wider spectrum | MEDIUM |
| Колісна техніка (БТР/БМП) | 8-50 Hz, engine + wheels | MEDIUM |
| Гусенична техніка (танк) | 8-30 Hz, гармоніки 60/90 Hz | HIGH |
| Артпостріл | Імпульс 0-500 Hz, ~50ms decay | CRITICAL |
| Вибух | 0.1-15 Hz, longer decay | CRITICAL |
| Дрон (hover) | 80-200 Hz, rotors | MEDIUM |
| Дрон (flyby) | 30-100 Hz, sweep | MEDIUM |
| РЕБ перешкода | 100-2000 Hz | HIGH |
| Копання | 2-8 Hz, ритмічне з паузами | LOW |

Модель SNR:
```
SNR(d) = P_launch_dBm - α·L_km - 10·log10(d_m) - NF_dB
α = 0.35 dB/km (G.657.A2)
NF = 5 dB
P_launch = 0 dBm
```

Імовірність виявлення (логістична):
```
P_detect = 1 / (1 + exp(-k·(SNR - SNR_threshold)))
k = 0.5, SNR_threshold = 3 dB
```

Хибні спрацьовування (False Alarm Rate):
| Умова | FAR (на годину) | Характеристика |
|-------|-----------------|----------------|
| Ясно | 0-1 | Базовий |
| Легкий вітер | 2-5 | 0.5-3 Hz шум |
| Сильний вітер | 5-15 | Піковий шум |
| Легкий дощ | 3-8 | Wideband 10-100 Hz |
| Сильний дощ | 10-30 | Система частково сліпа |

---

**`simulation/mesh_simulator.py`** — Mesh-мережа симулятор

Симулює тактичну волоконно-оптичну mesh-мережу з динамічною маршрутизацією.

Артилерійська модель пошкоджень:
```
P_break(r, R) = 1 - exp(-r / R)

Калібр          R (радіус)
82мм міномет    15 м
152мм гаубиця   30 м
РСЗВ            50 м
```

Для кожного лінку перевіряється 12 точок уздовж кабелю. Якщо хоч одна точка потрапляє в зону ураження з імовірністю P_break > random порога — лінк рве.

OSPF-подібна маршрутизація:
- Primary path (Dijkstra) + backup path (link-disjoint)
- Bandwidth: 1 Gbps базовий, -5% за хоп (BATMAN-adv overhead)
- Latency: 5 мкс/км (fiber) + 0.5 мс/хоп (processing)
- Failover: 3-5 секунд типово для BATMAN-adv

Модель живлення:
| Стан | Споживання |
|------|-----------|
| IDLE | 2W |
| ACTIVE | 5W |
| DEGRADED | 3W |

Solar: панель × ККД × sun_factor(t), пікове 0.8 опівдні, 0 вночі.

Network Health Score:
- Connectivity (30%): % активних лінків
- Coverage (20%): % живих вузлів
- Redundancy (30%): % пар з backup-path
- Battery (20%): середній % заряду
- Рейтинг: EXCELLENT / GOOD / FAIR / POOR / CRITICAL

---

**`simulation/rf_detector.py`** — RF-Opto пасивна детекція

Виявляє RF-випромінювання (РЕБ, радари, FPV-контролери) через волокно без жодного радіо-компонента. Принцип: ефект Керра + термо-оптичний ефект у волокні змінюють фазу світла при впливі RF-поля.

---

### 3.2. Detection Pipeline (ядро ISR)

**`sensing/detection_pipeline.py`** — Повний pipeline обробки сигналу

Працює на edge-вузлах. Чистий Python, без numpy.

```
Raw Signal → SignalBuffer → SignalFilter → FeatureExtractor → TargetClassifier → Event JSON
```

Класи:

**SignalBuffer** — кільцевий буфер для raw-семплів. capacity-based eviction.

**SignalFilter** — цифрові фільтри:
- `low_pass(data, cutoff_ratio)` — EMA low-pass
- `band_pass(data, low_ratio, high_ratio)` — смуговий
- `remove_dc(data)` — видалення DC-складової

**FeatureExtractor** — витяг ознак:
| Метод | Що рахує | Для чого |
|-------|----------|----------|
| `compute_rms` | Root Mean Square | Загальна енергія сигналу |
| `compute_peak_amplitude` | Макс. амплітуда | Імпульси (арт/вибух) |
| `compute_zero_crossing_rate` | Частота перетину нуля | Домінуюча частота |
| `compute_fft_peak` | DFT peak (256-point) | Основна частота |
| `compute_spectral_centroid` | Weighted avg frequency | Низькі vs високі |
| `compute_rhythm_score` | Autocorrelation | Періодичність (кроки vs шум) |
| `extract_all` | Усі ознаки разом | Повний feature vector |

**TargetClassifier** — rule-based класифікатор (без ML):

10 правил, кожне з умовами за ознаками. Soft scoring: кожна умова оцінюється від 0 до 1, середнє × weight = підсумковий score.

Приклади правил:
- Footstep: freq 0.5-8 Hz, rms 0.05-0.25, zcr 0-0.08
- Tracked vehicle: freq 10-40 Hz, rms 0.55-2.0, peak_amp 1.0-5.0
- Artillery: peak_to_rms 3.0-50.0, freq 15-300 Hz, rhythm < 0.4
- Drone: freq 80-300 Hz, zcr 0.10-0.60

**DetectionPipeline** — об'єднує все:
- feed_sample() — по одному семплу
- process_window() — обробка вікна цілком
- Вихід: стандартизований ISR event JSON

Формат ISR Event:
```json
{
  "event_id": "a3f2b1c4",
  "timestamp": "2026-04-19T12:03:21Z",
  "target_type": "tracked_vehicle",
  "confidence": 0.82,
  "threat_level": "high",
  "features": {
    "rms": 0.45,
    "peak_amp": 1.2,
    "zcr": 0.03,
    "fft_peak_freq": 15.2,
    "spectral_centroid": 18.3,
    "rhythm_score": 0.08,
    "peak_to_rms": 2.67
  },
  "segment_id": "seg_03",
  "position_m": 2500.0,
  "source": "piezo_sensor",
  "action_recommended": "investigate"
}
```

---

### 3.3. Multi-Sensor Fusion

**`sensing/multi_sensor.py`** — злиття даних з кількох сенсорів

Проблема: один сенсор дає ~50-60% точності. Рішення: 2-3 сенсори на сегмент + кореляція за часом.

**MultiSensorFusion** — правила:
- 2+ сенсори згодні → confidence +0.2 за кожен додатковий
- 1 сенсор → confidence -0.1 (штраф)
- Мінімум 2 сенсори для action "strike_ready"

**TimeCorrelator** — відстежує рух цілей:
- Якщо подія переміщується seg_01 → seg_02 → seg_03 — це реальна ціль, не шум
- Оцінює швидкість: distance / time між сегментами
- Оцінює напрямок: towards_front / towards_rear / lateral / static
- Класифікує поведінку: patrol / movement / approach / retreat / static
- Правило: "одиничне виявлення = не подія"

**EdgeAutonomy** — робота без C2:
- C2 підключений → події пересилаються
- C2 відключений + confidence > 0.8 + threat >= high → локальний alert
- C2 відключений + confidence > 0.9 + threat == critical → emergency beacon
- Інше → черга на відправку при відновленні C2

---

### 3.4. C2 (Command & Control)

**`c2/server.py`** — FastAPI сервер

REST API:
| Endpoint | Метод | Призначення |
|----------|-------|-------------|
| `/api/events` | POST | Прийом подій від edge-вузлів |
| `/api/events` | GET | Список подій (фільтри: threat, segment, limit) |
| `/api/events/{id}` | GET | Подія за ID |
| `/api/events/{id}/ack` | POST | Оператор підтвердив |
| `/api/strike-request` | POST | Запит удару (FPV / артилерія / розвідка) |
| `/api/network/status` | GET | Стан mesh-мережі |
| `/api/tracks` | GET | Активні треки цілей |
| `/api/system` | GET | Статус C2 системи |
| `/ws/events` | WebSocket | Real-time push подій |

Функції:
- **Дедуплікація**: відхиляє події від того ж вузла/сегмента/типу протягом 30 сек
- **Фільтр шуму**: відхиляє low-confidence + low-SNR події
- **Track management**: автоматично створює та оновлює треки цілей
- **Background maintenance**: чистить події старіші за 24 год кожні 60 сек

**`c2/operator_ui.html`** — інтерфейс оператора

Односторінковий HTML, без build step, vanilla JS + CSS.

4 вкладки:
1. **Events** — таблиця подій, кольорова кодування threat (green/yellow/orange/red/flashing red), кнопки ACK та Strike Request, автооновлення кожні 2 сек
2. **Tracks** — активні треки цілей, timeline візуалізація, напрямок, швидкість
3. **Network** — стан вузлів (battery %, alive/dead), лінків, health score
4. **System** — uptime, events processed, sensors online

Особливості:
- Темна тактична тема (#0a0a0f фон, #00ff88 акцент)
- Audio alert для critical подій (Web Audio API beep)
- Бігучий рядок critical алертів внизу
- WebSocket для real-time

---

### 3.5. Калькулятори

**`calculator/fiber_budget.py`** — оптичний бюджет лінії

Підтримує:
- 9 типів SFP модулів (від generic 1310nm до Cisco 10G)
- 4 типи волокна (G.652D, G.657A2, G.657B3, drone_spent)
- Loss budget: fiber + splices + connectors + bends + environment
- Класифікація: OK / MARGINAL / UNUSABLE

**`calculator/topology_planner.py`** — планування топології

Minimum Spanning Tree + redundancy links. Deployment plan з рекомендаціями.

**`calculator/splice_loss_estimator.py`** — оцінка втрат на сплайсах

14 комбінацій (метод + якість сколу), Monte Carlo симуляція (1000 ітерацій), рекомендація оптимального методу.

---

### 3.6. Dashboard

**`web/dashboard.py`** — Streamlit дашборд (запуск: `streamlit run web/dashboard.py`)

Вкладки:
1. **Tactical Map** — folium інтерактивна карта (вузли, лінки, артудари, DAS-події)
2. **Live Sim** — автоматична симуляція з деградацією мережі
3. **Mesh Network** — розгортання, артудари, маршрутизація, health score
4. **DAS Sensing** — конфігурація, environmental conditions, FFT waveform
5. **RF Detection** — пасивна RF-детекція
6. **Link Budget** — калькулятор оптичного бюджету
7. **Trophy Intel** — підключення до ворожого кабелю
8. **Survivability** — чекліст маскування, деградація під обстрілом

---

### 3.7. Документація

**`docs/ISR_ARCHITECTURE.md`** — Повна ISR-архітектура (15 вузлів)

4-рівнева система:
```
[Sensor Layer] → [Edge Nodes (10-20)] → [Backbone Fiber] → [C2 Core]
```

- Приклад розгортання: 15 вузлів, ring + 2 cross-links, 3 км лінії фронту
- Data flow: normal operation, C2-disconnected autonomy, strike workflow
- Latency budget: < 500 мс від сенсора до оператора
- Вартість повного розгортання: $5,130-7,858

**`docs/DETECTION_ACCURACY.md`** — Як досягти 80%+ точності

7-кроковий план:
| Крок | Метод | Приріст точності |
|------|-------|------------------|
| 1 | Clean signal (DC removal, band-pass) | +10% |
| 2 | Feature extraction (RMS, FFT, rhythm) | +5-10% |
| 3 | Rule-based v2 (decision tree) | +5-10% |
| 4 | Multi-sensor fusion (2-3 сенсори) | +5-8% |
| 5 | Time correlation (track movement) | +3-5% |
| 6 | Калібрування (обов'язкове, 2 години) | Критично |
| 7 | ML (KNN/Random Forest, 200+ записів) | → 85-92% |

Пороги для різних умов:
| Умова | Множник порога |
|-------|---------------|
| Ясно | 1.0 |
| Легкий вітер | 1.3 |
| Сильний вітер | 1.8 |
| Легкий дощ | 1.5 |
| Сильний дощ | 2.5 (система частково сліпа) |

**`docs/ARCHITECTURE.md`** — Загальна архітектура системи
**`docs/DEPLOYMENT_GUIDE.md`** — Керівництво з розгортання
**`docs/FIELD_SPLICING_GUIDE.md`** — Польова сплайсинг-інструкція (30 сек на стик)
**`docs/ISR_INTELLIGENCE_GUIDE.md`** — Керівництво з ISR-розвідки
**`docs/TROPHY_INTELLIGENCE.md`** — Трофейна розвідка (підключення до чужого кабелю)
**`docs/TEST_PROTOCOL.md`** — Польовий чекліст тестування

---

### 3.8. Архітектура вузлів

**`architecture/node.md`** — Специфікація v0.1

3 варіанти:
| Варіант | Основа | Fiber порти | Ціна |
|---------|--------|-------------|------|
| A (Budget) | RPi 4B + медіаконвертер | 1 | $88-136 |
| B (Ring) | RPi 4B + USB-Ethernet + 2 конвертери | 2 | $140-229 |
| C (Premium) | Banana Pi BPI-R3 (2× вбудованих SFP) | 2 | $143-232 |

Рекомендований: **варіант C** (Banana Pi BPI-R3) — не потрібні медіаконвертери, 2× SFP + 5× GbE, ~$100.

**`architecture/node_v2.md`** — Специфікація v0.2 (бойова)

Фізична живучість вузла:

Маскування:
- **Візуальне**: жодних LED, чорний/земляний корпус, форма каменю/сміття
- **Теплове**: НЕ герметичний корпус, контакт із землею через алюмінієву пластину, "розмазати тепло, а не сховати". BPI-R3 idle ~3W → ΔT ~5-8°C — це мало
- **Anti-tracing**: вузол зміщений 2-5 м від лінії кабелю, fiber підходить з різних боків

```
[Батарея LiFePO4]     ← закопана 10-20 см, 2-5 м від обчислювача
       │
    3м DC кабель
       │
[Compute + SFP]        ← замаскований, НЕ на лінії кабелю
  Banana Pi BPI-R3     ← алюмінієва пластина знизу = радіатор
  2× SFP
  WireGuard
       │         │
  [Fiber IN] [Fiber OUT]  ← підходять з РІЗНИХ боків
```

Заміна за 2 хвилини:
1. Відключити живлення старого
2. Відключити 2 fiber конектори
3. Витягти старий
4. Вставити новий
5. Підключити 2 конектори + живлення
6. Перевірити: `batctl n`

Тест "5 хвилин": якщо людина знаходить вузол за < 5 хв — провал.

---

### 3.9. Обладнання

**`hardware/BOM.md`** — Повний BOM з цінами (AliExpress, 2026)

| Комплект | Ціна | Що дає |
|----------|------|--------|
| 1. Мінімальна лінія (2 вузли) | $130 | Зв'язок point-to-point |
| 2. 5-вузлова mesh | $1,808 | Сектор оборони |
| 3. DAS-розвідка | $615-2,320 | φ-OTDR interrogation |
| 4. Трофейна розвідка | $228-478 | Підключення до чужого кабелю |
| 5. Хмарний вузол | $34/міс | ML-аналіз (опціонально) |

**`hardware/CONNECTION_DIAGRAMS.md`** — 7 Mermaid-схем підключення

**`hardware/equipment_research.md`** — Дослідження реального обладнання:
- SFP модулі: generic 1310nm 20km, $3-8 за штуку
- Механічні сплайси: L925BP ($0.20-0.90), 3M FMS-01 ($8-15)
- OTDR: JD6800 ($50-300 в/у)

---

### 3.10. Мережа

**`network/mesh.md`** — BATMAN-adv mesh

- Протокол: BATMAN-adv (kernel module, Linux)
- VPN: WireGuard на кожному інтерфейсі
- Failover: 3-5 сек типово
- Моніторинг: batctl

**`network/topology.md`** — 4 топології

| Топологія | Вузли | Витримує обривів | Складність |
|-----------|-------|------------------|------------|
| Point-to-point | 2 | 0 | Мінімальна |
| Chain | 3-5 | 0 | Низька |
| Ring | 4-8 | 1 | Середня |
| Partial mesh | 8-20 | 2+ | Висока |

---

### 3.11. Сенсорика

**`sensing/pipeline.md`** — Повний pipeline: signal → filter → FFT → features → classify

**`sensing/pseudo_das_mvp.md`** — Piezo + ESP32 + ADS1256 MVP

Збірка:
- П'єзо-сенсор (FSR/piezo film) → ADS1256 ADC (24-bit, 30k SPS, $12) → ESP32 → UART → Edge Node
- Вартість сенсорного модуля: ~$28 за сегмент

**`sensing/pseudo_das_research.md`** — Дослідження сенсорів, ADC, MCU

---

### 3.12. Pitch

**`pitch/spiderlink_pitch.html`** — 10-слайдова презентація для командування

Слайди:
1. Проблема (РЕР бачить RF)
2. Рішення (fiber = невидимість)
3. Як це працює (4 рівні)
4. DAS-сенсорика
5. Mesh-мережа
6. Живучість
7. Трофейна розвідка
8. Вартість
9. MVP за 3 дні
10. Наступні кроки

---

### 3.13. Інше

**`battle_demo.py`** — ASCII-візуалізація 10-фазового бойового сценарію:
1. Розгортання → 2. Виявлення пішоходів → 3. Техніка → 4. Артудар → 5. Обрив лінків → 6. Rerouting → 7. DAS детекція → 8. Дрон → 9. РЕБ → 10. Трофейний кабель

**`examples/generate_datasets.py`** — Генератор синтетичних датасетів для навчання

---

## 4. Тести

75 тестів, усі зелені:

| Файл | Тестів | Що тестує |
|------|--------|-----------|
| test_das_simulator.py | 8 | DAS: створення, сегменти, події, SNR, terrain |
| test_mesh_simulator.py | 9 | Mesh: відстані, лінки, routing, артилерія, battery |
| test_rf_detector.py | 8 | RF: Kerr effect, detection sweep, weak sources |
| test_fiber_budget.py | 8 | Оптичний бюджет: SFP, fiber types, cost |
| test_splice_loss.py | 6 | Сплайси: mechanical, fusion, Monte Carlo |
| test_topology.py | 5 | Топологія: MST, deployment plan |
| test_detection_pipeline.py | 16 | Pipeline: buffer, filters, features, classifier, full chain |
| test_multi_sensor.py | 15 | Fusion, correlation, tracks, edge autonomy |

Запуск: `python3 -m pytest tests/ -v`

---

## 5. Залежності

Мінімальні для симуляторів: **тільки Python 3.11+**, без зовнішніх бібліотек.

Повні (для dashboard + C2):
```
fastapi
uvicorn
streamlit
folium
pyyaml
numpy
```

---

## 6. Вартість польового розгортання

### MVP (3 дні, 2 вузли + сенсори): $255 + $28

| Компонент | Ціна |
|-----------|------|
| Banana Pi BPI-R3 × 2 | $200 |
| SFP модулі × 4 | $20 |
| Відпрацьований fiber (БПЛА) | $0 |
| Швидкі SC-конектори × 4 | $8 |
| LiFePO4 батареї × 2 | $60 |
| MicroSD × 2 | $12 |
| Інструменти (стриппер + скол) | $20 |
| П'єзо + ADS1256 + ESP32 × 2 | $28 |
| **РАЗОМ** | **~$348** |

### Повна система (15 вузлів, 3 км): $5,130-7,858

| Категорія | Вартість |
|-----------|----------|
| Edge Nodes (×15) | $2,535-3,645 |
| SFP модулі (×30) | $90-240 |
| Інструменти | $58 |
| C2 (ноутбук + резерв) | $200-500 |
| Fiber (відпрацьований БПЛА) | $0 |
| Батареї (×15) | $900-1,200 |
| Сенсори (×30) | $840 |
| Трофейний комплект | $228-478 |

---

## 7. Інтеграція з бойовими системами

### Рівень 1: Ручний (MVP, реалізовано)

```
Сенсор → Edge Node → C2 → Оператор бачить "vehicle seg_03" → Запускає FPV вручну
```

Система дає: сектор, час, тип цілі, confidence. Оператор вирішує і діє.

### Рівень 2: Напівавтомат (наступний крок)

```
Система рекомендує: "tracked_vehicle у seg_03, heading south, speed 15 km/h"
→ Оператор підтверджує → FPV auto-directed у сектор
```

### Рівень 3: Повна інтеграція (майбутнє)

```
Система auto-assigns FPV на основі track prediction
Потребує: стабільна детекція >80%, надійний зв'язок, ROE
```

---

## 8. Що далі

1. **Польові записи** — 20-50 реальних сигналів (footstep, vehicle, noise) для калібрування
2. **ML-класифікатор** — KNN/Random Forest на зібраних даних (після 200+ записів)
3. **Реальне залізо** — Banana Pi BPI-R3 + SFP + piezo, тести в полі
4. **Автоматизація** — Level 2: система рекомендує сектор + тип цілі → оператор підтверджує FPV
5. **Масштабування** — від 2 вузлів до 15+, інтеграція з артилерійськими системами

---

## 9. Ключові принципи проєкту

1. **Не ускладнюй** — MVP спочатку: детекція → передача → оператор бачить → оператор діє
2. **Все з реального заліза** — тільки моделі з цінами, тільки доступне на AliExpress
3. **Вузли — витратний матеріал** — вони БУДУТЬ знищуватись. <$200, заміна за 2 хв
4. **Волокно — головний козир** — 0 RF, <1 мс/км, не боїться РЕБ
5. **MVP підхід** — point-to-point → chain → ring → mesh, не навпаки
6. **Без ML спочатку** — rule-based класифікація працює на 70-80%, ML потім для бусту

---

*SpiderLink TFN v1.0 — Квітень 2026*
