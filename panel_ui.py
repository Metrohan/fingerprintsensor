# panel_ui.py
import time
import requests
import os
import sys
import socket
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "drivers"))

from ili9486 import ILI9486
from logger import setup_logger

log = setup_logger("panel")

API_BASE = "http://127.0.0.1:5000"
ASSET_DIR = os.path.join(BASE_DIR, "assets")

# ---------- AYARLAR ----------
COOLDOWN_SECONDS = 10
_last_processed_time = 0
_last_user_id = None
_current_ip = None

# ---------- YARDIMCI FONKSİYONLAR ----------

def get_ip():
    global _current_ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        _current_ip = s.getsockname()[0]
        s.close()
    except:
        _current_ip = "N/A"
    return _current_ip

def fetch_last_event():
    try:
        r = requests.get(API_BASE + "/api/last-event", timeout=0.8)
        if r.status_code == 200:
            return r.json(), None
        return None, r.text
    except:
        return None, None

def wait_for_api(max_wait=30):
    log.info("API bekleniyor...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = requests.get(API_BASE + "/api/last-event", timeout=1)
            if r.status_code in (200, 404):
                log.info("✓ API hazır")
                return True
        except:
            time.sleep(1)
    return False

# ---------- SADECE YAZI ALANINI BEYAZA BOYA ----------

def clear_message_area(tft: ILI9486):
    # Beyaz zemin
    tft.fill_rect(0, 30, 480, 190, 255, 255, 255)

# ---------- EKRAN ÇİZİMLERİ ----------

def draw_home_screen(tft: ILI9486):
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(255, 255, 255)

    tft.draw_text_center(60, "HOSGELDINIZ", 0, 0, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(120, "PARMAK OKUTUN", 0, 0, 0, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(165, "Sensoru Temizleyiniz", 0, 0, 0, 255, 255, 255, size=1, paint_bg=False)

    ip = _current_ip if _current_ip else get_ip()
    tft.draw_text(10, 300, f"IP: {ip}", 0, 0, 0, 255, 255, 255, size=1, paint_bg=True)

def show_welcome(tft: ILI9486, name: str):
    clear_message_area(tft)
    name = (name or "").upper()[:16]
    now = datetime.now()

    tft.draw_text_center(60, "GIRIS YAPILDI", 0, 150, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(120, name, 0, 0, 0, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(170, now.strftime("%H:%M"), 80, 80, 80, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(210, now.strftime("%d/%m/%Y"), 80, 80, 80, 255, 255, 255, size=1, paint_bg=False)

def show_goodbye(tft: ILI9486, name: str, total_minutes: int):
    clear_message_area(tft)
    name = (name or "").upper()[:16]
    now = datetime.now()

    h = total_minutes // 60
    m = total_minutes % 60
    total_str = f"{h} SAAT {m:02d} DK"

    tft.draw_text_center(60, "CIKIS YAPILDI", 180, 100, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(120, name, 0, 0, 0, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(170, total_str, 80, 80, 80, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(210, now.strftime("%H:%M %d/%m/%Y"), 80, 80, 80, 255, 255, 255, size=1, paint_bg=False)

def show_error(tft: ILI9486, msg="HATA"):
    clear_message_area(tft)
    tft.draw_text_center(100, "HATA", 200, 0, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(160, msg[:24].upper(), 0, 0, 0, 255, 255, 255, size=1, paint_bg=False)

# ---------- ANA DÖNGÜ ----------

def main():
    global _last_processed_time, _last_user_id

    log.info("LCD başlatılıyor...")
    tft = ILI9486()
    get_ip()
    time.sleep(0.5)

    draw_home_screen(tft)

    if not wait_for_api():
        return

    last_event_id = None
    init_data, _ = fetch_last_event()
    if init_data and init_data.get("status") != "empty":
        last_event_id = init_data.get("timestamp")

    while True:
        try:
            data, err = fetch_last_event()

            if err or data is None or data.get("status") == "empty":
                time.sleep(0.1)
                continue

            ts = data.get("timestamp")
            user_data = data.get("user", {})
            user_id = user_data.get("id")
            now = time.time()

            if ts == last_event_id:
                time.sleep(0.1)
                continue

            if user_id == _last_user_id and (now - _last_processed_time) < COOLDOWN_SECONDS:
                time.sleep(0.1)
                continue

            last_event_id = ts
            _last_processed_time = now
            _last_user_id = user_id

            event = data.get("event")
            name = f"{user_data.get('first_name','')} {user_data.get('last_name','')}".strip()

            if event == "check_in":
                show_welcome(tft, name)
                time.sleep(3)

            elif event == "check_out":
                show_goodbye(tft, name, int(data.get("total_duration_minutes", 0)))
                time.sleep(3)

            else:
                show_error(tft, data.get("msg", "HATA"))
                time.sleep(2)

            draw_home_screen(tft)

        except Exception as e:
            log.error(f"Döngü Hatası: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
