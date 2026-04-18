# TFN System Architecture

## Overview

Tactical Fiber Network (SpiderLink) operates on 3 layers:

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

## Layer 1: Physical

### Fiber Cable
- Type: Single-mode G.657.A2 (bend-insensitive)
- Source: Spent FPV drone fiber ($0)
- Attenuation: 0.35 dB/km @ 1310nm, 0.22 dB/km @ 1550nm
- Typical lengths: 1-10 km per link

### Nodes
- **Trench Node**: Basic mesh node in forward position
- **Relay Node**: Connection point between fiber segments
- **Base Station**: Main aggregation point with SFP switch
- **DAS Interrogator**: φ-OTDR equipped node for sensing

### Field Splicing
- Mechanical splices: 30 seconds, 0.1-0.3 dB loss
- Quick connectors: 60 seconds, 0.2-0.5 dB loss
- No fusion splicing required in the field

---

## Layer 2: Processing

### DAS Pipeline
```
Fiber → φ-OTDR → Raw backscatter → High-pass filter → FFT (1024pt)
→ Feature extraction → ML classifier → Alert generation
```

### RF-Opto Detection
```
Fiber → Phase monitor → Kerr effect analysis → RF source classification
→ Position estimation → Alert generation
```

### OTDR Monitoring
```
Fiber → OTDR pulse → Return trace → Event detection
→ Break/degradation localization → Alert generation
```

---

## Layer 3: Intelligence

### ML Classification
- Input: FFT spectrum (1024 points)
- Model: 3-layer Conv1D + Dense (12 classes)
- Inference: 5-50ms on edge hardware
- Training: Master Node (RTX 4090)

### Tactical Map
- Real-time event overlay
- Fiber path visualization
- Node/link health indicators
- Threat level color coding

### Counter-Battery
- Artillery fire detection
- Trajectory estimation
- Automatic target coordinates
- <30s from detection to fire mission

---

## Network Architecture

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

## Data Flow

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

## Security Architecture

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

*Architecture v2.0*
