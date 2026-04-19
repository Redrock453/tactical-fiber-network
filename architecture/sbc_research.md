# Дослідження SBC для вузлів Tactical Fiber Network (TFN)

> Дата: Квітень 2026  
> Призначення: вибір Single Board Computer для розгортання польових edge-вузлів TFN

---

## Порівняльна таблиця

| Модель | SoC | CPU | RAM | Ethernet | SFP | USB | Споживання (idle/load) | Габарити, мм | Ціна (AliExpress), USD |
|---|---|---|---|---|---|---|---|---|---|
| **Raspberry Pi 4 B** | BCM2711 | 4x Cortex-A72 @ 1.8GHz | 2/4/8 GB LPDDR4 | 1x GbE | Ні | 2x USB 3.0 + 2x USB 2.0 | 2.5W / 6.5W | 85.6 × 56.5 | $38–$78 |
| **Raspberry Pi 5** | BCM2712 | 4x Cortex-A76 @ 2.4GHz | 4/8 GB LPDDR4x | 1x GbE | Ні | 2x USB 3.0 + 2x USB 2.0 | 3.5W / 12W | 85.6 × 56.5 | $60–$120 |
| **Orange Pi 5** | RK3588S | 4x A76 @ 2.4 + 4x A55 @ 1.8 | 4/8/16 GB LPDDR4x | 1x GbE | Ні | 2x USB 3.0 + 2x USB 2.0 + USB-C | 2.5W / 8W | 89 × 52 | $65–$140 |
| **Orange Pi 3B** | RK3566 | 4x Cortex-A55 @ 1.8GHz | 2/4/8 GB LPDDR4 | 1x GbE | Ні | 1x USB 3.0 + 2x USB 2.0 | 1.5W / 4W | 69 × 36 | $30–$55 |
| **NanoPi R6S** | RK3588S | 4x A76 @ 2.4 + 4x A55 @ 1.8 | 8 GB LPDDR4x | 1x GbE + **2x 2.5GbE** | Ні | 1x USB 3.0 + 1x USB 2.0 | 3W / 10W | 62 × 90 | $110–$130 |
| **Banana Pi BPI-R3** | MT7986 (Filogic 830) | 4x Cortex-A53 @ 2.0GHz | 2 GB DDR4 | 5x GbE + **2x SFP 2.5GbE** | **Так (2x)** | 1x USB 3.0 | 4W / 10W | 100.5 × 148 | $85–$110 |
| **NanoPi R5S** | RK3568B2 | 4x Cortex-A55 @ 2.0GHz | 2/4 GB LPDDR4x | 1x GbE + **2x 2.5GbE** | Ні | 2x USB 3.2 Gen 1 | 2W / 5W | 62 × 90 | $55–$80 |
| **Radxa ROCK 3A** | RK3568 | 4x Cortex-A55 @ 2.0GHz | 2/4/8 GB LPDDR4 | 1x GbE | Ні | 1x USB 3.0 + 2x USB 2.0 | 1.5W / 4.5W | 85 × 52 | $35–$70 |

---

## Детальний огляд кожної плати

---

### 1. Raspberry Pi 4 Model B

| Параметр | Значення |
|---|---|
| **SoC** | Broadcom BCM2711 |
| **CPU** | Quad-core ARM Cortex-A72 @ 1.5GHz (rev B0) / 1.8GHz (rev C0, з 2021) |
| **GPU** | VideoCore VI @ 500MHz |
| **RAM** | 1 / 2 / 3 / 4 / 8 GB LPDDR4-3200 |
| **Ethernet** | 1x Gigabit (true GbE через PCIe, не через USB) |
| **SFP** | Ні |
| **USB** | 2x USB 3.0 + 2x USB 2.0 Type-A |
| **Бездротове** | Wi-Fi 5 (2.4/5 GHz) + Bluetooth 5.0 |
| **Сховище** | microSD (UHS-I) |
| **Живлення** | USB-C, 5V/3A (15W макс) |
| **Споживання** | idle: ~2.5W, load: ~6.5W (8GB варіант) |
| **GPIO** | 40-pin роз'єм |
| **Дисплей** | 2x micro-HDMI (до 4K@60) |
| **Габарити** | 85.6 × 56.5 × 17мм (credit card size) |
| **Вага** | ~46г |
| **Ціна (AliExpress 2026)** | 2GB: ~$38, 4GB: ~$55, 8GB: ~$78 |
| **Доступність** | Висока, серійне виробництво до 2034 |
| **ОС** | Raspberry Pi OS, Ubuntu, Debian, Kali, DietPi |

