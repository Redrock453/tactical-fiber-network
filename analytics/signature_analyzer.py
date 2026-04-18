#!/usr/bin/env python3
"""
SpiderLink Analyzer — сигнальний аналізатор для DigitalOcean
=============================================

Цей скрипт призначений для:
1. Simulation Mode: генерація синтетичних даних для тестування
2. Analysis Mode: FFT аналіз та класифікація сигналів
"""

import numpy as np
import json
from datetime import datetime


class SpiderLinkAnalyzer:
    """
    Tactical Fiber Network - Signal Analysis Engine
    Для розгортання на DigitalOcean Droplets.
    """
    
    def __init__(self, mode="simulation"):
        self.mode = mode
        # Словник сигнатур (частотні діапазони в Гц)
        self.signatures = {
            "infantry": (1.0, 3.0),       # Кроки людини
            "heavy_vehicle": (10.0, 45.0),  # Гусенична/колісна техніка
            "ew_interference": (500.0, 2000.0), # Вплив РЕБ на фазу світла
            "ambient_noise": (0.1, 0.5)      # Вітер, опади
        }

    def generate_mock_data(self, target_type="infantry"):
        """Генерація синтетичного сигналу для тестування без заліза."""
        fs = 5000  # Частота дискретизації
        t = np.linspace(0, 1, fs)
        
        # Базовий шум
        signal = 0.5 * np.random.normal(size=fs)
        
        # Додавання сигнатури
        freq_min, freq_max = self.signatures.get(target_type, (1, 2))
        target_freq = (freq_min + freq_max) / 2
        signal += 5 * np.sin(2 * np.pi * target_freq * t)
        
        return signal

    def analyze(self, raw_data):
        """FFT аналіз та класифікація."""
        # Швидке перетворення Фур'є
        fft_result = np.fft.fft(raw_data)
        psd = np.abs(fft_result)**2  # Спектральна щільність потужності
        freqs = np.fft.fftfreq(len(psd), d=1/5000)
        
        # Пошук домінуючої частоти
        idx = np.argmax(psd[1:len(psd)//2]) + 1
        peak_freq = abs(freqs[idx])
        
        # Класифікація
        detected = "unknown"
        for label, (f_min, f_max) in self.signatures.items():
            if f_min <= peak_freq <= f_max:
                detected = label
                break
                
        return {
            "timestamp": datetime.now().isoformat(),
            "peak_frequency_hz": round(peak_freq, 2),
            "classification": detected,
            "status": "ALERT" if detected in ["infantry", "heavy_vehicle", "ew_interference"] else "CLEAR"
        }


if __name__ == "__main__":
    analyzer = SpiderLinkAnalyzer(mode="simulation")
    
    # Тестовий прогін: детекція піхоти
    print("[SpiderLink] Starting analysis simulation...")
    test_data = analyzer.generate_mock_data(target_type="infantry")
    result = analyzer.analyze(test_data)
    
    print(f"[RESULT] {json.dumps(result, indent=4)}")