# TFN Mesh Networking — BATMAN-adv + Failover

## Що ми будуємо

Не просто "mesh", а **самовідновлювану проводну мережу без єдиної точки відмови**.

---

## 1. Чому BATMAN-adv

| Протокол | Плюси | Мінуси | Для TFN |
|----------|-------|--------|---------|
| **BATMAN-adv** | Вбудований в Linux kernel, простий, працює на L2, не потрібен IP для routing | Не оптимізує маршрути глобально | **Рекомендований** |
| OLSR | IP-level, краща оптимізація | Складніший, потребує демон | Альтернатива |
| Static routes | Простий | Не самовідновлюється | Тільки для тесту |

### Чому саме BATMAN-adv
- Працює на Layer 2 — прозорий для IP
- Може об'єднувати кілька інтерфейсів (fiber + WiFi)
- Автоматичне перемикання при обриві
- Частина Linux kernel з 3.x — нічого не треба ставити
- `batctl` — єдиний інструмент керування

---

## 2. Топології (поетапно)

### v0.2 — RING (кільце) — обов'язковий мінімум

```
    A ——— B
    |     |
    |     |
    D ——— C

Кожен вузол має 2 з'єднання
Один обрив → мережа працює
```

**Чому ring:**
- Мінімум коду
- Один обрив = все одно зв'язок
- Легко тестувати
- 4 вузли = мінімальний MVP

### v0.3 — PARTIAL MESH

```
    A ——— B ——— C
    |  /  |  /  |
    D ——— E ——— F

2+ маршрутів між будь-якими вузлами
Витримує 2+ обривів
```

### v0.4 — FULL MESH (довгостроково)

```
    A ——— B ——— C
    |\ /| |\ /|
    | X | | X |
    |/ \| |/ \|
    D ——— E ——— F

Максимальна живучість
Складніший routing
```

---

## 3. Налаштування BATMAN-adv

### Крок 1 — Встановлення

```bash
# На кожному вузлі (Raspberry Pi / Orange Pi / Debian)
apt update && apt install -y batctl bridge-utils

# Перевірити що модуль є
modprobe batman-adv
lsmod | grep batman
```

### Крок 2 — Створення mesh-інтерфейсу

```bash
# Створити bat0
ip link add name bat0 type batadv

# Додати fiber-інтерфейси
ip link set eth0 master bat0   # SFP #1
ip link set eth1 master bat0   # SFP #2 (якщо є)

# Або через USB-Ethernet адаптер
ip link set eth1 master bat0

# Підняти
ip link set bat0 up
ip link set eth0 up
ip link set eth1 up

# Призначити IP
ip addr add 192.168.10.X/24 dev bat0
```

### Крок 3 — Скрипт автозапуску

```bash
#!/bin/bash
# /usr/local/bin/tfn-mesh.sh
# TFN Mesh Node Setup

NODE_ID=$1
IP_ADDR="192.168.10.${NODE_ID}"

modprobe batman-adv

ip link add name bat0 type batadv

# Fiber interfaces
ip link set eth0 master bat0
ip link set eth1 master bat0  # другий порт (якщо є)

ip link set eth0 up
ip link set eth1 up
ip link set bat0 up

ip addr add ${IP_ADDR}/24 dev bat0

# Оптимізація
batctl gw_mode off       # Немає gateway — чиста mesh
batctl hop_penalty 30    # Штрафи за зайві хопи
batctl aggregation 1     # Увімкнути агрегацію

echo "TFN Node ${NODE_ID} online: ${IP_ADDR}"
```

### Крок 4 — Systemd service

```ini
# /etc/systemd/system/tfn-mesh.service
[Unit]
Description=TFN Mesh Network
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/tfn-mesh.sh %i
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable tfn-mesh@1   # Node ID = 1
systemctl start tfn-mesh@1
```

---

## 4. Failover — що відбувається при обриві

### BATMAN-adv behavior

```
Нормальний стан:
  A → B → C → D → A (ring, шлях A→C = 2 hops)

Обрив B→C:
  BATMAN виявляє: ~3-5 секунд
  Новий маршрут: A → D → C (3 hops замість 2)
  Мережа продовжує працювати

Другий обрив C→D:
  BATMAN переобчислює: ~3-5 сек
  Якщо ring з 4 вузлів — мережа може розділитись на 2 сегменти
  Потрібен partial mesh для подолання 2+ обривів
```

