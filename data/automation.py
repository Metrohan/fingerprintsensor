import sqlite3
import pandas as pd
import gspread
from time import sleep
from datetime import datetime, timedelta
import os

# --- Yapılandırma ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(SCRIPT_DIR, 'attendance.db')
SHEET_TITLE = 'Laboratuvar Giriş Çıkış Takibi'
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'service_account.json')
UPDATE_INTERVAL_SECONDS = 10  # Google Sheets güncelleme aralığı
MAX_WEEKS_TO_KEEP = 3  # En fazla 3 hafta tutulacak

def get_current_work_day():
    """
    24 saat sabah 6'dan sabah 6'ya (06:00-05:59).
    Sabah 6'dan önce: dünün devamı
    """
    now = datetime.now()
    if now.hour < 6:
        return (now - timedelta(days=1)).date()
    return now.date()

def get_week_start_end(date):
    """Pazartesi-Pazar haftasının başlangıç ve bitiş tarihlerini döndürür."""
    # ISO takviminde haftanın hangi günü olduğunu bul (1=Pazartesi, 7=Pazar)
    weekday = date.isoweekday()
    # Pazartesi'yi bul (mevcut günden weekday-1 gün geriye git)
    week_start = date - timedelta(days=weekday - 1)
    # Pazar'ı bul (pazartesinden 6 gün ileri)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end

def get_week_name(date):
    """Hafta adını döndürür. Örn: '2025-W50'"""
    iso_calendar = date.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"

def auto_checkout_forgotten_users():
    """
    Çıkış yapmayı unutanları otomatik çıkış yapar.
    SADECE check_in var ama check_out NULL olan ve bir önceki günün kayıtları için 
    çıkış saatini 05:59 yapar.
    """
    try:
        current_work_day = get_current_work_day()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Bir önceki çalışma gününden bugüne kadar check_out NULL olanları bul
        # (check_in var, yani giriş yapmış ama çıkış yapmamış)
        c.execute("""
            SELECT id, check_in, date
            FROM attendance
            WHERE check_out IS NULL 
              AND check_in IS NOT NULL
              AND DATE(check_in) < ?
        """, (str(current_work_day),))
        
        forgotten_sessions = c.fetchall()
        
        for session_id, check_in, session_date in forgotten_sessions:
            # check_in tarihinin bir sonraki günü saat 05:59'u hesapla
            check_in_dt = datetime.fromisoformat(check_in)
            checkout_time = check_in_dt.replace(hour=5, minute=59, second=0) + timedelta(days=1)
            
            # Süreyi hesapla - İŞ KURALI: Unutulan çıkışlar (05:59) için süre 0 sayılacak
            duration_minutes = 0
            
            # Güncelle
            c.execute("""
                UPDATE attendance
                SET check_out = ?, duration_minutes = ?
                WHERE id = ?
            """, (checkout_time.isoformat(), duration_minutes, session_id))
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Otomatik çıkış: Session ID {session_id} -> {checkout_time.strftime('%H:%M')}")
        
        conn.commit()
        conn.close()
        
        return len(forgotten_sessions)
    except Exception as e:
        print(f"Otomatik çıkış hatası: {e}")
        return 0

