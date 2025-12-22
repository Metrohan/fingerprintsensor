import RPi.GPIO as GPIO
import subprocess
import time
import os

# AYARLAR
PIN = 15  # GPIO 3 (Fiziksel 5. pin)
SCRIPT_PATH = "/home/ilab/Desktop/fingerprint/start_all.sh"

GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("🚀 Sistem Hazır. GPIO 3 üzerindeki butona basılması bekleniyor...")

try:
    while True:
        if GPIO.input(PIN) == GPIO.LOW:
            print("🎯 Buton algılandı! start_all.sh başlatılıyor...")
            
            # Çalışma dizinini ayarla
            os.chdir("/home/ilab/Desktop/fingerprint")
            
            # Betiği çalıştır
            subprocess.run(["bash", "start_all.sh"])
            
            # Titreşim veya çift basmayı önlemek için bekleme
            time.sleep(5)
            
        time.sleep(0.1)

except Exception as e:
    print(f"Hata: {e}")
finally:
    GPIO.cleanup()