**Переваги для TFN:**
- Найкраща програмна підтримка та документація
- Стабільні драйвери, LTE mainline kernel
- Величезна спільнота, тисячі готових рішень
- Гарантована доступність до 2034 року
- PoE HAT для живлення через Ethernet
- USB-C живлення від польових АКБ/PA

**Недоліки для TFN:**
- Тільки 1x Ethernet порт (потрібен USB-Ethernet adapter для другого)
- Cortex-A72 — застаріла архітектура (2026)
- Ціна зростає (3GB — $83.75 у 2026 через тарифи)
- Немає NVMe / eMMC onboard
- microSD — слабке місце для надійності

---

### 2. Raspberry Pi 5

| Параметр | Значення |
|---|---|
| **SoC** | Broadcom BCM2712 |
| **CPU** | Quad-core ARM Cortex-A76 @ 2.4GHz |
| **GPU** | VideoCore VII @ 800MHz |
| **RAM** | 1 / 2 / 4 / 8 / 16 GB LPDDR4x-4267 |
| **Ethernet** | 1x Gigabit |
| **SFP** | Ні (але є PCIe 2.0 x1 для PCIe NIC) |
| **USB** | 2x USB 3.0 + 2x USB 2.0 Type-A |
| **Бездротове** | Wi-Fi 5 (2.4/5 GHz) + Bluetooth 5.0/BLE |
| **PCIe** | 1x PCIe 2.0 x1 (через FPC або HAT) |
| **Сховище** | microSD |
| **Живлення** | USB-C, 5V/5A (PD) |
| **Споживання** | idle: ~3.5W, load: ~12W |
| **GPIO** | 40-pin стандартний |
| **Дисплей** | 2x micro-HDMI (4K@60 dual) |
| **Габарити** | 85.6 × 56.5 × 19мм |
| **Вага** | ~50г |
| **Ціна (AliExpress 2026)** | 4GB: ~$60, 8GB: ~$85, 16GB: ~$120 |
| **Доступність** | Висока |
| **ОС** | Raspberry Pi OS (Bookworm), Ubuntu 24.04+, Debian 13 |

**Переваги для TFN:**
- Значно продуктивніший за Pi 4 (2-3x CPU)
- PCIe 2.0 слот → можливість підключення PCIe NIC (2.5GbE або навіть SFP+)
- Підтримка 16GB RAM для складних сценаріїв
- M.2 HAT для NVMe SSD
- PoE+ HAT підтримка

**Недоліки для TFN:**
- Все ще лише 1x вбудований Ethernet
- Вища ціна
- Потребує 27W USB-C PD (більший акумулятор)
- PCIe потрібен додатковий HAT (більше габарити)
- Новіша платформа → менше протестованих сценаріїв

---

### 3. Orange Pi 5 (RK3588S)

| Параметр | Значення |
|---|---|
| **SoC** | Rockchip RK3588S |
| **CPU** | 4x Cortex-A76 @ 2.4GHz + 4x Cortex-A55 @ 1.8GHz (big.LITTLE) |
| **GPU** | Mali-G610 MP4 (OpenGL ES 3.2, Vulkan 1.2, OpenCL 2.2) |
| **NPU** | 6 TOPS (INT4/INT8/INT16/FP16) |
| **RAM** | 4 / 8 / 16 / 32 GB LPDDR4x |
| **Ethernet** | 1x Gigabit |
| **SFP** | Ні |
| **USB** | 2x USB 3.0 Type-A + 1x USB 2.0 Type-A + 1x USB-C (OTG) |
| **Бездротове** | Немає onboard (опційний модуль) |
| **PCIe** | PCIe 3.0 x4 (M.2 M-key для NVMe) |
| **Сховище** | microSD + M.2 2280 NVMe SSD |
| **Живлення** | USB-C PD, 5V/4A |
| **Споживання** | idle: ~2.5W, load: ~8W |
| **Габарити** | 89 × 52 × 1.6мм |
| **Вага** | ~58г |
| **Ціна (AliExpress 2026)** | 4GB: ~$65, 8GB: ~$90, 16GB: ~$140 |
| **Доступність** | Висока (AliExpress, Amazon) |
| **ОС** | Ubuntu 22.04/24.04, Debian 12, Android 12/13, Armbian |

