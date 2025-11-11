# Endüstriyel Eğitim Sistemi - Modüler Mimari 

Bu depo, ESP32 tabanlı sensör/aktüatör haberleşmesi ile çalışan modüler bir eğitim sistemi içerir. Her modül bağımsız çalışır ve ilgili API endpoint'lerine veri gönderir.

## Proje Dosyaları (kısa açıklama + link)
- [config.py](config.py) — Ortak ayarlar ve API endpoint'leri (örn. [`API_ENDPOINTS`](config.py))
- [esp32_comm.py](esp32_comm.py) — UART üzerinden ESP32 iletişimi ve callback sistemi (sınıf: [`ESP32Communication`](esp32_comm.py))
- [nfc_reader.py](nfc_reader.py) — PN532 NFC okuma döngüsü ve callback (sınıf: [`NFCReader`](nfc_reader.py))
- [main_gui.py](main_gui.py) — Tkinter GUI ve modül yönetimi (sınıf: [`MainGUI`](main_gui.py))
- [module_power.py](module_power.py) — Akım & güç ölçümü modülü (PowerModule)
- [module_production.py](module_production.py) — Enerji üretimi modülü (ProductionModule)
- [module_color.py](module_color.py) — Renk algılama ve ürün sayma (ColorModule)
- [module_fault.py](module_fault.py) — Arıza tespit modülü (FaultModule)
- [module_weight.py](module_weight.py) — Ağırlık ölçüm modülü, sabit ölçüm sayısı (WeightModule)
- [module_conveyor.py](module_conveyor.py) — Konveyör sayacı / hız (ConveyorModule)
- [module_ocr.py](module_ocr.py) — Manuel OCR modülü, Tesseract tabanlı (OCRModule)
- [module_metal.py](module_metal.py) — Metal algılama modülü (MetalModule)
- [deneme2.py](deneme2.py) — API çağrı örneği / yardımcı script
- [Project PCB/](Project%20PCB/) — Donanım / PCB dokümanları ve çizimler

## Project PCB — Görseller
Aşağıda Project PCB klasörüne yüklediğiniz iki görsel doğrudan gösterilmektedir. Dosya isimleri depo içerisindeki adlara göre değişiyorsa, bağlantıları düzenleyin.

![PCB - Top View](https://github.com/umutnergis/Universty-IOT-Education-Set/blob/main/Project%20PCB/esp32-stm32-pcb.png)
![PCB - Schematic]([Project%20PCB/pcb_schematic.png](https://github.com/umutnergis/Universty-IOT-Education-Set/blob/main/Project%20PCB/rpi_pcb.png))

Dosya bağlantıları:
- [Project PCB/pcb_top.png](Project%20PCB/pcb_top.png)
- [Project PCB/pcb_schematic.png](Project%20PCB/pcb_schematic.png)
- Klasör: [Project PCB/](Project%20PCB/)

## Modüller — Özet
- Modül 1 (Power): wc_id=1 — akım/güç verileri → endpoint: `energy` ([config.py](config.py))
- Modül 2 (Color): wc_id=2 — kamera tabanlı renk algılama ve sayaç → endpoint: `prodEvent` ([module_color.py](module_color.py))
- Modül 3 (Fault): wc_id=3 — Fire/Voice/Vibration algılama → endpoint: `faultEvent` ([module_fault.py](module_fault.py))
- Modül 4 (Weight): wc_id=4 — hassas tartım, ölçüm toplama → endpoint: `weightEvent` ([module_weight.py](module_weight.py))
- Modül 5 (Conveyor): wc_id=5 — konveyör sayaç & hız → endpoint: `conveyorEvent` ([module_conveyor.py](module_conveyor.py))
- OCR: Manuel, session gerektirmez — [`OCRModule`](module_ocr.py)

(Detaylı davranış için ilgili modül dosyalarına bakın: örn. [`WeightModule`](module_weight.py), [`ColorModule`](module_color.py), [`ConveyorModule`](module_conveyor.py))

## Kurulum (kısa)
1. Sistem paketleri:
   sudo apt-get update
   sudo apt-get install python3-pip python3-pil python3-pil.imagetk
2. Python paketleri:
   pip3 install --upgrade pip
   pip3 install pyserial RPi.GPIO requests pillow
   pip3 install opencv-python-headless numpy   # Kamera için
   pip3 install adafruit-circuitpython-pn532   # NFC için (opsiyonel)
3. UART:
   sudo raspi-config → Interface Options → Serial Port → Login shell: NO, Serial hardware: YES → reboot

## Çalıştırma
- Ana GUI: python3 main_gui.py
  - GUI entry: [`MainGUI`](main_gui.py)
- Modül testleri (tek tek):
  - python3 module_power.py
  - python3 module_color.py
  - python3 module_fault.py
  - python3 module_weight.py
  - python3 module_conveyor.py
  - python3 esp32_comm.py
  - python3 nfc_reader.py

## Önemli Notlar / Davranışlar
- NFC ile session yönetimi: GUI içindeki [`MainGUI.start_session`](main_gui.py) akışı kullanılır. NFC okuma: [`NFCReader`](nfc_reader.py).
- OCR modülü manueldir: sadece "OKU" tetiklenince çalışır; Tesseract gerekli ([module_ocr.py](module_ocr.py)).
- Weight modülü: sabit sayıda ölçüm toplar (default 8) → ortalama gönderilir ([module_weight.py](module_weight.py)).
- ESP32 ↔ Pi protokolü: `start`, `stop`, `test` (Pi→ESP32) ve `cur=...`, `pow=...`, `weight=...`, `Count`, `Fire`, `Voice`, `Vibration` (ESP32→Pi) — uygulama içinde parse ve callback'ler [esp32_comm.py](esp32_comm.py) tarafından işlenir.

## API & Konfigürasyon
- API ana url'leri ve anahtar: [config.py](config.py) (`API_BASE_URL`, `API_KEY`, `API_ENDPOINTS`)
- Tüm modüller config'deki endpoint'leri kullanır (örnek: `API_ENDPOINTS['product']`, `API_ENDPOINTS['weight']`)

## Hata Ayıklama / Test İpuçları
1. Logları kontrol edin (her dosyada logging kullanılıyor).
2. Modülleri tek tek başlatıp test edin (ör. python3 module_color.py).
3. ESP32 seri iletişimini test edin: python3 esp32_comm.py.
4. NFC çalışmıyorsa PN532 kurulumu ve paketleri kontrol edin.

## Katkı / Geliştirme
- Kod düzeni: modüller bağımsızdır ve GUI tarafından callback ile güncellenir — GUI: [`main_gui.py`](main_gui.py).
- Yeni modül eklemek için mevcut modül örneklerini takip edin ve `MainGUI.modules` sözlüğüne ekleyin.

---

Daha fazla bilgi için ilgili dosyalara bakınız: [main_gui.py](main_gui.py), [module_ocr.py](module_ocr.py), [module_weight.py](module_weight.py), [module_color.py](module_color.py), [module_conveyor.py](module_conveyor.py), [module_fault.py](module_fault.py), [module_production.py](module_production.py), [module_metal.py](module_metal.py), [esp32_comm.py](esp32_comm.py), [nfc_reader.py](nfc_reader.py), [deneme2.py](deneme2.py), [config.py](config.py), [Project PCB/](Project%20PCB/)
