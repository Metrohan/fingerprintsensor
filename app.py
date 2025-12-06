# app.py
# Raspberry Pi 3 + Waveshare UART Fingerprint Reader
# Yoklama sistemi (SQLite + Flask + Web UI)

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import sqlite3
from datetime import datetime, date
import os
import time
import sys
from functools import wraps

DB_PATH = "attendance.db"

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

# =====================================================
#       Kullanıcı Kimlik Bilgileri (Hardcoded)
# =====================================================
# Gerçek uygulamada veritabanında tutulmalı
USERS = {
    "ilab": {"password": "pievision", "role": "user"},  # user: yoklama giriş/çıkış
    "admin": {"password": "ayTacdurmaz", "role": "admin"}  # admin: kullanıcı yönetimi
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
        self.connect()

    def connect(self):
        """Open serial port."""
        if not UART_AVAILABLE:
            print("[UART] serial modülü yok, demo mod.")
            return
        try:
            self.ser = serial.Serial(self.port_name, self.baud, timeout=1)
            time.sleep(0.5)
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass
            print(f"[UART] Port açıldı: {self.port_name} @ {self.baud}")
        except Exception as e:
            print(f"[UART] Port açılamadı: {e}")
            self.ser = None

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
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass
            time.sleep(0.05)
            self.ser.write(pkt)
            print(f"[TX] {' '.join(f'{b:02X}' for b in pkt)}")
            sys.stdout.flush()
            return True
        except Exception as e:
            print(f"[TX ERROR] {e}")
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
                    print(f"[RX BUFFER] {len(data)} byte geldi, toplam {len(buf)}")
                    sys.stdout.flush()

                    while len(buf) >= 8:
                        if buf[0] == 0xF5 and buf[7] == 0xF5:
                            pkt = bytes(buf[:8])
                            chk_expect = self.calc_checksum(pkt[1], pkt[2], pkt[3], pkt[4], pkt[5])
                            if pkt[6] != chk_expect:
                                print(f"[RX] Bad checksum: got 0x{pkt[6]:02X}, expected 0x{chk_expect:02X}")
                                buf.pop(0)
                                continue

                            if expected_cmd is not None and pkt[1] != expected_cmd:
                                print(f"[RX] Cmd mismatch: expected 0x{expected_cmd:02X}, got 0x{pkt[1]:02X}, skip")
                                buf = buf[8:]
                                continue

                            print(f"[RX] {' '.join(f'{b:02X}' for b in pkt)}")
                            sys.stdout.flush()
                            return pkt
                        else:
                            buf.pop(0)

                time.sleep(0.05)
            except Exception as e:
                print(f"[RX ERROR] {e}")
                break

        print(f"[RX] Timeout, buffer len={len(buf)}")
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

                print(f"[ENROLL] {step_name} send: {' '.join(f'{b:02X}' for b in pkt)}")
                sys.stdout.flush()
                self.ser.write(pkt)

                start = time.time()
                while time.time() - start < timeout_per_step:
                    resp = self.read_packet(timeout=0.5, expected_cmd=cmd)
                    if not resp:
                        continue
                    print(f"[ENROLL] {step_name} resp: {' '.join(f'{b:02X}' for b in resp)}")
                    sys.stdout.flush()
                    ack = self.get_ack(resp)
                    ack_msg = self.get_error_message(ack) if ack is not None else "Yanıt yok"
                    ack_hex = f"0x{ack:02X}" if ack is not None else "0xFF"
                    print(f"[ENROLL] {step_name} ACK={ack_hex} - {ack_msg}")
                    sys.stdout.flush()

                    if ack == ACK_SUCCESS:
                        print(f"[ENROLL] ✓ {step_name} başarılı")
                        return True, None
                    if ack == ACK_USER_EXIST or ack == ACK_FIN_EXIST:
                        print(f"[ENROLL] {step_name}: Parmak izi zaten kayıtlı (başarılı sayılıyor)")
                        return True, None
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

        print(f"[ENROLL] Starting enrollment for ID={fp_id}")
        print("[ENROLL] STEP1: place finger and keep it still...")
        ok, msg = send_enroll_step(0x01, "STEP1 (CMD=0x01)")
        if not ok:
            return False, msg

        print("[ENROLL] Remove finger, then place it again (STEP2)...")
        time.sleep(1.0)
        ok, msg = send_enroll_step(0x02, "STEP2 (CMD=0x02)")
        if not ok:
            return False, msg

        print("[ENROLL] Remove finger, then place it a third time (STEP3)...")
        time.sleep(1.0)
        ok, msg = send_enroll_step(0x03, "STEP3 (CMD=0x03)")
        if not ok:
            return False, msg

        print("[ENROLL] Enrollment completed successfully.")
        return True, None

    # ------------- MATCH (1:N) 0x0C – ÖNEMLİ KISIM --------------

    def match_fingerprint(self, timeout=15, comparison_level=6):
        """
        1:N karşılaştırma (CMD=0x0C).
        Manual 2.8'e göre:
        Response: F5 0C UserID_HI UserID_LO user_privilege / ACK_NOUSER / ACK_TIMEOUT 00 CHK F5

        Q3 (resp[4]):
            - 0x05 (ACK_NOUSER)   -> kullanıcı yok
            - 0x08 (ACK_TIMEOUT)  -> okuma/timeout
            - 0x01 / 0x02 / 0x03  -> privilege (1,2,3) -> BAŞARILI MATCH
        """
        if not self.ser:
            return None, "Serial not open"

        if comparison_level < 1 or comparison_level > 9:
            comparison_level = 6

        print("[MATCH] Place finger FIRMLY on sensor...")
        sys.stdout.flush()

        # CMD=0x0C, P1=0x00, P2=comparison_level
        sent = self.send_packet(0x0C, 0x00, comparison_level, 0x00, 0x00)
        if not sent:
            return None, "Failed to send MATCH command"

        resp = self.read_packet(timeout=timeout, expected_cmd=0x0C)
        if not resp:
            return None, "No response from sensor"

        print(f"[MATCH] resp: {' '.join(f'{b:02X}' for b in resp)}")
        sys.stdout.flush()

        if len(resp) < 5:
            return None, "Invalid response length"

        user_hi = resp[2]
        user_lo = resp[3]
        q3 = resp[4]  # burada ya privilege(1/2/3) ya da ACK_NOUSER/ACK_TIMEOUT

        # Önce gerçek hata kodlarını kontrol et
        if q3 == ACK_NOUSER:
            print(f"[MATCH] ACK=0x{q3:02X} (ACK_NOUSER) - Bu parmak izi sensörde kayıtlı değil")
            return None, "Parmak izi sistemde kayıtlı değil"
        if q3 == ACK_TIMEOUT:
            print(f"[MATCH] ACK=0x{q3:02X} (ACK_TIMEOUT) - Parmak izi algılanamadı")
            return None, "Zaman aşımı - Parmağınızı sensöre düzgün yerleştirin"

        # Kalan durumlar (1,2,3) -> privilege -> başarılı eşleşme
        user_id = (user_hi << 8) | user_lo
        print(f"[MATCH] ✓ Eşleşme başarılı! Fingerprint ID={user_id}, Privilege={q3}")
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

        print(f"[DELETE] Deleting fingerprint ID={fp_id}")
        sys.stdout.flush()

        sent = self.send_packet(0x04, user_hi, user_lo, 0x00, 0x00)
        if not sent:
            return False, "Failed to send DELETE command"

        resp = self.read_packet(timeout=5.0, expected_cmd=0x04)
        if not resp:
            return False, "No response from sensor"

        print(f"[DELETE] resp: {' '.join(f'{b:02X}' for b in resp)}")
        sys.stdout.flush()

        ack = self.get_ack(resp)
        ack_msg = self.get_error_message(ack)
        ack_hex = f"0x{ack:02X}" if ack is not None else "0xFF"
        print(f"[DELETE] ACK={ack_hex} - {ack_msg}")
        
        if ack == ACK_SUCCESS:
            print(f"[DELETE] ✓ Parmak izi ID={fp_id} başarıyla silindi")
            return True, None
        elif ack == ACK_NOUSER:
            print(f"[DELETE] ID={fp_id} sensörde bulunamadı (zaten silinmiş veya hiç kaydedilmemiş)")
            return True, None  # Zaten yoksa da başarılı sayalım
        else:
            print(f"[DELETE] ✗ ID={fp_id} silinemedi: {ack_msg}")
            return False, ack_msg


# Global sensor instance
sensor = FingerprintSensor() if UART_AVAILABLE else None

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
            print("[DB] init_db.py çalıştırıldı / tablo oluşturuldu.")
        except Exception as e:
            print(f"[DB] init_db import error: {e}")

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
      - Eğer bugüne ait açık kayıt yoksa -> check_in
      - Eğer açık kayıt varsa -> check_out
    """
    now = datetime.now()
    today_str = date.today().isoformat()

    conn = get_db()
    cur = conn.cursor()

    # Kullanıcıyı bul
    cur.execute("SELECT id, first_name, last_name FROM users WHERE fingerprint_id = ?", (fp_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return None, f"Fingerprint ID {fp_id} için kullanıcı bulunamadı."

    user_id = user["id"]

    # Açık kayıt var mı?
    cur.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND date = ? AND check_in IS NOT NULL AND check_out IS NULL
    """, (user_id, today_str))
    open_rec = cur.fetchone()

    if open_rec is None:
        # GİRİŞ
        cur.execute("""
            INSERT INTO attendance (user_id, date, check_in)
            VALUES (?, ?, ?)
        """, (user_id, today_str, now.isoformat()))
        conn.commit()
        conn.close()
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
        # ÇIKIŞ
        cur.execute("""
            UPDATE attendance
            SET check_out = ?
            WHERE id = ?
        """, (now.isoformat(), open_rec["id"]))
        conn.commit()
        conn.close()
        return {
            "event": "check_out",
            "timestamp": now.isoformat(),
            "user": {
                "id": user_id,
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
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
    print(f"[AUTH] ✓ ilab auto-logged in")
    sys.stdout.flush()
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
        print(f"[AUTH] Admin login failed: user '{username}' not found")
        sys.stdout.flush()
        return redirect(url_for("admin_login_page"))
    
    user_data = USERS[username]
    if user_data["password"] != password:
        flash("Kullanıcı adı veya şifre hatalı.", "error")
        print(f"[AUTH] Admin login failed: wrong password for user '{username}'")
        sys.stdout.flush()
        return redirect(url_for("admin_login_page"))
    
    # Sadece admin kullanıcısı erişsin
    if user_data["role"] != "admin":
        flash("Bu sayfaya sadece admin erişim sağlayabilir.", "error")
        print(f"[AUTH] Non-admin user '{username}' tried to access admin login")
        sys.stdout.flush()
        return redirect(url_for("admin_login_page"))
    
    # Admin login başarılı - session'a kaydet
    session['user'] = username
    session['role'] = user_data['role']
    print(f"[AUTH] ✓ Admin '{username}' logged in")
    sys.stdout.flush()
    flash(f"✓ Hoşgeldiniz {username}!", "success")
    return redirect(url_for("dashboard_today"))

@app.route("/logout", methods=["GET", "POST"])
def logout_page():
    username = session.get('user', 'unknown')
    role = session.get('role', 'unknown')
    session.clear()
    print(f"[AUTH] User '{username}' (role: {role}) logged out")
    sys.stdout.flush()
    
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
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.first_name, u.last_name, a.check_in, a.check_out
        FROM attendance a
        JOIN users u ON u.id = a.user_id
        WHERE a.date = ?
        ORDER BY a.check_in
    """, (today_str,))
    rows = cur.fetchall()
    conn.close()

    records = []
    inside_count = 0
    for r in rows:
        status = "Girdi"
        if r["check_out"]:
            status = "Çıktı"
        else:
            inside_count += 1

        # Timestamp formatını düzelt: YYYY-MM-DDTHH:MM:SS -> DD.MM.YYYY HH:MM
        check_in_formatted = None
        check_out_formatted = None
        
        if r["check_in"]:
            dt = datetime.fromisoformat(r["check_in"])
            check_in_formatted = dt.strftime("%d.%m.%Y %H:%M")
        
        if r["check_out"]:
            dt = datetime.fromisoformat(r["check_out"])
            check_out_formatted = dt.strftime("%d.%m.%Y %H:%M")

        records.append({
            "first_name": r["first_name"],
            "last_name": r["last_name"],
                "check_in": check_in_formatted,
            "check_out": check_out_formatted,
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

        print(f"[USER NEW] Received: first_name={first_name}, last_name={last_name}, fp_id={fingerprint_id}, dept={department}, class={class_}, pos={position}")
        sys.stdout.flush()

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
            print(f"[USER NEW] User saved to DB: {first_name} {last_name} (FP_ID={fp_id_int})")
            sys.stdout.flush()
            flash(f"✓ {first_name} {last_name} başarıyla kaydedildi (ID: {fp_id_int})", "success")
        except sqlite3.IntegrityError as e:
            print(f"[USER NEW] DB IntegrityError: {e}")
            sys.stdout.flush()
            flash(f"✗ Fingerprint ID {fp_id_int} zaten kayıtlı!", "error")
        except Exception as e:
            print(f"[USER NEW] Unexpected DB error: {e}")
            sys.stdout.flush()
            flash(f"✗ Veritabanı hatası: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for("users_page"))

    return render_template("user_form.html")

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
    
    print(f"[DELETE USER] Deleting user ID={user_id}, fingerprint_id={fp_id}, name={first_name} {last_name}")
    sys.stdout.flush()
    
    # Önce sensörden parmak izini sil
    if UART_AVAILABLE and sensor and sensor.is_ready():
        print(f"[DELETE USER] Deleting fingerprint ID={fp_id} from sensor...")
        sys.stdout.flush()
        ok, msg = sensor.delete_fingerprint(fp_id)
        if ok:
            print(f"[DELETE USER] Fingerprint ID={fp_id} deleted from sensor successfully.")
        else:
            print(f"[DELETE USER] Failed to delete fingerprint ID={fp_id} from sensor: {msg}")
            flash(f"⚠ Sensörden parmak izi silinemedi: {msg}", "warning")
    else:
        print("[DELETE USER] Sensor not available, skipping fingerprint deletion from sensor.")
    
    # Veritabanından kullanıcıyı sil
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    print(f"[DELETE USER] User ID={user_id} deleted from database.")
    sys.stdout.flush()
    
    flash(f"✓ {first_name} {last_name} ve parmak izi silindi.", "success")
    return redirect(url_for("users_page"))

# -------- API: Enroll (UI'den "Parmak oku ve ID ver") --------

@app.route("/api/scan-fingerprint", methods=["GET"])
@admin_required
def api_scan_fingerprint():
    print("[API] /api/scan-fingerprint called")
    sys.stdout.flush()
    
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        print("[API] ERROR: Sensor not available or not ready")
        sys.stdout.flush()
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500
    
    try:
        new_id = get_next_fingerprint_id_from_db()
        print(f"[API] Yeni parmak izi kaydı başlatılıyor - ID={new_id}")
        sys.stdout.flush()
        
        ok, msg = sensor.enroll_fingerprint(new_id, timeout_per_step=20)
        
        if ok:
            print(f"[API] ✓ Parmak izi başarıyla kaydedildi - ID={new_id}")
            sys.stdout.flush()
            return jsonify({
                "status": "ok",
                "msg": f"Parmak izi başarıyla kaydedildi (ID={new_id})",
                "fingerprint_id": new_id
            })
        else:
            print(f"[API] ✗ Parmak izi kaydı başarısız - ID={new_id}: {msg}")
            sys.stdout.flush()
            return jsonify({"status": "error", "msg": msg or "Parmak izi kaydedilemedi - Tekrar deneyin"}), 400
    except Exception as e:
        print(f"[API] Exception in scan-fingerprint: {e}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "msg": str(e)}), 500

# -------- API: Match + Attendance (Ana sayfa butonu) --------

@app.route("/api/match-fingerprint", methods=["GET"])
@user_required
def api_match_fingerprint():
    print("[API] /api/match-fingerprint called")
    sys.stdout.flush()
    
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        print("[API] ERROR: Sensor not available or not ready")
        sys.stdout.flush()
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500

    try:
        print("[API] Calling sensor.match_fingerprint()...")
        sys.stdout.flush()
        
        fp_id, err = sensor.match_fingerprint(timeout=15, comparison_level=6)
        
        if fp_id is None:
            print(f"[API] ✗ Eşleşme başarısız: {err}")
            sys.stdout.flush()
            return jsonify({"status": "error", "msg": err or "Parmak izi eşleşmesi bulunamadı"}), 400

        print(f"[API] ✓ Eşleşme başarılı: fingerprint_id={fp_id}, yoklama işleniyor...")
        sys.stdout.flush()
        
        result, logic_err = process_attendance_event(fp_id)
        
        if logic_err:
            print(f"[API] ✗ Yoklama işleme hatası: {logic_err}")
            sys.stdout.flush()
            return jsonify({"status": "error", "msg": logic_err}), 400

        user_info = result['user']
        user_name = f"{user_info['first_name']} {user_info['last_name']}"
        event_text = "Giriş" if result['event'] == 'check_in' else "Çıkış"
        
        print(f"[API] ✓ Yoklama kaydedildi: {event_text} - {user_name} (ID={user_info['id']})")
        sys.stdout.flush()
        
        return jsonify({
            "status": "ok",
            "event": result["event"],
            "timestamp": result["timestamp"],
            "user": user_name,
            "fingerprint_id": fp_id,
            "user_id": user_info["id"]
        })
    except Exception as e:
        print(f"[API] Exception in match-fingerprint: {e}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "msg": str(e)}), 500

# =====================================================

if __name__ == "__main__":
    init_db_if_needed()
    app.run(host="0.0.0.0", port=5000)