**Переваги для TFN:**
- Потужний 8-ядерний CPU (big.LITTLE) — найкраща обчислювальна потужність
- NPU 6 TOPS для ML/AI на edge (виявлення аномалій трафіку)
- M.2 NVMe SSD — надійне сховище, швидше за microSD
- До 32GB RAM
- PCIe 3.0 x4 → можливість встановлення додаткових NIC
- Низьке енергоспоживання idle
- Компактний розмір

**Недоліки для TFN:**
- Тільки 1x Ethernet (потрібен USB-адаптер або PCIe NIC)
- Немає вбудованого Wi-Fi/Bluetooth
- Якість Linux-дистрибутивів від Xunlong нижча за Raspberry Pi
- Закритий GPU драйвер (Mali)
- Деякі версії Armbian нестабільні

---

### 4. Orange Pi 3B

| Параметр | Значення |
|---|---|
| **SoC** | Rockchip RK3566 |
| **CPU** | Quad-core ARM Cortex-A55 @ 1.8GHz |
| **GPU** | Mali-G52 |
| **NPU** | 0.8 TOPS |
| **RAM** | 2 / 4 / 8 GB LPDDR4 |
| **Ethernet** | 1x Gigabit |
| **SFP** | Ні |
| **USB** | 1x USB 3.0 + 2x USB 2.0 Type-A |
| **Бездротове** | Wi-Fi 5 (2.4/5 GHz) + Bluetooth 5.0 |
| **PCIe/M.2** | M.2 2280 (NVMe/SATA) |
| **Сховище** | microSD + M.2 SSD + опційний eMMC модуль |
| **Живлення** | USB-C, 5V/3A |
| **Споживання** | idle: ~1.5W, load: ~4W |
| **Габарити** | 69 × 36 × 1.6мм |
| **Вага** | ~35г |
| **Ціна (AliExpress 2026)** | 2GB: ~$30, 4GB: ~$40, 8GB: ~$55 |
| **Доступність** | Висока |
| **ОС** | Ubuntu, Debian, Android 12, Armbian |

**Переваги для TFN:**
- Дуже низька ціна
- Дуже компактний (найменший з оглянутих)
- Мінімальне енергоспоживання
- Вбудований Wi-Fi 5 + BT 5.0
- M.2 NVMe підтримка
- Підходить для простих edge-вузлів (DNS, DHCP, monitoring)

**Недоліки для TFN:**
- Слабкий CPU (тільки A55, немає big ядeр)
- Тільки 1x Ethernet
- Немає USB 3.0 другий порт
- Mалий NPU (0.8 TOPS — практично марний)
- Обмежена виробнича потужність для складних задач

---

### 5. NanoPi R6S ⭐ ВИБІР ДЛЯ TFN (Multi-Ethernet)

| Параметр | Значення |
|---|---|
| **SoC** | Rockchip RK3588S |
| **CPU** | 4x Cortex-A76 @ 2.4GHz + 4x Cortex-A55 @ 1.8GHz |
| **GPU** | Mali-G610 MP4 |
| **NPU** | 6 TOPS |
| **RAM** | 8 GB LPDDR4x @ 2133MHz (фіксовано) |
| **eMMC** | 32 GB onboard (HS400) |
| **Ethernet** | **1x GbE + 2x 2.5GbE** (PCIe) |
| **SFP** | Ні |
| **USB** | 1x USB 3.0 Type-A + 1x USB 2.0 Type-A |
| **Бездротове** | Немає onboard |
| **Сховище** | microSD + 32GB eMMC |
| **GPIO** | 12-pin FPC (SPI, UART, I2C) |
| **LEDs** | SYS, WAN, LAN1, LAN2 (4x) |
| **RTC** | HYM8563TS з батарейкою |
| **Живлення** | USB-C PD (5V/9V/12V/20V) |
| **Споживання** | idle: ~3W, load: ~10W |
| **Габарити** | 62 × 90 × 1.6мм (PCB), з корпусом ~68×100×30мм |
| **Вага** | PCB ~45г, з корпусом ~120г |
| **Ціна (AliExpress 2026)** | 8GB/32GB eMMC: ~$110–$130 (з CNC корпусом) |
| **Доступність** | Добра (AliExpress, Amazon) |
| **ОС** | FriendlyWrt (OpenWrt 24.10), Debian 13, Ubuntu 24.04, Android 14 |

