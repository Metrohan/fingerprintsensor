# config.py - Yapılandırma Dosyası
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'guvenli_gizli_anahtar_123'
    DB_PATH = "attendance.db"
    SERIAL_PORT = "/dev/serial0"
    BAUD_RATE = 19200
    TIMEOUT = 1.0
# ========== FLASK AYARLARI ==========
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False

# ========== VERITABANI AYARLARI ==========
DB_PATH = "attendance.db"

# ========== UART/SENSÖR AYARLARI ==========
UART_PORT = "/dev/serial0"  # Raspberry Pi default serial port
UART_BAUD = 19200           # Waveshare modül baud rate
UART_TIMEOUT = 1            # Zaman aşımı (saniye)

# ========== GÜVENLİK AYARLARI ==========
SECRET_KEY = "buraya_bir_secret_yaz"  # Flask session için
# Üretim ortamında: os.urandom(24).hex()

# ========== YOKLAMA AYARLARI ==========
AUTO_REFRESH_INTERVAL = 10  # Dashboard otomatik yenileme (saniye)
DATE_FORMAT = "%d.%m.%Y"    # Tarih formatı
TIME_FORMAT = "%H:%M:%S"    # Saat formatı

# ========== LOGGING AYARLARI ==========
LOG_LEVEL = "INFO"          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "app.log"        # Log dosyası (optional)

# ========== UI AYARLARI ==========
TIMEZONE = "Europe/Istanbul"  # Saat dilimi
PAGE_REFRESH = 10           # Sayfayı yenileme süresi (saniye)

# ========== SENSÖR KOMUTLARI ==========
SENSOR_COMMANDS = {
    "GET_USER_COUNT": 0x09,     # Kullanıcı sayısını al
    "MATCH_FINGERPRINT": 0x0C,  # Parmak izi eşleştir
    "ADD_FINGERPRINT": 0x01,    # Yeni parmak izi ekle
    "DELETE_USER": 0x04,        # Kullanıcı sil
}

# ========== SENSÖR PROTOKOLÜ ==========
SENSOR_HEADER = 0xF5
SENSOR_FOOTER = 0xF5
SENSOR_PKT_LENGTH = 8
