# SpiderLink TFN — Полное описание проекта

## Версия 1.0 — Апрель 2026

---

## 1. Что это такое

**SpiderLink TFN (Tactical Fiber Network)** — это полевая система скрытого наблюдения и связи на основе оптоволоконных кабелей.

Принцип: отработанные оптоволоконные кабели от FPV-дронов (бесплатный материал) укладываются в землю вдоль линии фронта. К ним подключаются дешёвые вычислительные узлы ($169-243 каждый). Система образует mesh-сеть, которая:

- **Невидима для РЕР** — нулевая RF-эмиссия, радио-разведка противника не способна обнаружить сеть
- **Обнаруживает цели** — пьезо-сенсоры вдоль кабеля фиксируют шаги, технику, артиллерию, дроны
- **Передаёт данные** — волоконно-оптический канал связи, латентность < 1 мс/км
- **Работает под обстрелом** — ring-топология с резервными маршрутами, узлы — расходный материал (<$200, замена за 2 минуты)

Репозиторий: https://github.com/Redrock453/tactical-fiber-network

---

## 2. Как это работает (общая схема)

```
[Сенсоры] → [Edge Node] → [Fiber Mesh] → [C2 Server] → [Оператор]
  piezo       фильтрация     BATMAN-adv     FastAPI       Browser
  ADS1256     классификация   WireGuard      WebSocket     Strike btn
              event JSON      ring route     events DB     Audio alert
```

Четыре уровня:

| Уровень | Компонент | Задача |
|---------|-----------|--------|
| **Sensor Layer** | Piezo + ADS1256 ADC + ESP32 | Захват акустического сигнала |
| **Edge Nodes** | Banana Pi BPI-R3 + SFP | Фильтрация, классификация, маршрутизация |
| **Backbone Fiber** | G.657.A2 (отработанный БПЛА) | Передача данных, нулевая RF-эмиссия |
| **C2 Core** | Ноутбук / mini PC | Агрегация, визуализация, принятие решений |

---

## 3. Структура репозитория

### 3.1. Симуляторы

Все симуляторы написаны на чистом Python (без numpy), могут работать автономно.

**`simulation/das_simulator.py`** — DAS (Distributed Acoustic Sensing) симулятор

Имитирует φ-OTDR interrogation оптоволоконного кабеля. Обнаруживает и классифицирует 11 типов целей:

| Тип цели | Частоты | Уровень угрозы |
|----------|---------|----------------|
| Одиночный пешеход | 1-4 Hz, гармоніки 2x, 3x | LOW |
| Группа людей | 1-4 Hz, wider spectrum | MEDIUM |
| Колёсная техника (БТР/БМП) | 8-50 Hz, engine + wheels | MEDIUM |
| Гусеничная техника (танк) | 8-30 Hz, гармоніки 60/90 Hz | HIGH |
| Артвыстрел | Импульс 0-500 Hz, ~50ms decay | CRITICAL |
| Взрыв | 0.1-15 Hz, longer decay | CRITICAL |
| Дрон (hover) | 80-200 Hz, rotors | MEDIUM |
| Дрон (flyby) | 30-100 Hz, sweep | MEDIUM |
| РЕБ помеха | 100-2000 Hz | HIGH |
| Копание | 2-8 Hz, ритмичное с паузами | LOW |

Модель SNR:
```
SNR(d) = P_launch_dBm - α·L_km - 10·log10(d_m) - NF_dB
α = 0.35 dB/km (G.657.A2)
NF = 5 dB
P_launch = 0 dBm
```

Вероятность обнаружения (логистическая):
```
P_detect = 1 / (1 + exp(-k·(SNR - SNR_threshold)))
k = 0.5, SNR_threshold = 3 dB
```

Ложные срабатывания (False Alarm Rate):
| Условие | FAR (в час) | Характеристика |
|---------|-------------|----------------|
| Ясно | 0-1 | Базовый |
| Лёгкий ветер | 2-5 | 0.5-3 Hz шум |
| Сильный ветер | 5-15 | Пиковый шум |
| Лёгкий дождь | 3-8 | Wideband 10-100 Hz |
| Сильный дождь | 10-30 | Система частично слепа |

