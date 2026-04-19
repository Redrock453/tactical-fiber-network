# TFN Pseudo-DAS MVP — п'єзо + ESP32 + fiber

## Що це

Бюджетна альтернатива справжньому DAS (φ-OTDR), яка доводить головний принцип:

> **Лінія = сенсор + канал передачі**

---

## Architecture

```
[П'єзо ×4] → [ADS1256 ADC] → [ESP32-S3] → WiFi → [RPi] → [Fiber] → [Master]
   │              │                │                        │
   └──────────────┴────────────────┘                        │
   Аналоговий сигнал, 24-bit, 30k SPS                       │
                                                Python FFT + Classify
```

---

## Shopping List — один сенсорний вузол

| # | Компонент | Модель | Ціна | Qty | Разом |
|---|-----------|--------|------|-----|-------|
| 1 | MCU | ESP32-S3-DevKitC | $6-13 | 1 | $10 |
| 2 | ADC | ADS1256 24-bit module | $8-15 | 1 | $12 |
| 3 | П'єзо-сенсор | Piezo disc 27mm | $0.05-0.10 | 10 | $1 |
| 4 | Мультиплексор | CD74HC4067 (16-ch) | $0.50-1 | 1 | $1 |
| 5 | ОУ | LM358 (amplifier) | $0.10-0.20 | 2 | $0.30 |
| 6 | Резистори/конденсатори | Assorted kit | $2-5 | 1 | $3 |
| 7 | Макетна плата | Breadboard + wires | $3-5 | 1 | $4 |
| 8 | Корпус | IP67 plastic box | $3-8 | 1 | $5 |
| 9 | Кабель | 2-wire shielded, 5м | $2-3 | 1 | $3 |
| **Разом** | | | | | **~$39** |

### З RPi + fiber (повний вузол)

| Додати | Ціна |
|--------|------|
| RPi 4 + SD | $50 |
| Медіаконвертер + SFP | $20 |
| Powerbank | $15 |
| **Повний вузол** | **~$124** |

---

## Wiring — ADS1256 + ESP32

```
ADS1256 Module   ESP32-S3
──────────────   ─────────
CS    ─────────── GPIO 5
SCLK  ─────────── GPIO 18
DIN   ─────────── GPIO 23
DOUT  ─────────── GPIO 19
DRDY  ─────────── GPIO 4
VCC   ─────────── 3.3V
GND   ─────────── GND

П'єзо → LM358 amp → ADS1256 AIN0
                     ADS1256 AIN1 (п'єзо #2 через мультиплексор)
                     ...
```

---

## ESP32 Firmware (Arduino)

```cpp
#include <SPI.h>
#include <ADS1256.h>

#define CS_PIN 5
#define DRDY_PIN 4
#define MUX_PIN_0 32
#define MUX_PIN_1 33
#define MUX_PIN_2 25
#define MUX_PIN_3 26

ADS1256 adc(CS_PIN, DRDY_PIN, 2.5);

const int SAMPLE_RATE = 1000;
const int NUM_CHANNELS = 4;
int current_channel = 0;
unsigned long last_sample = 0;

void setup() {
    Serial.begin(115200);
    SPI.begin(18, 19, 23, 5);
    adc.begin();
    adc.setSpeed(30000);
    
    pinMode(MUX_PIN_0, OUTPUT);
    pinMode(MUX_PIN_1, OUTPUT);
    pinMode(MUX_PIN_2, OUTPUT);
    pinMode(MUX_PIN_3, OUTPUT);
}

void selectChannel(int ch) {
    digitalWrite(MUX_PIN_0, ch & 0x01);
    digitalWrite(MUX_PIN_1, (ch >> 1) & 0x01);
    digitalWrite(MUX_PIN_2, (ch >> 2) & 0x01);
    digitalWrite(MUX_PIN_3, (ch >> 3) & 0x01);
}

void loop() {
    unsigned long now = micros();
    if (now - last_sample < 1000000 / SAMPLE_RATE) return;
    last_sample = now;
    
    selectChannel(current_channel);
    delayMicroseconds(10);
    
    int32_t raw = adc.readADC();
    float voltage = raw * 2.5 / 0x7FFFFF;
    
    Serial.printf("CH%d:%.6f\n", current_channel, voltage);
    
    current_channel = (current_channel + 1) % NUM_CHANNELS;
}
```

