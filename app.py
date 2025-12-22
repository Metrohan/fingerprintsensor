# app.py
# Raspberry Pi 3 + Waveshare UART Fingerprint Reader
# Yoklama sistemi (SQLite + Flask + Web UI)

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import sqlite3
from datetime import datetime, date, timedelta
import os
import time
import sys
import threading
from functools import wraps
from logger import setup_logger
import logging

# Logger oluştur
log = setup_logger("app")

# Proje kök dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "attendance.db")

def get_current_work_day():
    """
    24 saat sabah 6'dan sabah 6'ya (06:00-05:59).
    Sabah 6'dan önce: dünün devamı
    """
    now = datetime.now()
    if now.hour < 6:
        return (now - timedelta(days=1)).date()
    return now.date()

# Ekrana iletilecek son yoklama olayı (panel_ui tarafından poll edilir)
last_display_event = {
    "event": None,
    "timestamp": None,
    "user": None,
    "total_duration_minutes": 0,
    "msg": None,
}

# Son hata bildiriminin zamanı (kayıtsız parmak için flood engeli)
last_error_event_time = 0

# --------- UART / Fingerprint config ---------
try:
    import serial
    UART_AVAILABLE = True
except ImportError:
    UART_AVAILABLE = False

PORT = "/dev/serial0"
BAUD = 19200

# ACK codes from manual
ACK_SUCCESS    = 0x00  # generic success (çoğu komut için)
ACK_FAIL       = 0x01
ACK_FULL       = 0x04
ACK_NOUSER     = 0x05
ACK_USER_EXIST = 0x06
ACK_FIN_EXIST  = 0x07
ACK_TIMEOUT    = 0x08

app = Flask(__name__)
app.secret_key = "bir_sir_gir_buraya_secret_key_12345"
app.config['SESSION_TYPE'] = 'filesystem'

# Werkzeug (Flask) HTTP loglarını sustur
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# =====================================================
#       Kullanıcı Kimlik Bilgileri (Hardcoded)
# =====================================================
# Gerçek uygulamada veritabanında tutulmalı
USERS = {
    "ilab": {"password": "pievision", "role": "user"},  # user: yoklama giriş/çıkış
    "admin": {"password": "aYTaCDurmaz", "role": "admin"}  # admin: kullanıcı yönetimi
}

def login_required(f):
    """Login zorunluluğu decorator'ı"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Lütfen önce giriş yapınız.", "error")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Admin yetkisi zorunluluğu decorator'ı"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Lütfen önce giriş yapınız.", "error")
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            flash("Bu işlem için yetkiniz yoktur.", "error")
            return redirect(url_for('dashboard_today'))
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    """User/Attendance role'ü zorunluluğu decorator'ı"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Lütfen önce giriş yapınız.", "error")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
#       Fingerprint Sensor Class
# =====================================================