---

**`simulation/mesh_simulator.py`** — Mesh-сеть симулятор

Симулирует тактическую волоконно-оптическую mesh-сеть с динамической маршрутизацией.

Артиллерийская модель повреждений:
```
P_break(r, R) = 1 - exp(-r / R)

Калибр          R (радиус)
82мм миномёт    15 м
152мм гаубица   30 м
РСЗО            50 м
```

Для каждого линка проверяется 12 точек вдоль кабеля. Если хоть одна точка попадает в зону поражения с вероятностью P_break > random порога — линк рвётся.

OSPF-подобная маршрутизация:
- Primary path (Dijkstra) + backup path (link-disjoint)
- Bandwidth: 1 Gbps базовый, -5% за хоп (BATMAN-adv overhead)
- Latency: 5 мкс/км (fiber) + 0.5 мс/хоп (processing)
- Failover: 3-5 секунд типично для BATMAN-adv

Модель питания:
| Состояние | Потребление |
|-----------|-------------|
| IDLE | 2W |
| ACTIVE | 5W |
| DEGRADED | 3W |

Solar: панель × КПД × sun_factor(t), пиковое 0.8 в полдень, 0 ночью.

Network Health Score:
- Connectivity (30%): % активных линков
- Coverage (20%): % живых узлов
- Redundancy (30%): % пар с backup-path
- Battery (20%): средний % заряда
- Рейтинг: EXCELLENT / GOOD / FAIR / POOR / CRITICAL

---

**`simulation/rf_detector.py`** — RF-Opto пассивная детекция

Обнаруживает RF-излучение (РЕБ, радары, FPV-контроллеры) через волокно без единого радио-компонента. Принцип: эффект Керра + термо-оптический эффект в волокне изменяют фазу света при воздействии RF-поля.

---

### 3.2. Detection Pipeline (ISR ядро)

**`sensing/detection_pipeline.py`** — Полный pipeline обработки сигнала

Работает на edge-узлах. Чистый Python, без numpy.

```
Raw Signal → SignalBuffer → SignalFilter → FeatureExtractor → TargetClassifier → Event JSON
```

Классы:

**SignalBuffer** — кольцевой буфер для raw-семплов. capacity-based eviction.

**SignalFilter** — цифровые фильтры:
- `low_pass(data, cutoff_ratio)` — EMA low-pass
- `band_pass(data, low_ratio, high_ratio)` — полосовой
- `remove_dc(data)` — удаление DC-составляющей

**FeatureExtractor** — извлечение признаков:
| Метод | Что считает | Для чего |
|-------|------------|----------|
| `compute_rms` | Root Mean Square | Общая энергия сигнала |
| `compute_peak_amplitude` | Макс. амплитуда | Импульсы (арт/взрыв) |
| `compute_zero_crossing_rate` | Частота пересечения нуля | Доминирующая частота |
| `compute_fft_peak` | DFT peak (256-point) | Основная частота |
| `compute_spectral_centroid` | Weighted avg frequency | Низкие vs высокие |
| `compute_rhythm_score` | Autocorrelation | Периодичность (шаги vs шум) |
| `extract_all` | Все признаки разом | Полный feature vector |

**TargetClassifier** — rule-based классификатор (без ML):

10 правил, каждое с условиями по признакам. Soft scoring: каждое условие оценивается от 0 до 1, среднее × weight = итоговый score.

Примеры правил:
- Footstep: freq 0.5-8 Hz, rms 0.05-0.25, zcr 0-0.08
- Tracked vehicle: freq 10-40 Hz, rms 0.55-2.0, peak_amp 1.0-5.0
- Artillery: peak_to_rms 3.0-50.0, freq 15-300 Hz, rhythm < 0.4
- Drone: freq 80-300 Hz, zcr 0.10-0.60