def get_week_data(week_start, week_end):
    """Belirli hafta için günlük bazda veritabanından veri çeker - her kullanıcı günde tek satır."""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Her kullanıcı için günlük: ilk giriş, son çıkış, toplam süre
        query = f"""
            SELECT
                T.date AS 'Tarih',
                U.first_name AS 'Ad',
                U.last_name AS 'Soyad',
                U.department AS 'Departman',
                MIN(T.check_in) AS 'İlk Giriş',
                (SELECT check_out FROM attendance WHERE user_id = U.id 
                 AND date = T.date
                 AND check_out IS NOT NULL
                 ORDER BY check_out DESC LIMIT 1) AS 'Son Çıkış',
                SUM(T.duration_minutes) AS 'Toplam Dakika',
                CASE 
                    WHEN (SELECT COUNT(*) FROM attendance WHERE user_id = U.id 
                         AND date = T.date
                         AND check_out IS NULL) > 0
                    THEN 'İçeride'
                    ELSE 'Dışarıda'
                END AS 'Durum'
            FROM
                attendance AS T
            JOIN
                users AS U ON T.user_id = U.id
            WHERE
                T.date >= '{week_start}' AND T.date <= '{week_end}'
            GROUP BY
                T.date, U.id, U.first_name, U.last_name, U.department
            ORDER BY
                T.date, MIN(T.check_in);
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Veritabanı hatası: {e}")
        return pd.DataFrame()

def format_duration(minutes):
    """Dakikayı 'Xs Yd' formatına çevirir."""
    if not minutes or minutes == 0:
        return "0s 0d"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}s {mins}d"

def update_google_sheet(gc, week_name, df, log_update=True):
    """Belirli hafta için Google Sheet'i günceller - her gün araya boşluk bırakarak."""
    try:
        spreadsheet = gc.open(SHEET_TITLE)
        
        # Worksheet'i bul veya oluştur
        try:
            sheet = spreadsheet.worksheet(week_name)
        except gspread.exceptions.WorksheetNotFound:
            # Yeni sheet oluştur
            sheet = spreadsheet.add_worksheet(title=week_name, rows=200, cols=7)
            print(f"Yeni hafta sheet'i oluşturuldu: {week_name}")
        
        headers = ['Ad', 'Soyad', 'Departman', 'İlk Giriş', 'Son Çıkış', 'Toplam Süre', 'Durum']
        
        if len(df) == 0:
            sheet.clear()
            sheet.update([headers], 'A1')
            return
        
        # Her gün için ayrı bölüm oluştur
        all_rows = [headers]
        red_rows = []  # Kırmızı boyanacak satır numaraları
        current_date = None
        
        for idx, row in df.iterrows():
            tarih = row.get('Tarih', '')
            
            # Yeni gün başladığında boş satır ekle ve tarih başlığı ekle
            if tarih != current_date:
                if current_date is not None:
                    # Önceki günden sonra boş satır
                    all_rows.append(['', '', '', '', '', '', ''])
                
                # Tarih başlığı
                tarih_obj = datetime.strptime(tarih, '%Y-%m-%d').date()
                tarih_str = tarih_obj.strftime('%d.%m.%Y %A')
                
                # Türkçe gün isimleri
                gun_isimleri = {
                    'Monday': 'Pazartesi',
                    'Tuesday': 'Salı',
                    'Wednesday': 'Çarşamba',
                    'Thursday': 'Perşembe',
                    'Friday': 'Cuma',
                    'Saturday': 'Cumartesi',
                    'Sunday': 'Pazar'
                }
                for eng, tr in gun_isimleri.items():
                    tarih_str = tarih_str.replace(eng, tr)
                
                all_rows.append([f'📅 {tarih_str}', '', '', '', '', '', ''])
                current_date = tarih
            
            ad = row.get('Ad', '')
            soyad = row.get('Soyad', '')
            department = row.get('Departman', '')
            ilk_giris = row.get('İlk Giriş', '')
            son_cikis = row.get('Son Çıkış', '') if row.get('Son Çıkış') else ''
            toplam_dakika = row.get('Toplam Dakika', 0) or 0
            durum = row.get('Durum', 'Bilinmiyor')
            
            # Otomatik çıkış kontrolü (son çıkış 05:59 ise VE İçeride ise)
            # Bu durumda kırmızı boya ve durumu Dışarıda yap
            is_auto_checkout = False
            if son_cikis and durum == 'İçeride':
                try:
                    son_cikis_dt = datetime.fromisoformat(son_cikis)
                    if son_cikis_dt.hour == 5 and son_cikis_dt.minute == 59:
                        is_auto_checkout = True
                        durum = 'Dışarıda'  # Durumu güncelle
                        red_rows.append(len(all_rows) + 1)  # +1 çünkü 1-indexed
                except:
                    pass
            
            # Süreyi formatla
            toplam_sure_str = format_duration(toplam_dakika)
            
            # Tarihleri formatla (sadece saat)
            try:
                if ilk_giris:
                    ilk_giris = datetime.fromisoformat(ilk_giris).strftime('%H:%M')
            except:
                pass
            
            try:
                if son_cikis:
                    son_cikis = datetime.fromisoformat(son_cikis).strftime('%H:%M')
            except:
                pass
            
            all_rows.append([ad, soyad, department, ilk_giris, son_cikis, toplam_sure_str, durum])
        
        # Sheet'i güncelle
        sheet.clear()
        sheet.update(all_rows, 'A1')
        
        # Başlık satırını formatla
        sheet.format('A1:G1', {
            'backgroundColor': {'red': 0.2, 'green': 0.5, 'blue': 0.8},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}},
            'horizontalAlignment': 'CENTER'
        })
        
        # Kırmızı satırları boya (otomatik çıkış)
        if red_rows:
            for row_num in red_rows:
                sheet.format(f'A{row_num}:G{row_num}', {
                    'backgroundColor': {'red': 1.0, 'green': 0.8, 'blue': 0.8},
                    'textFormat': {'bold': True}
                })
        
        if log_update:
            unique_dates = df['Tarih'].nunique() if 'Tarih' in df.columns else 0
            total_records = len(df)
            auto_checkout_count = len(red_rows)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ {week_name} güncellendi: {total_records} kayıt, {unique_dates} gün{f' ({auto_checkout_count} otomatik çıkış)' if auto_checkout_count > 0 else ''}")
        
    except Exception as e:
        print(f"Google Sheets hatası ({week_name}): {e}")
        print(f"Google Sheets hatası ({week_name}): {e}")

