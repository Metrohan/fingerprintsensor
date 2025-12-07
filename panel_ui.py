# panel_ui.py
import time
import requests
import os
from datetime import datetime
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT

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
    try:
        tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png")
    except Exception:
        tft.fill_screen(10, 20, 40)

    # i-Lab teması için optimize edilmiş konumlar
    tft.draw_text_center(
        75, "HOSGELDINIZ",
        0, 0, 0,   # yazı rengi
        10, 20, 40,
        size=3,
        paint_bg=False
    )
    tft.draw_text_center(
        155, "PARMAK OKUTUN",
        0, 0, 0,
        10, 20, 40,
        size=2,
        paint_bg=False
    )


def show_loading(tft: ILI9486):
    """(Şu an kullanılmıyor ama dursun) Parmak okunurken gösterilen ekran."""
    try:
        tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png")
    except Exception:
        tft.fill_screen(30, 30, 30)
    tft.draw_text_center(
        150, "OKUNUYOR...",
        0, 0, 0,
        30, 30, 30,
        size=3,
        paint_bg=False
    )


def show_error(tft: ILI9486, msg: str = "KAYITSIZ"):
    """Parmak izi kaydı yok veya genel hata ekranı."""
    try:
        tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png")
    except Exception:
        tft.fill_screen(90, 30, 0)

    tft.draw_text_center(
        75, "KAYITSIZ",
        0, 0, 0,
        90, 30, 0,
        size=3,
        paint_bg=False
    )
    tft.draw_text_center(
        150, "YETKILIYLE",
        0, 0, 0,
        90, 30, 0,
        size=2,
        paint_bg=False
    )
    tft.draw_text_center(
        185, "GORUSUNUZ",
        0, 0, 0,
        90, 30, 0,
        size=2,
        paint_bg=False
    )

    if msg:
        short = msg[:24]
        tft.draw_text_center(
            240, short.upper(),
            0, 0, 0,
            90, 30, 0,
            size=1,
            paint_bg=False
        )


def show_welcome(tft: ILI9486, name: str):
    """GİRİŞ ekranı – ad soyad ekranda büyük gözükecek."""
    try:
        tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png")
    except Exception:
        tft.fill_screen(0, 100, 0)

    name = (name or "").upper()[:16]
    now = datetime.now()

    tft.draw_text_center(
        75, "GIRIS YAPILDI",
        0, 0, 0,
        255, 255, 255,
        size=3,
        paint_bg=False
    )
    tft.draw_text_center(
        140, name,
        0, 0, 0,
        255, 255, 255,
        size=2,
        paint_bg=False
    )
    tft.draw_text_center(
        205, now.strftime("%H:%M"),
        0, 0, 0,
        255, 255, 0,
        size=2,
        paint_bg=False
    )
    tft.draw_text_center(
        245, now.strftime("%d/%m/%Y"),
        0, 0, 0,
        255, 255, 0,
        size=1,
        paint_bg=False
    )


def show_goodbye(tft: ILI9486, name: str, total_minutes: int):
    """ÇIKIŞ ekranı – ad soyad + toplam süre."""
    try:
        tft.draw_image(0, 0, f"{ASSET_DIR}/home_bg.png")
    except Exception:
        tft.fill_screen(0, 0, 120)

    name = (name or "").upper()[:16]
    now = datetime.now()

    h = total_minutes // 60
    m = total_minutes % 60
    total_str = f"{h} SAAT {m:02d} DK"

    tft.draw_text_center(
        75, "CIKIS YAPILDI",
        0, 0, 0,
        255, 255, 255,
        size=3,
        paint_bg=False
    )
    tft.draw_text_center(
        140, name,
        0, 0, 0,
        255, 255, 255,
        size=2,
        paint_bg=False
    )
    tft.draw_text_center(
        205, total_str,
        0, 0, 0,
        255, 255, 0,
        size=2,
        paint_bg=False
    )
    tft.draw_text_center(
        245, now.strftime("%H:%M %d/%m/%Y"),
        0, 0, 0,
        255, 255, 255,
        size=1,
        paint_bg=False
    )


# ---------- Ana Döngü ----------

def main():
    print("[PANEL] LCD baslatiliyor...")
    tft = ILI9486()
    time.sleep(0.5)

    print("[PANEL] Baslangic ekrani...")
    draw_home_screen(tft)

    print("[PANEL] Parmak izini bekliyor...")

    while True:
        try:
            data, err = fetch_last_event()

            if err:
                print(f"[PANEL] API hatasi: {err}")
                time.sleep(0.5)
                continue

            if not data or data.get("status") == "empty":
                time.sleep(0.1)
                continue

            if data.get("status") != "ok":
                msg = data.get("msg", "Bilinmeyen hata") if data else "Bilinmeyen hata"
                print(f"[PANEL] Beklenmeyen cevap: {msg}")
                show_error(tft, msg=msg)
                time.sleep(1.0)  # hata ekranı biraz hızlı dönsün
                draw_home_screen(tft)
                continue

            user = data.get("user", {}) or {}
            first_name = user.get("first_name", "").strip()
            last_name = user.get("last_name", "").strip()
            full_name = (first_name + " " + last_name).strip()
            event = data.get("event", "")
            msg = data.get("msg") or "KAYITSIZ"
            total_minutes = int(data.get("total_duration_minutes", 0) or 0)

            print(f"[PANEL] Event={event}, User={full_name}")

            # Event türüne göre farklı ekran süreleri
            delay = 1.2  # default

            if event == "check_in":
                show_welcome(tft, full_name)
                delay = 1.0
            elif event == "check_out":
                show_goodbye(tft, full_name, total_minutes)
                delay = 1.8
            elif event == "error":
                show_error(tft, msg=msg)
                delay = 1.2
            else:
                show_error(tft, msg=f"Bilinmeyen event: {event}")
                delay = 1.0

            time.sleep(delay)
            draw_home_screen(tft)

        except Exception as e:
            print(f"[PANEL] Exception: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1.0)
            draw_home_screen(tft)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[PANEL] Program durduruldu")
        import RPi.GPIO as GPIO
        GPIO.cleanup()
