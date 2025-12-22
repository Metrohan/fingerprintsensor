import sqlite3
import pandas as pd
import gspread
from time import sleep
from datetime import datetime
import os

# --- Yapılandırma ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # data/ klasörü
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # Proje ana klasörü
DB_PATH = os.path.join(SCRIPT_DIR, 'attendance.db')  # Veritabanı data/ klasöründe
SHEET_TITLE = 'Laboratuvar Giriş Çıkış Takibi'  # Google Sheets dosyanızın adı
WORKSHEET_NAME = 'Aktif Girişler'  # Güncelleme yapılacak sayfanın adı
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'service_account.json')  # API kimlik doğrulama dosyası
UPDATE_INTERVAL_SECONDS = 10  # Güncelleme sıklığı (10 saniyede bir kontrol)

# --- SQL Sorgusu ---
# Bugünkü kullanıcı bazlı özet: İlk giriş, son çıkış, toplam süre
SQL_QUERY = """
    SELECT
        U.first_name AS 'Ad',
        U.last_name AS 'Soyad',
        U.department AS 'Departman',
        MIN(T.check_in) AS 'İlk Giriş',
        (SELECT check_out FROM attendance WHERE user_id = U.id AND DATE(check_in) = DATE('now', 'localtime') ORDER BY check_in DESC LIMIT 1) AS 'Son Çıkış',
        SUM(T.duration_minutes) AS 'Toplam Dakika',
        CASE 
            WHEN (SELECT check_out FROM attendance WHERE user_id = U.id AND DATE(check_in) = DATE('now', 'localtime') ORDER BY check_in DESC LIMIT 1) IS NULL 
            THEN 'İçeride'
            ELSE 'Dışarıda'
        END AS 'Durum'
    FROM
        attendance AS T
    JOIN
        users AS U ON T.user_id = U.id
    WHERE
        DATE(T.check_in) = DATE('now', 'localtime')
    GROUP BY
        U.id, U.first_name, U.last_name, U.department
    ORDER BY
        MIN(T.check_in);
"""

def get_active_users():
    """Veritabanından o anda içeride olan kullanıcıları çeker."""
    try:
        print(f"DEBUG: DB_PATH = {DB_PATH}")
        print(f"DEBUG: Dosya var mı? {os.path.exists(DB_PATH)}")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(SQL_QUERY, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Veritabanı okuma hatası: {e}")
        print(f"DEBUG: DB_PATH = {DB_PATH}")
        return pd.DataFrame()

def format_duration(minutes):
    """Dakikayı 'Xs Yd' formatına çevirir."""
    if not minutes or minutes == 0:
        return "0s 0d"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}s {mins}d"

def update_google_sheet(df):
    """Pandas DataFrame'i Google Sheet'e yazar - Günlük özet formatında."""
    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sheet = gc.open(SHEET_TITLE).worksheet(WORKSHEET_NAME)
        headers = ['Ad', 'Soyad', 'Şu An İçeride', 'İlk Giriş', 'Son Çıkış', 'Toplam Süre', 'Durum']

        if len(df) == 0:
            # Boş veri - sadece başlık yaz
            sheet.clear()
            sheet.update([headers], 'A1')
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bugün kayıt yok, sadece başlık yazıldı.")
            return

        # DataFrame'i işle
        rows = []
        for _, row in df.iterrows():
            ad = row.get('Ad', '')
            soyad = row.get('Soyad', '')
            department = row.get('Departman', '')
            ilk_giris = row.get('İlk Giriş', '')
            son_cikis = row.get('Son Çıkış', '') if row.get('Son Çıkış') else ''
            toplam_dakika = row.get('Toplam Dakika', 0) or 0
            durum = row.get('Durum', 'Bilinmiyor')
            
            # Süreyi formatla
            toplam_sure_str = format_duration(toplam_dakika)
            
            # Tarihleri formatla
            try:
                if ilk_giris:
                    ilk_giris_dt = datetime.fromisoformat(ilk_giris)
                    ilk_giris = ilk_giris_dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass
            
            try:
                if son_cikis:
                    son_cikis_dt = datetime.fromisoformat(son_cikis)
                    son_cikis = son_cikis_dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass
            
            rows.append([ad, soyad, department, ilk_giris, son_cikis, toplam_sure_str, durum])

        # Sheets'i güncelle
        sheet.clear()
        sheet.update([headers] + rows, 'A1')
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Google Sheet güncellendi. {len(rows)} kullanıcı.")
    except gspread.exceptions.WorksheetNotFound:
        print(f"HATA: '{WORKSHEET_NAME}' isimli sayfa bulunamadı. Lütfen kontrol edin.")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"HATA: '{SHEET_TITLE}' isimli dosya bulunamadı. Lütfen kontrol edin.")
    except Exception as e:
        print(f"Google Sheets API hatası: {e}")


def main_automation_loop():
    """7/24 sürekli çalışacak ana döngü."""
    print("Lab Giriş Çıkış Otomasyonu Başlatılıyor...")
    print(f"Kontrol Sıklığı: {UPDATE_INTERVAL_SECONDS} saniye.")
    print("FORMAT: Günlük özet - İlk giriş, son çıkış, toplam süre")
    print(f"DEBUG: Script dizini: {SCRIPT_DIR}")
    print(f"DEBUG: DB yolu: {DB_PATH}")
    print(f"DEBUG: Credentials yolu: {CREDENTIALS_FILE}")
    print(f"DEBUG: DB var mı? {os.path.exists(DB_PATH)}")
    print(f"DEBUG: Credentials var mı? {os.path.exists(CREDENTIALS_FILE)}")
    print("")

    while True:
        active_users_df = get_active_users()
        current_user_count = len(active_users_df)
        
        # Her zaman güncelle
        update_google_sheet(active_users_df)
        
        if current_user_count > 0:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sheet güncellendi ({current_user_count} kullanıcı)")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bugün henüz kayıt yok.")

        sleep(UPDATE_INTERVAL_SECONDS)

if __name__ == "__main__":
    main_automation_loop()