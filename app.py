# app.py
# Raspberry Pi 3 + Waveshare UART Fingerprint Reader
# Yoklama sistemi (SQLite + Flask + Web UI)

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import sqlite3
from datetime import datetime, date
import os
import time
import sys

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
app.secret_key = "bir_sir_gir_buraya"

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
            return "No response"
        if ack == ACK_SUCCESS:
            return "Success"
        if ack == ACK_FAIL:
            return "Operation failed"
        if ack == ACK_FULL:
            return "Database full"
        if ack == ACK_NOUSER:
            return "User not found"
        if ack == ACK_USER_EXIST:
            return "User already exists"
        if ack == ACK_FIN_EXIST:
            return "Fingerprint already exists"
        if ack == ACK_TIMEOUT:
            return "Acquisition timeout"
        return f"Unknown ACK=0x{ack:02X}"

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
                    print(f"[ENROLL] {step_name} ACK=0x{ack:02X}" if ack is not None else "[ENROLL] No ACK")
                    sys.stdout.flush()

                    if ack == ACK_SUCCESS:
                        print(f"[ENROLL] OK {step_name}")
                        return True, None
                    if ack == ACK_USER_EXIST or ack == ACK_FIN_EXIST:
                        print(f"[ENROLL] {step_name}: Finger already enrolled (treat as success)")
                        return True, None
                    if ack == ACK_TIMEOUT:
                        return False, f"{step_name}: Timeout"
                    if ack == ACK_FULL:
                        return False, f"{step_name}: Storage full"
                    if ack == ACK_FAIL:
                        return False, f"{step_name}: Failed"

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
            print("[MATCH] NOUSER - sensörde bu parmak yok.")
            return None, "Fingerprint not found in sensor"
        if q3 == ACK_TIMEOUT:
            print("[MATCH] TIMEOUT - parmak düzgün okunamadı.")
            return None, "Timeout / no finger detected"

        # Kalan durumlar (1,2,3) -> privilege -> başarılı eşleşme
        user_id = (user_hi << 8) | user_lo
        print(f"[MATCH] Match SUCCESS. ID={user_id}, privilege={q3}")
        return user_id, None


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
#       Web Routes
# =====================================================

@app.route("/")
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
        status = "İçeride"
        if r["check_out"]:
            status = "Çıkmış"
        else:
            inside_count += 1

        records.append({
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "check_in": r["check_in"],
            "check_out": r["check_out"],
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
def users_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, fingerprint_id, first_name, last_name, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return render_template("users.html", users=rows)

@app.route("/users/new", methods=["GET", "POST"])
def user_new():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        fingerprint_id = request.form.get("fingerprint_id", "").strip()
        department = request.form.get("department", "").strip()
        class_ = request.form.get("class", "").strip()
        position = request.form.get("position", "").strip()
        try:
            cur.execute(
                "INSERT INTO users (fingerprint_id, first_name, last_name, department, class, position) VALUES (?, ?, ?, ?, ?, ?)",
                (fp_id_int, first_name, last_name, department, class_, position)
            )
            conn.commit()
            flash(f"✓ {first_name} {last_name} başarıyla kaydedildi (ID: {fp_id_int})", "success")
        except sqlite3.IntegrityError:
            flash(f"✗ Fingerprint ID {fp_id_int} zaten kayıtlı!", "error")
        finally:
            conn.close()
        return redirect(url_for("users_page"))

    return render_template("user_form.html")

@app.route("/users/delete/<int:user_id>", methods=["POST"])
def user_delete(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        flash("Kullanıcı bulunamadı.", "error")
        return redirect(url_for("users_page"))

    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash(f"✓ {user['first_name']} {user['last_name']} silindi.", "success")
    return redirect(url_for("users_page"))

# -------- API: Enroll (UI'den "Parmak oku ve ID ver") --------

@app.route("/api/scan-fingerprint", methods=["GET"])
def api_scan_fingerprint():
    print("[API] /api/scan-fingerprint called")
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500
    try:
        new_id = get_next_fingerprint_id_from_db()
        print(f"[API] Enrolling new fingerprint with ID={new_id}")
        ok, msg = sensor.enroll_fingerprint(new_id, timeout_per_step=20)
        if ok:
            return jsonify({
                "status": "ok",
                "msg": f"Fingerprint enrolled successfully (ID={new_id})",
                "fingerprint_id": new_id
            })
        else:
            return jsonify({"status": "error", "msg": msg or "Enrollment failed"}), 400
    except Exception as e:
        print(f"[API] Exception in scan-fingerprint: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# -------- API: Match + Attendance (Ana sayfa butonu) --------

@app.route("/api/match-fingerprint", methods=["GET"])
def api_match_fingerprint():
    print("[API] /api/match-fingerprint called")
    if not UART_AVAILABLE or not sensor or not sensor.is_ready():
        return jsonify({"status": "error", "msg": "Fingerprint sensor not available"}), 500

    try:
        fp_id, err = sensor.match_fingerprint(timeout=15, comparison_level=6)
        if fp_id is None:
            return jsonify({"status": "error", "msg": err or "No match found"}), 400

        result, logic_err = process_attendance_event(fp_id)
        if logic_err:
            return jsonify({"status": "error", "msg": logic_err}), 400

        return jsonify({
            "status": "ok",
            "event": result["event"],
            "timestamp": result["timestamp"],
            "user": result["user"]
        })
    except Exception as e:
        print(f"[API] Exception in match-fingerprint: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# =====================================================

if __name__ == "__main__":
    init_db_if_needed()
    app.run(host="0.0.0.0", port=5000)
