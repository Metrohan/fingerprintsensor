#!/usr/bin/env python3
# test_lcd.py - LCD test ve diagnostic

import time
import sys
from ili9486 import ILI9486

print("[TEST] LCD Test başlatılıyor...")
print(f"[TEST] TFT_WIDTH={ILI9486.__init__.__globals__['TFT_WIDTH']}")

try:
    print("[TEST] LCD nesnesi oluşturuluyor...")
    tft = ILI9486()
    time.sleep(1)
    
    print("[TEST] Ekran siyah (fill_screen) test edilyor...")
    tft.fill_screen(0, 0, 0)
    time.sleep(1)
    
    print("[TEST] Ekran kırmızı test edilyor...")
    tft.fill_screen(255, 0, 0)
    time.sleep(1)
    
    print("[TEST] Ekran yeşil test edilyor...")
    tft.fill_screen(0, 255, 0)
    time.sleep(1)
    
    print("[TEST] Ekran mavi test edilyor...")
    tft.fill_screen(0, 0, 255)
    time.sleep(1)
    
    print("[TEST] Ekran beyaz test edilyor...")
    tft.fill_screen(255, 255, 255)
    time.sleep(1)
    
    print("[TEST] Text test - HELLO yazısı çiziliyor...")
    tft.fill_screen(0, 100, 0)  # Yeşil
    tft.draw_text(20, 50, "HELLO", 255, 255, 255, 0, 100, 0, size=2)
    time.sleep(2)
    
    print("[TEST] Text test - 123 yazısı çiziliyor...")
    tft.fill_screen(0, 0, 100)  # Mavi
    tft.draw_text(20, 50, "123", 255, 255, 255, 0, 0, 100, size=3)
    time.sleep(2)
    
    print("[TEST] Cleanup...")
    tft.cleanup()
    
    print("[TEST] ✓ Tüm testler başarılı!")
    
except Exception as e:
    print(f"[TEST] ✗ Hata: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
