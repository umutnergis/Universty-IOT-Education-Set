#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODÜL 4: Ağırlık Ölçümü (DÜZELTILMIŞ)
- ESP32'den weight= verisi
- Ağırlık algılandığında SABİT sayıda ölçüm alındığında 1 kere API'ye POST
- wc_id = 4
- PWM/speed_rpm entegrasyonlu
- YENI: measurements_needed parametresi (default 8)
"""

import requests
import logging
from datetime import datetime
from config import API_ENDPOINTS, API_KEY, WC_IDS

logger = logging.getLogger(__name__)


class WeightModule:
    """Ağırlık Ölçüm Modülü"""
    
    def __init__(self, esp32_comm, measurements_needed=8):
        self.esp32 = esp32_comm
        self.wc_id = WC_IDS['weight']
        self.session_id = 0
        self.running = False
        
        # Ağırlık verileri
        self.current_weight = 0.0
        self.tare_value = 0.0
        
        # ✅ PWM değeri
        self.speed_rpm = 0
        
        # ✅ Ağırlık algılama durumu
        self.weight_detected = False  # Ağırlık > 0.5g mi?
        self.weight_sent = False      # Ağırlık gönderildi mi?
        
        # ✅ YENI: Sabit sayıda ölçüm sistemi
        self.measurements_needed = measurements_needed  # Kaç ölçüm lazım? (default: 8)
        self.measurement_list = []  # Ölçülen değerleri topla
        self.last_display_weight = 0.0  # Ekranda gösterilecek son ağırlık
        
        # İstatistikler
        self.min_weight = float('inf')
        self.max_weight = float('-inf')
        self.total_weight = 0.0
        self.measurement_count = 0
        
        # Callback'ler
        self.on_weight_update = None
        
        logger.info(f"Ağırlık Modülü oluşturuldu (wc_id={self.wc_id}, measurements_needed={measurements_needed})")
    
    def start(self, session_id):
        """Modülü başlat"""
        if self.running:
            logger.warning("Ağırlık modülü zaten çalışıyor")
            return False
        
        self.session_id = session_id
        self.running = True
        
        # ESP32 callback kaydet
        self.esp32.register_callback('weight', self._on_weight_received)
        
        # ✅ PWM callback'ini kaydet
        self.esp32.register_callback('pwm', self._on_pwm_changed)
        
        # İstatistikleri sıfırla
        self.reset_statistics()
        
        logger.info(f"✅ Ağırlık modülü başladı (session_id={session_id})")
        return True
    
    def stop(self):
        """Modülü durdur"""
        if not self.running:
            return False
        
        self.running = False
        
        # Callback'leri kaldır
        self.esp32.unregister_callback('weight')
        
        # ✅ PWM callback'ini kaldır
        self.esp32.unregister_callback('pwm')
        
        logger.info("⏹ Ağırlık modülü durdu")
        return True
    
    def _on_pwm_changed(self, value):
        """ESP32'den PWM mesajı geldiğinde"""
        if value is not None:
            self.speed_rpm = value
            logger.debug(f"⚡ PWM değeri güncellendi: {self.speed_rpm}")
    
    def _on_weight_received(self, value):
        """ESP32'den ağırlık verisi geldiğinde"""
        if not self.running:
            return
        
        # Ham değer
        raw_weight = value * 50
        
        # Tara düzeltmesi
        self.current_weight = raw_weight - self.tare_value
        
        logger.debug(f"⚖️ Ağırlık (ham): {self.current_weight:.1f} g")

        if self.current_weight > 0.5:
            
            if not self.weight_detected:
                # ✅ YENI ÜRÜN ALGILANDI
                self.weight_detected = True
                self.weight_sent = False
                self.measurement_list = []  # Yeni ölçümleri başlat
                self.last_display_weight = self.current_weight
                
                # ✅ ÖNEMLİ: İstatistikleri sıfırla (yeni ürün için)
                self.reset_statistics()
                
                logger.info(f"⚖️ Ağırlık algılandı: {self.current_weight:.1f} g (Ölçüm başlıyor...)")
            
            # ✅ Eğer henüz 8 ölçüm yapılmadıysa, ölçümleri topla
            if not self.weight_sent:
                # Ölçümü listeye ekle
                self.measurement_list.append(self.current_weight)
                self.last_display_weight = self.current_weight
                logger.debug(f"📊 Ölçüm: {len(self.measurement_list)}/{self.measurements_needed}")
                
                # İstatistikleri güncelle
                self._update_statistics(self.current_weight)
                
                # Eğer sabit sayıda ölçüm alındıysa API'ye GÖNDER
                if len(self.measurement_list) >= self.measurements_needed:
                    # Ortalama ağırlığı hesapla
                    average_weight = sum(self.measurement_list) / len(self.measurement_list)
                    
                    # ✅ ÖNEMLI: Ortalamayı ekrana sabit kıl
                    self.last_display_weight = average_weight
                    
                    logger.info(f"✅ {self.measurements_needed} ölçüm tamamlandı! Ortalama: {average_weight:.1f}g → API'ye gönderiliyor...")
                    wc_product_id = self._send_to_api_get_product_id()
                    self._send_to_api(wc_product_id=wc_product_id, weight_to_send=average_weight)
                    self.weight_sent = True
                    logger.info(f"✅ ORTALAMA EKRANA SABİT KALDI: {self.last_display_weight:.1f}g")
            else:
                # ✅ POST yapıldıktan sonra (weight_sent=True) yeni ölçümler ALINIYOR
                # FAKAT ekran DEĞİŞMİYOR - sabit kalıyor!
                logger.debug(f"⚠️ POST yapıldı, ekran sabit: {self.last_display_weight:.1f}g (ürün kaldırılana kadar)")
        else:
            # ✅ ÜRÜN KALDIRILDI
            if self.weight_detected:
                logger.info(f"⚖️ Ağırlık kaldırıldı: {self.current_weight:.1f} g")
                logger.info(f"✅ Ekran değeri sabit kaldı: {self.last_display_weight:.1f}g (Yeni ürün bekliyor)")
                self.weight_detected = False
                self.weight_sent = False
                self.measurement_list = []
        
        # GUI güncelle (her zaman mevcut/son değeri göster)
        if self.on_weight_update:
            if self.weight_detected:
                self.on_weight_update(self.last_display_weight)
            else:
                self.on_weight_update(0.0)
    
    def _update_statistics(self, weight):
        """İstatistikleri güncelle"""
        self.measurement_count += 1
        self.total_weight += weight
        
        if weight < self.min_weight:
            self.min_weight = weight
        
        if weight > self.max_weight:
            self.max_weight = weight

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
    
    def _send_to_api(self, wc_product_id=None, weight_to_send=None):
        """Ağırlık verisini API'ye gönder"""
        try:
            headers = {
                'apiKey': API_KEY, 
                'Content-Type': 'application/json'
            }
            
            # ✅ weight_to_send parametresi (ortalama ağırlık)
            data = {
                "session_id": self.session_id,
                "wc_id": self.wc_id,
                "quantity": weight_to_send if weight_to_send is not None else self.current_weight,
                "product_id": wc_product_id,
                "speed_rpm": self.speed_rpm  # ✅ PWM değeri
            }
            
            logger.debug(f"API POST: {data}")
            
            response = requests.post(
                API_ENDPOINTS['weight'],
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Weight API başarılı: {weight_to_send:.1f}g, Product ID: {wc_product_id}, Speed: {self.speed_rpm}")
            else:
                logger.warning(f"⚠️ Weight API hatası: HTTP {response.status_code}")
                logger.debug(f"Response: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error("❌ Weight API timeout")
        except Exception as e:
            logger.error(f"❌ Weight API hatası: {e}")
        
    def tare(self):
        """Tara al (sıfırlama)"""
        self.tare_value = self.current_weight + self.tare_value
        self.current_weight = 0.0
        
        # ✅ Ağırlık algılama durumunu sıfırla
        self.weight_detected = False
        self.weight_sent = False
        self.measurement_list = []
        self.last_display_weight = 0.0
        
        logger.info(f"Tara alındı: {self.tare_value:.1f} g")
        
        self.reset_statistics()
        
        if self.on_weight_update:
            self.on_weight_update(0.0)
    
    def reset_statistics(self):
        """İstatistikleri sıfırla"""
        self.min_weight = float('inf')
        self.max_weight = float('-inf')
        self.total_weight = 0.0
        self.measurement_count = 0
        logger.info("İstatistikler sıfırlandı")
    
    def get_statistics(self):
        """İstatistikleri döndür"""
        avg_weight = self.total_weight / self.measurement_count if self.measurement_count > 0 else 0.0
        
        return {
            'current': self.current_weight,
            'min': self.min_weight if self.min_weight != float('inf') else 0.0,
            'max': self.max_weight if self.max_weight != float('-inf') else 0.0,
            'average': avg_weight,
            'count': self.measurement_count,
            'speed_rpm': self.speed_rpm,  # ✅ PWM değeri
            'measurements_taken': len(self.measurement_list),  # ✅ YENI
            'measurements_needed': self.measurements_needed  # ✅ YENI
        }
    
    def get_weight(self):
        """Mevcut ağırlığı döndür"""
        return self.current_weight


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
    
    # ✅ measurements_needed=8 ile oluştur
    weight_module = WeightModule(esp32, measurements_needed=8)
    
    def on_weight(weight):
        stats = weight_module.get_statistics()
        print(f"📊 Ekran Ağırlığı: {weight:.1f} g | PWM: {stats['speed_rpm']} | Ölçüm: {stats['measurements_taken']}/{stats['measurements_needed']}")
    
    weight_module.on_weight_update = on_weight
    weight_module.start(session_id=123)  # ✅ BAŞLAT
    
    try:
        print("Ağırlık modülü çalışıyor... (Çıkmak için Ctrl+C)")
        print("Tara almak için: weight_module.tare()")
        print("\n📋 YENI DAVRANIŞ:")
        print("1. Ağırlık > 0.5g → 8 ölçüm al")
        print("2. 8 ölçüm tamamlandığında → Ortalama ağırlığı API'ye gönder (1 kere)")
        print("3. Ağırlık < 0.5g → Ekran değeri sabit kaldı (yeni ürün bekleniyor)")
        print("4. Yeni ürün > 0.5g → Tekrar 8 ölçüm al ve gönder\n")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        weight_module.stop()
        esp32.close()
        print("\nTest sonlandı")