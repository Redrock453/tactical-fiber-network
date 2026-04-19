# Керівництво з розгортання TFN

## Швидке розгортання (15 хвилин)

### Передумови

- 2+ пристрої з Ethernet + SFP або USB-SFP адаптером
- FPV оптоволоконний кабель (1–10 км)
- Механічні з'єднувачі + швидкі конектори
- Базовий набір інструментів (стриpper + кливер)

### Крок 1: Підготовка волокна (5 хв)

```
1. Find clean section of fiber (trim damaged ends)
2. Strip 20mm of buffer on each end
3. Clean with alcohol wipe
4. Cleave at 10mm from buffer
5. Install quick SC connector on each end
```

### Крок 2: Підключення вузлів (5 хв)

```
Node A:                              Node B:
[Quick SC] → patch cable → SFP  ←→  SFP ← patch cable ← [Quick SC]
                 ↕                                   ↕
           Media converter                     Media converter
                 ↕                                   ↕
            Raspberry Pi                        Raspberry Pi
                 ↕                                   ↕
           Ethernet switch                    Ethernet switch
```

### Крок 3: Налаштування (5 хв)

```bash
# On both nodes:
ip link add bat0 type batadv
ip link set eth0 master bat0
ip link set bat0 up
ip addr add 10.10.10.X/24 dev bat0

# Check link:
ethtool -m eth0 | grep "Rx optical power"
# Should show: -15 to -25 dBm
```

### Крок 4: Перевірка

```bash
ping 10.10.10.Y  # other node
iperf3 -c 10.10.10.Y  # bandwidth test
```

---

## Розгортання ямережі (1–2 години)

### Планування

```bash
python -m calculator.topology_planner
```

Це генерує:
- План розміщення вузлів
- Інструкції з прокладки волокна
- Перелік обладнання
- Кошторис витрат

### Скрипт налаштування вузла

```bash
#!/bin/bash
# TFN Node Setup (Raspberry Pi / Debian)

# Install dependencies
apt update && apt install -y batctl bridge-utils iw wireless-tools

# Configure BATMAN-adv
modprobe batman-adv
ip link add bat0 type batadv
ip link set eth0 master bat0
ip link set bat0 up
ip addr add 10.10.10.$1/24 dev bat0

# Enable forwarding
sysctl -w net.ipv4.ip_forward=1

# Start DAS monitor (if interrogator node)
if [ "$2" = "das" ]; then
    python3 /opt/tfn/calculator/das_analyser.py --simulate &
fi

# Start mesh health monitor
python3 /opt/tfn/analytics/mesh_health.py &
```

### Налаштування вузла DAS

```bash
# Connect φ-OTDR to SFP monitor port
# Configure interrogator parameters:
python3 -c "
from simulation.das_simulator import DASSimulator
das = DASSimulator(fiber_length_meters=5000)
das.auto_segment()
# In production: connect to real interrogator API
"

# Start alert service:
python3 -c "
from analytics.mesh_health import MeshHealthMonitor
mon = MeshHealthMonitor()
# Monitor loop...
"
```

---

## Розгортання через Docker (Хмара)

```bash
# Build
docker build -t tfn .

# Run with cloud analysis
docker run -d \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -p 8100:8100 \
  -p 8501:8501 \
  tfn

# Access:
# Dashboard: http://localhost:8501
# API: http://localhost:8100/docs
```

---

## Моніторинг

### Стан ямережі

```bash
python3 -m analytics.mesh_health
```

### Виявлення обривів

```bash
python3 -m analytics.break_locator
```

### Моніторинг DAS

```bash
python3 -m calculator.das_analyser --simulate --duration 60
```

---

## Усунення несправностей

| Проблема | Перевірка | Рішення |
|----------|-----------|---------|
| Немає з'єднання | `ethtool eth0` | Перевірте посадку SFP, підключення волокна |
| Низька потужність RX | `ethtool -m eth0` | Очистіть конектори, перевірте з'єднувачі |
| Високий BER | Ping тест | Замініть деградований з'єднувач |
| Вузол офлайн | Перевірка батареї | Замініть/зарядіть батарею |
| Хибні спрацьовування DAS | Налаштування порогу | Знижте чутливість або додайте ML-фільтр |

---

*Керівництво з розгортання v2.0*
