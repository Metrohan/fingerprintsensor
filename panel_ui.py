# panel_ui.py
import time
import requests
from datetime import datetime
from ili9486 import ILI9486, TFT_WIDTH, TFT_HEIGHT

API_BASE = "http://127.0.0.1:5000"

def call_match():
    """API'den fingerprint eşleştirme çağrısı."""
    try:
        print(f"[API] GET {API_BASE}/api/match-fingerprint ...")
        r = requests.get(API_BASE + "/api/match-fingerprint", timeout=30)
        print(f"[API] Status Code: {r.status_code}")
        print(f"[API] Response Text: {r.text[:200]}")  # İlk 200 karakter
        
        if r.status_code == 200:
            try:
                return r.json(), None
            except Exception as json_err:
                print(f"[API] JSON parse hatası: {json_err}")
                return None, f"JSON hatası: {r.text[:100]}"
        else:
            try:
                return None, r.json().get("msg", f"Error {r.status_code}")
            except:
                return None, f"Error {r.status_code}: {r.text[:100]}"
    except Exception as e:
        print(f"[API] Exception: {e}")
        return None, str(e)


def draw_home_screen(tft: ILI9486):
    """Ana bekleme ekranı."""
    bg = (20, 20, 40)
    tft.fill_screen(*bg)
    tft.draw_text(
        30, 80,
        "HOSGELDINIZ",
        255, 255, 255,
        *bg,
        size=2
    )
    tft.draw_text(
        30, 160,
        "PARMAK OKUTUN",
        255, 200, 0,
        *bg,
        size=2
    )


def show_welcome(tft: ILI9486, name: str):
    """Hoşgeldin mesajı göster (giriş)."""
    print(f"[DISPLAY] Hoşgeldin: {name}")
    bg = (0, 100, 0)
    tft.fill_screen(*bg)

    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")

    # Başlık
    tft.draw_text(30, 30, "HOSGELDIN", 255, 255, 255, *bg, size=2)

    # İsim (max 12 karakter)
    name_short = name[:12]
    tft.draw_text(30, 80, name_short, 255, 255, 255, *bg, size=2)

    # Saat
    tft.draw_text(30, 130, time_str, 255, 255, 0, *bg, size=2)

    # Tarih
    tft.draw_text(30, 170, date_str, 255, 255, 0, *bg, size=1)


def show_goodbye(tft: ILI9486, name: str, total_hours: int, total_minutes: int):
    """Hoşçakal mesajı göster (çıkış)."""
    print(f"[DISPLAY] Hoşçakal: {name} - Toplam: {total_hours}:{total_minutes:02d}")
    bg = (0, 0, 100)
    tft.fill_screen(*bg)

    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")

    # Başlık
    tft.draw_text(30, 30, "HOSCAKAL", 255, 255, 255, *bg, size=2)

    # İsim
    name_short = name[:12]
    tft.draw_text(30, 80, name_short, 255, 255, 255, *bg, size=2)

    # Tarih
    tft.draw_text(30, 130, date_str, 255, 255, 0, *bg, size=1)

    # Saat
    tft.draw_text(30, 160, time_str, 255, 255, 0, *bg, size=2)

    # Toplam çalışma süresi
    total_str = f"{total_hours}:{total_minutes:02d}"
    tft.draw_text(30, 210, total_str, 0, 255, 0, *bg, size=2)


def show_error(tft: ILI9486, msg: str = "Parmak izi kayitli degil"):
    """Parmak izi kaydı yok veya hata mesajı."""
    print(f"[DISPLAY] Hata: {msg}")
    bg = (100, 50, 0)
    tft.fill_screen(*bg)

    # Başlık
    tft.draw_text(30, 80, "KAYITSIZ", 255, 255, 255, *bg, size=2)

    # Alt satırlar
    tft.draw_text(30, 150, "YETKILIYLE", 255, 255, 255, *bg, size=1)
    tft.draw_text(30, 180, "GORUSUNUZ", 255, 255, 255, *bg, size=1)


def show_loading(tft: ILI9486):
    """Yükleniyor mesajı."""
    bg = (50, 50, 50)
    tft.fill_screen(*bg)
    tft.draw_text(30, 120, "OKUNUYOR", 255, 255, 255, *bg, size=2)


def main():
    print("[PANEL] LCD başlatılıyor...")
    tft = ILI9486()
    time.sleep(0.5)

    print("[PANEL] Başlangıç ekranı...")
    draw_home_screen(tft)

    print("[PANEL] Parmak izini bekliyor...")
    print("[PANEL] NOT: API çağrısı yapılmıyor, sürekli bekleme modunda")
    print("[PANEL] Manuel test için bir tuşa basın...")

    while True:
        try:
            # Kullanıcıdan input bekle (gerçek sistemde parmak izi sensörü IRQ kullanılır)
            input(">>> Parmak izi okutmak için ENTER'a basın (Ctrl+C çıkış): ")
            
            # Parmak izi oku (match)
            print("[PANEL] API /api/match-fingerprint çağrılıyor...")
            show_loading(tft)
            data, err = call_match()

            if err:
                print(f"[PANEL] API Hatası: {err}")
                show_error(tft, msg=str(err))
                time.sleep(3)
                draw_home_screen(tft)
                continue

            if not data or data.get("status") != "ok":
                print("[PANEL] Eşleştirme yok veya status != ok")
                msg = data.get("msg", "Parmak izi bulunamadı") if data else "Parmak izi bulunamadı"
                show_error(tft, msg=msg)
                time.sleep(3)
                draw_home_screen(tft)
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
            else:
                # Beklenmedik event ise ufak bilgi ver
                show_error(tft, msg=f"Bilinmeyen event: {event}")

            time.sleep(3)
            draw_home_screen(tft)

        except KeyboardInterrupt:
            print("\n[PANEL] Çıkış yapılıyor...")
            break
        except Exception as e:
            print(f"[PANEL] Exception: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)
            draw_home_screen(tft)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[PANEL] Program durduruldu")
        import RPi.GPIO as GPIO
        GPIO.cleanup()