**Переваги для TFN:**
- **3x Ethernet порти з коробки** — ідеально для маршрутизатора (WAN + 2x LAN)
- 2x 2.5GbE — резерв пропускної здатності
- RK3588S — потужний 8-ядерний CPU
- 32GB eMMC onboard — не потрібна microSD
- FriendlyWrt (OpenWrt) — готовий router OS з коробки
- NPU 6 TOPS для аналізу трафіку
- RTC з батарейкою — збереження часу без живлення
- 4x LED індикатори (SYS, WAN, LAN1, LAN2) — візуальний моніторинг
- CNC алюмінієвий корпус — пасивне охолодження + захист
- Компактний розмір з корпусом
- М.2 можливий через USB

**Недоліки для TFN:**
- Фіксовано 8GB RAM (не розширюється)
- Немає вбудованого Wi-Fi
- Лише 2x USB порти
- Дорожчий за інші варіанти
- Неофіційні ОС можуть мати обмеження

---

### 6. Banana Pi BPI-R3 ⭐ НАЙКРАЩИЙ ДЛЯ FIBER (SFP!)

| Параметр | Значення |
|---|---|
| **SoC** | MediaTek MT7986 (Filogic 830) |
| **CPU** | Quad-core ARM Cortex-A53 @ 2.0GHz |
| **GPU** | Integrated IMG |
| **RAM** | 2 GB DDR4 |
| **Сховище** | 8GB eMMC + 128MB SPI NAND + microSD |
| **Ethernet** | **5x GbE** |
| **SFP** | **Так, 2x SFP 2.5GbE** |
| **USB** | 1x USB 3.0 + 2x USB слоти |
| **Бездротове** | Wi-Fi 6 (4x4 2.4GHz MT7975N + 4x4 5GHz MT7975P) — опційні модулі |
| **Mini PCIe** | 1x (через USB) — для 4G/LTE модемів |
| **M.2** | M.2 Key-M PCIe |
| **GPIO** | 26-pin |
| **Кнопки** | Reset, WPS, Boot switch |
| **Живлення** | DC 12V/2A |
| **Споживання** | idle: ~4W, load: ~10W |
| **Габарити** | 100.5 × 148мм |
| **Вага** | ~200г (без корпусу) |
| **Ціна (AliExpress 2026)** | ~$85–$110 (плата), ~$120–$150 (з металевим корпусом) |
| **Доступність** | Добра (AliExpress SINOVOIP store) |
| **ОС** | OpenWrt 22.03/24.10 (офіційна підтримка), Debian, Ubuntu |

**Переваги для TFN:**
- **2x SFP 2.5GbE** — пряме підключення оптоволокна без конвертерів!
- **5x GbE** — багато портів для комутації
- Апаратна акселерація MediaTek Filogic (FastPath)
- Mini PCIe → 4G/LTE модем для backup-каналу
- M.2 для NVMe SSD
- Wi-Fi 6 (4x4) — опційно для локального покриття
- OpenWrt офіційно підтримується (mainline)
- 3 варіанти завантаження: eMMC, SPI NAND, microSD
- Захисний металевий корпус

**Недоліки для TFN:**
- Cortex-A53 — слабший CPU за RK3588S
- Лише 2GB RAM (не розширюється)
- Габарити більші за інші SBC
- DC 12V живлення (не USB-C PD) — потрібен спеціальний БЖ
- SFP серdes фіксований на 2.5Gbase-X (не всі SFP модулі сумісні)
- Складніший initial setup (jumper конфігурація)

**Сумісні SFP модулі (перевірені):**
- SFP-2.5G-T-R-RM (2.5G Copper RJ45)
- SFP-2.5G-BX0-U/D (2.5G оптика, WDM)
- TP-LINK TL-SM410U (2.5G Copper)
- TP-LINK TL-SM411LSA (2.5G Optical Fiber)

---

### 7. FriendlyELEC NanoPi R5S

| Параметр | Значення |
|---|---|
| **SoC** | Rockchip RK3568B2 |
| **CPU** | Quad-core ARM Cortex-A55 @ 2.0GHz |
| **GPU** | Mali-G52 |
| **NPU** | 0.8 TOPS |
| **RAM** | 2 / 4 GB LPDDR4x |
| **eMMC** | 8 / 16 GB onboard |
| **Ethernet** | **1x GbE + 2x 2.5GbE** (PCIe) |
| **SFP** | Ні |
| **USB** | 2x USB 3.2 Gen 1 Type-A |
| **M.2** | M.2 Key-M PCIe 2.1 x1 (NVMe/WiFi) |
| **Сховище** | microSD + eMMC + M.2 NVMe |
| **GPIO** | 12-pin FPC |
| **LEDs** | SYS, WAN, LAN1, LAN2 (4x) |
| **RTC** | HYM8563TS |
| **Живлення** | USB-C PD (5V/9V/12V) |
| **Споживання** | idle: ~2W, load: ~5W |
| **Габарити** | 62 × 90 × 1.6мм |
| **Ціна (AliExpress 2026)** | 2GB/8GB: ~$55, 4GB/16GB: ~$80 (з CNC корпусом +$15) |
| **Доступність** | Добра |
| **ОС** | FriendlyWrt (OpenWrt 24.10), Debian 13, Ubuntu, Android 14 |

