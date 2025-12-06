# panel_ui.py
import time
import requests

from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT
from xpt2046 import XPT2046

API_BASE = "http://127.0.0.1:5000"

# Touch raw değerlerini ekrana map etmek için (kalibrasyon)
# XPT2046 genellikle 0-4095 aralığında değer döner
# Dokunmatik ters çalışıyorsa ya da rotasyon yanlışsa bu değerleri ayarla
RAW_X_MIN = 250
RAW_X_MAX = 3900
RAW_Y_MIN = 250
RAW_Y_MAX = 3900

def map_value(val, in_min, in_max, out_min, out_max):
    """Aralığı dönüştür (clamp ile)"""
    if val < in_min: val = in_min
    if val > in_max: val = in_max
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def raw_to_screen(x_raw, y_raw):
    """Touch raw koordinatlarını ekran piksel koordinatlarına dönüştür."""
    # Eğer dokunmatik ters çalışıyorsa (sol-üst vs sağ-alt ters) flip et
    screen_x = map_value(x_raw, RAW_X_MIN, RAW_X_MAX, 0, TFT_WIDTH - 1)
    screen_y = map_value(y_raw, RAW_Y_MIN, RAW_Y_MAX, 0, TFT_HEIGHT - 1)
    
    # FLIP SEÇENEĞİ: Koordinatlar ters ise uncomment et
    # screen_x = TFT_WIDTH - 1 - screen_x
    # screen_y = TFT_HEIGHT - 1 - screen_y
    
    return screen_x, screen_y

def draw_main_menu(tft: ILI9486):
    # Arka plan
    tft.fill_screen(0, 0, 0)
    # Sol buton: Yoklama (yeşil)
    tft.fill_rect(10, 50, 140, 200, 0, 150, 0)
    # Sağ buton: Yeni Kayıt (mavi)
    tft.fill_rect(170, 50, 140, 200, 0, 0, 180)

    # Ufak görsel text yerine sadece renkli panel yapıyoruz.
    # Zamanla text çizimi ekleriz.

def show_message(tft: ILI9486, line1="", line2="", color=(0,0,0)):
    # Basit: tüm ekranı tek renge boya, message için üstte debug/log, şimdilik print kullanıyoruz.
    r, g, b = color
    tft.fill_screen(r, g, b)
    print("Ekran mesajı:", line1, "|", line2)

def call_match():
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

def call_scan():
    try:
        r = requests.get(API_BASE + "/api/scan-fingerprint", timeout=60)
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

    draw_main_menu(tft)
    print("Dokunmatik panel: Sol=Yoklama, Sağ=Yeni Kayıt")

    while True:
        pt = touch.read_point()
        if pt is None:
            time.sleep(0.05)
            continue

        x_raw, y_raw = pt
        x, y = raw_to_screen(x_raw, y_raw)
        print("Touch:", x_raw, y_raw, "=>", x, y)

        # Sol buton (Yoklama): x ~ 10..150, y ~ 50..250
        if 10 <= x <= 150 and 50 <= y <= 250:
            show_message(tft, "Yoklama aliniyor", "", (50, 50, 50))
            data, err = call_match()
            if err:
                show_message(tft, "HATA", err, (120, 0, 0))
            else:
                user = data.get("user", {})
                name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
                event = data.get("event", "")
                if event == "check_in":
                    show_message(tft, name, "GIRIS", (0, 120, 0))
                elif event == "check_out":
                    show_message(tft, name, "CIKIS", (0, 0, 120))
                else:
                    show_message(tft, name, "BILINMEYEN", (60, 60, 0))
            time.sleep(2)
            draw_main_menu(tft)

        # Sağ buton (Yeni Kayıt): x ~ 170..310, y ~ 50..250
        elif 170 <= x <= 310 and 50 <= y <= 250:
            show_message(tft, "Yeni kayit", "Parmak okuyun", (50, 50, 50))
            data, err = call_scan()
            if err:
                show_message(tft, "HATA", err, (120, 0, 0))
            else:
                fid = data.get("fingerprint_id", "?")
                msg = f"Finger ID: {fid}"
                show_message(tft, "Kayit OK", msg, (0, 120, 0))
            time.sleep(2)
            draw_main_menu(tft)

        else:
            # Menunun disina dokunulduysa ignore
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import RPi.GPIO as GPIO
        GPIO.cleanup()