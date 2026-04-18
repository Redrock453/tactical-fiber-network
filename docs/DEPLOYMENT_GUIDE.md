# TFN Deployment Guide

## Quick Deploy (15 minutes)

### Prerequisites

- 2+ devices with Ethernet + SFP or USB-SFP adapter
- Spent FPV fiber cable (1-10 km)
- Mechanical splices + quick connectors
- Basic tool kit (stripper + cleaver)

### Step 1: Prepare Fiber (5 min)

```
1. Find clean section of fiber (trim damaged ends)
2. Strip 20mm of buffer on each end
3. Clean with alcohol wipe
4. Cleave at 10mm from buffer
5. Install quick SC connector on each end
```

### Step 2: Connect Nodes (5 min)

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

### Step 3: Configure (5 min)

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

### Step 4: Verify

```bash
ping 10.10.10.Y  # other node
iperf3 -c 10.10.10.Y  # bandwidth test
```

---

## Mesh Network Deployment (1-2 hours)

### Planning

```bash
python -m calculator.topology_planner
```

This generates:
- Node placement plan
- Fiber drop instructions
- Equipment list
- Cost estimate

### Node Setup Script

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

### DAS Node Setup

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

## Docker Deployment (Cloud)

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

## Monitoring

### Mesh Health

```bash
python3 -m analytics.mesh_health
```

### Break Detection

```bash
python3 -m analytics.break_locator
```

### DAS Monitoring

```bash
python3 -m calculator.das_analyser --simulate --duration 60
```

---

## Troubleshooting

| Problem | Check | Fix |
|---------|-------|-----|
| No link | `ethtool eth0` | Check SFP seated, fiber connected |
| Low RX power | `ethtool -m eth0` | Clean connectors, check splices |
| High BER | Ping test | Replace degraded splice |
| Node offline | Battery check | Replace/charge battery |
| DAS false alarms | Threshold adjust | Lower sensitivity or add ML filter |

---

*Deployment Guide v2.0*
