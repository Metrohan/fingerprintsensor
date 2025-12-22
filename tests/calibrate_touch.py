#!/usr/bin/env python3
# calibrate_touch.py
# Dokunmatik panel kalibrasyonu

import time
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT
from xpt2046 import XPT2046

def calibrate():
    """
    4 köşeye dokunarak kalibrasyonu yap:
    1. Sol-üst: (10, 10)
    2. Sağ-üst: (310, 10)
    3. Sol-alt: (10, 470)
    4. Sağ-alt: (310, 470)
    """
    tft = ILI9486()
    touch = XPT2046()
    time.sleep(0.5)

    calibration_points = [
        (10, 10, "SOL-ÜST"),
        (310, 10, "SAĞ-ÜST"),
        (10, 470, "SOL-ALT"),
        (310, 470, "SAĞ-ALT"),
    ]

    raw_values = []

    for screen_x, screen_y, label in calibration_points:
        # Ekrana işaret koy
        tft.fill_screen(0, 0, 0)
        tft.fill_rect(screen_x - 5, screen_y - 5, 10, 10, 255, 255, 0)
        print(f"\n{label} noktasına (x={screen_x}, y={screen_y}) dokunun...")
        time.sleep(1)

        # 10 örnek al
        samples = []
        for _ in range(10):
            pt = touch.read_point()
            if pt:
                samples.append(pt)
                print(f"  Raw: {pt}")
            time.sleep(0.1)

        if samples:
            avg_x = sum(p[0] for p in samples) / len(samples)
            avg_y = sum(p[1] for p in samples) / len(samples)
            print(f"  Ortalama: ({avg_x:.0f}, {avg_y:.0f})")
            raw_values.append(((screen_x, screen_y), (avg_x, avg_y)))

    print("\n" + "="*50)
    print("KALİBRASYON SONUÇLARI:")
    print("="*50)

    if len(raw_values) >= 2:
        # Min/Max hesapla
        xs = [r[1][0] for r in raw_values]
        ys = [r[1][1] for r in raw_values]
        
        raw_x_min = min(xs)
        raw_x_max = max(xs)
        raw_y_min = min(ys)
        raw_y_max = max(ys)

        print(f"RAW_X_MIN = {raw_x_min:.0f}")
        print(f"RAW_X_MAX = {raw_x_max:.0f}")
        print(f"RAW_Y_MIN = {raw_y_min:.0f}")
        print(f"RAW_Y_MAX = {raw_y_max:.0f}")

        print("\nBu değerleri panel_ui.py'de güncelleyin:")
        print(f"""
RAW_X_MIN = {raw_x_min:.0f}
RAW_X_MAX = {raw_x_max:.0f}
RAW_Y_MIN = {raw_y_min:.0f}
RAW_Y_MAX = {raw_y_max:.0f}
        """)

        # Eğer sol-üst vs sağ-alt ters ise flip gerekli
        # raw_values[0] = sol-üst, raw_values[3] = sağ-alt
        if len(raw_values) >= 4:
            lu_x, lu_y = raw_values[0][1]  # sol-üst raw
            ld_x, ld_y = raw_values[2][1]  # sol-alt raw
            ru_x, ru_y = raw_values[1][1]  # sağ-üst raw
            rd_x, rd_y = raw_values[3][1]  # sağ-alt raw
            
            # Kontrol: sol < sağ ve üst < alt olmalı
            if lu_x > ru_x:
                print("\n⚠️  X ekseni ters! (sol > sağ)")
                print(f"Çözüm: raw_to_screen()'de X'i flip et veya RAW_X_MIN/MAX'ı swap et")
            if lu_y > ld_y:
                print("\n⚠️  Y ekseni ters! (üst > alt)")
                print(f"Çözüm: raw_to_screen()'de Y'yi flip et veya RAW_Y_MIN/MAX'ı swap et")

        # Test et
        print("\n" + "="*50)
        print("TEST: Rasgele noktalara dokunun (Ctrl+C'ye basın)")
        print("="*50)
        
        tft.fill_screen(50, 50, 50)
        time.sleep(1)

        try:
            while True:
                pt = touch.read_point()
                if pt:
                    x_raw, y_raw = pt
                    # Map et
                    screen_x = int((x_raw - raw_x_min) * (TFT_WIDTH - 1) / (raw_x_max - raw_x_min))
                    screen_y = int((y_raw - raw_y_min) * (TFT_HEIGHT - 1) / (raw_y_max - raw_y_min))
                    
                    # Clamp et
                    screen_x = max(0, min(TFT_WIDTH - 1, screen_x))
                    screen_y = max(0, min(TFT_HEIGHT - 1, screen_y))
                    
                    print(f"Raw: ({x_raw:.0f}, {y_raw:.0f}) => Screen: ({screen_x}, {screen_y})")
                    
                    # Ekrana nokta çiz
                    if 0 <= screen_x < TFT_WIDTH and 0 <= screen_y < TFT_HEIGHT:
                        tft.fill_rect(screen_x - 3, screen_y - 3, 6, 6, 0, 255, 0)
                
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nKalibasyon tamamlandı.")

    tft.cleanup()
    touch.cleanup()

if __name__ == "__main__":
    calibrate()
