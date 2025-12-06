# panel_ui.py
import time
import requests
from datetime import datetime
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT
from xpt2046 import XPT2046

API_BASE = "http://127.0.0.1:5000"

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

def show_welcome(tft: ILI9486, name: str):
    """Hoşgeldin mesajı göster (giriş)."""
    print(f"[DISPLAY] Hoşgeldin: {name}")
    tft.fill_screen(0, 100, 0)  # Yeşil arka plan
    
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")
    
    # Başlık
    tft.draw_text(30, 30, "HOSGELDIN", 255, 255, 255, 0, 100, 0, size=2)
    
    # İsim (sadece 12 karakter)
    name_short = name[:12]
    tft.draw_text(30, 80, name_short, 255, 255, 255, 0, 100, 0, size=2)
    
    # Saat
    tft.draw_text(30, 130, time_str, 255, 255, 0, 0, 100, 0, size=2)
    
    # Tarih
    tft.draw_text(30, 170, date_str, 255, 255, 0, 0, 100, 0, size=1)

def show_goodbye(tft: ILI9486, name: str, total_hours: int, total_minutes: int):
    """Hoşçakal mesajı göster (çıkış)."""
    print(f"[DISPLAY] Hoşçakal: {name} - Toplam: {total_hours}:{total_minutes:02d}")
    tft.fill_screen(0, 0, 100)  # Mavi arka plan
    
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")
    
    # Başlık
    tft.draw_text(30, 30, "HOSCAKAL", 255, 255, 255, 0, 0, 100, size=2)
    
    # İsim
    name_short = name[:12]
    tft.draw_text(30, 80, name_short, 255, 255, 255, 0, 0, 100, size=2)
    
    # Tarih
    tft.draw_text(30, 130, date_str, 255, 255, 0, 0, 0, 100, size=1)
    
    # Saat
    tft.draw_text(30, 160, time_str, 255, 255, 0, 0, 0, 100, size=2)
    
    # Toplam çalışma süresi
    total_str = f"{total_hours}:{total_minutes:02d}"
    tft.draw_text(30, 210, total_str, 0, 255, 0, 0, 0, 100, size=2)

def show_error(tft: ILI9486):
    """Parmak izi kaydı yok mesajı."""
    print("[DISPLAY] Hata: Parmak izi kayıtlı değil")
    tft.fill_screen(100, 50, 0)  # Turuncu arka plan
    
    # Başlık
    tft.draw_text(30, 80, "KAYITSIZ", 255, 255, 255, 100, 50, 0, size=2)
    
    # Altlık
    tft.draw_text(30, 150, "YETKILIYLE", 255, 255, 255, 100, 50, 0, size=1)
    tft.draw_text(30, 180, "GORUSUNUZ", 255, 255, 255, 100, 50, 0, size=1)

def show_loading(tft: ILI9486):
    """Yükleniyor mesajı."""
    tft.fill_screen(50, 50, 50)  # Gri arka plan
    tft.draw_text(30, 120, "OKUNUYOR", 255, 255, 255, 50, 50, 50, size=2)

def main():
    print("[PANEL] LCD ve dokunmatik başlatılıyor...")
    tft = ILI9486()
    # touch = XPT2046()  # Şimdilik kullanmıyoruz
    time.sleep(0.5)

    # Başlangıç ekranı
    print("[PANEL] Başlangıç ekranı gösteriliyor")
    tft.fill_screen(20, 20, 40)
    print("[PANEL] Ekran boyandı, yazı yazılıyor...")
    tft.draw_text(30, 80, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, size=2)
    tft.draw_text(30, 160, "PARMAK OKUTUN", 255, 200, 0, 20, 20, 40, size=2)
    print("[PANEL] Yazılar yazıldı")

    print("[PANEL] Parmak izini okutmayı bekleyin...")

    while True:
        try:
            # Parmak izi oku
            print("[PANEL] API çağrısı yapılıyor...")
            show_loading(tft)
            data, err = call_match()

            if err:
                print(f"[PANEL] API Hatası: {err}")
                show_error(tft)
                time.sleep(3)
                tft.fill_screen(20, 20, 40)
                tft.draw_text(30, 80, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, size=2)
                tft.draw_text(30, 160, "PARMAK OKUTUN", 255, 200, 0, 20, 20, 40, size=2)
                continue

            if not data:
                print("[PANEL] Parmak izi bulunamadı")
                show_error(tft)
                time.sleep(3)
                tft.fill_screen(20, 20, 40)
                tft.draw_text(30, 80, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, size=2)
                tft.draw_text(30, 160, "PARMAK OKUTUN", 255, 200, 0, 20, 20, 40, size=2)
                continue

            # Başarılı eşleştirme
            user = data.get("user", {})
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            event = data.get("event", "")
            
            print(f"[PANEL] Event: {event}, Kullanıcı: {name}")

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
            tft.draw_text(30, 80, "HOSGELDINIZ", 255, 255, 255, 20, 20, 40, size=2)
            tft.draw_text(30, 160, "PARMAK OKUTUN", 255, 200, 0, 20, 20, 40, size=2)
        
        except Exception as e:
            print(f"[PANEL] Exception: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[PANEL] Program durduruldu")
        import RPi.GPIO as GPIO
        GPIO.cleanup()
