# panel_ui.py
import time
import requests
from datetime import datetime
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT

API_BASE = "http://127.0.0.1:5000"


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
    bg = (10, 20, 40)
    tft.fill_screen(*bg)

    # Ortalanmış büyük başlık
    tft.draw_text_center(40, "HOSGELDINIZ", 255, 255, 255, *bg, size=3)
    # Alt satır
    tft.draw_text_center(140, "PARMAK OKUTUN", 255, 200, 0, *bg, size=2)


def show_loading(tft: ILI9486):
    """Parmak okunurken gösterilen ekran."""
    bg = (30, 30, 30)
    tft.fill_screen(*bg)
    tft.draw_text_center(120, "OKUNUYOR", 255, 255, 255, *bg, size=3)


def show_error(tft: ILI9486, msg: str = "KAYITSIZ"):
    """Parmak izi kaydı yok veya genel hata ekranı."""
    bg = (90, 30, 0)
    tft.fill_screen(*bg)

    tft.draw_text_center(40, "KAYITSIZ", 255, 255, 255, *bg, size=3)
    tft.draw_text_center(140, "YETKILIYLE", 255, 255, 255, *bg, size=2)
    tft.draw_text_center(190, "GORUSUNUZ", 255, 255, 255, *bg, size=2)

    # Hata mesajının kendisini küçük yazıyla alta koyabiliriz
    if msg:
        # 1 satıra sığması için kısalt
        short = msg[:24]
        tft.draw_text_center(250, short.upper(), 255, 255, 0, *bg, size=1)


def show_welcome(tft: ILI9486, name: str):
    """GİRİŞ ekranı – ad soyad ekranda büyük gözükecek."""
    bg = (0, 100, 0)
    tft.fill_screen(*bg)

    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")

    # Başlık
    tft.draw_text_center(30, "GIRIS YAPILDI", 255, 255, 255, *bg, size=3)

    # İsim (ilk 16 karakteri al, büyük harf)
    name = (name or "").upper()[:16]
    tft.draw_text_center(110, name, 255, 255, 255, *bg, size=2)

    # Saat ve tarih
    tft.draw_text_center(190, time_str, 255, 255, 0, *bg, size=2)
    tft.draw_text_center(230, date_str, 255, 255, 0, *bg, size=2)


def show_goodbye(tft: ILI9486, name: str, total_minutes: int):
    """ÇIKIŞ ekranı – ad soyad + toplam süre."""
    bg = (0, 0, 120)
    tft.fill_screen(*bg)

    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")

    # Toplam süreyi saate/dakikaya çevir
    h = total_minutes // 60
    m = total_minutes % 60
    total_str = f"{h} SAAT {m:02d} DK"

    # Başlık
    tft.draw_text_center(30, "CIKIS YAPILDI", 255, 255, 255, *bg, size=3)

    # İsim
    name = (name or "").upper()[:16]
    tft.draw_text_center(110, name, 255, 255, 255, *bg, size=2)

    # Süre + Saat/Tarih
    tft.draw_text_center(170, total_str, 255, 255, 0, *bg, size=2)
    tft.draw_text_center(230, time_str + "  " + date_str, 255, 255, 255, *bg, size=1)


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
                time.sleep(1)
                continue

            if not data or data.get("status") == "empty":
                time.sleep(0.1)
                continue

            if data.get("status") != "ok":
                msg = data.get("msg", "Bilinmeyen hata") if data else "Bilinmeyen hata"
                print(f"[PANEL] Beklenmeyen cevap: {msg}")
                show_error(tft, msg=msg)
                time.sleep(3)
                draw_home_screen(tft)
                continue

            # Burada JSON'dan ad-soyadı çekiyoruz
            user = data.get("user", {}) or {}
            first_name = user.get("first_name", "").strip()
            last_name = user.get("last_name", "").strip()
            full_name = (first_name + " " + last_name).strip()
            event = data.get("event", "")

            print(f"[PANEL] Event={event}, User={full_name}")

            if event == "check_in":
                show_welcome(tft, full_name)
            elif event == "check_out":
                total_minutes = int(data.get("total_duration_minutes", 0) or 0)
                show_goodbye(tft, full_name, total_minutes)
            else:
                show_error(tft, msg=f"Bilinmeyen event: {event}")

            time.sleep(3)
            draw_home_screen(tft)

        except Exception as e:
            print(f"[PANEL] Exception: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(2)
            draw_home_screen(tft)
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[PANEL] Program durduruldu")
        import RPi.GPIO as GPIO
        GPIO.cleanup()