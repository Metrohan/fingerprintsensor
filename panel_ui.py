# panel_ui.py
import time
import requests
from datetime import datetime
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT
from xpt2046 import XPT2046

API_BASE = "http://127.0.0.1:5000"

# Touch raw değerlerini ekrana map etmek için (kalibrasyon)
RAW_X_MIN = 250
RAW_X_MAX = 3900
RAW_Y_MIN = 250
RAW_Y_MAX = 3900

def map_value(val, in_min, in_max, out_min, out_max):
    """Aralığı dönüştür (clamp ile)"""
    if val < in_min: val = in_min
    if val > in_max: val = in_max
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def show_welcome(tft: ILI9486, name: str):
    """Hoşgeldin mesajı göster (giriş)."""
    tft.fill_screen(0, 100, 0)  # Yeşil arka plan
    
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")
    
    # Başlık
    tft.draw_text(10, 20, "HOSGELDIN", 255, 255, 255, 0, 100, 0, scale=2)
    
    # İsim (büyük)
    tft.draw_text(10, 60, name, 255, 255, 255, 0, 100, 0, scale=2)
    
    # Saat
    tft.draw_text(10, 100, time_str, 255, 255, 0, 0, 100, 0, scale=2)
    
    # Tarih
    tft.draw_text(10, 130, date_str, 255, 255, 0, 0, 100, 0, scale=2)

def show_goodbye(tft: ILI9486, name: str, total_hours: int, total_minutes: int):
    """Hoşçakal mesajı göster (çıkış)."""
    tft.fill_screen(0, 0, 100)  # Mavi arka plan
    
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")
    
    # Başlık
    tft.draw_text(10, 20, "HOSCAKAL", 255, 255, 255, 0, 0, 100, scale=2)
    
    # İsim
    tft.draw_text(10, 60, name, 255, 255, 255, 0, 0, 100, scale=2)
    
    # Tarih
    tft.draw_text(10, 100, date_str, 255, 255, 0, 0, 0, 100, scale=2)
    
    # Saat
    tft.draw_text(10, 130, time_str, 255, 255, 0, 0, 0, 100, scale=2)
    
    # Toplam çalışma süresi
    if total_hours > 0 or total_minutes > 0:
        total_str = f"{total_hours}:{total_minutes:02d}"
        tft.draw_text(10, 160, "Toplam:", 255, 255, 255, 0, 0, 100, scale=1)
        tft.draw_text(10, 175, total_str, 0, 255, 0, 0, 0, 100, scale=2)

def show_error(tft: ILI9486):
    """Parmak izi kaydı yok mesajı."""
    tft.fill_screen(100, 50, 0)  # Turuncu arka plan
    
    # Başlık
    tft.draw_text(10, 50, "PARMAK IZI KAYITSIZ", 255, 255, 255, 100, 50, 0, scale=1)
    
    # Altlık
    tft.draw_text(10, 100, "Yetkiliyle", 255, 255, 255, 100, 50, 0, scale=1)
    tft.draw_text(10, 120, "gorusunuz", 255, 255, 255, 100, 50, 0, scale=1)

def show_loading(tft: ILI9486):
    """Yükleniyor mesajı."""
    tft.fill_screen(50, 50, 50)  # Gri arka plan
    tft.draw_text(10, 100, "Okunuyor...", 255, 255, 255, 50, 50, 50, scale=2)

def call_match():
    """API'den fingerprint eşleştirme çağrısı."""
    try:
        r = requests.get(API_BASE + "/api/match-fingerprint", timeout=30)
        if r.status_code == 200:
            return r.json(), None
        else:
            try:
                return None, r.json().get("msg", f"Error {r.status_code}")
            except:
                return None, f"Error {r.status_code}"
    except Exception as e:
        return None, str(e)

def main():
    tft = ILI9486()
    touch = XPT2046()
    time.sleep(0.5)

    # Başlangıç ekranı
    tft.fill_screen(20, 20, 40)
    tft.draw_text(50, 100, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, scale=2)
    tft.draw_text(50, 150, "Parmak izi okutun", 255, 200, 0, 20, 20, 40, scale=1)

    print("Panel hazır. Parmak izini okutmayı bekleyin...")

    while True:
        # Parmak izi oku
        show_loading(tft)
        data, err = call_match()

        if err:
            print(f"Hata: {err}")
            show_error(tft)
            time.sleep(3)
            tft.fill_screen(20, 20, 40)
            tft.draw_text(50, 100, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, scale=2)
            tft.draw_text(50, 150, "Parmak izi okutun", 255, 200, 0, 20, 20, 40, scale=1)
            continue

        if not data:
            print("Parmak izi bulunamadı")
            show_error(tft)
            time.sleep(3)
            tft.fill_screen(20, 20, 40)
            tft.draw_text(50, 100, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, scale=2)
            tft.draw_text(50, 150, "Parmak izi okutun", 255, 200, 0, 20, 20, 40, scale=1)
            continue

        # Başarılı eşleştirme
        user = data.get("user", {})
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        event = data.get("event", "")
        
        print(f"{name} - {event}")

        if event == "check_in":
            show_welcome(tft, name)
        elif event == "check_out":
            total_minutes = data.get("total_duration_minutes", 0)
            total_hours = total_minutes // 60
            total_mins = total_minutes % 60
            show_goodbye(tft, name, total_hours, total_mins)
        
        time.sleep(3)

        # Ana ekrana dön
        tft.fill_screen(20, 20, 40)
        tft.draw_text(50, 100, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, scale=2)
        tft.draw_text(50, 150, "Parmak izi okutun", 255, 200, 0, 20, 20, 40, scale=1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("Program durduruldu.")