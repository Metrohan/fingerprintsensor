# init_db.py
import sqlite3
import os

# Proje kök dizini
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(UTILS_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "attendance.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_id INTEGER NOT NULL UNIQUE,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    department     TEXT,
    class          TEXT,
    position       TEXT,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    date               DATE NOT NULL,
    check_in           DATETIME,
    check_out          DATETIME,
    duration_minutes   INTEGER DEFAULT 0,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""")

conn.commit()
conn.close()
print("attendance.db created successfully - tables ready (no sample users)")