**DetectionPipeline** — объединяет всё:
- feed_sample() — по одному семплу
- process_window() — обработка окна целиком
- Выход: стандартизированный ISR event JSON

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

**`sensing/multi_sensor.py`** — слияние данных с нескольких сенсоров

Проблема: один сенсор даёт ~50-60% точности. Решение: 2-3 сенсора на сегмент + корреляция по времени.

**MultiSensorFusion** — правила:
- 2+ сенсора согласны → confidence +0.2 за каждый дополнительный
- 1 сенсор → confidence -0.1 (штраф)
- Минимум 2 сенсора для action "strike_ready"

**TimeCorrelator** — отслеживает движение целей:
- Если событие перемещается seg_01 → seg_02 → seg_03 — это реальная цель, не шум
- Оценивает скорость: distance / time между сегментами
- Оценивает направление: towards_front / towards_rear / lateral / static
- Классифицирует поведение: patrol / movement / approach / retreat / static
- Правило: "одиночное обнаружение = не событие"

**EdgeAutonomy** — работа без C2:
- C2 подключён → события пересылаются
- C2 отключён + confidence > 0.8 + threat >= high → локальный alert
- C2 отключён + confidence > 0.9 + threat == critical → emergency beacon
- Остальное → очередь на отправку при восстановлении C2

---

### 3.4. C2 (Command & Control)

**`c2/server.py`** — FastAPI сервер

REST API:
| Endpoint | Метод | Назначение |
|----------|-------|------------|
| `/api/events` | POST | Приём событий от edge-узлов |
| `/api/events` | GET | Список событий (фильтры: threat, segment, limit) |
| `/api/events/{id}` | GET | Событие по ID |
| `/api/events/{id}/ack` | POST | Оператор подтвердил |
| `/api/strike-request` | POST | Запрос удара (FPV / артилерия / разведка) |
| `/api/network/status` | GET | Состояние mesh-сети |
| `/api/tracks` | GET | Активные треки целей |
| `/api/system` | GET | Статус C2 системы |
| `/ws/events` | WebSocket | Real-time push событий |

Функции:
- **Дедупликация**: отклоняет события от того же узла/сегмента/типа в течение 30 сек
- **Фильтр шума**: отклоняет low-confidence + low-SNR события
- **Track management**: автоматически создаёт и обновляет треки целей
- **Background maintenance**: чистит события старше 24ч каждые 60 сек

**`c2/operator_ui.html`** — интерфейс оператора

Одностраничный HTML, без build step, vanilla JS + CSS.

4 вкладки:
1. **Events** — таблица событий, цветовая кодировка threat (green/yellow/orange/red/flashing red), кнопки ACK и Strike Request, автообновление каждые 2 сек
2. **Tracks** — активные треки целей, timeline визуализация, направление, скорость
3. **Network** — состояние узлов (battery %, alive/dead), линков, health score
4. **System** — uptime, events processed, sensors online

