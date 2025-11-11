#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODÜL: Metal Algılama
- Metal dedektörü ile metal ürün algılama
- Ürün sayımı ve API entegrasyonu
- wc_id = 2
- PWM/speed_rpm entegrasyonlu
"""

import requests
import logging
from datetime import datetime
from config import API_ENDPOINTS, API_KEY, WC_IDS

logger = logging.getLogger(__name__)


class MetalModule:
    """Metal Algılama Modülü"""
    
    def __init__(self, esp32_comm):
        self.esp32 = esp32_comm
        self.wc_id = WC_IDS['metal']  # wc_id = 2
        
        self.session_id = 0
        self.running = False
        
        # Sayaçlar
        self.metal_count = 0
        self.last_sent_count = 0
        
        # Zaman takibi
        self.start_time = None
        self.total_runtime = 0
        
        # ✅ PWM değeri
        self.speed_rpm = 0
        
        # Callback
        self.on_metal_detected = None
        
        logger.info(f"Metal Modülü oluşturuldu (wc_id={self.wc_id})")
    
    def start(self, session_id):
        """Modülü başlat"""
        if self.running:
            logger.warning("Metal modülü zaten çalışıyor")
            return False
        
        if not session_id or session_id == 0:
            logger.error("Geçersiz session_id!")
            return False
        
        self.session_id = session_id
        self.running = True
        self.start_time = datetime.now()
        
        # ✅ Metal ve PWM callback'lerini kaydet
        self.esp32.register_callback('count', self._on_metal_detected)
        self.esp32.register_callback('pwm', self._on_pwm_changed)
        
        # ESP32'ye başlat komutu
        self.esp32.send_command("start")
        
        logger.info(f"✅ Metal modülü başladı (session_id={session_id})")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            logger.warning("Metal modülü zaten durmuş")
            return False
        
        self.running = False
        
        # Runtime hesapla
        if self.start_time:
            runtime = (datetime.now() - self.start_time).total_seconds()
            self.total_runtime += runtime
        
        # ✅ Callback'leri kaldır
        self.esp32.unregister_callback('metal')
        self.esp32.unregister_callback('count')
        self.esp32.unregister_callback('pwm')
        
        # ESP32'ye dur komutu
        self.esp32.send_command("stop")
        
        logger.info(f"⏹ Metal modülü durdu (Toplam: {self.metal_count} metal, {self.total_runtime:.1f}s)")
        return True
    
    def _on_pwm_changed(self, value):
        """ESP32'den PWM mesajı geldiğinde"""
        if value is not None:
            self.speed_rpm = value
            logger.debug(f"⚡ PWM değeri güncellendi: {self.speed_rpm}")
    
    def _on_metal_detected(self, value):
        """ESP32'den metal mesajı geldiğinde"""
        if not self.running:
            return
        
        self.metal_count += 1
        logger.info(f"🔩 Metal algılandı: {self.metal_count}")
        
        # API'ye gönder (her yeni metal algılamada)
        if self.metal_count != self.last_sent_count:
            wc_product_id = self._send_to_api_get_product_id()
            self._send_to_api(wc_product_id=wc_product_id)
            self.last_sent_count = self.metal_count
        
        # GUI güncelle
        if self.on_metal_detected:
            self.on_metal_detected(self.metal_count)
    
    def _send_to_api(self, wc_product_id=None):
        """Metal algılamayı API'ye gönder"""
        try:
            headers = {
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
            
            # Runtime ve hız hesapla
            runtime = 0
            if self.start_time:
                runtime = (datetime.now() - self.start_time).total_seconds()
            rate = (self.metal_count / runtime * 60) if runtime > 0 else 0
            
            # ✅ DÜZELTME: speed_rpm parametresi düzgün
            data = {
                "session_id": self.session_id,
                "wc_id": self.wc_id,
                "quantity": 1,
                "product_id": wc_product_id,
                "speed_rpm": self.speed_rpm,  # ✅ PWM değeri buraya yazılıyor
            }
            
            logger.debug(f"API POST: {data}")
            
            response = requests.post(
                API_ENDPOINTS['conveyor'],  # Metal için de prodEvent endpoint
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201, 501]:
                logger.info(f"✅ Metal API başarılı: count={self.metal_count}, rate={rate:.1f}/min, speed={self.speed_rpm}")
            else:
                logger.warning(f"⚠️ Metal API hatası: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error("❌ Metal API timeout")
        except Exception as e:
            logger.error(f"❌ Metal API hatası: {e}")
    
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
                
    def reset_counter(self):
        """Sayacı sıfırla"""
        old_count = self.metal_count
        self.metal_count = 0
        self.last_sent_count = 0
        
        if self.running:
            self.start_time = datetime.now()
        
        logger.info(f"🔄 Metal sayacı sıfırlandı (eski: {old_count})")
        
        if self.on_metal_detected:
            self.on_metal_detected(0)
    
    def get_statistics(self):
        """Anlık istatistikler"""
        runtime = 0
        if self.start_time and self.running:
            runtime = (datetime.now() - self.start_time).total_seconds()
        
        rate = (self.metal_count / runtime * 60) if runtime > 0 else 0
        
        return {
            'count': self.metal_count,
            'runtime': runtime,
            'rate_per_minute': rate,
            'total_runtime': self.total_runtime + runtime,
            'speed_rpm': self.speed_rpm  # ✅ YENI: İstatistiklerde gösterim
        }
    
    def get_count(self):
        """Mevcut sayı"""
        return self.metal_count


# Test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    from esp32_comm import ESP32Communication
    import time
    
    print("Metal Algılama Modülü Test")
    print("=" * 50)
    
    esp32 = ESP32Communication()
    esp32.start_reading()
    
    metal_module = MetalModule(esp32)
    
    def on_metal(count):
        stats = metal_module.get_statistics()
        print(f"📊 Metal: {count} | "
              f"Süre: {stats['runtime']:.1f}s | "
              f"Hız: {stats['rate_per_minute']:.1f} metal/dk | "
              f"PWM: {stats['speed_rpm']}")
    
    metal_module.on_metal_detected = on_metal
    
    # Mock session ID ile başlat
    metal_module.start(session_id=999)
    
    try:
        print("\n✅ Metal modülü çalışıyor... (Çıkmak için Ctrl+C)")
        print("ESP32'den 'Metal' veya 'Count' mesajı bekliyor...\n")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Durduruluyor...")
        metal_module.stop()
        esp32.close()
        print("✅ Test sonlandı")