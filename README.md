# Tactical Fiber Network (TFN) — Project SpiderLink

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg?logo=docker)](https://docker.com)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests: 75 passed](https://img.shields.io/badge/tests-75%20passed-brightgreen.svg?logo=pytest)]()
[![UA](https://img.shields.io/badge/🇺🇦-Ukraine-blue.svg)](https://github.com/Redrock453)

> **Система раннього виявлення + прихований зв'язок + підтримка удару.**
> Побудована на відпрацьованому оптоволоконному кабелі від FPV-дронів. Zero-RF. Mesh redundancy. ISR pipeline.

---

##Mission Brief

SpiderLink перетворює **безкоштовний відпрацьований кабель від FPV-дронів** на повноцільну бойову систему:

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
# 1. Клонування
git clone https://github.com/Redrock453/tactical-fiber-network.git
cd tactical-fiber-network

# 2. Залежності (чистий Python, без numpy)
pip install -r requirements.txt

# 3. Симулятори
python3 -m simulation.das_simulator    # DAS: 11 типів цілей
python3 -m simulation.mesh_simulator   # Mesh: артудар + rerouting

# 4. Калькулятори
python3 -m calculator.fiber_budget      # Оптичний бюджет

# 5. Дашборд
streamlit run web/dashboard.py
```

### Docker (опціонально)

```bash
docker build -t tfn .
docker run -p 8501:8501 tfn
```

---

## Sensor Characteristics (11 Target Types)

| # | Ціль | Частота | Амплітуда | Загроза | Дистанція |
|---|------|---------|-----------|---------|-----------|
| 1 | Пішохід | 1-4 Hz | ±0.02g | LOW | 5-15 м |
| 2 | Група людей (3+) | 1-4 Hz | ±0.05g | MEDIUM | 5-15 м |
| 3 | Колісна техніка | 8-50 Hz | ±0.3g | MEDIUM | 10-30 м |
| 4 | Гусенична техніка | 8-30 Hz + 60/90 Hz | ±0.8g | HIGH | 15-50 м |
| 5 | Артпостріл | 0-500 Hz (імпульс) | ±2.0g | CRITICAL | 50-200 м |
| 6 | Вибух | 0.1-15 Hz | ±1.5g | CRITICAL | 30-100 м |
| 7 | Дрон FPV | 80-200 Hz | ±0.1g | MEDIUM | 10-25 м |
| 8 | Дрон payload | 30-80 Hz | ±0.05g | LOW | 5-15 м |
| 9 | РЕБ-система | 100-2000 Hz | ±0.5g | HIGH | 20-80 м |
| 10 | Копання/траншея | 2-8 Hz (ритм) | ±0.03g | LOW | 3-10 м |
| 11 | Будівля/конструкція | 1-10 Hz | ±0.01g | INFO | 5-20 м |

**Модель детекції:** `P_detect = 1 / (1 + e^-(SNR - β))`, де β = 1.0 (поріг)

**Модель SNR:** `SNR = P_launch - α·L - 10·log10(d) - NF`

---

## Testing

```bash
# Усі тести
python3 -m pytest tests/ -v

# specific test suite
python3 -m pytest tests/test_das_simulator.py -v
python3 -m pytest tests/test_detection_pipeline.py -v
python3 -m pytest tests/test_multi_sensor.py -v

# coverage
python3 -m pytest tests/ --cov=sensing --cov=calculator -v

# CI mode
python3 -m pytest tests/ -v --tb=short
```

### Test Coverage

| Suite | Тестів | Покриття |
|-------|--------|----------|
| DAS Simulator | 8 | SNR, FFT, terrain, false alarms |
| Mesh Simulator | 9 | P_break, OSPF, battery, solar |
| RF Detector | 8 | Kerr effect, detection sweep |
| Fiber Budget | 8 | Оптичний бюджет |
| Splice Loss | 6 | Monte Carlo |
| Topology | 5 | MST топологія |
| Detection Pipeline | 16 | Buffer, filters, features, classify |
| Multi Sensor | 15 | Fusion, tracks, edge autonomy |

---

## Repository Structure

```
tactical-fiber-network/
├── simulation/                    # Симулятори (чистий Python)
│   ├── das_simulator.py           # DAS: SNR, FFT, 11 типів цілей
│   ├── mesh_simulator.py          # Mesh: P_break, OSPF, battery
│   └── rf_detector.py            # RF-Opto: ефект Керра
│
├── sensing/                       # ISR Detection Pipeline
│   ├── detection_pipeline.py     # Signal → Filter → Features → Classify
│   └── multi_sensor.py           # Fusion, TimeCorrelator, EdgeAutonomy
│
├── c2/                          # Command & Control
│   ├── server.py                # FastAPI: REST + WebSocket
│   └── operator_ui.html          # Тактичний UI
│
├── calculator/                   # Калькулятори
│   ├── fiber_budget.py          # Оптичний бюджет
│   ├── topology_planner.py     # MST + redundancy
│   └── splice_loss_estimator.py
│
├── analytics/                    # Аналітика
│   ├── signature_analyzer.py     # FFT-аналіз
│   ├── mesh_health.py         # Моніторинг
│   └── break_locator.py       # OTDR
│
├── web/
│   └── dashboard.py            # Streamlit
│
├── architecture/               # Специфікації
│   ├── node.md              # v0.1
│   └── node_v2.md          # v0.2
│
├── hardware/                 # Обладнання
│   ├── BOM.md              # Повний BOM
│   └── CONNECTION_DIAGRAMS.md
│
├── network/                  # Мережева архітектура
│   ├── mesh.md            # BATMAN-adv
│   └── topology.md
│
├── configs/                  # YAML
├── tests/                   # 75 тестів
├── battle_demo.py           # ASCII сценарій
└── PROJECT_OVERVIEW.md
```

---

## ISR Pipeline

```
Raw Signal → SignalBuffer → SignalFilter → FeatureExtractor → TargetClassifier → ISR Event
```

| Етап | Функція |
|------|--------|
| SignalBuffer | Кільцевий буфер 1024 січок |
| SignalFilter | Low-pass, band-pass, DC removal |
| FeatureExtractor | RMS, FFT peak, spectral centroid, rhythm score, zero-crossing |
| TargetClassifier | Rule-based: 11 типів |
| Event JSON | Стандартизований вихід |

### Multi-Sensor Fusion

- **2+ сенсори погоджуються** → confidence +0.2
- **1 сенсор** → confidence -0.1
- **TimeCorrelator** → трекінг руху цілі
- **EdgeAutonomy** → локальний alert без C2 (confidence > 0.8)

---

## Cost

| Комплект | Ціна | Призначення |
|----------|------|------------|
| **MVP 3 дні** | ~$348 | 2 вузл�� + с��нсори |
| **5 вузлів mesh** | ~$1,808 | Сектор оборони |
| **15 вузлів ISR** | $5,130-7,858 | Лінія фронту з C2 |
| **Один вузол** | $169-243 | BPI-R3, заміна 2 хв |

---

## Field Splicing

| Метод | Час | Втрати | Ціна |
|-------|-----|--------|------|
| Механічний сплайс | 30 сек | 0.1-0.2 дБ | $10 |
| Швидкий коннектор | 60 сек | 0.2-0.3 дБ | $3 |
| Зварювання | 5-15 хв | 0.02 дБ | $2000+ |

### Cable Protection

| Метод | Захист | Ціна/м |
|-------|--------|--------|
| Металопластикова гофра | Від колісної | $2 |
| Сталева гофра Ø25 мм | Від гусеничної | $4 |
| Кевларова оплетка | Від осколків | $8 |

---

## Contributing

Див. [CONTRIBUTING.md](CONTRIBUTING.md)

### Areas of Contribution

- **Simulation:** Нові сценарії, фізичні моделі
- **DAS:** Профілі сигнатур, ML класифікатор
- **RF-Opto:** Моделі детекції
- **Calculator:** Інструменти оптимізації
- **Hardware:** BOM, обладнання
- **Documentation:** Польові гіди, діаграми
- **Web:** Візуалізація

### Commit Convention

```
feat: new feature
fix: bug fix
docs: documentation
sim: simulation/scenario
calc: calculator update
test: tests
infra: CI/CD, Docker
```

---

## Security

- Ніколи не комітити `.env`, токени, ключі
- WireGuard на кожному інтерфейсі
- Див. [SECURITY.md](SECURITY.md)

---

*SpiderLink TFN — Квітень 2026. Ліцензія MIT.*