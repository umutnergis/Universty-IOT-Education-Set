#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODÜL 2: Renk Algılama ve Sayma
- Kamera ile renk algılama
- Otomatik ürün sayımı (kamera tabanlı)
- Her ürün için API'ye POST
- wc_id = 2
- PWM/speed_rpm entegrasyonlu
"""

import requests
import logging
import cv2
import numpy as np
import time
from PIL import Image, ImageTk
from config import API_ENDPOINTS, API_KEY, WC_IDS

logger = logging.getLogger(__name__)


class ColorModule:
    """Renk Algılama Modülü"""
    
    def __init__(self, esp32_comm, camera_index=0):
        self.esp32 = esp32_comm
        self.wc_id = WC_IDS['color']  # wc_id = 2
        self.session_id = 0
        self.running = False
        
        # Kamera
        self.camera = None
        self.camera_index = camera_index
        self.camera_running = False
        
        # Sayaç
        self.product_count = 0
        self.last_sent_count = 0
        
        # ✅ PWM değeri
        self.speed_rpm = 0
        
        # Seçilen renk
        self.selected_color = "Kirmizi"
        
        # Renk aralıkları (HSV) - İyileştirilmiş değerler
        self.color_ranges = {
            "Kirmizi": {
                "lower1": np.array([0, 100, 100]),
                "upper1": np.array([10, 255, 255]),
                "lower2": np.array([170, 100, 100]),
                "upper2": np.array([180, 255, 255])
            },
            "Sari": {
                "lower1": np.array([15, 100, 100]),
                "upper1": np.array([35, 255, 255])
            },
            "Mavi": {
                "lower1": np.array([100, 100, 100]),
                "upper1": np.array([130, 255, 255])
            }
        }
        
        # Ürün algılama parametreleri
        self.min_area = 1000  # Minimum alan (piksel²)
        self.detection_cooldown = 1.5  # Saniye (aynı ürünü tekrar saymamak için)
        self.last_detection_time = 0
        self.product_detected = False
        
        # Callback'ler
        self.on_count_update = None
        self.on_frame_update = None
        
        # İşlenmiş frame (GUI için)
        self.processed_frame = None
        
        logger.info(f"Renk Modülü oluşturuldu (wc_id={self.wc_id})")
    
    def start(self, session_id):
        """Modülü başlat"""
        if self.running:
            logger.warning("Renk modülü zaten çalışıyor")
            return False
        
        self.session_id = session_id
        self.running = True
        
        # Kamerayı başlat
        self._start_camera()
        
        # ✅ PWM callback'ini kaydet
        self.esp32.register_callback('pwm', self._on_pwm_changed)
        
        # Sayacı sıfırla
        self.product_count = 0
        self.last_sent_count = 0
        self.last_detection_time = 0
        self.product_detected = False
        
        # Motor başlat (opsiyonel)
        self.esp32.send_command("start")
        
        logger.info(f"✅ Renk modülü başladı (session_id={session_id})")
        logger.info(f"🎨 Seçili renk: {self.selected_color}")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            return False
        
        self.running = False
    
        # Kamerayı durdur
        self._stop_camera()
        
        # ✅ PWM callback'ini kaldır
        self.esp32.unregister_callback('pwm')
        
        # Motor durdur
        self.esp32.send_command("stop")
        
        logger.info("⏹ Renk modülü durdu")
        return True
    
    def _on_pwm_changed(self, value):
        """ESP32'den PWM mesajı geldiğinde"""
        if value is not None:
            self.speed_rpm = value
            logger.debug(f"⚡ PWM değeri güncellendi: {self.speed_rpm}")
    
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
    
    def _detect_color(self, frame):
        """Frame'de renk algıla ve işaretle"""
        if frame is None:
            return frame, False
        
        # HSV'ye çevir
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        
        # Seçilen rengin aralıklarını al
        color_range = self.color_ranges.get(self.selected_color)
        if not color_range:
            return frame, False
        
        # Maske oluştur
        if "lower2" in color_range:  # Kırmızı için 2 aralık
            mask1 = cv2.inRange(hsv, color_range["lower1"], color_range["upper1"])
            mask2 = cv2.inRange(hsv, color_range["lower2"], color_range["upper2"])
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            mask = cv2.inRange(hsv, color_range["lower1"], color_range["upper1"])
        
        # Gürültü temizleme
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Konturları bul (OpenCV versiyon uyumlu)
        result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = result[0] if len(result) == 2 else result[1]
        
        detected = False
        result_frame = frame.copy()
        
        # En büyük konturu bul
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            # Minimum alan kontrolü
            if area > self.min_area:
                detected = True
                
                # Dikdörtgen çiz
                x, y, w, h = cv2.boundingRect(largest_contour)
                cv2.rectangle(result_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                
                # Bilgi yazısı
                text = f"{self.selected_color} - {int(area)} px2"
                cv2.putText(result_frame, text, (x, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Durum bilgisi (üst sol köşe)
        status_text = f"Renk: {self.selected_color} | Urun: {self.product_count}"
        cv2.putText(result_frame, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return result_frame, detected
    
    def _process_detection(self, detected):
        """Algılama sonucunu işle ve sayaç güncelle"""
        if not self.running:
            return
        
        current_time = time.time()
        
        # Renk algılandı
        if detected:
            # Cooldown kontrolü
            if current_time - self.last_detection_time > self.detection_cooldown:
                if not self.product_detected:
                    # Yeni ürün!
                    self.product_count += 1
                    self.last_detection_time = current_time
                    self.product_detected = True
                    
                    logger.info(f"🔢 Ürün algılandı! Toplam: {self.product_count}")
                    
                    # API'ye gönder
                    wc_product_id = self._send_to_api_get_product_id()
                    self._send_to_api(wc_product_id=wc_product_id)
                    
                    # GUI güncelle
                    if self.on_count_update:
                        self.on_count_update(self.product_count)
        else:
            # Renk kayboldu, bir sonraki ürün için hazır
            if self.product_detected:
                self.product_detected = False
    
    def _send_to_api_get_product_id(self):
        """Ürün ID'sini API'den al - DÜZELTILMIŞ VERSİYON"""
        try:
            headers = {
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
            url = f"{API_ENDPOINTS['wc_id_name']}/{self.wc_id}"
            
            response = requests.get(
                url,
                headers=headers,
                timeout=5
            )
            
            logger.debug(f"Product ID API - Status: {response.status_code}, URL: {url}")
            
            # ✅ DÜZELTME: 200 ile 201'i kontrol et
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    product_id = data.get('product_id', None)
                    
                    if product_id is not None:
                        logger.info(f"✅ Ürün ID alındı: {product_id}")
                        return product_id
                    else:
                        logger.warning(f"⚠️ Ürün ID bulunamadı. API Yanıtı: {data}")
                        return None
                        
                except ValueError as e:
                    logger.error(f"❌ JSON parse hatası: {e}")
                    logger.debug(f"Response text: {response.text}")
                    return None
            else:
                logger.warning(f"⚠️ Ürün ID API hatası: HTTP {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("❌ API timeout (5s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("❌ API bağlantı hatası")
            return None
        except Exception as e:
            logger.error(f"❌ Ürün ID API hatası: {e}")
            return None
        
    def _send_to_api(self, wc_product_id=None):
        """Ürün sayısını API'ye gönder"""
        try:
            headers = {
                'apiKey': f'{API_KEY}',
                'Content-Type': 'application/json'
            }
            
            # ✅ speed_rpm parametresi eklendi
            data = {
                "session_id": self.session_id,
                "wc_id": self.wc_id,
                "quantity": 1,
                "product_id": wc_product_id,
                "speed_rpm": self.speed_rpm  # ✅ PWM değeri
            }
            
            logger.debug(f"API POST: {data}")
            
            response = requests.post(
                API_ENDPOINTS['conveyor'],  # ✅ DÜZELTME: 'product' → 'conveyor'
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Color API başarılı: count={self.product_count}, color={self.selected_color}, speed={self.speed_rpm}")
            else:
                logger.warning(f"⚠️ Color API hatası: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error("❌ Product API timeout")
        except Exception as e:
            logger.error(f"❌ Product API hatası: {e}")
    
    def get_camera_frame(self):
        """Kamera frame'i al ve renk algılama yap (GUI için)"""
        if not self.camera_running or not self.camera:
            return None
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                return None
            
            # BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Renk algılama (sadece modül çalışıyorsa)
            if self.running:
                processed_frame, detected = self._detect_color(frame_rgb)
                self._process_detection(detected)
                return processed_frame
            else:
                # Modül duruyorsa sadece görüntüyü göster
                return frame_rgb
                
        except Exception as e:
            logger.error(f"Frame okuma hatası: {e}")
            return None
    
    def set_color(self, color_name):
        """Hedef rengi değiştir"""
        if color_name in self.color_ranges:
            self.selected_color = color_name
            logger.info(f"🎨 Seçilen renk: {color_name}")
            return True
        return False
    
    def reset_counter(self):
        """Sayacı sıfırla"""
        self.product_count = 0
        self.last_sent_count = 0
        self.last_detection_time = 0
        self.product_detected = False
        logger.info("🔄 Sayaç sıfırlandı")
        
        if self.on_count_update:
            self.on_count_update(0)
    
    def get_statistics(self):
        """Anlık istatistikler"""
        return {
            'count': self.product_count,
            'color': self.selected_color,
            'speed_rpm': self.speed_rpm  # ✅ YENI
        }
    
    def get_count(self):
        """Mevcut sayıyı döndür"""
        return self.product_count


# Test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    from esp32_comm import ESP32Communication
    import time
    
    esp32 = ESP32Communication()
    esp32.start_reading()
    
    color_module = ColorModule(esp32)
    
    def on_count(count):
        stats = color_module.get_statistics()
        print(f"📊 Sayaç: {count} | Renk: {stats['color']} | PWM: {stats['speed_rpm']}")
    
    color_module.on_count_update = on_count
    color_module.start(session_id=123)
    
    print("Renk modülü çalışıyor... Test için kameraya sarı nesne gösterin")
    print("Renk değiştirmek için: r=Kırmızı, y=Sarı, b=Mavi, q=Çıkış")
    
    try:
        import cv2
        while True:
            frame = color_module.get_camera_frame()
            if frame is not None:
                # RGB -> BGR (OpenCV gösterimi için)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imshow("Renk Algılama Test", frame_bgr)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                color_module.set_color("Kırmızı")
                print("🔴 Kırmızı seçildi")
            elif key == ord('y'):
                color_module.set_color("Sarı")
                print("🟡 Sarı seçildi")
            elif key == ord('b'):
                color_module.set_color("Mavi")
                print("🔵 Mavi seçildi")
            
    except KeyboardInterrupt:
        pass
    finally:
        color_module.stop()
        esp32.close()
        cv2.destroyAllWindows()
        print("\n✅ Test sonlandı")
