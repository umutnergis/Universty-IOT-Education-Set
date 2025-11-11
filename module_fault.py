#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u
"""
MODÜL 3: Arıza Tespit Sistemi
- ESP32'den Fire, Voice, Vibration mesajları
- Her arıza için API'ye POST
- wc_id = 3
- start_ts ve end_ts zamanlarını tutar
"""

import requests
import logging
from datetime import datetime, timedelta
from config import API_ENDPOINTS, API_KEY, WC_IDS

logger = logging.getLogger(__name__)


class FaultModule:
    """Arıza Tespit Modülü"""
    
    def __init__(self, esp32_comm):
        self.esp32 = esp32_comm
        self.wc_id = WC_IDS['fault'] 
        self.session_id = 0
        self.running = False

        self.fault_fire = False
        self.fault_voice = False
        self.fault_vibration = False
        
        # Arıza zamanları
        self.fault_timestamps = {
            'fire': {'start': None, 'end': None},
            'voice': {'start': None, 'end': None},
            'vibration': {'start': None, 'end': None}
        }

        self.on_fault_update = None
        
        logger.info(f"Arıza Modülü oluşturuldu (wc_id={self.wc_id})")
    
    def _get_iso_timestamp(self):
        """Türkiye saatinde ISO 8601 formatında zaman döndür (UTC+3)"""
        # Türkiye saati = UTC + 3 saat (yazlık/kışlık saat farkı göz ardı)
        tr_time = datetime.utcnow() + timedelta(hours=3)
        return tr_time.isoformat(timespec='milliseconds')
    
    def start(self, session_id):
        """Modülü başlat"""
        if self.running:
            logger.warning("Arıza modülü zaten çalışıyor")
            return False
        
        self.session_id = session_id
        self.running = True
        
        # ESP32 callback'leri kaydet
        self.esp32.register_callback('fire', self._on_fire_detected)
        self.esp32.register_callback('voice', self._on_voice_detected)
        self.esp32.register_callback('vibration', self._on_vibration_detected)
        
        # Motor başlat
        self.esp32.send_command("start")
        
        # Arızaları sıfırla
        self.fault_fire = False
        self.fault_voice = False
        self.fault_vibration = False
        
        # Zamanları sıfırla
        for fault_type in self.fault_timestamps:
            self.fault_timestamps[fault_type] = {'start': None, 'end': None}
        
        logger.info(f"✅ Arıza modülü başladı (session_id={session_id})")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            return False
        
        self.running = False
        
        # Callback'leri kaldır
        self.esp32.unregister_callback('fire')
        self.esp32.unregister_callback('voice')
        self.esp32.unregister_callback('vibration')
        
        # Motor durdur
        self.esp32.send_command("stop")
        
        logger.info("⏹ Arıza modülü durdu")
        return True
    
    def _on_fire_detected(self, value):
        """Yangın sensörü tetiklendi"""
        if not self.running:
            return
        
        self.fault_fire = True
        self.fault_timestamps['fire']['start'] = self._get_iso_timestamp()
        logger.warning("🔥 YANGIN TESPİT EDİLDİ!")
        
        # ✅ MOTOR DURDUR
        self.esp32.send_command("stop")
        
        self._send_to_api(2, 'critical', 'fire')
        
        if self.on_fault_update:
            self.on_fault_update('fire', True)
        
    def _on_voice_detected(self, value):
        if not self.running:
            return
        
        self.fault_voice = True
        self.fault_timestamps['voice']['start'] = self._get_iso_timestamp()
        logger.warning("🔊 YÜKSEK SES TESPİT EDİLDİ!")
        
        # ✅ MOTOR DURDUR
        self.esp32.send_command("stop")
        
        self._send_to_api(9, 'warning', 'voice')
        
        if self.on_fault_update:
            self.on_fault_update('voice', True)
        
    def _on_vibration_detected(self, value):
        if not self.running:
            return
        
        self.fault_vibration = True
        self.fault_timestamps['vibration']['start'] = self._get_iso_timestamp()
        logger.warning("📳 TİTREŞİM TESPİT EDİLDİ!")
        
        # ✅ MOTOR DURDUR
        self.esp32.send_command("stop")
        
        self._send_to_api(8, 'warning', 'vibration')
        
        if self.on_fault_update:
            self.on_fault_update('vibration', True)
    
    def _send_to_api(self, fault_type, severity, fault_key):
        """Arıza bilgisini API'ye gönder"""
        try:
            headers = {
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
            
            start_ts = self.fault_timestamps[fault_key]['start']
            
            data = {
                "fault_id": 0,
                "wc_id": self.wc_id,
                "session_id": self.session_id,
                "fault_type_id": fault_type,
                "start_ts": start_ts,
                "end_ts": start_ts  # Arıza başında start_ts ve end_ts aynı
            }
            
            response = requests.post(
                API_ENDPOINTS['fault'],
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Fault API: {fault_type} ({severity})")
            else:
                logger.warning(f"⚠️ Fault API hatası: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Fault API hatası: {e}")
    
    def _send_to_api_with_end(self, fault_type, severity, fault_key):
        """Arıza sonlandırılırken API'ye end_ts ile gönder"""
        try:
            headers = {
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
            
            start_ts = self.fault_timestamps[fault_key]['start']
            end_ts = self.fault_timestamps[fault_key]['end']
            
            data = {
                "fault_id": 0,
                "wc_id": self.wc_id,
                "session_id": self.session_id,
                "fault_type_id": fault_type,
                "start_ts": start_ts,
                "end_ts": end_ts
            }
            
            response = requests.post(
                API_ENDPOINTS['fault'],
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Fault Sonlandırma API: {fault_type} ({severity}) - {start_ts} -> {end_ts}")
            else:
                logger.warning(f"⚠️ Fault Sonlandırma API hatası: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Fault Sonlandırma API hatası: {e}")
    
    def clear_fault(self, fault_type):
        """Arızayı temizle ve motoru başlat"""
        fault_mapping = {
            'fire': (self.fault_fire, 2),
            'voice': (self.fault_voice, 9),
            'vibration': (self.fault_vibration, 8)
        }
        
        if fault_type == 'fire':
            self.fault_fire = False
            self.fault_timestamps['fire']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(2, 'critical', 'fire')
        elif fault_type == 'voice':
            self.fault_voice = False
            self.fault_timestamps['voice']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(9, 'warning', 'voice')
        elif fault_type == 'vibration':
            self.fault_vibration = False
            self.fault_timestamps['vibration']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(8, 'warning', 'vibration')
        
        logger.info(f"Arıza temizlendi: {fault_type}")
        
        # ✅ EĞER TÜM ARIZALAR TEMİZSE MOTORU BAŞLAT
        if not self.get_fault_status()['any_active']:
            self.esp32.send_command("start")
            logger.info("✅ Motor yeniden başlatıldı")
        
        if self.on_fault_update:
            self.on_fault_update(fault_type, False)
    
    def clear_all_faults(self):
        """Tüm arızaları temizle ve motoru başlat"""
        # Her bir aktif arızayı end_ts ile sonlandır
        if self.fault_fire:
            self.fault_timestamps['fire']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(2, 'critical', 'fire')
            
        if self.fault_voice:
            self.fault_timestamps['voice']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(9, 'warning', 'voice')
            
        if self.fault_vibration:
            self.fault_timestamps['vibration']['end'] = self._get_iso_timestamp()
            self._send_to_api_with_end(8, 'warning', 'vibration')
        
        self.fault_fire = False
        self.fault_voice = False
        self.fault_vibration = False
        logger.info("Tüm arızalar temizlendi")
        
        # ✅ MOTORU BAŞLAT
        self.esp32.send_command("start")
        logger.info("✅ Motor yeniden başlatıldı")
        
        if self.on_fault_update:
            self.on_fault_update('all', False)
    
    def get_fault_status(self):
        """Arıza durumlarını döndür"""
        return {
            'fire': self.fault_fire,
            'voice': self.fault_voice,
            'vibration': self.fault_vibration,
            'any_active': self.fault_fire or self.fault_voice or self.fault_vibration,
            'timestamps': self.fault_timestamps
        }


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
    
    fault_module = FaultModule(esp32)
    
    def on_fault(fault_type, active):
        status = "AKTİF" if active else "TEMİZ"
        print(f"⚠️ {fault_type.upper()}: {status}")
    
    fault_module.on_fault_update = on_fault
    fault_module.start(session_id=123)
    
    try:
        print("Arıza modülü çalışıyor... (Çıkmak için Ctrl+C)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        fault_module.stop()
        esp32.close()
        print("\nTest sonlandı")
