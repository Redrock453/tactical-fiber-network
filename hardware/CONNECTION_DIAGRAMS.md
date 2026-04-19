# TFN — Схеми підключення (Connection Diagrams)

## 1. Мінімальна лінія (2 вузли)

```mermaid
graph LR
    subgraph Node A [Вузол A — Окоп]
        A1[SFP модуль<br/>1310nm 20km]
        A2[Медіаконвертер]
        A3[Ноутбук / RPi]
        A1 --- A2 --- A3
    end

    subgraph Fiber [Оптоволокно 1-10 км]
        F1[Швидкий SC<br/>коннектор]
        F2[Волокно БПЛА<br/>G.657.A2]
        F3[Механічний<br/>сплайс ×3]
        F4[Швидкий SC<br/>коннектор]
        F1 --- F2 --- F3 --- F4
    end

    subgraph Node B [Вузол B — Тил]
        B1[SFP модуль<br/>1310nm 20km]
        B2[Медіаконвертер]
        B3[Ноутбук / RPi]
        B1 --- B2 --- B3
    end

    A1 ==>|LC патч-корд| F1
    F4 ==>|LC патч-корд| B1
```

### З'єднання
1. Ноутбук → Ethernet → Медіаконвертер → SFP → [SC коннектор] → **Волокно** → [SC коннектор] → SFP → Медіаконвертер → Ethernet → Ноутбук

---

## 2. Mesh-мережа (5 вузлів)

```mermaid
graph TB
    subgraph Tier1 [Tier 1 — Тил]
        REAR[🏠 Тилова база<br/>Master Node<br/>RPi + WiFi]
        CP[📻 Командний пункт<br/>RPi + BATMAN-adv]
    end

    subgraph Tier2 [Tier 2 — ЛБЗ]
        A[🔰 Позиція Alpha<br/>Edge Node]
        B[🔰 Позиція Bravo<br/>Edge Node]
        C[🔰 Позиція Charlie<br/>Edge Node]
    end

    REAR ---|Оптоволокно 3км| CP
    CP ---|Оптоволокно 2км| A
    CP ---|Оптоволокно 2.5км| B
    A ---|Оптоволокно 1.5км| B
    B ---|Оптоволокно 2км| C
    REAR -.->|Оптоволокно 4км<br/>РЕЗЕРВ| C

    style REAR fill:#0066cc,color:#fff
    style CP fill:#0066cc,color:#fff
    style A fill:#009933,color:#fff
    style B fill:#009933,color:#fff
    style C fill:#009933,color:#fff
```

### Маршрутизація
- Протокол: B.A.T.M.A.N. advanced (в ядрі Linux)
- Автоматичне перемикання при обриві: < 5 сек
- Резервування: мінімум 2 шляхи до кожного вузла

---

## 3. DAS-сенсор (φ-OTDR)

```mermaid
graph LR
    subgraph Interrogator [DAS Інтеррогатор]
        LASER[Лазер<br/>1550nm]
        DET[Фотоприймач<br/>+ ADC]
        PROC[Edge Processor<br/>FFT + ML]
        LASER -->|імпульс| DET --> PROC
    end

    subgraph Fiber [Оптоволокно 5-40 км]
        CH1[Канал 0-1000м<br/>🟢 Тихо]
        CH2[Канал 1000-2000м<br/>🟡 Піхота]
        CH3[Канал 2000-3500м<br/>🔴 Техніка]
        CH4[Канал 3500-5000м<br/>🟢 Тихо]
        CH1 --- CH2 --- CH3 --- CH4
    end

    subgraph Targets [Цілі]
        T1[👣 Піхота<br/>1200м від кабелю]
        T2[🚛 БТР ×3<br/>2500м]
        T3[💥 Артпостріл<br/>3200м]
        T1 -.->|вібрація| CH2
        T2 -.->|вібрація| CH3
        T3 -.->|ударна хвиля| CH3
    end

    PROC -->|Backscatter<br/>аналіз| Fiber
    Fiber -->|фазові<br/>зміни| DET
```

---

## 4. Трофейна розвідка

