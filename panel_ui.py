# panel_ui.py
import time
import requests
import os
import sys
import socket
from datetime import datetime

# Proje kök dizinini path'e ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "drivers"))

from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT
from logger import setup_logger

# Logger oluştur
log = setup_logger("panel")

API_BASE = "http://127.0.0.1:5000"
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")


# ---------- API Yardımcıları ----------

def fetch_last_event():
    """Panel için son yoklama olayını çeker (pasif dinleme)."""
    try:
        r = requests.get(API_BASE + "/api/last-event", timeout=5)
        if r.status_code == 200:
            return r.json(), None
        try:
            return None, r.json().get("msg", f"Error {r.status_code}")
        except Exception:
            return None, f"Error {r.status_code}"
    except Exception as e:
        return None, str(e)


# ---------- Ekran Çizim Fonksiyonları ----------

def draw_home_screen(tft: ILI9486):
    """Ana bekleme ekranı."""
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(10, 20, 40)

    # Ortalanmış büyük başlık
    tft.draw_text_center(60, "HOSGELDINIZ", 0, 0, 0, 10, 20, 40, size=3, paint_bg=False)
    # Alt satır
    tft.draw_text_center(120, "PARMAK OKUTUN", 0, 0, 0, 10, 20, 40, size=2, paint_bg=False)
    
    # Sensör temizleme uyarısı (kırmızı, orta-alt arasında)
    tft.draw_text_center(165, "Sensoru Temizleyiniz", 0, 0, 0, 255, 100, 0, size=1, paint_bg=False)
    
    # IP adresi (sol alt köşe)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "N/A"
    tft.draw_text(10, 300, f"IP: {ip}", 200, 200, 200, 0, 0, 0, size=1, paint_bg=False)


def show_loading(tft: ILI9486):
    """Parmak okunurken gösterilen ekran."""
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(30, 30, 30)
    tft.draw_text_center(120, "OKUNUYOR", 0, 0, 0, 30, 30, 30, size=3, paint_bg=False)


def show_error(tft: ILI9486, msg: str = "KAYITSIZ"):
    """Parmak izi kaydı yok veya genel hata ekranı."""
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(90, 30, 0)

    tft.draw_text_center(40, "KAYITSIZ", 0, 0, 0, 90, 30, 0, size=3, paint_bg=False)
    tft.draw_text_center(140, "YETKILIYLE", 0, 0, 0, 90, 30, 0, size=2, paint_bg=False)
    tft.draw_text_center(190, "GORUSUNUZ", 0, 0, 0, 90, 30, 0, size=2, paint_bg=False)

    # Hata mesajının kendisini küçük yazıyla alta koyabiliriz
    if msg:
        # 1 satıra sığması için kısalt
        short = msg[:24]
        tft.draw_text_center(250, short.upper(), 0, 0, 0, 90, 30, 0, size=1, paint_bg=False)


def show_welcome(tft: ILI9486, name: str):
    """GİRİŞ ekranı – ad soyad ekranda büyük gözükecek."""
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(0, 100, 0)

    name = (name or "").upper()[:16]
    now = datetime.now()

    tft.draw_text_center(40, "GIRIS YAPILDI", 0, 0, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(110, name, 0, 0, 0, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(170, now.strftime("%H:%M"), 0, 0, 0, 255, 255, 0, size=2, paint_bg=False)
    tft.draw_text_center(220, now.strftime("%d/%m/%Y"), 0, 0, 0, 255, 255, 0, size=2, paint_bg=False)


def show_goodbye(tft: ILI9486, name: str, total_minutes: int):
    """ÇIKIŞ ekranı – ad soyad + toplam süre."""
    if not tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png"):
        tft.fill_screen(0, 0, 120)

    name = (name or "").upper()[:16]
    now = datetime.now()

    h = total_minutes // 60
    m = total_minutes % 60
    total_str = f"{h} SAAT {m:02d} DK"

    tft.draw_text_center(40, "CIKIS YAPILDI", 0, 0, 0, 255, 255, 255, size=3, paint_bg=False)
    tft.draw_text_center(110, name, 0, 0, 0, 255, 255, 255, size=2, paint_bg=False)
    tft.draw_text_center(170, total_str, 0, 0, 0, 255, 255, 0, size=2, paint_bg=False)
    tft.draw_text_center(220, now.strftime("%H:%M %d/%m/%Y"), 0, 0, 0, 255, 255, 255, size=1, paint_bg=False)


# ---------- Ana Döngü ----------

def main():
    log.info("LCD başlatılıyor...")
    tft = ILI9486()
    time.sleep(0.5)

    log.info("Başlangıç ekranı...")
    draw_home_screen(tft)

    log.info("Parmak izini bekliyor...")

    while True:
        try:
            data, err = fetch_last_event()

            if err:
                log.error(f"API hatası: {err}")
                time.sleep(1)
                continue

            if not data or data.get("status") == "empty":
                time.sleep(0.1)
                continue

            if data.get("status") != "ok":
                msg = data.get("msg", "Bilinmeyen hata") if data else "Bilinmeyen hata"
                log.warning(f"Beklenmeyen cevap: {msg}")
                show_error(tft, msg=msg)
                time.sleep(1.5)
                draw_home_screen(tft)
                continue

            # Burada JSON'dan ad-soyadı çekiyoruz
            user = data.get("user", {}) or {}
            first_name = user.get("first_name", "").strip()
            last_name = user.get("last_name", "").strip()
            full_name = (first_name + " " + last_name).strip()
            event = data.get("event", "")
            msg = data.get("msg") or "KAYITSIZ"

            log.info(f"Event={event}, User={full_name}")

            if event == "check_in":
                show_welcome(tft, full_name)
            elif event == "check_out":
                total_minutes = int(data.get("total_duration_minutes", 0) or 0)
                show_goodbye(tft, full_name, total_minutes)
            elif event == "error":
                show_error(tft, msg=msg)
            else:
                show_error(tft, msg=f"Bilinmeyen event: {event}")

            time.sleep(1.5)
            draw_home_screen(tft)

        except Exception as e:
            log.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)
            draw_home_screen(tft)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Program durduruldu")
        import RPi.GPIO as GPIO
        GPIO.cleanup()