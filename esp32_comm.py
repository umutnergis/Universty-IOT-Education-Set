#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32 Serial Haberleşme Sınıfı
Tüm modüller bu sınıfı kullanır
"""

import serial
import time
import logging
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class ESP32Communication:
    """ESP32 ile UART üzerinden haberleşme"""
    
    def __init__(self, port='/dev/serial0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.lock = Lock()
        self.callbacks = {}  # Mesaj tiplerine göre callback fonksiyonları
        self.running = False
        self.connect()
    
    def connect(self):
        """Serial bağlantı kur"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=1
            )
            
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            self.connected = True
            logger.info(f"✓ ESP32 bağlandı: {self.port} @ {self.baudrate} baud")
            time.sleep(1)
            return True
            
        except Exception as e:
            logger.error(f"✗ ESP32 bağlantı hatası: {e}")
            self.connected = False
            return False
    
    def start_reading(self):
        """Okuma thread'ini başlat"""
        if not self.running:
            self.running = True
            self.read_thread = Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            logger.info("ESP32 okuma başladı")
    
    def stop_reading(self):
        """Okuma thread'ini durdur"""
        self.running = False
        logger.info("ESP32 okuma durdu")
    
    def _read_loop(self):
        """Sürekli okuma döngüsü"""
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._parse_message(line)
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Okuma hatası: {e}")
                time.sleep(0.1)
    
    def _parse_message(self, message):
        """Gelen mesajı parse et ve ilgili callback'i çağır"""
        try:
            # cur=X.XX formatı
            if message.startswith("cur="):
                value = float(message.split("=")[1])
                self._call_callback('current', value)
            
            # pow=X.XX formatı
            elif message.startswith("pow="):
                value = float(message.split("=")[1])
                self._call_callback('power', value)
            
            # uretimw=X.XX formatı (Enerji Üretimi Watt)
            elif message.startswith("uretimw="):
                value = float(message.split("=")[1])
                self._call_callback('production_w', value)
            
            # uretima=X.XX formatı (Enerji Üretimi Amper)
            elif message.startswith("uretima="):
                value = float(message.split("=")[1])
                self._call_callback('production_a', value)
            
            # weight=X.XX formatı
            elif message.startswith("weight="):
                value = float(message.split("=")[1])
                self._call_callback('weight', value)
            
            # ✅ PWM=X formatı (0-255 arasında)
            elif message.startswith("PWM:"):
                value = int(message.split(":")[1])
                self._call_callback('pwm', value)
                logger.debug(f"PWM değeri alındı: {value}")
            
            # Sensör mesajları
            elif message == "Count":
                self._call_callback('count', None)
            elif message == "Fire":
                self._call_callback('fire', True)
            elif message == "Voice":
                self._call_callback('voice', True)
            elif message == "Vibration":
                self._call_callback('vibration', True)
            else:
                logger.debug(f"Bilinmeyen mesaj: {message}")
                
        except Exception as e:
            logger.error(f"Parse hatası: {e} - Mesaj: {message}")
    
    def _call_callback(self, msg_type, value):
        """Kayıtlı callback fonksiyonunu çağır"""
        if msg_type in self.callbacks:
            try:
                self.callbacks[msg_type](value)
            except Exception as e:
                logger.error(f"Callback hatası ({msg_type}): {e}")
    
    def register_callback(self, msg_type, callback_func):
        """Bir mesaj tipi için callback kaydet"""
        self.callbacks[msg_type] = callback_func
        logger.debug(f"Callback kaydedildi: {msg_type}")
    
    def unregister_callback(self, msg_type):
        """Callback kaydını kaldır"""
        if msg_type in self.callbacks:
            del self.callbacks[msg_type]
            logger.debug(f"Callback kaldırıldı: {msg_type}")
    
    def send_command(self, command):
        """ESP32'ye komut gönder"""
        with self.lock:
            try:
                if self.ser and self.ser.is_open:
                    self.ser.write((command + '\n').encode('utf-8'))
                    logger.info(f"📤 ESP32'ye gönderildi: {command}")
                    return True
                else:
                    logger.warning(f"ESP32 bağlı değil: {command}")
                    return False
            except Exception as e:
                logger.error(f"Gönderme hatası: {e}")
                self.connected = False
                return False
    
    def close(self):
        """Bağlantıyı kapat"""
        self.stop_reading()
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                logger.info("✓ ESP32 kapatıldı")
        except:
            pass


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def on_current(value):
        print(f"Akım: {value} A")
    
    def on_power(value):
        print(f"Güç: {value} W")
    
    def on_pwm(value):
        print(f"🔌 PWM: {value} (0-255)")
    
    esp32 = ESP32Communication()
    esp32.register_callback('current', on_current)
    esp32.register_callback('power', on_power)
    esp32.register_callback('pwm', on_pwm)
    esp32.start_reading()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        esp32.close()