# Endüstriyel Eğitim Sistemi - Modüler Mimari

## 📁 Proje Yapısı

```
deneme/
├── config.py              # Ortak ayarlar ve konfigürasyon
├── esp32_comm.py          # ESP32 serial haberleşme
├── nfc_reader.py          # NFC kart okuyucu
├── module_power.py        # Modül 1: Akım & Güç (wc_id=1)
├── module_color.py        # Modül 2: Renk Algılama (wc_id=2)
├── module_fault.py        # Modül 3: Arıza Tespit (wc_id=3)
├── module_weight.py       # Modül 4: Ağırlık Ölçüm (wc_id=4)
├── module_conveyor.py     # Modül 5: Konveyör (wc_id=5)
├── main_gui.py            # Ana GUI yöneticisi
├── gui_modules.py         # GUI modül ekranları (main_gui.py'ye eklenecek)
└── README.md              # Bu dosya
```

## 🎯 Modül Yapısı

Her modül **bağımsız** çalışır ve **farklı API endpoint**'lerine veri gönderir:

### Modül 1: Akım & Güç Ölçümü
- **wc_id:** 1
- **ESP32 Mesajları:** `cur=X.XX`, `pow=X.XX`
- **API Endpoint:** `/api/v1/energy`
- **Veri Formatı:**
```json
{
  "wc_id": 1,
  "voltage_v": 24,
  "current_a": 0.16,
  "power_w": 12.5
}
```

### Modül 2: Renk Algılama
- **wc_id:** 2
- **ESP32 Mesajları:** `Count`
- **API Endpoint:** `/api/v1/prodEvent`
- **Veri Formatı:**
```json
{
  "sessionId": 123,
  "wc_id": 2,
  "eventType": "product_detected",
  "color": "Kırmızı",
  "count": 5
}
```

### Modül 3: Arıza Tespit
- **wc_id:** 3
- **ESP32 Mesajları:** `Fire`, `Voice`, `Vibration`
- **API Endpoint:** `/api/v1/faultEvent`
- **Veri Formatı:**
```json
{
  "sessionId": 123,
  "wc_id": 3,
  "faultType": "fire",
  "severity": "critical",
  "timestamp": "2025-01-15T10:30:00",
  "status": "active"
}
```

### Modül 4: Ağırlık Ölçüm
- **wc_id:** 4
- **ESP32 Mesajları:** `weight=X.XX`
- **API Endpoint:** `/api/v1/weightEvent`
- **Veri Formatı:**
```json
{
  "sessionId": 123,
  "wc_id": 4,
  "weight_g": 125.5,
  "timestamp": "2025-01-15T10:30:00",
  "tare_g": 0.0
}
```

### Modül 5: Konveyör
- **wc_id:** 5
- **ESP32 Mesajları:** `Count`
- **API Endpoint:** `/api/v1/conveyorEvent`
- **Veri Formatı:**
```json
{
  "sessionId": 123,
  "wc_id": 5,
  "itemCount": 50,
  "runtime_seconds": 120.5,
  "rate_per_minute": 24.8,
  "timestamp": "2025-01-15T10:30:00"
}
```

## 🚀 Kurulum

### 1. Gerekli Kütüphaneler

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-pil python3-pil.imagetk

pip3 install --upgrade pip
pip3 install pyserial RPi.GPIO requests pillow

# NFC için (opsiyonel)
pip3 install adafruit-circuitpython-pn532

# Kamera için (opsiyonel)
pip3 install opencv-python-headless numpy
```

### 2. UART Etkinleştirme

```bash
sudo raspi-config
# Interface Options -> Serial Port
# Login shell: NO
# Serial port hardware: YES

sudo reboot
```

## 📝 main_gui.py Güncelleme

`gui_modules.py` dosyasındaki fonksiyonları `main_gui.py` içindeki `MainGUI` sınıfına ekleyin:

```python
# main_gui.py dosyasının sonuna ekleyin:

# gui_modules.py'deki tüm show_* fonksiyonlarını buraya kopyalayın
```

## ▶️ Çalıştırma

```bash
cd /home/pi/Desktop/deneme
python3 main_gui.py
```

## 🎮 Kullanım

### Adım 1: NFC Kart Okutma
- Herhangi bir modülü başlatmadan önce NFC kartınızı okutun
- Kart okunduğunda buzzer 2 kez bip sesi çıkarır
- Session otomatik başlar

### Adım 2: Modül Seçimi
- Sol menüden istediğiniz modülü seçin
- Her modül bağımsız çalışır

### Adım 3: Başlatma
- Ekrandaki **▶ BAŞLAT** butonuna veya
- Fiziksel **START** butonuna basın
- ESP32'ye `start` komutu gönderilir
- Modül çalışmaya başlar

### Adım 4: Veri İzleme
- Her modül kendi verisini gösterir
- Veriler otomatik olarak ilgili API'ye gönderilir
- Her API çağrısı loglanır

### Adım 5: Durdurma
- **⏹ DURDUR** butonuna veya
- Fiziksel **STOP** butonuna basın
- ESP32'ye `stop` komutu gönderilir

## 🔧 ESP32 Protokolü

### Raspberry Pi → ESP32
```
start       # Motor başlat
stop        # Motor durdur
test        # Test komutu
```

### ESP32 → Raspberry Pi
```
cur=0.16         # Akım verisi (Amper)
pow=12.5         # Güç verisi (Watt)
weight=125.5     # Ağırlık verisi (gram)
Count            # Ürün geçişi
Fire             # Yangın algılandı
Voice            # Ses algılandı
Vibration        # Titreşim algılandı
```

## 🐛 Test Etme

Her modülü ayrı ayrı test edebilirsiniz:

```bash
# Güç modülü test
python3 module_power.py

# Renk modülü test
python3 module_color.py

# Arıza modülü test
python3 module_fault.py

# Ağırlık modülü test
python3 module_weight.py

# Konveyör modülü test
python3 module_conveyor.py

# ESP32 haberleşme test
python3 esp32_comm.py

# NFC okuyucu test
python3 nfc_reader.py
```

## 📊 API Endpoint Özeti

| Modül | wc_id | Endpoint | Açıklama |
|-------|-------|----------|----------|
| Güç | 1 | /api/v1/energy | Akım ve güç verileri |
| Renk | 2 | /api/v1/prodEvent | Ürün sayım verileri |
| Arıza | 3 | /api/v1/faultEvent | Arıza bildirimleri |
| Ağırlık | 4 | /api/v1/weightEvent | Ağırlık ölçümleri |
| Konveyör | 5 | /api/v1/conveyorEvent | Konveyör verileri |

## 🔑 Özellikler

✅ **Modüler Yapı:** Her modül bağımsız çalışır
✅ **Farklı API'ler:** Her modül kendi endpoint'ine gönderir
✅ **Farklı wc_id'ler:** Her istasyon benzersiz ID'ye sahip
✅ **Test Edilebilir:** Her modül ayrı test edilebilir
✅ **Callback Sistemi:** GUI ile modüller arasında esnek iletişim
✅ **Thread-Safe:** Çoklu thread desteği
✅ **Hata Yönetimi:** Kapsamlı loglama ve hata yakalama

## 📞 Destek

Herhangi bir sorun için:
1. Log dosyalarını kontrol edin
2. Her modülü ayrı ayrı test edin
3. ESP32 bağlantısını kontrol edin
4. API erişimini test edin

## 🎓 Gaziantep Üniversitesi
Mühendislik Fakültesi
Endüstriyel Eğitim Sistemi