def cleanup_old_weeks(gc):
    """3 haftadan eski sheet'leri siler."""
    try:
        spreadsheet = gc.open(SHEET_TITLE)
        current_work_day = get_current_work_day()
        
        # Şu anki haftadan 3 hafta öncesinin başlangıcı
        cutoff_date = current_work_day - timedelta(weeks=MAX_WEEKS_TO_KEEP)
        
        all_sheets = spreadsheet.worksheets()
        for sheet in all_sheets:
            sheet_name = sheet.title
            
            # Hafta formatında mı kontrol et (YYYY-Www)
            if sheet_name.count('-W') == 1:
                try:
                    # Hafta isminden tarihi çıkar
                    parts = sheet_name.split('-W')
                    year = int(parts[0])
                    week = int(parts[1])
                    
                    # O haftanın pazartesini bul
                    week_monday = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%W-%w').date()
                    
                    # Cutoff'tan eski mi?
                    if week_monday < cutoff_date:
                        spreadsheet.del_worksheet(sheet)
                        print(f"Eski hafta silindi: {sheet_name}")
                except:
                    pass
        
    except Exception as e:
        print(f"Cleanup hatası: {e}")

def main_automation_loop():
    """7/24 çalışan ana döngü."""
    print("=" * 60)
    print("Lab Giriş Çıkış Otomasyonu - Haftalık Takip Sistemi")
    print("=" * 60)
    print(f"Güncelleme: {UPDATE_INTERVAL_SECONDS} saniye")
    print(f"24 saat döngüsü: 06:00-05:59")
    print(f"Hafta formatı: Pazartesi-Pazar")
    print(f"Maksimum hafta: {MAX_WEEKS_TO_KEEP} (eski haftalar otomatik silinir)")
    print(f"DB: {DB_PATH}")
    print(f"Credentials: {CREDENTIALS_FILE}")
    print("=" * 60)
    print("")
    
    last_cleanup_day = None
    last_record_count = {}
    update_counter = 0
    
    while True:
        try:
            # Otomatik çıkış kontrolü (her döngüde)
            auto_checkout_forgotten_users()
            
            # Google Sheets bağlantısı
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
            
            # Şu anki çalışma günü ve haftası
            work_day = get_current_work_day()
            week_start, week_end = get_week_start_end(work_day)
            week_name = get_week_name(work_day)
            
            # Haftalık veriyi çek
            week_df = get_week_data(week_start, week_end)
            
            # Sheet'i güncelle
            current_count = len(week_df)
            prev_count = last_record_count.get(week_name, -1)
            
            # Sadece kayıt sayısı değiştiğinde veya her 10 güncellemede bir log yaz
            update_counter += 1
            should_log = (current_count != prev_count) or (update_counter % 10 == 0)
            
            update_google_sheet(gc, week_name, week_df, log_update=should_log)
            last_record_count[week_name] = current_count
            
            # Günde 1 kez eski haftaları temizle (sabah 6'da)
            if last_cleanup_day != work_day:
                cleanup_old_weeks(gc)
                last_cleanup_day = work_day
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Hata: {e}")
        
        sleep(UPDATE_INTERVAL_SECONDS)

if __name__ == "__main__":

    main_automation_loop()
