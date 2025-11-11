#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODÜL: OCR (Optical Character Recognition)
- Kamera ile yazı algılama
- MANUEL OKUMA: Sadece "OKU" butonuna basıldığında çalışır
- Tesseract OCR kullanarak metin okuma
- Session ve API gerekmez
"""

import cv2
import numpy as np
import logging
from PIL import Image
import time
from threading import Thread

try:
    import pytesseract
    # Windows için Tesseract path (gerekirse değiştirin)
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("⚠️ pytesseract yüklü değil! pip install pytesseract yapın")

logger = logging.getLogger(__name__)


class OCRModule:
    """OCR Modülü - Manuel kamera ile yazı okuma"""
    
    def __init__(self, esp32_comm=None, camera_index=0):
        self.esp32 = esp32_comm
        self.running = False
        
        # Kamera
        self.camera = None
        self.camera_index = camera_index
        self.camera_running = False
        
        # OCR ayarları
        self.ocr_language = 'tur'  # Tesseract dil kodu (eng=İngilizce, tur=Türkçe)
        self.ocr_config = '--psm 6'  # PSM 6: Tek düz metin bloğu
        
        # Son okunan metin
        self.detected_text = ""
        self.is_reading = False  # OCR işlemi devam ediyor mu?
        
        # Callback
        self.on_text_update = None
        self.on_reading_status = None  # Okuma durumu callback'i
        
        # İşlenmiş frame
        self.current_frame = None
        
        # Preprocessing ayarları
        self.use_preprocessing = True
        self.threshold_value = 127
        
        logger.info("OCR Modülü oluşturuldu (Manuel mod)")
        
        if not TESSERACT_AVAILABLE:
            logger.error("❌ Tesseract OCR yüklü değil!")
    
    def start(self, session_id=None):
        """Modülü başlat (session_id kullanılmıyor)"""
        if self.running:
            logger.warning("OCR modülü zaten çalışıyor")
            return False
        
        if not TESSERACT_AVAILABLE:
            logger.error("❌ Tesseract OCR yüklü değil!")
            return False
        
        self.running = True
        
        # Kamerayı başlat
        self._start_camera()
        
        # Metni sıfırla
        self.detected_text = ""
        self.is_reading = False
        
        logger.info("✅ OCR modülü başladı (Manuel mod - OKU butonuna basın)")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            return False
        
        self.running = False
        
        # Kamerayı durdur
        self._stop_camera()
        
        logger.info("⏹ OCR modülü durdu")
        return True
    
    def _start_camera(self):
        """Kamerayı başlat"""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise Exception("Kamera açılamadı")
            
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            self.camera_running = True
            logger.info("📹 Kamera başladı")
            
        except Exception as e:
            logger.error(f"Kamera hatası: {e}")
            self.camera = None
    
    def _stop_camera(self):
        """Kamerayı durdur"""
        self.camera_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
            logger.info("📹 Kamera durdu")
    
    def _preprocess_for_ocr(self, frame):
        """Frame'i OCR için hazırla"""
        if frame is None:
            return None
        
        # Gri tonlamaya çevir
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        if self.use_preprocessing:
            # Gaussian blur (gürültü azaltma)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold (siyah-beyaz)
            _, threshold = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY)
            
            return threshold
        else:
            return gray
    
    def read_text(self):

        if not self.running or not self.camera_running:
            logger.error("❌ Kamera çalışmıyor!")
            return False
        
        if self.is_reading:
            logger.warning("⚠️ OCR zaten çalışıyor, lütfen bekleyin")
            return False
        
        Thread(target=self._perform_ocr_async, daemon=True).start()
        return True
    
    def _perform_ocr_async(self):
        """OCR işlemini async olarak yap"""
        if not TESSERACT_AVAILABLE:
            return
        
        try:
            self.is_reading = True
            
            # Durum callback'i
            if self.on_reading_status:
                self.on_reading_status(True)
            
            logger.info("📖 OCR başladı...")
            
            # Mevcut frame'i al
            if self.current_frame is None:
                logger.error("❌ Frame yok!")
                return
            
            # Preprocessing
            processed = self._preprocess_for_ocr(self.current_frame)
            if processed is None:
                logger.error("❌ Preprocessing hatası!")
                return
            
            # PIL Image'e çevir
            pil_image = Image.fromarray(processed)
            
            # Tesseract OCR
            text = pytesseract.image_to_string(
                pil_image,
                lang=self.ocr_language,
                config=self.ocr_config
            )
            
            # Temizle (boşlukları ve satır sonlarını düzenle)
            text = text.strip()
            
            # Sonucu kaydet
            self.detected_text = text
            
            if text:
                logger.info(f"✅ OCR tamamlandı: '{text[:50]}...'")
            else:
                logger.warning("⚠️ Metin algılanamadı")
            
            # Callback
            if self.on_text_update:
                self.on_text_update(self.detected_text)
            
        except Exception as e:
            logger.error(f"❌ OCR hatası: {e}")
            self.detected_text = f"[HATA: {str(e)}]"
            if self.on_text_update:
                self.on_text_update(self.detected_text)
        
        finally:
            self.is_reading = False
            
            # Durum callback'i
            if self.on_reading_status:
                self.on_reading_status(False)
    
    def get_camera_frame(self):
        """Kamera frame'i al (GUI için) - OCR YAPMA, sadece görüntüyü göster"""
        if not self.camera_running or not self.camera:
            return None
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                return None
            
            # BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Mevcut frame'i sakla (OKU butonuna basıldığında kullanılacak)
            self.current_frame = frame_rgb.copy()
            
            # Frame'e durum bilgisi yaz
            result_frame = frame_rgb.copy()
            
            # Durum bilgisi (üst köşe)
            if self.is_reading:
                status = "OCR OKUYOR..."
                color = (255, 165, 0)  # Turuncu
            elif self.running:
                status = "Hazir - OKU butonuna basin"
                color = (0, 255, 0)  # Yeşil
            else:
                status = "Durduruldu"
                color = (255, 0, 0)  # Kırmızı
            
            cv2.putText(result_frame, status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Preprocessing göstergesi
            if self.use_preprocessing:
                cv2.putText(result_frame, "Preprocessing: ON", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            return result_frame
                
        except Exception as e:
            logger.error(f"Frame okuma hatası: {e}")
            return None
    
    def set_language(self, lang_code):
        """OCR dilini değiştir (örn: 'eng', 'tur')"""
        self.ocr_language = lang_code
        logger.info(f"🌐 OCR dili değiştirildi: {lang_code}")
    
    def toggle_preprocessing(self):
        """Preprocessing'i aç/kapat"""
        self.use_preprocessing = not self.use_preprocessing
        logger.info(f"🔧 Preprocessing: {'AÇIK' if self.use_preprocessing else 'KAPALI'}")
    
    def set_threshold(self, value):
        """Threshold değerini değiştir (0-255)"""
        self.threshold_value = max(0, min(255, value))
        logger.info(f"🎚️ Threshold: {self.threshold_value}")
    
    def clear_text(self):
        """Algılanan metni temizle"""
        self.detected_text = ""
        if self.on_text_update:
            self.on_text_update("")
        logger.info("🧹 Metin temizlendi")
    
    def get_text(self):
        """Son algılanan metni döndür"""
        return self.detected_text
    
    def is_busy(self):
        """OCR işlemi devam ediyor mu?"""
        return self.is_reading


# Test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    ocr_module = OCRModule()
    
    def on_text(text):
        print(f"📝 Metin: '{text}'")
    
    def on_status(reading):
        if reading:
            print("⏳ OCR okuyor...")
        else:
            print("✅ OCR tamamlandı")
    
    ocr_module.on_text_update = on_text
    ocr_module.on_reading_status = on_status
    ocr_module.start()
    
    print("OCR modülü çalışıyor (Manuel mod)")
    print("Komutlar: r=Oku, p=Preprocessing aç/kapa, c=Temizle, q=Çıkış")
    
    try:
        import cv2
        while True:
            frame = ocr_module.get_camera_frame()
            if frame is not None:
                # RGB -> BGR (OpenCV gösterimi için)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imshow("OCR Test - Manuel Mod", frame_bgr)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("📖 Okuma başlatılıyor...")
                ocr_module.read_text()
            elif key == ord('p'):
                ocr_module.toggle_preprocessing()
            elif key == ord('c'):
                ocr_module.clear_text()
            
    except KeyboardInterrupt:
        pass
    finally:
        ocr_module.stop()
        cv2.destroyAllWindows()
        print("\n✅ Test sonlandı")
