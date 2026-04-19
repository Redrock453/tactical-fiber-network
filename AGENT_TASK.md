# AGENT TASK — Tactical Fiber Network Improvements
# Виконати автономно. Репо: https://github.com/Redrock453/tactical-fiber-network
# Мова: тільки УКРАЇНСЬКА або ENGLISH

## ПРІОРИТЕТ 1 — Реалістична фізика DAS (simulation/das_simulator.py)

### Проблема
Поточна класифікація — toy model. Потрібна SNR-based модель з реальними FFT сигнатурами.

### Завдання
1. SNR model:
   ```
   SNR(d) = P_launch - α*L - 10*log10(d) - NF
   α = 0.35 dB/km (G.657.A2), d = відстань від кабелю до цілі
   ```

2. FFT frequency signatures для кожного типу цілі:
   - Пішохід: 1-4 Hz, крок ~1.5 Hz, гармоніки
   - БТР/БМП: 10-50 Hz, двигун + колеса/гусениці
   - Танк: 8-30 Hz + гармоніки на 60, 90 Hz
   - Артвистріл: імпульс 0-500 Hz (затухає за ~50ms)
   - Дрон: 80-200 Hz (ротори), 4-8 лопатей
   - Копання: 2-8 Hz, ритмічне з паузами

3. SNR-based probability:
   - Замінити "95-99%" на SNR-based detection probability curve
   - Gaussian noise overlay
   - FAR (False Alarm Rate) для wind/rain

4. False Alarm Rate model:
   - Wind: 0.5-3 Hz
   - Rain: wideband 10-100 Hz
   - Distant traffic: схоже на техніку але нижчий SNR

## ПРІОРИТЕТ 2 — Mesh з реалістичною моделлю ушкоджень

1. Артилерійська модель:
   - radius = 15-50m
   - P_break = 1 - exp(-r/R)
   - Техніка: P_break = 0.3 при перетині

2. OSPF-like rerouting:
   - Альтернативний шлях з latency calculation
   - Bandwidth degradation при multi-hop

3. Battery/Power model:
   - Споживання: 2W idle, 5W active
   - Battery: 20-100 Wh
   - Time-to-failure calculation

## ПРІОРИТЕТ 3 — Практичні MVP документи

1. architecture/node.md — специфікація вузла v0.1
2. network/topology.md — 3 топології (p2p, chain, ring)
3. sensing/pipeline.md — signal → filter → FFT → classify
4. sensing/pseudo_das_mvp.md — п'єзо + ESP32 MVP
5. tests/plan.md — план реальних тестів

## ПРІОРИТЕТ 4 — Дослідження реального обладнання

З конкретними моделями, цінами, посиланнями:
- SBC: RPi 4/5, Orange Pi 5, NanoPi R6S
- SFP: конкретні моделі з AliExpress
- Медіаконвертери: що реально працює
- П'єзо-сенсори: конкретні моделі для псевдо-DAS
- ESP32: варіанти з АЦП

## DONE CRITERIA
- [ ] pytest tests/ -v — всі зелені
- [ ] python -m simulation.das_simulator — показує SNR values
- [ ] python -m simulation.mesh_simulator — показує альтернативні маршрути
- [ ] Всі нові .md файли створені та заповнені
