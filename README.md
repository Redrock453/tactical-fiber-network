# Tactical Fiber Network (TFN) — Project SpiderLink

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Tests: 75 passed](https://img.shields.io/badge/tests-75%20passed-brightgreen.svg)]()
[![UA](https://img.shields.io/badge/🇺🇦-Ukraine-blue.svg)](https://github.com/Redrock453)

> **Польова система раннього виявлення + прихований зв'язок + підтримка удару.**
> Побудована на відпрацьованому оптоволоконні БПЛА. Zero-RF. Mesh redundancy. ISR pipeline.

---

## Що це

SpiderLink перетворює **безкоштовний відпрацьований кабель від FPV-дронів** на повноцінну бойову систему:

```
Сенсор → Edge Node → Fiber Mesh → C2 → Оператор → Дія
 piezo    класифікація  BATMAN-adv  FastAPI  Browser   FPV/удар
          SNR + FFT     WireGuard   WebSocket  карта
```

| Здатність | Як |
|-----------|-----|
| **Невидимість** | 0% RF-випромінювання — РЕР не бачить |
| **Виявлення** | DAS/п'єзо сенсори: кроки, техніка, артилерія, дрони |
| **Передача** | Fiber: < 1 мс/км, не глушиться РЕБ |
| **Живучість** | Ring + cross-links, вузли <$200, заміна за 2 хв |
| **C2** | FastAPI server + тактичний UI для оператора |
| **Удар** | Система дає сектор + тип цілі → оператор діє |

---

## Quick Start

```bash
git clone https://github.com/Redrock453/tactical-fiber-network.git
cd tactical-fiber-network
pip install -r requirements.txt

# DAS симулятор (виявлення 11 типів цілей)
python3 -m simulation.das_simulator

# Mesh симулятор (розгортання + артудар + rerouting)
python3 -m simulation.mesh_simulator

# Оптичний бюджет лінії
python3 -m calculator.fiber_budget

# Streamlit дашборд
streamlit run web/dashboard.py

# Усі тести
python3 -m pytest tests/ -v
```

---

## Структура репозиторію

```
tactical-fiber-network/
├── simulation/                    # Симулятори (чистий Python, без numpy)
│   ├── das_simulator.py           # DAS: SNR, FFT, 11 типів цілей, false alarms
│   ├── mesh_simulator.py          # Mesh: P_break артилерія, OSPF, battery/solar
│   └── rf_detector.py             # RF-Opto: пасивна детекція через ефект Керра
│
├── sensing/                       # ISR Detection Pipeline
│   ├── detection_pipeline.py      # Signal → Filter → Features → Classify → Event
│   └── multi_sensor.py            # Fusion (2+ сенсори), TimeCorrelator, EdgeAutonomy
│
├── c2/                            # Command & Control
│   ├── server.py                  # FastAPI: 9 REST + WebSocket, дедуплікація
│   └── operator_ui.html           # Тактичний UI: events, tracks, network, system
│
├── calculator/                    # Калькулятори
│   ├── fiber_budget.py            # Оптичний бюджет (9 SFP, 4 fiber типи)
│   ├── topology_planner.py        # MST + redundancy
│   └── splice_loss_estimator.py   # Monte Carlo, 14 методів
│
├── analytics/                     # Аналітика
│   ├── signature_analyzer.py      # FFT-аналіз
│   ├── mesh_health.py             # Моніторинг mesh
│   └── break_locator.py           # OTDR локалізація обривів
│
├── web/
│   └── dashboard.py               # Streamlit: folium карта, live sim, survivability
│
├── architecture/                  # Специфікації вузлів
│   ├── node.md                    # v0.1: 3 варіанти ($88-232)
│   ├── node_v2.md                 # v0.2: маскування, thermal, anti-tracing
│   └── sbc_research.md            # Порівняння 8 SBC плат
│
├── hardware/                      # Обладнання з цінами
│   ├── BOM.md                     # Повний BOM (AliExpress 2026)
│   ├── CONNECTION_DIAGRAMS.md     # 7 Mermaid-схем
│   └── equipment_research.md      # SFP, сплайси, OTDR
│
├── network/                       # Мережева архітектура
│   ├── mesh.md                    # BATMAN-adv, ring, failover
│   └── topology.md                # p2p → chain → ring → partial mesh
│
├── docs/                          # Документація
│   ├── ISR_ARCHITECTURE.md        # 15-вузлова 4-рівнева ISR-архітектура
│   ├── DETECTION_ACCURACY.md      # 7 кроків від 50% до 85%+ точності
│   ├── ARCHITECTURE.md            # Загальна архітектура
│   ├── DEPLOYMENT_GUIDE.md        # Розгортання
│   ├── FIELD_SPLICING_GUIDE.md    # Сплайсинг за 30 сек
│   ├── ISR_INTELLIGENCE_GUIDE.md  # ISR-розвідка
│   ├── TROPHY_INTELLIGENCE.md     # Трофейна розвідка
│   └── TEST_PROTOCOL.md           # Польовий чекліст
│
├── pitch/
│   └── spiderlink_pitch.html      # 10-слайдова презентація для командування
│
├── configs/                       # YAML конфігурації
├── tests/                         # 75 тестів (усі зелені)
├── battle_demo.py                 # ASCII бойовий сценарій (10 фаз)
└── PROJECT_OVERVIEW.md            # Повний опис проєкту
```

---

## ISR Pipeline (детекція → класифікація → дія)

### Edge Node (sensing/detection_pipeline.py)

```
Raw Signal → SignalBuffer → SignalFilter → FeatureExtractor → TargetClassifier → Event JSON
```

| Етап | Що робить |
|------|-----------|
| SignalFilter | Low-pass, band-pass, DC removal |
| FeatureExtractor | RMS, FFT peak, spectral centroid, rhythm score, zero-crossing rate |
| TargetClassifier | Rule-based (10 типів): footstep, vehicle, drone, artillery, digging... |
| DetectionPipeline | Об'єднує все, видає стандартизований ISR Event JSON |

### Multi-Sensor Fusion (sensing/multi_sensor.py)

- **2+ сенсори згодні** → confidence +0.2 (буст)
- **1 сенсор** → confidence -0.1 (штраф)
- **TimeCorrelator** — трекає рух цілі між сегментами: швидкість, напрям, поведінка
- **EdgeAutonomy** — якщо C2 відключений: confidence > 0.8 + high threat → локальний alert

### C2 Server (c2/server.py)

FastAPI: прийом подій, дедуплікація, трекінг, WebSocket push, strike requests.

### Operator UI (c2/operator_ui.html)

Темний тактичний інтерфейс: таблиця подій, треки цілей, стан мережі, audio alert для critical.

---

## Інтеграція з НРК

```
DAS виявляє техніку (20–80 м від кабелю)
         ↓
Detection Pipeline → класифікація + SNR confidence
         ↓
Сигнал по волокну в тил (< 1 мс/км, без RF)
         ↓
C2 Server → WebSocket push → Operator UI
         ↓
Оператор НРК: сектор + тип цілі + confidence → дія
Час реакції: 30–60 сек від виявлення до удару
```

**Кабель = лінія виявлення + вогнева відповідь.**

- Без RF-сигнатури — невидимий для РЕР противника
- Без FPV-розвідки — оператор НРК у повній безпеці
- EdgeAutonomy: локальний alert навіть без C2 (confidence > 0.8)
- Trophy Intelligence: підключення до ворожого кабелю за 3–5 хв → їхня активність видна нам

---

## DAS-симулятор (11 типів цілей)

| Ціль | Частоти | Загроза |
|------|---------|---------|
| Пішохід | 1-4 Hz, гармоніки 2x, 3x | LOW |
| Група людей | 1-4 Hz, wider | MEDIUM |
| Колісна техніка | 8-50 Hz | MEDIUM |
| Гусенична техніка | 8-30 Hz + 60/90 Hz гармоніки | HIGH |
| Артпостріл | Імпульс 0-500 Hz | CRITICAL |
| Вибух | 0.1-15 Hz | CRITICAL |
| Дрон | 80-200 Hz | MEDIUM |
| РЕБ | 100-2000 Hz | HIGH |
| Копання | 2-8 Hz, ритмічне | LOW |

Модель SNR: `SNR = P_launch - α·L - 10·log10(d) - NF` з логістичною P_detect.

---

## Mesh-мережа (під обстрілом)

Артилерійська модель: `P_break(r) = 1 - exp(-r/R)`, калібри: 82мм (15м), 152мм (30м), РСЗВ (50м).

OSPF-подібна маршрутизація: primary + backup (link-disjoint), bandwidth/latency estimation.

Failover: 3-5 сек (BATMAN-adv типово).

---

## Порівняння з RF

| Параметр | RF-зв'язок | **SpiderLink TFN** |
|----------|-----------|-------------------|
| Стелс | Виявляється РЕР за секунди | **0% випромінювання** |
| РЕБ-стійкість | Глушиться повністю | **Абсолютний імунітет** |
| Латентність | 2-10 сек | **< 500 мс (sensor → operator)** |
| Кабель | Купувати | **$0 (відпрацьований БПЛА)** |
| Розвідка | Немає | **DAS + Trophy Intelligence** |

---

## Вартість

| Комплект | Ціна | Що дає |
|----------|------|--------|
| **MVP 3 дні** (2 вузли + сенсори) | **~$348** | Зв'язок + детекція |
| **5 вузлів mesh** | **$1,808** | Сектор оборони |
| **15 вузлів повна ISR** | **$5,130-7,858** | Лінія фронту з C2 |
| Один вузол (Banana Pi BPI-R3) | **$169-243** | 2× SFP, заміна за 2 хв |

Детально: [hardware/BOM.md](hardware/BOM.md)

---

## Польовий сплайсинг (без зварювання)

| Метод | Час | Втрати | Ціна |
|-------|-----|--------|------|
| Механічний сплайс (FMS-01) | **30 сек** | 0.1-0.2 дБ | $10 |
| Швидкий коннектор (SC) | **60 сек** | 0.2-0.3 дБ | $3 |
| Зварювання | 5-15 хв | 0.02 дБ | $2000+ |

Мінімум для роботи: **стриппер ($5) + скол ($15) + 5 сплайсів ($50) = $70**

### Захист кабелю на критичних ділянках

Стандартний FPV-кабель (~0.9 мм) розрахований на одноразовий виліт.
На перехрестях доріг, де може проїхати техніка — локальне бронювання:

| Метод | Захист | Ціна | Монтаж |
|---|---|---|---|
| Металопластикова гофра | Від колісної техніки | **$2/м** | 1 хв |
| Сталева гофра (Ø25 мм) | Від гусеничної техніки | **$4/м** | 2 хв |
| Кевларова оплетка (ADSS) | Від осколків, натягу 200–600 Н | **$8/м** | Польові умови |

> Принцип: тонкий кабель по полю + механічний захист тільки на вразливих точках.
> Броня по всій довжині — не потрібна і не виправдана за вагою.

Детально: [docs/FIELD_SPLICING_GUIDE.md](docs/FIELD_SPLICING_GUIDE.md)

---

## Тести

```
75 тестів — усі зелені

test_das_simulator.py      8   DAS: SNR, FFT, terrain, false alarms
test_mesh_simulator.py     9   Mesh: P_break, OSPF, battery, solar
test_rf_detector.py        8   RF: Kerr effect, detection sweep
test_fiber_budget.py       8   Оптичний бюджет
test_splice_loss.py        6   Сплайси: Monte Carlo
test_topology.py           5   MST топологія
test_detection_pipeline.py 16  Pipeline: buffer, filters, features, classify
test_multi_sensor.py       15  Fusion, tracks, edge autonomy
```

Запуск: `python3 -m pytest tests/ -v`

---

## Статус

- [x] Концепція + документування
- [x] DAS-симулятор (SNR, FFT, false alarms)
- [x] Mesh-симулятор (артилерія, OSPF, battery/solar)
- [x] RF-Opto пасивна детекція
- [x] Detection Pipeline (filter → features → classify)
- [x] Multi-Sensor Fusion + Time Correlator
- [x] C2 Server (FastAPI) + Operator UI
- [x] Streamlit дашборд з folium картою
- [x] Специфікація вузла v0.1 + v0.2 (маскування, thermal)
- [x] Повний BOM з цінами (AliExpress 2026)
- [x] ISR-архітектура (15 вузлів, 4 рівні)
- [x] 75 тестів (усі зелені)
- [ ] Прототип на реальному залізі
- [x] Польові записи для калібрування
- [ ] ML-класифікатор (KNN/Random Forest)

---

## Безпека

- Ніколи не комітьте `.env`, токени, ключі
- WireGuard на кожному інтерфейсі
- Див. [SECURITY.md](SECURITY.md)

## Contributing

Див. [CONTRIBUTING.md](CONTRIBUTING.md)

---

*SpiderLink TFN — Квітень 2026. Ліцензія MIT.*
