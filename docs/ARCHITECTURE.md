# Архітектура системи TFN

## Огляд

Тактична волоконно-оптична мережа (SpiderLink) працює на 3 рівнях:

```
┌─────────────────────────────────────────────────────┐
│                 LAYER 3: INTELLIGENCE                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │  ML      │ │ Tactical │ │ Counter- │            │
│  │  Class.  │ │   Map    │ │ battery  │            │
│  └──────────┘ └──────────┘ └──────────┘            │
├─────────────────────────────────────────────────────┤
│                 LAYER 2: PROCESSING                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │  FFT +   │ │  RF-Opto │ │  OTDR    │            │
│  │  DAS     │ │  Detect  │ │  Break   │            │
│  │  Analysis│ │          │ │  Locate  │            │
│  └──────────┘ └──────────┘ └──────────┘            │
├─────────────────────────────────────────────────────┤
│                 LAYER 1: PHYSICAL                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │  Fiber   │ │  Mesh    │ │  Splicing│            │
│  │  Cable   │ │  Nodes   │ │  (Field) │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

---

## Рівень 1: Фізичний

### Волоконно-оптичний кабель
- Тип: Одномодовий G.657.A2 (стійкий до вигинів)
- Джерело: Волокно від відпрацьованих FPV-дронів ($0)
- Затухання: 0.35 дБ/км @ 1310нм, 0.22 дБ/км @ 1550нм
- Типова довжина: 1-10 км на лінк

### Вузли
- **Окопний вузол**: Базовий вузол мережі на передовій позиції
- **Ретрансляційний вузол**: Точка з'єднання між сегментами волокна
- **Базова станція**: Головна точка агрегації з SFP-комутатором
- **Опитувач DAS**: Вузол з обладнанням φ-OTDR для зондування

### Польова сплайка
- Механічні сплайки: 30 секунд, втрати 0.1-0.3 дБ
- Швидкі конектори: 60 секунд, втрати 0.2-0.5 дБ
- Зварювання волокна в польових умовах не потрібне

---

## Рівень 2: Обробка

### Конвеєр DAS
```
Fiber → φ-OTDR → Raw backscatter → High-pass filter → FFT (1024pt)
→ Feature extraction → ML classifier → Alert generation
```

### Виявлення RF-Opto
```
Fiber → Phase monitor → Kerr effect analysis → RF source classification
→ Position estimation → Alert generation
```

### Моніторинг OTDR
```
Fiber → OTDR pulse → Return trace → Event detection
→ Break/degradation localization → Alert generation
```

---

## Рівень 3: Інтелект

### ML Класифікація
- Вхід: FFT спектр (1024 точки)
- Модель: 3-шаровий Conv1D + Dense (12 класів)
- Вивід: 5-50мс на крайовому обладнанні
- Навчання: Master Node (RTX 4090)

### Тактична карта
- Накладання подій у реальному часі
- Візуалізація маршруту волокна
- Індикатори стану вузлів/лінків
- Кольорове кодування рівня загрози

### Контрбатарейна боротьба
- Виявлення артилерійського вогню
- Оцінка траєкторії
- Автоматичні координати цілі
- <30с від виявлення до вогневого завдання

---

## Мережева архітектура

```
[Master Node (Rear)]
    │
    ├── WireGuard VPN ── [DigitalOcean Droplet (Cloud ML)]
    │
    ├── Fiber trunk ── [Base Station]
    │                      │
    │                      ├── Fiber ── [Trench Node A]
    │                      │                ├── DAS monitoring
    │                      │                └── Local routing
    │                      │
    │                      ├── Fiber ── [Relay Node]
    │                      │                │
    │                      │                ├── Fiber ── [Trench Node B]
    │                      │                └── Fiber ── [Observation Post]
    │                      │
    │                      └── Fiber ── [DAS Interrogator]
    │                                       │
    │                                       └── Trophy cable (enemy)
    │
    └── Telegram Bot / Web Dashboard
```

---

## Потік даних

```
Sensor Data:
  DAS backscatter → Edge FFT → Feature vector → [local classify OR cloud classify]
  RF phase shift → Edge analysis → RF detection → alert
  OTDR trace → Edge processing → break location → alert

Alerts:
  Local alert → Edge Node → Telegram / Dashboard
  Cloud alert → Master Node → Push notification

Commands:
  Operator → Dashboard → Edge Node → Adjust parameters
  Commander → Tactical Map → Fire mission coordinates
```

---

## Архітектура безпеки

```
Physical Security:
  - No RF emission (invisible to RER)
  - Fiber requires physical access to tap
  - Encrypted traffic (WireGuard)

Network Security:
  - WireGuard VPN (ChaCha20-Poly1305)
  - UFW firewall (only WireGuard port open)
  - No public services exposed

Data Security:
  - Local processing by default
  - Encrypted transmission to cloud
  - No data stored in clear on cloud
  - OPSEC: no real coordinates in repo
```

---

*Архітектура v2.0*