```mermaid
sequenceDiagram
    participant O as Наш патруль
    participant FC as Швидкий FC-коннектор
    participant C as Ворожий кабель
    participant OTDR as Портативний OTDR
    participant M as Master Node

    Note over O,C: Ніч, нейтральна смуга
    O->>C: Виявлено шматок кабелю
    O->>FC: Зачистка + скол (30 сек)
    FC->>C: Підключення до кінця
    OTDR->>C: Надсилання імпульсу
    C-->>OTDR: Backscatter трасування
    
    Note over C: 1500м — патруль<br/>3000м — техніка ×3<br/>3800м — генератор (КП?)
    
    OTDR->>M: Дані за зашифрованим каналом
    M->>M: ML-класифікація
    M-->>O: ISR-звіт + координати
    Note over O: Відхід за 5 хвилин
```

---

## 5. Edge Node — внутрішня схема

```mermaid
graph TB
    subgraph EdgeNode [Edge Node — Окоп]
        BAT[LiFePO4 батарея<br/>12V 20Ah]
        DC[DC-DC конвертер<br/>12V→5V USB-C]
        RPI[Raspberry Pi 5<br/>8GB RAM]
        SW[Ethernet світч<br/>5-порт]
        MC[Медіаконвертер<br/>SFP→RJ45]
        SFP[SFP модуль<br/>1310nm]
        
        BAT -->|12V| DC -->|5V USB-C| RPI
        BAT -->|12V| MC
        RPI ---|Ethernet| SW
        MC ---|Ethernet| SW
        SFP ---|LC duplex| MC
    end

    FIBER[Оптоволокно] ==>|SC коннектор| SFP

    subgraph Software [ПЗ на RPi]
        BATMAN[B.A.T.M.A.N.<br/>mesh routing]
        WG[WireGuard<br/>VPN]
        DAS[DAS Monitor<br/>FFT аналіз]
        ALERT[Alert Service<br/>Telegram]
        BATMAN --- WG --- DAS --- ALERT
    end

    RPI --- Software

    style BAT fill:#ff9900,color:#000
    style RPI fill:#009933,color:#fff
    style SFP fill:#0066cc,color:#fff
```

---

## 6. RF-Opto детекція

```mermaid
graph LR
    subgraph Enemy [Ворожі джерела RF]
        EW[РЕБ станція<br/>1кВт, 2.4ГГц]
        FPV[FPV пульт<br/>0.5Вт, 2.4ГГц]
        RADAR[Радар<br/>10кВт, 10ГГц]
    end

    subgraph Passive [Пасивна детекція через волокно]
        FIBER[Оптоволоконний кабель<br/>= пасивна антена]
        KERR[Ефект Керра<br/>Δn = n₂×E²]
        THERMO[Термооптичний<br/>ΔT → Δn]
    end

    EW -->|RF поле| FIBER
    FPV -->|RF поле| FIBER
    RADAR -->|RF поле| FIBER
    FIBER --> KERR
    FIBER --> THERMO

    KERR -->|ΔΦ > 10⁻⁶ рад| DETECT[φ-OTDR<br/>Детекція!]
    THERMO --> DETECT

    DETECT -->|Позиція + потужність| ALERT[Alert:<br/>РЕБ на 3800м<br/>~500Вт]
```

---

## 7. Повна архітектура системи

```mermaid
graph TB
    subgraph Frontline [Лінія бойового зіткнення]
        N1[Вузол A<br/>DAS + Mesh]
        N2[Вузол B<br/>DAS + Mesh]
        N3[Вузол C<br/>Mesh]
        N1 ---|fiber| N2 ---|fiber| N3
    end

    subgraph Rear [Тил]
        CP[КП<br/>Base Station]
        MASTER[Master Node<br/>RTX 4090]
    end

    subgraph Cloud [Хмара]
        DO[DigitalOcean<br/>ML Training]
        GRAF[Grafana<br/>Dashboard]
        TG[Telegram<br/>Alerts]
    end

    N3 ---|fiber| CP
    N1 ---|fiber redundant| CP
    CP ---|fiber| MASTER
    MASTER ---|WireGuard| DO
    DO --- GRAF
    DO --- TG

    TROPHY[🏆 Ворож. кабель<br/>Трофей] -.->|φ-OTDR| N1

    style N1 fill:#cc3300,color:#fff
    style N2 fill:#cc3300,color:#fff
    style N3 fill:#cc3300,color:#fff
    style CP fill:#0066cc,color:#fff
    style MASTER fill:#6633cc,color:#fff
    style DO fill:#0066ff,color:#fff
    style TROPHY fill:#ffcc00,color:#000
```

---

*Схеми підключення v1.0 — Mermaid diagrams*
