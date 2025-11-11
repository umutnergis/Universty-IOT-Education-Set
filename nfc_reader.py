#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFC Kart Okuyucu Sınıfı
Tüm modüller bu sınıfı kullanır
"""

import time
import logging
import binascii
from threading import Thread

try:
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C
    NFC_AVAILABLE = True
except ImportError:
    NFC_AVAILABLE = False
    print("⚠️ NFC kütüphanesi bulunamadı")

logger = logging.getLogger(__name__)


class NFCReader:
    """PN532 NFC okuyucu sınıfı"""
    
    def __init__(self):
        self.pn532 = None
        self.running = False
        self.last_card_id = ""
        self.current_card_id = ""
        self.card_present = False
        self.on_card_detected = None  # Callback fonksiyonu
        self.on_card_removed = None   # Callback fonksiyonu
        
        self.setup()
    
    def setup(self):
        """NFC modülünü başlat"""
        if not NFC_AVAILABLE:
            logger.warning("NFC kütüphanesi yok")
            return False
        
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pn532 = PN532_I2C(i2c, debug=False)
            
            ic, ver, rev, support = self.pn532.firmware_version
            logger.info(f'PN532 hazır! Versiyon: {ver}.{rev}')
            
            self.pn532.SAM_configuration()
            return True
            
        except Exception as e:
            logger.error(f'NFC setup hatası: {e}')
            self.pn532 = None
            return False
    
    def start_reading(self):
        """Okuma thread'ini başlat"""
        if not self.pn532:
            logger.warning("NFC modülü yok, okuma başlatılamadı")
            return False
        
        if not self.running:
            self.running = True
            self.read_thread = Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            logger.info("NFC okuma başladı")
            return True
        return False
    
    def stop_reading(self):
        """Okuma thread'ini durdur"""
        self.running = False
        logger.info("NFC okuma durdu")
    
    def _read_loop(self):
        """Sürekli kart okuma döngüsü"""
        while self.running:
            try:
                if self.pn532:
                    # Kart oku (500ms timeout)
                    uid = self.pn532.read_passive_target(timeout=0.5)
                    
                    if uid:
                        # UID'yi hexadecimal string'e çevir
                        card_id = binascii.hexlify(uid).decode('ascii').upper()
                        
                        # Yeni kart mı?
                        if card_id != self.last_card_id:
                            self.current_card_id = card_id
                            self.last_card_id = card_id
                            self.card_present = True
                            
                            logger.info(f"✓ NFC Kart okundu: {card_id}")
                            
                            # Callback çağır
                            if self.on_card_detected:
                                self.on_card_detected(card_id)
                    else:
                        # Kart yok
                        if self.card_present:
                            self.card_present = False
                            logger.info("NFC Kart çıkarıldı")
                            
                            # Callback çağır
                            if self.on_card_removed:
                                self.on_card_removed()
                    
                    time.sleep(0.3)  # 300ms bekleme
                else:
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"NFC okuma hatası: {e}")
                time.sleep(1)
    
    def get_card_id(self):
        """Mevcut kart ID'sini döndür"""
        return self.current_card_id if self.card_present else None
    
    def is_card_present(self):
        """Kart var mı?"""
        return self.card_present


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def on_card(card_id):
        print(f"🎴 Kart algılandı: {card_id}")
    
    def on_remove():
        print("❌ Kart çıkarıldı")
    
    nfc = NFCReader()
    nfc.on_card_detected = on_card
    nfc.on_card_removed = on_remove
    nfc.start_reading()
    
    try:
        print("NFC kart okutun... (Çıkmak için Ctrl+C)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        nfc.stop_reading()
        print("\nTest sonlandı")
