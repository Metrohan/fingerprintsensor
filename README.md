# 🖐️ Parmak İzi Yoklama Sistemi

Raspberry Pi 3 tabanlı parmak izi okuyucu ile çalışan yoklama takip sistemi.

## 📁 Proje Yapısı

```
raspberry/
├── app.py              # Flask web sunucusu (ana uygulama)
├── panel_ui.py         # LCD ekran arayüzü
├── automation.py       # Google Sheets senkronizasyonu
├── logger.py           # Merkezi loglama modülü
├── start_all.sh        # Tüm servisleri başlat
├── stop_all.sh         # Tüm servisleri durdur
│
├── drivers/            # Donanım sürücüleri
│   ├── ili9486.py      # LCD ekran sürücüsü
│   └── xpt2046.py      # Dokunmatik ekran sürücüsü
│
├── data/               # Veri dosyaları
│   ├── attendance.db   # SQLite veritabanı
│   ├── service_account.json  # Google API anahtarı
│   └── system.log      # Sistem logları
│
├── utils/              # Yardımcı araçlar
│   ├── init_db.py      # Veritabanı başlatma
│   ├── clear_sensor.py # Sensör temizleme
│   └── config.py       # Yapılandırma
│
├── tests/              # Test dosyaları
│   ├── test_lcd.py     # LCD testi
│   ├── test_sensor.py  # Sensör testi
│   └── calibrate_touch.py  # Dokunmatik kalibrasyon
│
├── assets/             # Görsel dosyalar
│   └── home_bg.png     # Ana ekran arka planı
│
├── templates/          # HTML şablonları
└── static/             # CSS/JS dosyaları
```

## 🚀 Hızlı Başlangıç

### Tüm Servisleri Başlat
```bash
./start_all.sh
```

### Servisleri Durdur
```bash
./stop_all.sh
```

### Servis Durumunu Kontrol Et
```bash
./start_all.sh status
```

## 🔧 Servisler

| Servis | Dosya | Açıklama |
|--------|-------|----------|
| Flask Web | `app.py` | Web arayüzü ve API (port 5000) |
| LCD Panel | `panel_ui.py` | Giriş/çıkış ekran gösterimi |
| Otomasyon | `automation.py` | Google Sheets senkronizasyonu |

## 📊 Log Takibi

Tüm loglar `data/system.log` dosyasına yazılır:
```bash
tail -f data/system.log
```

## 🌐 Web Arayüzü

- **Kullanıcı Girişi:** http://localhost:5000/login
- **Admin Girişi:** http://localhost:5000/admin-login

## ⚙️ Gereksinimler

```bash
pip install flask gspread pandas pillow numpy RPi.GPIO pyserial
```

## 🔌 Donanım

- Raspberry Pi 3/4
- Waveshare UART Parmak İzi Sensörü
- 3.5" ILI9486 TFT LCD Ekran

## 📝 Özellikler

- ✅ Parmak izi kaydı ve eşleştirme
- ✅ Web tabanlı kullanıcı yönetimi
- ✅ LCD ekranda giriş/çıkış bildirimi
- ✅ Google Sheets'e otomatik senkronizasyon
- ✅ Merkezi loglama sistemi
- ✅ Türkçe arayüz
