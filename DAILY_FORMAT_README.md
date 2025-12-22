# Günlük Format Değişikliği - README

## 🎯 Yapılan Değişiklikler

### 1. Günlük Bazda Görüntüleme
- **Önceki**: Haftalık özet (her kullanıcı için tek satır)
- **Yeni**: Günlük detay (her kullanıcı için günlük tek satır)
- **Önemli**: Aynı kullanıcının aynı gündeki çoklu oturumları birleştirilir
  - İlk giriş saati gösterilir
  - Son çıkış saati gösterilir
  - Toplam süre tüm oturumların toplamıdır

### 2. Gün Ayırıcıları
- Her yeni günde **boş satır** eklenir
- Tarih başlığı gösterilir: 📅 16.12.2025 Pazartesi

### 3. Otomatik Çıkış (05:59)
- Eğer kullanıcı 05:59'a kadar çıkış yapmazsa
- Otomatik olarak 05:59'da çıkış yapılır
- Bu kayıtlar **kırmızı** ile işaretlenir

### 4. Format Örneği

```
Ad      | Soyad  | Departman     | İlk Giriş | Son Çıkış | Toplam  | Durum
------------------------------------------------------------------------
📅 16.12.2025 Pazartesi
Ahmet   | Yılmaz | Mühendislik   | 08:00     | 17:00     | 8s 0d   | Dışarıda
Ayşe    | Demir  | Tasarım       | 09:00     | 18:00     | 9s 0d   | Dışarıda

📅 17.12.2025 Salı
Ahmet   | Yılmaz | Mühendislik   | 08:30     | 16:30     | 8s 0d   | Dışarıda
Mehmet  | Kaya   | Yazılım       | 10:00     | 19:00     | 9s 0d   | Dışarıda

📅 18.12.2025 Çarşamba
Ayşe    | Demir  | Tasarım       | 07:00     | 15:00     | 8s 0d   | Dışarıda
Mehmet  | Kaya   | Yazılım       | 08:00     | -         | 0s 0d   | İçeride
```

**Not**: Ahmet 16.12'de 08:00-12:00 ve 13:00-17:00 olmak üzere 2 oturum yaptıysa:
- İlk Giriş: 08:00 (ilk oturumun başlangıcı)
- Son Çıkış: 17:00 (son oturumun bitişi)
- Toplam: 8s 0d (4s + 4s = 8 saat)

## Haftalık Sheet Yönetimi

### Yeni Sheet Oluşturma
- Her hafta (Pazartesi-Pazar) için ayrı sheet
- Format: `2025-W51`, `2025-W52`, vb.
- 7. gün tamamlandığında otomatik yeni sheet açılır

### Eski Sheet Temizleme
- 3 haftadan eski sheet'ler otomatik silinir
- Her gün sabah 6'da cleanup çalışır

## Değişen Dosyalar

### `/data/automation.py`
1. **`get_week_data()`**: 
   - Günlük bazda veri çeker
   - Her kullanıcı-gün kombinasyonu ayrı satır
   - `Tarih` kolonu eklendi

2. **`update_google_sheet()`**:
   - Her gün için başlık ekler
   - Günler arası boş satır bırakır
   - Türkçe gün isimleri
   - Sadece saat gösterir (tarih değil)
   - Başlık satırı mavi arka plan

## Test Dosyası

### `/tests/test_daily_format.py`
Test senaryoları:
- ✅ Günlük kayıtlar doğru çekiliyor mu (her kullanıcı-gün tek satır)
- ✅ Kayıtlar tarih ve saate göre sıralı mı
- ✅ Aynı kullanıcının çoklu oturumları birleşiyor mu (ilk giriş + son çıkış)
- ✅ Toplam süre tüm oturumların toplamı mı
- ✅ Hafta geçişi doğru çalışıyor mu (7 gün)
- ✅ Durum hesaplaması doğru mu (İçeride/Dışarıda)

## Raspberry Pi'da Çalıştırma

### Testleri Çalıştır
```bash
cd /home/ilab/Desktop/fingerprint
python3 tests/test_daily_format.py
```

### Servisleri Yeniden Başlat
```bash
./stop_all.sh
./start_all.sh
```

### Logları İzle
```bash
tail -f data/system.log
```

## Beklenen Sonuç

Google Sheets'te:
- Her gün ayrı bölüm olarak görünecek
- Günler arası boş satırla ayrılacak
- Her gün için tarih başlığı olacak
- **Her kullanıcı günde tek satırda görünecek**
  - İlk giriş saati
  - Son çıkış saati  
  - Toplam çalışma süresi (tüm oturumların toplamı)
- 05:59'a kadar çıkış yapmayanlar otomatik çıkış yapılacak
- Otomatik çıkışlar (05:59) **kırmızı renkli** olacak
- 7. gün sonunda yeni hafta sheet'i açılacak

## Özellikler

✅ Günlük detaylı takip
✅ Her kullanıcı günde tek satır (çoklu oturumlar birleştirilir)
✅ İlk giriş + Son çıkış gösterimi
✅ Toplam süre hesaplama (tüm oturumlar)
✅ Otomatik hafta geçişi
✅ Eski veri temizleme
✅ 05:59 otomatik çıkış + kırmızı işaretleme
✅ Türkçe gün isimleri
✅ 06:00-05:59 work day mantığı
✅ 12 saat yeni oturum kuralı
