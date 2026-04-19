# TFN Edge Node v0.1 — Specification

## Overview

Мінімальний працездатний вузол тактичної fiber-мережі. Може бути зібраний за 30 хвилин з доступних компонентів.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   TFN NODE v0.1                      │
│                                                      │
│  [Fiber IN] ── SFP ── Media Conv ──┐                 │
│                                     ├── [Ethernet]   │
│  [Fiber OUT] ── SFP ── Media Conv ──┘    Switch     │
│                                           │          │
│                                    ┌──────┴──────┐   │
│                                    │  SBC (RPi)  │   │
│                                    │  BATMAN-adv │   │
│                                    │  WireGuard  │   │
│                                    └─────────────┘   │
│                                           │          │
│  [Battery] ── DC-DC ──────────────────────┘          │
│  LiFePO4 12V    12V→5V USB-C                         │
└─────────────────────────────────────────────────────┘
```

---

## Component List — Варіант A (Budget, 1 fiber port)

| # | Компонент | Модель | Ціна | Примітка |
|---|-----------|--------|------|----------|
| 1 | SBC | Raspberry Pi 4B 4GB | $45-60 | Або Orange Pi 3B ($35) |
| 2 | Медіаконвертер | Generic 1000Base-LX | $15-25 | AliExpress, з SFP слотом |
| 3 | SFP модуль | 1.25G 1310nm 20km | $3-8 | Duplex LC, generic |
| 4 | Швидкий SC-коннектор | SC/UPC field-install | $1-3 | Для підключення кабелю |
| 5 | Патч-корд LC-LC | 1м simplex SM | $1-2 | |
| 6 | MicroSD | 16-32GB Class 10 | $5-8 | Або eMMC |
| 7 | Корпус | Пластиковий / саморобний | $3-5 | |
| 8 | Живлення | Powerbank 20Ah + кабель | $15-25 | Або 12V акум + DC-DC |
| **Разом** | | | **$88-136** | |

**Обмеження:** Тільки 1 fiber-порт = point-to-point або chain (не ring).

---

## Component List — Варіант B (Ring-ready, 2 fiber порти)

| # | Компонент | Модель | Ціна | Примітка |
|---|-----------|--------|------|----------|
| 1 | SBC | Raspberry Pi 4B 4GB | $45-60 | Потрібен 2й Ethernet |
| 2 | USB-Ethernet адаптер | Realtek RTL8156B 2.5G | $10-15 | Для другого порту |
| 3 | Медіаконвертер ×2 | Generic 1000Base-LX | $30-50 | 2 шт |
| 4 | SFP модуль ×2 | 1.25G 1310nm 20km | $6-16 | 2 шт |
| 5 | Швидкі SC-коннектори | SC/UPC | $2-6 | 2 шт |
| 6 | Патч-корди LC-LC ×2 | 1м simplex | $2-4 | |
| 7 | MicroSD | 32GB | $5-8 | |
| 8 | Корпус | Алюмінієвий, CNC | $10-20 | З радіатором |
| 9 | Живлення | LiFePO4 12V 20Ah | $30-50 | + DC-DC 12V→5V ($5) |
| **Разом** | | | **$140-229** | |

---

## Component List — Варіант C (Premium, вбудований SFP)

| # | Компонент | Модель | Ціна | Примітка |
|---|-----------|--------|------|----------|
| 1 | SBC з SFP | Banana Pi BPI-R3 | $80-120 | 2× SFP + 5× GbE |
| 2 | SFP модуль ×2 | 1.25G 1310nm 20km | $6-16 | Підключається напряму |
| 3 | Швидкі SC-коннектори | | $2-6 | |
| 4 | MicroSD / eMMC | 32GB | $5-10 | |
| 5 | Корпус | Алюмінієвий | $15-25 | |
| 6 | Живлення | LiFePO4 + DC-DC | $35-55 | |
| **Разом** | | | **$143-232** | Найкращий варіант |

---

## Software Stack

```
OS:         Debian 12 (Bookworm) або Raspberry Pi OS Lite
Routing:    BATMAN-adv (kernel module)
VPN:        WireGuard
Monitoring: batctl, custom scripts
DAS:        Python 3.11+ (якщо DAS-вузол)
Storage:    SQLite / JSON files
```

### Встановлення (один раз)

```bash
# 1. Базова система
apt update && apt upgrade -y
apt install -y batctl bridge-utils wireguard iperf3 python3 python3-pip

# 2. BATMAN-adv
modprobe batman-adv
echo "batman-adv" >> /etc/modules

# 3. WireGuard
wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey

# 4. TFN scripts
git clone https://github.com/Redrock453/tactical-fiber-network /opt/tfn
```

---

## Power Budget

| Компонент | Споживання |
|-----------|-----------|
| Raspberry Pi 4 (idle) | 2.5W |
| Raspberry Pi 4 (load) | 6.5W |
| Медіаконвертер ×2 | 3-4W |
| USB-Ethernet | 1-2W |
| **Разом idle** | **~6-8W** |
| **Разом load** | **~10-12W** |

### Час роботи від батарей

| Джерело | Ємність | Час (idle) | Час (load) |
|---------|---------|-----------|-----------|
| Powerbank 20Ah 5V | 100Wh | ~14 год | ~8 год |
| LiFePO4 12V 7Ah | 84Wh | ~12 год | ~7 год |
| LiFePO4 12V 20Ah | 240Wh | ~34 год | ~20 год |
| + Сонячна панель 20Вт | — | ∞ (вдень) | Заряджає |

---

## Physical Deployment

### Розміри

```
Корпус: ~15×10×5 см
Вага з батарелею: ~0.5-1.5 кг
```

### Підключення

```
[Fiber IN (SFP #1)] → [Вузол] → [Fiber OUT (SFP #2)]
                         │
                    [Ethernet] (для локального доступу)
                         │
                    [Живлення] (12V або USB-C)
```

### Польова установка

1. Встановити корпус у захищеному місці (окоп, бліндаж)
2. Підключити fiber-кабелі через швидкі коннектори
3. Підключити живлення
4. Перевірити: `batctl n` — бачить сусідів
5. Перевірити: `ping 192.168.10.X` — зв'язок є

Час установки: **5-10 хвилин**.

---

*Node Specification v0.1*