### Час відновлення

| Подія | Час виявлення | Час відновлення | Примітка |
|-------|---------------|-----------------|----------|
| Обрив кабелю | 1-3 сек | 3-5 сек | BATMAN purge timeout |
| Вузол offline | 1-3 сек | 3-5 сек | Те саме |
| Деградація лінії | Постійно | Миттєво | BATMAN сам обирає кращий маршрут |
| 2 обриви одночасно | 1-3 сек | 5-10 сек | Складніший перерахунок |

### Реальні цифри (не маркетингові)

- **Failover time: 3-5 секунд** (не "<1с")
- **Це нормально** для BATMAN-adv
- Для швидшого — потрібен custom Layer 1 monitoring (SFP DOM polling)

---

## 5. Проблеми та рішення

### Проблема 1: Broadcast Storm

Ring = ризик петлі. BATMAN-adv має вбудований loop detection, але:

```
Рішення:
- Не додавати зайві інтерфейси в mesh
- batctl bonding 1 — агрегація замість дублювання
- Якийсь періодичний batctl ping для моніторингу
```

### Проблема 2: Затримка при multi-hop

```
Кожен хоп додає ~0.5-1ms
5 вузлів chain = 4 hops = 2-4ms

Для TFN це прийнятно (не high-frequency trading)
Для реального часу (відео) — теж ок (30fps = 33ms frame)
```

### Проблема 3: Живлення

```
Вузол помер = сегмент впав

Рішення:
1. LiFePO4 батарея на кожному вузлі
2. Сонячна панель 10-20Вт для підзарядки
3. Моніторинг батареї через batctl або SNMP
4. Автоматичне вимкнення при <10% батареї
```

### Проблема 4: Дублювання пакетів

```
BATMAN-adv обробляє це на L2
Якщо бачиш дублікати:
  batctl bonding 1
  batctl fragmentation 1
```

---

## 6. Моніторинг mesh

```bash
# Показати всі вузли в mesh
batctl n

# Показати таблицю маршрутизації
batctl o

# Показати стан інтерфейсів
batctl if

# Ping через mesh
batctl ping 192.168.10.2

# Трейсрут
batctl traceroute 192.168.10.3

# Статистика
batctl s

# Локальні дані
batctl l
```

### Скрипт моніторингу

```bash
#!/bin/bash
# tfn-monitor.sh — простий моніторинг mesh

while true; do
    echo "=== $(date) ==="
    echo "Neighbors:"
    batctl n
    echo ""
    echo "Routes:"
    batctl o
    echo ""
    echo "Link quality:"
    for node in $(batctl n | grep -oP '\d+\.\d+\.\d+\.\d+'); do
        echo -n "  $node: "
        batctl ping -c 1 $node 2>/dev/null | grep "roundtrip" || echo "UNREACHABLE"
    done
    sleep 30
done
```

---

## 7. Критерій успіху

Проєкт стає серйозним, коли ти можеш сказати:

> **"Мережа витримує 1-2 обриви без втрати зв'язку між будь-якими вузлами"**

Не "mesh", не "інновація" — а **конкретна поведінка при відмові**.

---

## 8. Тест-план

### Тест 1: Нормальна робота
```bash
# На всіх вузлах:
batctl n   # всі бачать всіх
ping 192.168.10.X  # всі пінгуються
iperf3 -c 192.168.10.Y  # throughput
```

### Тест 2: Обрив кабелю
```bash
# 1. Запустити ping між A та C
ping 192.168.10.3

# 2. Фізично розрізати кабель B→C

# 3. Засікти:
#    - скільки пакетів втрачено
#    - скільки часу до відновлення
#    - який новий маршрут

# 4. Перевірити:
batctl o   # нові маршрути
```

### Тест 3: Вузол offline
```bash
# 1. Вимкнути живлення вузла B

# 2. Перевірити зв'язність A→C→D

# 3. Вімкнути B назад

# 4. Перевірити повернення маршрутів
```

### Тест 4: Навантаження + обрив
```bash
# 1. Запустити iperf3 між A та D
iperf3 -c 192.168.10.4 -t 60

# 2. Під час передачі — розрізати кабель

# 3. Зафіксувати: пропускна здатність до/після
```

---

*Mesh Networking v1.0 — BATMAN-adv + Failover Guide*
