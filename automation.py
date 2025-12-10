import sqlite3
import pandas as pd
import gspread
import os
from time import sleep
from datetime import datetime
from logger import setup_logger

# Logger oluştur
log = setup_logger("automation")

# Proje kök dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- YAPILANDIRMA AYARLARI ---
DB_PATH = os.path.join(BASE_DIR, "data", "attendance.db")
SHEET_TITLE = 'Laboratuvar Giriş Çıkış Takibi'
WORKSHEET_NAME = 'Aktif Girişler'
CREDENTIALS_FILE = os.path.join(BASE_DIR, "data", "service_account.json")
UPDATE_INTERVAL_SECONDS = 30

# --- SQL SORGUSU: O anda içeride olanları bulur ---
SQL_QUERY = """
    SELECT
        U.first_name,
        U.last_name,
        U.department,
        T.check_in,
        T.check_out
    FROM
        attendance AS T
    JOIN
        users AS U ON T.user_id = U.id
    WHERE
        T.check_out IS NULL
    ORDER BY
        T.check_in;
"""

def get_active_users():
    """SQLite'dan aktif kullanıcı verisini çeker."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(SQL_QUERY, conn) 
        conn.close()
        return df
    except Exception as e:
        log.error(f"Veritabanı okuma hatası: {e}")
        return pd.DataFrame()

def update_google_sheet(df):
    """DataFrame'i Google Sheet'e yazar ve Sheets'i temizler."""
    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sheet = gc.open(SHEET_TITLE).worksheet(WORKSHEET_NAME)
        
        headers = ['Ad', 'Soyad', 'Departman', 'Giriş Saati (UTC)', 'Çıkış Saati (UTC)']
        data_to_upload = df.values.tolist()
        
        sheet.clear()
        sheet.update([headers] + data_to_upload, 'A1')
        
        log.info(f"Sheets güncellendi. İçerideki kişi sayısı: {len(df)}")
        
    except gspread.exceptions.WorksheetNotFound:
        log.error("Sheets HATA: Çalışma Sayfası bulunamadı")
    except Exception as e:
        log.error(f"Sheets API hatası: {e}")

def main_automation_loop():
    """7/24 çalışacak ana döngü."""
    log.info("=== Lab Otomasyonu Başlatıldı ===")
    log.info(f"Güncelleme aralığı: {UPDATE_INTERVAL_SECONDS} saniye")
    
    update_google_sheet(pd.DataFrame(columns=['first_name', 'last_name', 'department', 'check_in', 'check_out']))
    
    last_update_had_users = False

    while True:
        active_users_df = get_active_users()
        current_user_count = len(active_users_df)
        
        if current_user_count > 0:
            update_google_sheet(active_users_df)
            last_update_had_users = True
        
        elif current_user_count == 0 and last_update_had_users:
            log.info("Lab boşaldı. Sheets temizleniyor.")
            update_google_sheet(active_users_df)
            last_update_had_users = False
        
        else:
            log.debug("Labda kimse yok, güncelleme atlandı.")

        sleep(UPDATE_INTERVAL_SECONDS)

if __name__ == "__main__":
    main_automation_loop()