class FingerprintSensor:
    def __init__(self, port=PORT, baud=BAUD):
        self.port_name = port
        self.baud = baud
        self.ser = None
        self.last_error_count = 0  # Ardışık hata sayısı
        self.connect()

    def connect(self):
        """Open serial port."""
        if not UART_AVAILABLE:
            log.warning("UART serial modülü yok, demo mod.")
            return
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(self.port_name, self.baud, timeout=1)
            time.sleep(0.5)
            self.clear_buffer()
            log.info(f"UART Port açıldı: {self.port_name} @ {self.baud}")
        except Exception as e:
            log.error(f"UART Port açılamadı: {e}")
            self.ser = None

    def clear_buffer(self):
        """Seri port buffer'ını temizle."""
        if self.ser:
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

    def reconnect_if_needed(self):
        """Ardışık hatalardan sonra yeniden bağlan."""
        if self.last_error_count >= 5:
            log.warning("UART Çok fazla hata, yeniden bağlanılıyor...")
            self.connect()
            self.last_error_count = 0

    def is_ready(self):
        return self.ser is not None and self.ser.is_open

    @staticmethod
    def calc_checksum(b1, b2, b3, b4, b5):
        return b1 ^ b2 ^ b3 ^ b4 ^ b5

    def send_packet(self, cmd, p1=0, p2=0, p3=0, p4=0):
        """8 byte komut paketi gönder."""
        if not self.ser:
            return False

        pkt = bytearray(8)
        pkt[0] = 0xF5
        pkt[1] = cmd
        pkt[2] = p1
        pkt[3] = p2
        pkt[4] = p3
        pkt[5] = p4
        pkt[6] = self.calc_checksum(pkt[1], pkt[2], pkt[3], pkt[4], pkt[5])
        pkt[7] = 0xF5

        try:
            self.clear_buffer()  # Her gönderimden önce buffer temizle
            time.sleep(0.02)
            self.ser.write(pkt)
            log.debug(f"TX: {' '.join(f'{b:02X}' for b in pkt)}")
            return True
        except Exception as e:
            log.error(f"TX ERROR: {e}")
            self.last_error_count += 1
            return False

    def read_packet(self, timeout=3.0, expected_cmd=None):
        """8 byte cevap paketi oku (0xF5 .... 0xF5)."""
        if not self.ser:
            return None

        start = time.time()
        buf = bytearray()

        while (time.time() - start) < timeout:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    buf.extend(data)
                    log.debug(f"RX BUFFER: {len(data)} byte geldi, toplam {len(buf)}")

                    while len(buf) >= 8:
                        if buf[0] == 0xF5 and buf[7] == 0xF5:
                            pkt = bytes(buf[:8])
                            chk_expect = self.calc_checksum(pkt[1], pkt[2], pkt[3], pkt[4], pkt[5])
                            if pkt[6] != chk_expect:
                                log.warning(f"RX Bad checksum: got 0x{pkt[6]:02X}, expected 0x{chk_expect:02X}")
                                buf.pop(0)
                                continue

                            if expected_cmd is not None and pkt[1] != expected_cmd:
                                log.warning(f"RX Cmd mismatch: expected 0x{expected_cmd:02X}, got 0x{pkt[1]:02X}, skip")
                                buf = buf[8:]
                                continue

                            log.debug(f"RX: {' '.join(f'{b:02X}' for b in pkt)}")
                            return pkt
                        else:
                            buf.pop(0)

                time.sleep(0.05)
            except Exception as e:
                log.error(f"RX ERROR: {e}")
                break

        # RX Timeout normal bir durum, sadece debug seviyesinde logla
        if len(buf) > 0:
            log.debug(f"RX Timeout, buffer len={len(buf)}")
        return None

    @staticmethod
    def get_ack(resp):
        """Generic ACK alanı (Q3 = resp[4])"""
        if resp and len(resp) >= 5:
            return resp[4]
        return None

    @staticmethod
    def get_error_message(ack):
        if ack is None:
            return "Sensörden yanıt alınamadı"
        if ack == ACK_SUCCESS:
            return "İşlem başarılı"
        if ack == ACK_FAIL:
            return "İşlem başarısız - Parmak izi net okunamadı, tekrar deneyin"
        if ack == ACK_FULL:
            return "Sensör hafızası dolu"
        if ack == ACK_NOUSER:
            return "Parmak izi sensörde kayıtlı değil"
        if ack == ACK_USER_EXIST:
            return "Bu kullanıcı zaten kayıtlı"
        if ack == ACK_FIN_EXIST:
            return "Bu parmak izi zaten kayıtlı"
        if ack == ACK_TIMEOUT:
            return "Zaman aşımı - Parmak izi algılanamadı"
        return f"Bilinmeyen hata (ACK=0x{ack:02X})"

    # ------------- ENROLL (kayıt) 3 adım --------------

    def enroll_fingerprint(self, fp_id, timeout_per_step=20):
        """
        3-step enrollment (CMD=0x01,0x02,0x03)
        fp_id: sensor içindeki ID (DB'deki fingerprint_id ile aynı)
        """
        if not self.ser:
            return False, "Serial not open"

        user_hi = (fp_id >> 8) & 0xFF
        user_lo = fp_id & 0xFF

        def send_enroll_step(cmd, step_name):
            pkt = bytearray(8)
            pkt[0] = 0xF5
            pkt[1] = cmd
            pkt[2] = user_hi
            pkt[3] = user_lo
            pkt[4] = 0x01  # privilege=1 (normal user)
            pkt[5] = 0x00
            pkt[6] = self.calc_checksum(pkt[1], pkt[2], pkt[3], pkt[4], pkt[5])
            pkt[7] = 0xF5

            try:
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

                log.debug(f"ENROLL {step_name} send: {' '.join(f'{b:02X}' for b in pkt)}")
                self.ser.write(pkt)

                start = time.time()
                while time.time() - start < timeout_per_step:
                    resp = self.read_packet(timeout=0.5, expected_cmd=cmd)
                    if not resp:
                        continue
                    log.debug(f"ENROLL {step_name} resp: {' '.join(f'{b:02X}' for b in resp)}")
                    ack = self.get_ack(resp)
                    ack_msg = self.get_error_message(ack) if ack is not None else "Yanıt yok"
                    ack_hex = f"0x{ack:02X}" if ack is not None else "0xFF"
                    log.info(f"ENROLL {step_name} ACK={ack_hex} - {ack_msg}")

                    if ack == ACK_SUCCESS:
                        log.info(f"ENROLL ✓ {step_name} başarılı")
                        return True, None
                    if ack == ACK_USER_EXIST or ack == ACK_FIN_EXIST:
                        log.warning(f"ENROLL {step_name}: ID zaten kayıtlı - Önce silinmeli")
                        return False, f"{step_name}: Bu ID zaten kayıtlı, önce silinmeli"
                    if ack == ACK_TIMEOUT:
                        return False, f"{step_name}: Zaman aşımı - Parmağınızı sensöre bastırın"
                    if ack == ACK_FULL:
                        return False, f"{step_name}: Sensör hafızası dolu"
                    if ack == ACK_FAIL:
                        return False, f"{step_name}: Başarısız - Parmak izi net algılanamadı"

                    return False, f"{step_name}: {self.get_error_message(ack)}"

                return False, f"{step_name}: No response from sensor"

            except Exception as e:
                return False, f"{step_name}: Exception {e}"

        log.info(f"ENROLL Başlatılıyor ID={fp_id}")
        
        # Önce mevcut kaydı silmeyi dene (varsa)
        log.info(f"ENROLL Mevcut kayıt kontrol ediliyor ID={fp_id}...")
        delete_ok, delete_msg = self.delete_fingerprint(fp_id)
        if delete_ok:
            log.info(f"ENROLL Önceki kayıt silindi, yeni kayıt başlatılıyor...")
            time.sleep(0.5)
        else:
            log.info(f"ENROLL Önceki kayıt yok veya silinemedi: {delete_msg}")
        
        log.info("ENROLL STEP1: parmak basılı tutun...")
        ok, msg = send_enroll_step(0x01, "STEP1 (CMD=0x01)")
        if not ok:
            return False, msg

        log.info("ENROLL Parmağı çekin, tekrar bastırın (STEP2)...")
        time.sleep(1.5)
        ok, msg = send_enroll_step(0x02, "STEP2 (CMD=0x02)")
        if not ok:
            return False, msg

        log.info("ENROLL Parmağı çekin, üçüncü kez bastırın (STEP3)...")
        time.sleep(1.5)
        ok, msg = send_enroll_step(0x03, "STEP3 (CMD=0x03)")
        if not ok:
            return False, msg

        log.info("ENROLL Kayıt başarıyla tamamlandı.")
        return True, None

    # ------------- MATCH (1:N) 0x0C – ÖNEMLİ KISIM --------------

    def match_fingerprint(self, timeout=15, comparison_level=7, silent=False):
        """
        1:N karşılaştırma (CMD=0x0C).
        Manual 2.8'e göre:
        Response: F5 0C UserID_HI UserID_LO user_privilege / ACK_NOUSER / ACK_TIMEOUT 00 CHK F5

        Q3 (resp[4]):
            - 0x05 (ACK_NOUSER)   -> kullanıcı yok
            - 0x08 (ACK_TIMEOUT)  -> okuma/timeout
            - 0x01 / 0x02 / 0x03  -> privilege (1,2,3) -> BAŞARILI MATCH
        
        silent: True ise timeout/nouser loglaması yapılmaz (arka plan tarama için)
        """
        if not self.ser:
            return None, "Serial not open"

        # Bağlantı kontrolü
        self.reconnect_if_needed()

        if comparison_level < 1 or comparison_level > 9:
            comparison_level = 7

        if not silent:
            log.info("MATCH: Parmak izi bekleniyor...")

        # CMD=0x0C, P1=0x00, P2=comparison_level
        sent = self.send_packet(0x0C, 0x00, comparison_level, 0x00, 0x00)
        if not sent:
            self.last_error_count += 1
            return None, "Failed to send MATCH command"

        resp = self.read_packet(timeout=timeout, expected_cmd=0x0C)
        if not resp:
            # Timeout normal bir durum (parmak yok), hata sayma
            return None, None  # Parmak yok, hata değil

        log.debug(f"MATCH resp: {' '.join(f'{b:02X}' for b in resp)}")

        if len(resp) < 5:
            self.last_error_count += 1
            return None, "Invalid response length"

        user_hi = resp[2]
        user_lo = resp[3]
        q3 = resp[4]  # burada ya privilege(1/2/3) ya da ACK_NOUSER/ACK_TIMEOUT

        # Başarılı okuma, hata sayacını sıfırla
        self.last_error_count = 0

        # Önce gerçek hata kodlarını kontrol et
        if q3 == ACK_NOUSER:
            if not silent:
                log.warning(f"MATCH ACK=0x{q3:02X} (ACK_NOUSER) - Bu parmak izi sensörde kayıtlı değil")
            return None, "Parmak izi sistemde kayıtlı değil"
        if q3 == ACK_TIMEOUT:
            # Timeout = parmak algılanmadı, bu normal
            return None, None  # Parmak yok

        # Kalan durumlar (1,2,3) -> privilege -> başarılı eşleşme
        user_id = (user_hi << 8) | user_lo
        
        # User ID 0 ise geçersiz
        if user_id == 0:
            return None, None
            
        log.info(f"MATCH ✓ Eşleşme başarılı! Fingerprint ID={user_id}, Privilege={q3}")
        return user_id, None

    # ------------- DELETE FINGERPRINT (0x04) --------------
    def delete_fingerprint(self, fp_id):
        """
        Sensörden bir parmak izini silme (CMD=0x04).
        fp_id: silmek istenen fingerprint ID
        Response: F5 04 00 00 ACK 00 CHK F5
        """
        if not self.ser:
            return False, "Serial not open"

        user_hi = (fp_id >> 8) & 0xFF
        user_lo = fp_id & 0xFF

        log.info(f"DELETE Parmak izi siliniyor ID={fp_id}")

        sent = self.send_packet(0x04, user_hi, user_lo, 0x00, 0x00)
        if not sent:
            return False, "Failed to send DELETE command"

        resp = self.read_packet(timeout=5.0, expected_cmd=0x04)
        if not resp:
            return False, "No response from sensor"

        log.debug(f"DELETE resp: {' '.join(f'{b:02X}' for b in resp)}")

        ack = self.get_ack(resp)
        ack_msg = self.get_error_message(ack)
        ack_hex = f"0x{ack:02X}" if ack is not None else "0xFF"
        log.info(f"DELETE ACK={ack_hex} - {ack_msg}")
        
        if ack == ACK_SUCCESS:
            log.info(f"DELETE ✓ Parmak izi ID={fp_id} başarıyla silindi")
            return True, None
        elif ack == ACK_NOUSER:
            log.info(f"DELETE ID={fp_id} sensörde bulunamadı (zaten silinmiş)")
            return True, None  # Zaten yoksa da başarılı sayalım
        else:
            log.error(f"DELETE ✗ ID={fp_id} silinemedi: {ack_msg}")
            return False, ack_msg