**Переваги для TFN:**
- **3x Ethernet (1x GbE + 2x 2.5GbE)** — маршрутизатор з коробки
- Дуже низьке енергоспоживання
- M.2 NVMe підтримка
- FriendlyWrt/OpenWrt готовий router OS
- RTC з батарейкою
- CNC алюмінієвий корпус
- Значно дешевший за R6S
- 2x USB 3.2 — для адаптерів / SSD

**Недоліки для TFN:**
- Cortex-A55 — слабший CPU (але достатній для маршрутизації)
- Макс 4GB RAM
- Немає SFP (потрібен media converter для fiber)
- Немає вбудованого Wi-Fi
- NPU практично марний (0.8 TOPS)

---

### 8. Radxa ROCK 3A

| Параметр | Значення |
|---|---|
| **SoC** | Rockchip RK3568 |
| **CPU** | Quad-core ARM Cortex-A55 @ 2.0GHz |
| **GPU** | Mali-G52 |
| **NPU** | 0.8 TOPS |
| **RAM** | 2 / 4 / 8 GB LPDDR4 |
| **Ethernet** | 1x Gigabit |
| **SFP** | Ні |
| **USB** | 1x USB 3.0 + 2x USB 2.0 Type-A + USB-C (OTG) |
| **Бездротове** | Немає onboard |
| **PCIe** | M.2 Key-M PCIe 3.0 x1 (NVMe) |
| **Сховище** | microSD + M.2 NVMe |
| **GPIO** | 40-pin (RPi-сумісний) |
| **Живлення** | USB-C PD, 5V/3A |
| **Споживання** | idle: ~1.5W, load: ~4.5W |
| **Габарити** | 85 × 52мм |
| **Вага** | ~45г |
| **Ціна (AliExpress 2026)** | 2GB: ~$35, 4GB: ~$50, 8GB: ~$70 |
| **Доступність** | Добра (AliExpress, Allnet) |
| **ОС** | Debian, Ubuntu, Android 12, Armbian |

**Переваги для TFN:**
- GPIO сумісний з Raspberry Pi (HAT підтримка)
- M.2 NVMe підтримка
- Дуже низька ціна
- Низьке енергоспоживання
- Хороша Linux підтримка (Armbian)

**Недоліки для TFN:**
- Тільки 1x Ethernet
- Немає Wi-Fi onboard
- Cortex-A55 — обмежена продуктивність
- Менша спільнота за Raspberry Pi

---

## Рекомендовані USB-Ethernet адаптери

Для плат із 1x Ethernet (RPi 4/5, Orange Pi 5, ROCK 3A) необхідний зовнішній адаптер для другого мережевого інтерфейсу.

### Realtek RTL8156B 2.5GbE USB-C

| Параметр | Значення |
|---|---|
| **Чіп** | Realtek RTL8156B |
| **Швидкість** | 10/100/1000/2500 Mbps |
| **Інтерфейс** | USB 3.0 / USB-C |
| **Linux підтримка** | Ядро 5.x+ (модуль `r8152`), відмінна |
| **Ціна (AliExpress)** | $8–$15 |
| **Бренди** | CableCreation, Plugable, TP-Link UE300 (1GbE), TRENDnet |

**Примітка:** RTL8156B — найкраще підтримуваний 2.5GbE USB адаптер у Linux. Альтернатива для 1GbE: RTL8153 (дешевший, ~$5).

### Рекомендація для TFN:
- **Для Pi 4/5:** RTL8156B USB-C → 2.5GbE другий порт
- **Для Orange Pi 5:** PCIe NIC (Intel I226-V або Realtek RTL8125) через M.2 → повноцінний 2.5GbE
- **Для ROCK 3A:** RTL8156B USB → другий GbE порт

---

## Польові корпуси (Field-suitable cases)