---

## RPi Reader Script

```python
#!/usr/bin/env python3
"""Read piezo data from ESP32 via serial/WiFi and classify."""

import serial
import numpy as np
import time
from collections import deque

FS = 1000
WINDOW = 1024

buffers = {i: deque(maxlen=WINDOW) for i in range(4)}

def read_serial(ser):
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line.startswith('CH') and ':' in line:
        ch_str, val_str = line.split(':')
        ch = int(ch_str[2:])
        val = float(val_str)
        buffers[ch].append(val)
        return ch, val
    return None, None

def bandpass_filter(signal, lowcut=1.0, highcut=250.0, fs=1000, order=4):
    from scipy.signal import butter, filtfilt
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return filtfilt(b, a, signal)

def classify(signal, fs=1000):
    if len(signal) < 256:
        return 'insufficient_data', 0.0
    
    window = np.hanning(len(signal))
    fft = np.fft.fft(signal * window)
    freqs = np.fft.fftfreq(len(fft), d=1/fs)
    mag = np.abs(fft[:len(fft)//2])
    freqs = freqs[:len(fft)//2]
    
    rms = np.sqrt(np.mean(signal**2))
    if rms < 0.01:
        return 'silence', 0.9
    
    peak_freq = freqs[np.argmax(mag)]
    
    e_foot = np.sum(mag[(freqs >= 1) & (freqs < 5)])
    e_veh_lo = np.sum(mag[(freqs >= 5) & (freqs < 20)])
    e_veh_hi = np.sum(mag[(freqs >= 20) & (freqs < 80)])
    e_drone = np.sum(mag[(freqs >= 80) & (freqs < 250)])
    
    scores = {
        'infantry': e_foot * 1.5,
        'wheeled': e_veh_lo * 1.2 + e_veh_hi * 0.5,
        'tracked': e_veh_lo * 1.8,
        'drone': e_drone * 2.0,
    }
    
    total = sum(scores.values()) + 0.01
    best = max(scores, key=scores.get)
    conf = min(scores[best] / total, 0.99)
    
    return best if conf > 0.3 else 'unknown', conf

def main():
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    print("[TFN] Pseudo-DAS reader started")
    
    last_classify = time.time()
    
    while True:
        ch, val = read_serial(ser)
        if ch is None:
            continue
        
        if time.time() - last_classify >= 1.0 and len(buffers[0]) >= 256:
            for c in range(4):
                signal = np.array(buffers[c])
                filtered = bandpass_filter(signal)
                target, conf = classify(filtered)
                if target != 'silence':
                    print(f"  [CH{c}] {target} ({conf*100:.0f}%) RMS={np.sqrt(np.mean(signal**2)):.4f}")
            last_classify = time.time()

if __name__ == '__main__':
    main()
```

---

## Що тестувати

| Тест | Дія | Очікуваний результат |
|------|-----|---------------------|
| 1 | Кроки поруч (3м) | `infantry 70-85%` |
| 2 | Біг поруч (5м) | `infantry 80-90%` |
| 3 | Автомобіль (10м) | `wheeled 80-90%` |
| 4 | Удар по землі | `unknown` або короткий `impulse` |
| 5 | Тиша | `silence > 90%` |
| 6 | Дощ | Випадкові спрацьовування < 1/хв |

---

## Наступні кроки

1. Зібрати 1 сенсорний вузол ($40)
2. Підключити до RPi через serial
3. Записати сигнали для кожного типу цілі
4. Зберегти у CSV для подальшого ML-навчання
5. Калібрувати пороги

---

*Pseudo-DAS MVP v1.0*