Особенности:
- Тёмная тактическая тема (#0a0a0f фон, #00ff88 акцент)
- Audio alert для critical событий (Web Audio API beep)
- Бегущая строка critical алертов внизу
- WebSocket для real-time

---

### 3.5. Калькуляторы

**`calculator/fiber_budget.py`** — оптический бюджет линии

Поддерживает:
- 9 типов SFP модулей (от generic 1310nm до Cisco 10G)
- 4 типа волокна (G.652D, G.657A2, G.657B3, drone_spent)
- Loss budget: fiber + splices + connectors + bends + environment
- Классификация: OK / MARGINAL / UNUSABLE

**`calculator/topology_planner.py`** — планирование топологии

Minimum Spanning Tree + redundancy links. Deployment plan с рекомендациями.

**`calculator/splice_loss_estimator.py`** — оценка потерь на сплайсах

14 комбинаций (метод + качество скола), Monte Carlo симуляция (1000 итераций), рекомендация оптимального метода.

---

### 3.6. Dashboard

**`web/dashboard.py`** — Streamlit дашборд (запуск: `streamlit run web/dashboard.py`)

7 вкладок:
1. **Tactical Map** — folium интерактивная карта (узлы, линки, артудары, DAS-события)
2. **Live Sim** — автоматическая симуляция с деградацией сети
3. **Mesh Network** — развёртывание, артудары, маршрутизация, health score
4. **DAS Sensing** — конфигурация, environmental conditions, FFT waveform
5. **RF Detection** — пассивная RF-детекция
6. **Link Budget** — калькулятор оптического бюджета
7. **Trophy Intel** — подключение к вражескому кабелю
8. **Survivability** — чеклист маскировки, деградация под обстрелом

---

### 3.7. Документация

**`docs/ISR_ARCHITECTURE.md`** — Полная ISR-архитектура (15 узлов)

4-уровневая система:
```
[Sensor Layer] → [Edge Nodes (10-20)] → [Backbone Fiber] → [C2 Core]
```

- Пример развёртывания: 15 узлов, ring + 2 cross-links, 3 км линии фронта
- Data flow: normal operation, C2-disconnected autonomy, strike workflow
- Latency budget: < 500 мс от сенсора до оператора
- Стоимость полного развёртывания: $5,130-7,858

**`docs/DETECTION_ACCURACY.md`** — Как достичь 80%+ точности

7-шаговый план:
| Шаг | Метод | Прирост точности |
|-----|-------|-------------------|
| 1 | Clean signal (DC removal, band-pass) | +10% |
| 2 | Feature extraction (RMS, FFT, rhythm) | +5-10% |
| 3 | Rule-based v2 (decision tree) | +5-10% |
| 4 | Multi-sensor fusion (2-3 sensors) | +5-8% |
| 5 | Time correlation (track movement) | +3-5% |
| 6 | Калибровка (обязательная, 2 часа) | Критично |
| 7 | ML (KNN/Random Forest, 200+ записей) | → 85-92% |

Пороги для разных условий:
| Условие | Множитель порога |
|---------|-----------------|
| Ясно | 1.0 |
| Лёгкий ветер | 1.3 |
| Сильный ветер | 1.8 |
| Лёгкий дождь | 1.5 |
| Сильный дождь | 2.5 (система частично слепа) |

**`docs/ARCHITECTURE.md`** — Общая архитектура системы
**`docs/DEPLOYMENT_GUIDE.md`** — Руководство по развёртыванию
**`docs/FIELD_SPLICING_GUIDE.md`** — Полевая сплайсинг-инструкция (30 сек на стык)
**`docs/ISR_INTELLIGENCE_GUIDE.md`** — Руководство по ISR-разведке
**`docs/TROPHY_INTELLIGENCE.md`** — Трофейная разведка (подключение к чужому кабелю)
**`docs/TEST_PROTOCOL.md`** — Полевой чеклист тестирования

---

### 3.8. Архитектура узлов

**`architecture/node.md`** — Спецификация v0.1

3 варианта:
| Вариант | Основа | Fiber порты | Цена |
|---------|--------|-------------|------|
| A (Budget) | RPi 4B + медиаконвертер | 1 | $88-136 |
| B (Ring) | RPi 4B + USB-Ethernet + 2 конвертера | 2 | $140-229 |
| C (Premium) | Banana Pi BPI-R3 (2× встроенных SFP) | 2 | $143-232 |

Рекомендуемый: **вариант C** (Banana Pi BPI-R3) — не нужны медиаконвертеры, 2× SFP + 5× GbE, ~$100.

**`architecture/node_v2.md`** — Спецификация v0.2 (боевая)

Физическая живучесть узла:

Маскировка:
- **Визуальная**: никаких LED, чёрный/земляной корпус, форма камня/мусора
- **Тепловая**: НЕ герметичный корпус, контакт с землёй через алюминиевую пластину, "размазать тепло, а не спрятать". BPI-R3 idle ~3W → ΔT ~5-8°C — это мало
- **Anti-tracing**: узел смещён 2-5 м от линии кабеля, fiber подходит с разных сторон

```
[Батарея LiFePO4]     ← закопана 10-20 см, 2-5 м от вычислителя
       │
    3м DC кабель
       │
[Compute + SFP]        ← замаскирован, НЕ на линии кабеля
  Banana Pi BPI-R3     ← алюминиевая пластина снизу = радиатор
  2× SFP
  WireGuard
       │         │
  [Fiber IN] [Fiber OUT]  ← подходят с РАЗНЫХ сторон
```

Замена за 2 минуты:
1. Отключить питание старого
2. Отключить 2 fiber коннектора
3. Вытащить старый
4. Вставить новый
5. Подключить 2 коннектора + питание
6. Проверить: `batctl n`

Тест "5 минут": если человек находит узел за < 5 мин — провал.

---

### 3.9. Оборудование

**`hardware/BOM.md`** — Полный BOM с ценами (AliExpress, 2026)

| Комплект | Цена | Что даёт |
|----------|------|----------|
| 1. Минимальная линия (2 узла) | $130 | Связь point-to-point |
| 2. 5-узловая mesh | $1,808 | Сектор обороны |
| 3. DAS-разведка | $615-2,320 | φ-OTDR interrogation |
| 4. Трофейная разведка | $228-478 | Подключение к чужому кабелю |
| 5. Облачный узел | $34/мес | ML-анализ (опционально) |

**`hardware/CONNECTION_DIAGRAMS.md`** — 7 Mermaid-схем подключения

**`hardware/equipment_research.md`** — Исследование реального оборудования:
- SFP модули: generic 1310nm 20km, $3-8 за штуку
- Механические сплайсы: L925BP ($0.20-0.90), 3M FMS-01 ($8-15)
- OTDR: JD6800 ($50-300 б/у)

---

### 3.10. Сеть

**`network/mesh.md`** — BATMAN-adv mesh

- Протокол: BATMAN-adv (kernel module, Linux)
- VPN: WireGuard на каждом интерфейсе
- Failover: 3-5 сек типично
- Мониторинг: batctl

**`network/topology.md`** — 4 топологии

| Топология | Узлы | Выдерживает обрывов | Сложность |
|-----------|------|---------------------|-----------|
| Point-to-point | 2 | 0 | Минимальная |
| Chain | 3-5 | 0 | Низкая |
| Ring | 4-8 | 1 | Средняя |
| Partial mesh | 8-20 | 2+ | Высокая |

---

### 3.11. Сенсорика

**`sensing/pipeline.md`** — Полный pipeline: signal → filter → FFT → features → classify

**`sensing/pseudo_das_mvp.md`** — Piezo + ESP32 + ADS1256 MVP

Сборка:
- Пьезо-сенсор (FSR/piezo film) → ADS1256 ADC (24-bit, 30k SPS, $12) → ESP32 → UART → Edge Node
- Стоимость сенсорного модуля: ~$28 за сегмент

**`sensing/pseudo_das_research.md`** — Исследование сенсоров, ADC, MCU

---

### 3.12. Pitch

**`pitch/spiderlink_pitch.html`** — 10-слайдовая презентация для командования

Слайды:
1. Проблема (РЕР видит RF)
2. Решение (fiber = невидимость)
3. Как это работает (4 уровня)
4. DAS-сенсорика
5. Mesh-сеть
6. Живучесть
7. Трофейная разведка
8. Стоимость
9. MVP за 3 дня
10. Следующие шаги

---

### 3.13. Прочее

**`battle_demo.py`** — ASCII-визуализация 10-фазового боевого сценария:
1. Развёртывание → 2. Обнаружение пешеходов → 3. Техника → 4. Артудар → 5. Обрыв линков → 6. Rerouting → 7. DAS детекция → 8. Drone → 9. РЕБ → 10. Трофейный кабель

**`examples/generate_datasets.py`** — Генератор синтетических датасетов для обучения

---

## 4. Тесты

75 тестов, все зелёные:

| Файл | Тестов | Что тестирует |
|------|--------|---------------|
| test_das_simulator.py | 8 | DAS: создание, сегменты, события, SNR, terrain |
| test_mesh_simulator.py | 9 | Mesh: расстояния, линки, routing, артиллерия, battery |
| test_rf_detector.py | 8 | RF: Kerr effect, detection sweep, weak sources |
| test_fiber_budget.py | 8 | Оптический бюджет: SFP, fiber types, cost |
| test_splice_loss.py | 6 | Сплайсы: mechanical, fusion, Monte Carlo |
| test_topology.py | 5 | Топология: MST, deployment plan |
| test_detection_pipeline.py | 16 | Pipeline: buffer, filters, features, classifier, full chain |
| test_multi_sensor.py | 15 | Fusion, correlation, tracks, edge autonomy |

Запуск: `python3 -m pytest tests/ -v`

---

## 5. Зависимости

Минимальные для симуляторов: **только Python 3.11+**, без внешних библиотек.

Полные (для dashboard + C2):
```
fastapi
uvicorn
streamlit
folium
pyyaml
numpy
```

---

## 6. Стоимость полевого развёртывания

### MVP (3 дня, 2 узла + сенсоры): $255 + $28

| Компонент | Цена |
|-----------|------|
| Banana Pi BPI-R3 × 2 | $200 |
| SFP модули × 4 | $20 |
| Отработанный fiber (БПЛА) | $0 |
| Быстрые SC-коннекторы × 4 | $8 |
| LiFePO4 батареи × 2 | $60 |
| MicroSD × 2 | $12 |
| Инструменты (стриппер + скол) | $20 |
| Пьезо + ADS1256 + ESP32 × 2 | $28 |
| **ИТОГО** | **~$348** |

### Полная система (15 узлов, 3 км): $5,130-7,858

| Категория | Стоимость |
|-----------|-----------|
| Edge Nodes (×15) | $2,535-3,645 |
| SFP модули (×30) | $90-240 |
| Инструменты | $58 |
| C2 (ноутбук + резерв) | $200-500 |
| Fiber (отработанный БПЛА) | $0 |
| Батареи (×15) | $900-1,200 |
| Сенсоры (×30) | $840 |
| Трофейный комплект | $228-478 |

---

## 7. Интеграция с боевыми системами

### Уровень 1: Ручной (MVP, реализовано)

```
Сенсор → Edge Node → C2 → Оператор видит "vehicle seg_03" → Запускает FPV вручную
```

Система даёт: сектор, время, тип цели, confidence. Оператор решает и действует.

### Уровень 2: Полуавтомат (следующий шаг)

```
Система рекомендует: "tracked_vehicle в seg_03, heading south, speed 15 km/h"
→ Оператор подтверждает → FPV auto-directed в сектор
```

### Уровень 3: Полная интеграция (будущее)

```
Система auto-assigns FPV на основе track prediction
Требует: стабильная детекция >80%, надёжная связь, ROE
```

---

## 8. Что дальше

1. **Полевые записи** — 20-50 реальных сигналов (footstep, vehicle, noise) для калибровки
2. **ML-классификатор** — KNN/Random Forest на собранных данных (после 200+ записей)
3. **Реальное железо** — Banana Pi BPI-R3 + SFP + piezo, тесты в поле
4. **Автоматизация** — Level 2: система рекомендует сектор + тип цели → оператор подтверждает FPV
5. **Масштабирование** — от 2 узлов к 15+, интеграция с артиллерийскими системами

---

## 9. Ключевые принципы проекта

1. **Не переусложняй** — MVP сначала: детекция → передача → оператор видит → оператор действует
2. **Всё из реального железа** — только модели с ценами, только доступное на AliExpress
3. **Вузлы — расходный материал** — они БУДУТ уничтожаться. <$200, замена за 2 мин
4. **Волокно — главный козырь** — 0 RF, <1 мс/км, не боится РЕБ
5. **MVP подход** — point-to-point → chain → ring → mesh, не наоборот
6. **Без ML сначала** — rule-based классификация работает на 70-80%, ML потом для буста

---

*SpiderLink TFN v1.0 — Апрель 2026*