### Вимоги TFN:
- Алюміній / сплав (тепловідведення + захист)
- Пасивне охолодження (без вентиляторів)
- Герметичність або частковий захист від пилу/вологи
- Кріплення на DIN-рейку або монтаж

| Корпус | Для плати | Матеріал | Охолодження | Ціна (AliExpress) |
|---|---|---|---|---|
| FriendlyELEC CNC корпус для NanoPi R6S | NanoPi R6S | Алюміній (CNC) | Пасивне (корпус = радіатор) | ~$15 (з платою) |
| FriendlyELEC CNC корпус для NanoPi R5S | NanoPi R5S | Алюміній (CNC) | Пасивне | ~$15 |
| BPI-R3 Metal Case | Banana Pi BPI-R3 | Метал | Пасивне | ~$25–$35 |
| GeeekPi Aluminum Case | Raspberry Pi 4 | Алюміній | Пасивне + радіатори | $10–$15 |
| Argon ONE V3 | Raspberry Pi 5 | Алюміній + пластик | Пасивне + опційний вентилятор | $20–$25 |
| Стандартний корпус Orange Pi 5 | Orange Pi 5 | Алюміній (CNC) | Пасивне | $10–$18 |

### Кастомні рішення для TFN:
1. **IP65/IP67 алюмінієві корпуси** (AliExpress) — $15–$30, розмір 100×100×50мм
2. **DIN-rail монтажні корпуси** — $10–$20
3. **Pelican-style влагозахищені кейси** — $25–$50
4. **3D-друковані корпуси** (PETG/ABS) — $3–$8 матеріал

---

## Рекомендації для TFN по сценаріях

### Сценарій A: Core Router Node (центральний маршрутизатор)
**Рекомендація: Banana Pi BPI-R3**
- 2x SFP → пряме підключення fiber
- 5x GbE → комутація локальних пристроїв
- Mini PCIe → 4G/LTE backup
- OpenWrt офіційна підтримка
- Альтернатива: NanoPi R6S + USB SFP adapter

### Сценарій B: Edge Node (розподілений вузол)
**Рекомендація: NanoPi R6S**
- 3x Ethernet (WAN + 2x LAN)
- RK3588S — потужний для edge-computing
- 32GB eMMC — надійне сховище
- Компактний з CNC корпусом
- FriendlyWrt / Debian на вибір

### Сценарій C: Sensor/Monitoring Node (мінімальний вузол)
**Рекомендація: NanoPi R5S або Orange Pi 3B**
- R5S: 3x Ethernet, M.2, низьке споживання
- OPi 3B: мінімальний розмір, мінімальна ціна, Wi-Fi onboard
- Обидва: достатньо для DNS/DHCP/monitoring/snort

### Сценарій D: Heavy Compute Node (AI/ML processing)
**Рекомендація: Orange Pi 5 (16GB) або Raspberry Pi 5 (16GB)**
- OPi 5: RK3588S + NPU 6 TOPS + NVMe
- RPi 5: 16GB + PCIe NIC + найкраща ОС підтримка
- Обидва: + USB-Ethernet adapter для другого порту

### Сценарій E: Budget Node (масове розгортання)
**Рекомендація: Radxa ROCK 3A або Orange Pi 3B**
- ROCK 3A: 8GB RAM + NVMe + RPi GPIO за $70
- OPi 3B: 4GB за $40, компактний, з Wi-Fi
- + RTL8153 USB-Ethernet adapter ($5)

---

## Підсумок: Матриця вибору

| Критерій | RPi 4 | RPi 5 | OPi 5 | OPi 3B | **R6S** | **BPI-R3** | R5S | ROCK 3A |
|---|---|---|---|---|---|---|---|---|
| Кількість Ethernet | 1 | 1 | 1 | 1 | **3** | **7** | **3** | 1 |
| SFP порт | - | - | - | - | - | **+** | - | - |
| CPU продуктивність | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Енергоспоживання | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Ціна/можливості | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Програмна підтримка | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| TFN Core Router | - | - | - | - | ⭐⭐⭐⭐ | **⭐⭐⭐⭐⭐** | ⭐⭐⭐ | - |
| TFN Edge Node | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | **⭐⭐⭐⭐⭐** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| TFN Sensor Node | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | **⭐⭐⭐⭐⭐** | ⭐⭐⭐⭐ |

---

*Всі ціни вказані на основі AliExpress станом на квітень 2026. Фактичні ціни можуть відрізнятися залежно від продавця, доставки та курсу валют.*
