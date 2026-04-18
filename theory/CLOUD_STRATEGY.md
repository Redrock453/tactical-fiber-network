# Стратегія хмарної обробки та керування

Для забезпечення максимальної живучості та масштабованості, важкі обчислення виносяться на хмарні Droplets (DigitalOcean).

---

## 1. Схема передачі даних

```
[Edge Node] --- (Fiber) ---> [Base Station] --- (VPN) ---> [DigitalOcean Droplet]
```

### Потік даних

1. **Edge** — збір даних з SFP (DOM)
2. **Base Station** — агрегація та передобробка
3. **VPN (WireGuard)** — шифрований тунель
4. **Cloud** — аналіз та класифікація

---

## 2. Роль хмарного сервера

### 2.1 Global Signature Database

Централізоване зберігання образів сигналів нових ворожих БПЛА та засобів РЕБ:

```
Database: signatures
- frequency_mhz: 2400
- modulation: "FHSS"
- pattern: "hopping"
- threat_level: "high"
```

### 2.2 Machine Learning Training

Навчання моделей на "сирих" даних, зібраних з різних ділянок фронту:

```python
import torch
from torch import nn

class SignalClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 64, kernel_size=3)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3)
        self.fc = nn.Linear(128, 5)  # 5 класів
    
    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        return self.fc(x)
```

### 2.3 Collaborative Intelligence

Якщо один вузол SpiderLink зафіксував нову частоту РЕБ, через хмару ця інформація миттєво оновлює алгоритми детекції на всіх інших вузлах.

---

## 3. Резервування

У випадку втрати зв'язку з хмарою, локальні термінали переходять у режим автономної роботи на базі спрощених евристичних алгоритмів.

```
Cloud Online:
  Повний ML-аналіз
  + База сигнатур
  + Telegram alerts

Cloud Offline:
  Edge-евристика
  + Локальний буфер
  + Ручний аналіз
```

---

## 4. Архітектура DigitalOcean

### Компоненти

| Компонент | Призначення | Вартість |
|----------|-------------|----------|
| Droplet s-4vcpu-8gb | Обробка | $24/міс |
| InfluxDB | Time-series DB | $0 |
| Grafana | Дашборд | $0 |
| Telegram Bot | Сповіщення | $0 |
| WireGuard | VPN | $0 |

### Розгортання

```bash
# Docker встановлення
curl -sSL https://get.docker.com | sh

# Запуск сервісів
docker run -d -p 8086:8086 influxdb:alpine
docker run -d -p 3000:3000 grafana/grafana
docker run -d -p 51820:51820/udp linuxserver/wireguard
```

---

## 5. Безпека

### VPN (WireGuard)

- Протокол: ChaCha20-Poly1305
- Порт: 51820/UDP
- Авторизація: За публічним ключем

### Firewall

```
iptables -A INPUT -p udp --dport 51820 -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -j DROP
```

### Fail2Ban

Захист від брутфорсу SSH.

---

## 6. Вартість володіння

| Стаття | $/місяць |
|--------|----------|
| Droplet | 24 |
| Storage | 10 |
| Резерв | 5 |
| **Разом** | **39** |

---

## 7. Моніторинг

- CPU < 50%
- RAM < 70%
- Disk < 80%
- Network < 100 Mbps

### Grafana дашборд

```
[CPU] ████████░░ 50%
[RAM] ██████░░░░ 60%
[DISK] ████░░░░░░ 40%
```

---

*Хмарна стратегія v1.0*