# Global sensor instance
sensor = FingerprintSensor() if UART_AVAILABLE else None

# Parmak izi donanımını eş zamanlı kullanımlardan korumak için kilit
sensor_lock = threading.Lock()

# Arka planda sürekli okuma thread'i
sensor_thread = None
sensor_paused = False  # Kayıt sırasında arka plan okumayı duraklatmak için

def sensor_background_loop():
    """Parmak izi sensörünü sürekli aktif tutar ve eşleşmeleri işler."""
    global last_error_event_time, last_display_event, sensor_paused
    log.info("SENSOR LOOP Başlatıldı")
    
    # Son başarılı okuma zamanı (gereksiz hata mesajlarını engellemek için)
    last_successful_read = time.time()
    consecutive_nouser_count = 0  # Ardışık kayıtsız parmak sayısı

    while True:
        try:
            # Kayıt işlemi sırasında duraklat
            if sensor_paused:
                time.sleep(0.1)
                continue

            if not UART_AVAILABLE or not sensor or not sensor.is_ready():
                time.sleep(1.0)
                continue

            # Sensörden kısa zaman aşımı ile parmak oku (silent=True: gereksiz log yok)
            with sensor_lock:
                fp_id, err = sensor.match_fingerprint(timeout=1, comparison_level=6, silent=True)

            if fp_id is None:
                # err=None ise parmak yok (normal durum)
                if err is None:
                    consecutive_nouser_count = 0  # Sıfırla
                    time.sleep(0.3)
                    continue
                
                # Kayıtsız parmak tespit edildi
                if err and ("kayıtlı" in err.lower() or "kayitli" in err.lower()):
                    consecutive_nouser_count += 1
                    
                    # Sadece 2+ ardışık kayıtsız okuma ve son hatadan 3 saniye geçtiyse bildir
                    # Bu, yanlışlıkla algılanan gürültüyü filtreler
                    now_ts = time.time()
                    if consecutive_nouser_count >= 2 and (now_ts - last_error_event_time > 3.0):
                        last_error_event_time = now_ts
                        last_display_event = {
                            "event": "error",
                            "timestamp": datetime.now().isoformat(),
                            "user": None,
                            "total_duration_minutes": 0,
                            "msg": err,
                        }
                        log.warning(f"SENSOR LOOP Kayıtsız parmak algılandı ({consecutive_nouser_count}x)")
                        consecutive_nouser_count = 0  # Bildirdikten sonra sıfırla
                        time.sleep(2.0)  # Tekrar tetiklemeyi önle
                        continue
                
                time.sleep(0.3)
                continue

            # Başarılı eşleşme
            consecutive_nouser_count = 0
            last_successful_read = time.time()
            
            log.info(f"SENSOR LOOP Parmak bulundu: fingerprint_id={fp_id}")

            result, logic_err = process_attendance_event(fp_id)
            if logic_err:
                log.error(f"SENSOR LOOP Yoklama hatası: {logic_err}")
                # Kullanıcı veritabanında bulunamadıysa ekrana göster
                if "bulunamadı" in logic_err.lower():
                    last_display_event = {
                        "event": "error",
                        "timestamp": datetime.now().isoformat(),
                        "user": None,
                        "total_duration_minutes": 0,
                        "msg": "Kullanıcı sistemde kayıtlı değil",
                    }
                time.sleep(2.0)
                continue

            user_info = result.get("user", {})
            user_name = f"{user_info.get('first_name','')} {user_info.get('last_name','')}".strip()
            event_label = "Giriş" if result.get("event") == "check_in" else "Çıkış"
            log.info(f"SENSOR LOOP ✓ {event_label} kaydedildi - {user_name}")

            # Parmağı çekmeden sürekli tetiklemeyi önlemek için gecikme
            time.sleep(2.0)

        except Exception as e:
            log.error(f"SENSOR LOOP Hata: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1.0)

# =====================================================
#       DB Helpers
# =====================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_if_needed():
    if not os.path.exists(DB_PATH):
        try:
            import init_db  # aynı klasörde
            log.info("DB init_db.py çalıştırıldı / tablo oluşturuldu.")
        except Exception as e:
            log.error(f"DB init_db import error: {e}")

def get_next_fingerprint_id_from_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT MAX(fingerprint_id) AS max_id FROM users")
    row = cur.fetchone()
    conn.close()
    max_id = row["max_id"] if row and row["max_id"] is not None else 0
    return max_id + 1

def process_attendance_event(fp_id: int):
    """
    Verilen fingerprint_id için bugünün yoklama mantığı:
    
    Her giriş-çıkış çifti AYRI bir satır olarak kaydedilir.
    - Giriş: check_in=now, check_out=NULL olan yeni satır oluştur
    - Çıkış: Bugünkü check_out=NULL olan son satırı bul, check_out=now ve duration hesapla
    
    Örnek: 14:00-15:00 (1s) + 17:00-19:00 (2s) = 3 saat
    - 14:00: Satır 1 -> check_in=14:00, check_out=NULL
    - 15:00: Satır 1 -> check_in=14:00, check_out=15:00, duration=60
    - 17:00: Satır 2 -> check_in=17:00, check_out=NULL
    - 19:00: Satır 2 -> check_in=17:00, check_out=19:00, duration=120
    
    Toplam süre = SUM(duration_minutes WHERE date=today) = 60+120 = 180 dakika (3 saat)
    """
    global last_display_event
    now = datetime.now()
    today_str = get_current_work_day().isoformat()

    conn = get_db()
    cur = conn.cursor()

    # Kullanıcıyı bul
    cur.execute("SELECT id, first_name, last_name FROM users WHERE fingerprint_id = ?", (fp_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return None, f"Fingerprint ID {fp_id} için kullanıcı bulunamadı."

    user_id = user["id"]

    # Bugünkü açık kayıt var mı? (check_out NULL olan)
    # Sadece son 12 saat içindeki açık kayıtlara bak (05:59 sonrası yeni kayıt için)
    twelve_hours_ago = (now - timedelta(hours=12)).isoformat()
    cur.execute("""
        SELECT id, check_in
        FROM attendance
        WHERE user_id = ? AND date = ? AND check_out IS NULL
          AND check_in >= ?
        ORDER BY check_in DESC
        LIMIT 1
    """, (user_id, today_str, twelve_hours_ago))
    open_record = cur.fetchone()
    
    log.debug(f"ATTENDANCE 🔍 Kontrol - User: {user_id}, Work Day: {today_str}, Açık kayıt: {'Var' if open_record else 'Yok'}")

    if open_record is None:
        # Açık kayıt yok -> Yeni giriş yap
        cur.execute("""
            INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes)
            VALUES (?, ?, ?, NULL, 0)
        """, (user_id, today_str, now.isoformat()))
        conn.commit()
        
        new_id = cur.lastrowid
        log.info(f"ATTENDANCE ✓ Giriş: {user['first_name']} {user['last_name']} - {now.strftime('%H:%M:%S')} (Record ID: {new_id}, Date: {today_str})")
        
        conn.close()

        # Panel için gösterilecek son olayı güncelle
        last_display_event = {
            "event": "check_in",
            "timestamp": now.isoformat(),
            "user": {
                "id": user_id,
                "first_name": user["first_name"],
                "last_name": user["last_name"],
            },
            "total_duration_minutes": 0,
            "msg": None,
        }
        
        return {
            "event": "check_in",
            "timestamp": now.isoformat(),
            "user": {
                "id": user_id,
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
        }, None
    
    else:
        # Açık kayıt var -> Çıkış kontrolü
        check_in_dt = datetime.fromisoformat(open_record["check_in"])
        elapsed_seconds = (now - check_in_dt).total_seconds()
        
        # Minimum 5 saniye geçmemişse çıkış yapma
        MIN_DURATION_SECONDS = 5
        if elapsed_seconds < MIN_DURATION_SECONDS:
            conn.close()
            remaining = int(MIN_DURATION_SECONDS - elapsed_seconds)
            log.warning(f"ATTENDANCE ⚠️  Çıkış için çok erken! {remaining} saniye daha bekleyin.")
            return None, f"Parmak izi sensörde kaldı. Lütfen {remaining} saniye bekleyin."
        
        duration_minutes = int(elapsed_seconds // 60)
        
        cur.execute("""
            UPDATE attendance
            SET check_out = ?, duration_minutes = ?
            WHERE id = ?
        """, (now.isoformat(), duration_minutes, open_record["id"]))
        
        # Güncellemenin başarılı olduğunu doğrula
        if cur.rowcount == 0:
            log.error(f"ATTENDANCE ❌ Çıkış güncellemesi başarısız! Record ID: {open_record['id']}")
            conn.rollback()
            conn.close()
            return None, "Çıkış kaydı güncellenemedi."
        
        conn.commit()
        log.debug(f"ATTENDANCE 💾 Çıkış kaydedildi - Record ID: {open_record['id']}, check_in: {check_in_dt.strftime('%H:%M')}, check_out: {now.strftime('%H:%M')}")
        
        # Bugünün toplam çalışma süresini hesapla (tüm oturumlar)
        cur.execute("""
            SELECT SUM(duration_minutes) as total_duration
            FROM attendance
            WHERE user_id = ? AND date = ? AND check_out IS NOT NULL
        """, (user_id, today_str))
        total_result = cur.fetchone()
        total_duration_minutes = total_result["total_duration"] if total_result and total_result["total_duration"] else 0
        
        conn.close()
        
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        
        log.info(f"ATTENDANCE ✓ Çıkış: {user['first_name']} {user['last_name']} - {now.strftime('%H:%M:%S')}")
        log.info(f"ATTENDANCE ⏱️  Oturum süresi: {hours}s {minutes}d | Günlük toplam: {total_duration_minutes} dakika")

        # Panel için gösterilecek son olayı güncelle
        last_display_event = {
            "event": "check_out",
            "timestamp": now.isoformat(),
            "user": {
                "id": user_id,
                "first_name": user["first_name"],
                "last_name": user["last_name"],
            },
            "total_duration_minutes": total_duration_minutes,
            "msg": None,
        }
        
        return {
            "event": "check_out",
            "timestamp": now.isoformat(),
            "user": {
                "id": user_id,
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            },
            "duration_minutes": duration_minutes,
            "total_duration_minutes": total_duration_minutes
        }, None

# =====================================================
#       Web Routes - Login & Auth
# =====================================================

@app.route("/login", methods=["GET"])
def login_page():
    """ilab kullanıcısı otomatik giriş yapar."""
    # İlabs zaten login'se dashboard'a git, aksi halde otomatik login yap
    if 'user' in session and session.get('user') == 'ilab':
        return redirect(url_for('dashboard_today'))
    
    # ilab otomatik login
    session['user'] = 'ilab'
    session['role'] = 'user'
    log.info("AUTH ✓ ilab auto-logged in")
    return redirect(url_for('dashboard_today'))

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login_page():
    """Admin giriş sayfası."""
    if request.method == "GET":
        if 'user' in session and session.get('role') == 'admin':
            return redirect(url_for('dashboard_today'))
        return render_template("admin_login.html")
    
    # POST request: Admin login işlemi
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    if not username or not password:
        flash("Kullanıcı adı ve şifre zorunlu.", "error")
        return redirect(url_for("admin_login_page"))
    
    if username not in USERS:
        flash("Kullanıcı adı veya şifre hatalı.", "error")
        log.warning(f"AUTH Admin login başarısız: kullanıcı '{username}' bulunamadı")
        return redirect(url_for("admin_login_page"))
    
    user_data = USERS[username]
    if user_data["password"] != password:
        flash("Kullanıcı adı veya şifre hatalı.", "error")
        log.warning(f"AUTH Admin login başarısız: yanlış şifre - '{username}'")
        return redirect(url_for("admin_login_page"))
    
    # Sadece admin kullanıcısı erişsin
    if user_data["role"] != "admin":
        flash("Bu sayfaya sadece admin erişim sağlayabilir.", "error")
        log.warning(f"AUTH Admin olmayan '{username}' admin login'e erişmeye çalıştı")
        return redirect(url_for("admin_login_page"))
    
    # Admin login başarılı - session'a kaydet
    session['user'] = username
    session['role'] = user_data['role']
    log.info(f"AUTH ✓ Admin '{username}' giriş yaptı")
    flash(f"✓ Hoşgeldiniz {username}!", "success")
    return redirect(url_for("dashboard_today"))

@app.route("/logout", methods=["GET", "POST"])
def logout_page():
    username = session.get('user', 'unknown')
    role = session.get('role', 'unknown')
    session.clear()
    log.info(f"AUTH Kullanıcı '{username}' (role: {role}) çıkış yaptı")
    
    # Admin logout'ta admin login sayfasına git
    if role == 'admin':
        flash("✓ Çıkış yapıldı.", "success")
        return redirect(url_for("admin_login_page"))
    else:
        # ilab logout'ta ilab otomatik login'e yönlendir
        flash("Yönlendiriliyorsunuz...", "info")
        return redirect(url_for("login_page"))

# =====================================================
#       Web Routes - Dashboard & Attendance
# =====================================================

@app.route("/")
@login_required
def dashboard_today():
    today_str = get_current_work_day().isoformat()
    conn = get_db()
    cur = conn.cursor()
    
    # Her kullanıcı için tüm giriş-çıkış kayıtlarını ve toplamlarını getir
    cur.execute("""
        SELECT 
            u.id as user_id,
            u.first_name, 
            u.last_name,
            MIN(a.check_in) as first_check_in,
            MAX(a.check_out) as last_check_out,
            SUM(a.duration_minutes) as total_duration,
            COUNT(CASE WHEN a.check_out IS NULL THEN 1 END) as open_sessions
        FROM users u
        LEFT JOIN attendance a ON u.id = a.user_id AND a.date = ?
        WHERE a.id IS NOT NULL
        GROUP BY u.id, u.first_name, u.last_name
        ORDER BY first_check_in
    """, (today_str,))
    rows = cur.fetchall()
    conn.close()

    records = []
    inside_count = 0
    
    for r in rows:
        # Durum: Açık oturum varsa (check_out=NULL) içeride
        if r["open_sessions"] > 0:
            status = "İçeride"
            inside_count += 1
        else:
            status = "Dışarıda"

        # Timestamp formatını düzelt
        first_check_in_formatted = None
        last_check_out_formatted = None
        duration_str = ""
        
        if r["first_check_in"]:
            dt = datetime.fromisoformat(r["first_check_in"])
            first_check_in_formatted = dt.strftime("%d.%m.%Y %H:%M")
        
        if r["last_check_out"]:
            dt = datetime.fromisoformat(r["last_check_out"])
            last_check_out_formatted = dt.strftime("%d.%m.%Y %H:%M")
        
        # Toplam süreyi formatlı göster
        total_duration = r["total_duration"] if r["total_duration"] else 0
        if total_duration > 0:
            hours = total_duration // 60
            minutes = total_duration % 60
            duration_str = f"{hours}s {minutes}d"

        records.append({
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "first_check_in": first_check_in_formatted,
            "last_check_out": last_check_out_formatted,
            "duration_minutes": total_duration,
            "duration_str": duration_str,
            "status": status
        })

    return render_template(
        "index.html",
        date=today_str,
        records=records,
        inside_count=inside_count,
        total=len(records),
    )

@app.route("/users")
@admin_required
def users_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, fingerprint_id, first_name, last_name, department, class, position, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return render_template("users.html", users=rows)

@app.route("/users/new", methods=["GET", "POST"])
@admin_required
def user_new():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        fingerprint_id = request.form.get("fingerprint_id", "").strip()
        department = request.form.get("department", "").strip()
        class_ = request.form.get("class", "").strip()
        position = request.form.get("position", "").strip()

        log.info(f"USER NEW Alındı: {first_name} {last_name}, fp_id={fingerprint_id}, dept={department}")

        if not first_name or not last_name:
            flash("Ad ve Soyad zorunlu.", "error")
            return redirect(url_for("user_new"))

        if not fingerprint_id:
            flash("Fingerprint ID zorunlu.", "error")
            return redirect(url_for("user_new"))

        try:
            fp_id_int = int(fingerprint_id)
        except ValueError:
            flash("Fingerprint ID sayı olmalı.", "error")
            return redirect(url_for("user_new"))

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (fingerprint_id, first_name, last_name, department, class, position) VALUES (?, ?, ?, ?, ?, ?)",
                (fp_id_int, first_name, last_name, department, class_, position)
            )
            conn.commit()
            log.info(f"USER NEW ✓ Kaydedildi: {first_name} {last_name} (FP_ID={fp_id_int})")
            flash(f"✓ {first_name} {last_name} başarıyla kaydedildi (ID: {fp_id_int})", "success")
        except sqlite3.IntegrityError as e:
            log.error(f"USER NEW DB IntegrityError: {e}")
            flash(f"✗ Fingerprint ID {fp_id_int} zaten kayıtlı!", "error")
        except Exception as e:
            log.error(f"USER NEW DB hatası: {e}")
            flash(f"✗ Veritabanı hatası: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for("users_page"))

    return render_template("user_form.html")

@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def user_edit(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST":
        # Form verilerini al
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        department = request.form.get("department", "").strip()
        class_name = request.form.get("class", "").strip()
        position = request.form.get("position", "").strip()
        
        if not first_name or not last_name:
            flash("✗ Ad ve Soyad zorunludur.", "error")
            return redirect(url_for("user_edit", user_id=user_id))
        
        try:
            cur.execute("""
                UPDATE users
                SET first_name = ?, last_name = ?, department = ?, class = ?, position = ?
                WHERE id = ?
            """, (first_name, last_name, department, class_name, position, user_id))
            conn.commit()
            
            log.info(f"USER EDIT ✓ Kullanıcı güncellendi ID={user_id}: {first_name} {last_name}")
            flash(f"✓ {first_name} {last_name} başarıyla güncellendi.", "success")
            
        except Exception as e:
            log.error(f"USER EDIT DB hatası: {e}")
            flash(f"✗ Veritabanı hatası: {e}", "error")
        finally:
            conn.close()
        
        return redirect(url_for("users_page"))
    
    # GET request - mevcut kullanıcı bilgilerini getir
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        flash("Kullanıcı bulunamadı.", "error")
        return redirect(url_for("users_page"))
    
    return render_template("user_form.html", user=user, edit_mode=True)

@app.route("/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def user_delete(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    # Kullanıcıyı ve fingerprint_id'yi al
    cur.execute("SELECT id, fingerprint_id, first_name, last_name FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash("Kullanıcı bulunamadı.", "error")
        return redirect(url_for("users_page"))
    
    fp_id = user["fingerprint_id"]
    first_name = user["first_name"]
    last_name = user["last_name"]
    
    log.info(f"DELETE USER Siliniyor: ID={user_id}, fp_id={fp_id}, {first_name} {last_name}")
    
    # Önce sensörden parmak izini sil
    if UART_AVAILABLE and sensor and sensor.is_ready():
        log.info(f"DELETE USER Sensörden parmak izi siliniyor ID={fp_id}...")
        ok, msg = sensor.delete_fingerprint(fp_id)
        if ok:
            log.info(f"DELETE USER ✓ Sensörden parmak izi silindi ID={fp_id}")
        else:
            log.error(f"DELETE USER ✗ Sensörden silinemedi ID={fp_id}: {msg}")
            flash(f"⚠ Sensörden parmak izi silinemedi: {msg}", "warning")
    else:
        log.warning("DELETE USER Sensör müsait değil, sensörden silme atlandı.")
    
    # Veritabanından kullanıcıyı sil
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    log.info(f"DELETE USER ✓ Veritabanından silindi ID={user_id}")
    
    flash(f"✓ {first_name} {last_name} ve parmak izi silindi.", "success")
    return redirect(url_for("users_page"))

# -------- API: Enroll (UI'den "Parmak oku ve ID ver") --------

@app.route("/api/scan-fingerprint", methods=["GET"])
@admin_required
def api_scan_fingerprint():
    global sensor_paused
    log.info("API /api/scan-fingerprint çağrıldı")
    
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        log.error("API HATA: Sensör müsait değil")
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500
    
    try:
        # Arka plan loop'u duraklat
        sensor_paused = True
        time.sleep(0.5)  # Loop'un kilidi bırakması için bekle
        
        new_id = get_next_fingerprint_id_from_db()
        log.info(f"API Yeni parmak izi kaydı başlatılıyor - ID={new_id}")
        
        with sensor_lock:
            ok, msg = sensor.enroll_fingerprint(new_id, timeout_per_step=20)
        
        if ok:
            log.info(f"API ✓ Parmak izi başarıyla kaydedildi - ID={new_id}")
            return jsonify({
                "status": "ok",
                "msg": f"Parmak izi başarıyla kaydedildi (ID={new_id})",
                "fingerprint_id": new_id
            })
        else:
            log.error(f"API ✗ Parmak izi kaydı başarısız - ID={new_id}: {msg}")
            return jsonify({"status": "error", "msg": msg or "Parmak izi kaydedilemedi - Tekrar deneyin"}), 400
    except Exception as e:
        log.error(f"API Exception in scan-fingerprint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "msg": str(e)}), 500
    finally:
        # Her durumda arka plan loop'u devam ettir
        sensor_paused = False

# -------- API: Match + Attendance (Ana sayfa butonu) --------

@app.route("/api/match-fingerprint", methods=["GET"])
# @user_required  # Panel UI için session kontrolü kaldırıldı
def api_match_fingerprint():
    global last_display_event
    log.info("API /api/match-fingerprint çağrıldı")
    
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        log.error("API HATA: Sensör müsait değil")
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500

    try:
        log.debug("API Calling sensor.match_fingerprint()...")

        with sensor_lock:
            fp_id, err = sensor.match_fingerprint(timeout=15, comparison_level=6, silent=False)
        
        if fp_id is None:
            err_msg = err or "Parmak izi eşleşmesi bulunamadı"
            if err:  # Sadece gerçek hata varsa logla
                log.warning(f"API Eşleşme başarısız: {err}")
                last_display_event = {
                    "event": "error",
                    "timestamp": datetime.now().isoformat(),
                    "user": None,
                    "total_duration_minutes": 0,
                    "msg": err,
                }
            return jsonify({"status": "error", "msg": err_msg}), 400

        log.info(f"API ✓ Eşleşme başarılı: fingerprint_id={fp_id}")
        
        result, logic_err = process_attendance_event(fp_id)
        
        if logic_err:
            log.error(f"API ✗ Yoklama işleme hatası: {logic_err}")
            last_display_event = {
                "event": "error",
                "timestamp": datetime.now().isoformat(),
                "user": None,
                "total_duration_minutes": 0,
                "msg": logic_err,
            }
            return jsonify({"status": "error", "msg": logic_err}), 400

        user_info = result['user']
        user_name = f"{user_info['first_name']} {user_info['last_name']}"
        event_text = "Giriş" if result['event'] == 'check_in' else "Çıkış"
        
        log.info(f"API ✓ Yoklama kaydedildi: {event_text} - {user_name}")
        
        # API Response düzenle: panel_ui.py'nin beklediği format
        response_data = {
            "status": "ok",
            "event": result["event"],
            "timestamp": result["timestamp"],
            "user": {
                "id": user_info["id"],
                "first_name": user_info["first_name"],
                "last_name": user_info["last_name"]
            },
            "fingerprint_id": fp_id
        }
        
        # Çıkış ise toplam saati de ekle
        if result["event"] == "check_out" and "total_duration_minutes" in result:
            response_data["total_duration_minutes"] = result["total_duration_minutes"]
        
        return jsonify(response_data)
    except Exception as e:
        log.error(f"API Exception in match-fingerprint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "msg": str(e)}), 500


# -------- API: Panel pasif bildirim --------

@app.route("/api/last-event", methods=["GET"])
def api_last_event():
    """Panel LCD pasif dinleme için son yoklama olayını döner ve sıfırlar."""
    global last_display_event

    event_type = last_display_event.get("event")
    if not event_type:
        # Boş response'ları loglama
        return jsonify({"status": "empty"})

    response_data = {
        "status": "ok",
        "event": event_type,
        "timestamp": last_display_event.get("timestamp"),
        "user": last_display_event.get("user"),
        "total_duration_minutes": last_display_event.get("total_duration_minutes", 0),
        "msg": last_display_event.get("msg"),
    }

    # Sadece event varsa logla (log.info ile - debug değil)
    user_info = response_data.get('user')
    if user_info:
        user_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
        log.info(f"API /api/last-event -> {event_type} | {user_name}")
    else:
        log.info(f"API /api/last-event -> {event_type}")

    # Bir kez okunduktan sonra sıfırla ki aynı event tekrar gösterilmesin
    last_display_event = {
        "event": None,
        "timestamp": None,
        "user": None,
        "total_duration_minutes": 0,
        "msg": None,
    }

    return jsonify(response_data)

# =====================================================

if __name__ == "__main__":
    init_db_if_needed()
    if UART_AVAILABLE and sensor:
        sensor_thread = threading.Thread(target=sensor_background_loop, daemon=True)
        sensor_thread.start()
        log.info("MAIN Arka plan parmak okuma başlatıldı")
    # Flask sunucusunu başlat
    app.run(host="0.0.0.0", port=5000)
