#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODÜL 1: Akım ve Güç Ölçümü
- ESP32'den cur= ve pow= verileri alır
- Her ölçümde API'ye POST atar
- wc_id = 1
"""

import requests
import logging
from datetime import datetime
from config import API_ENDPOINTS, API_KEY, WC_IDS

logger = logging.getLogger(__name__)


class PowerModule:
    """Akım ve Güç Ölçüm Modülü"""
    
    def __init__(self, esp32_comm):
        self.esp32 = esp32_comm
        self.wc_id = WC_IDS['power']  # wc_id = 1
        self.session_id = 0
        self.running = False
        
        # Ölçüm değerleri
        self.current_a = 0.0
        self.power_w = 0.0
        self.voltage_v = 24.0  # Sabit gerilim
        
        # Callback fonksiyonları (GUI güncellemesi için)
        self.on_data_update = None
        
        logger.info(f"Güç Modülü oluşturuldu (wc_id={self.wc_id})")
    
    def start(self, session_id):
        """Modülü başlat"""
        if self.running:
            logger.warning("Güç modülü zaten çalışıyor")
            return False
        
        self.session_id = session_id
        self.running = True
        
        # ESP32 callback'lerini kaydet
        self.esp32.register_callback('current', self._on_current_received)
        self.esp32.register_callback('power', self._on_power_received)
        
        # ESP32'ye motor başlat komutu
        self.esp32.send_command("start")
        
        logger.info(f"✅ Güç modülü başladı (session_id={session_id})")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            return False
        
        self.running = False
        
        # Callback'leri kaldır
        self.esp32.unregister_callback('current')
        self.esp32.unregister_callback('power')
        
        # ESP32'ye motor durdur komutu
        self.esp32.send_command("stop")
        
        logger.info("⏹ Güç modülü durdu")
        return True
    
    def _on_current_received(self, value):
        """ESP32'den akım verisi geldiğinde"""
        if not self.running:
            return
        
        self.current_a = value
        logger.info(f"⚡ Akım: {value:.2f} A")
        
        # API'ye gönder
        self._send_to_api()
        
        # GUI'yi güncelle
        if self.on_data_update:
            self.on_data_update('current', value)
    
    def _on_power_received(self, value):
        """ESP32'den güç verisi geldiğinde"""
        if not self.running:
            return
        
        self.power_w = value
        logger.info(f"🔋 Güç: {value:.1f} W")
        
        # API'ye gönder
        self._send_to_api()
        
        # GUI'yi güncelle
        if self.on_data_update:
            self.on_data_update('power', value)
    
    def _send_to_api(self):
        """Enerji verilerini API'ye gönder"""
        try:
            headers = {
                'apiKey': f'{API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                "wc_id": self.wc_id,
                "voltage_v": self.voltage_v,
                "current_a": self.current_a,
                "power_w": self.power_w,
                "session_id": self.session_id,
            }
            
            response = requests.post(
                API_ENDPOINTS['energy'],
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Energy API: {self.current_a:.2f}A, {self.power_w:.1f}W")
            else:
                logger.warning(f"⚠️ Energy API hatası: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Energy API gönderme hatası: {e}")
    
    def get_current_data(self):
        """Mevcut ölçüm verilerini döndür"""
        return {
            'current': self.current_a,
            'power': self.power_w,
            'voltage': self.voltage_v
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    from esp32_comm import ESP32Communication
    import time
    
    # ESP32 bağlantısı
    esp32 = ESP32Communication()
    esp32.start_reading()
    
    # Güç modülü
    power_module = PowerModule(esp32)
    
    # Callback fonksiyonu
    def on_update(data_type, value):
        print(f"📊 {data_type}: {value}")
    
    power_module.on_data_update = on_update
    
    # Modülü başlat (session_id=123 test için)
    power_module.start(session_id=123)
    
    try:
        print("Güç modülü çalışıyor... (Çıkmak için Ctrl+C)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        power_module.stop()
        esp32.close()
        print("\nTest sonlandı")
