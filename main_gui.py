#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import tkinter as tk
from tkinter import ttk, messagebox
import RPi.GPIO as GPIO
import logging
import requests
from threading import Thread
import time

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except:
    PIL_AVAILABLE = False

# Modüller
from esp32_comm import ESP32Communication
from nfc_reader import NFCReader
from module_power import PowerModule
from module_production import ProductionModule
from module_color import ColorModule
from module_fault import FaultModule
from module_weight import WeightModule
from module_conveyor import ConveyorModule
from module_ocr import OCRModule
from module_metal import MetalModule

from config import *

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class MainGUI:
    """Ana GUI ve Modül Yöneticisi"""
    
    def __init__(self):
        # Tkinter root
        self.root = tk.Tk()
        self.root.title("MES Eğitim Sistemi")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#2c3e50')
        self.root.bind('<Escape>', lambda e: self.exit_application())
        
        # GPIO Setup
        self.buzzer_pwm = None  # ÖNEMLİ: Önce None olarak tanımla
        self.setup_gpio()
        
        # Donanım bağlantıları
        self.esp32 = ESP32Communication(UART_PORT, UART_BAUDRATE)
        self.esp32.start_reading()
        
        self.nfc = NFCReader()
        self.nfc.on_card_detected = self.on_nfc_card_detected
        self.nfc.start_reading()
        
        # Modüller
        self.modules = {
            'power': PowerModule(self.esp32),
            'production': ProductionModule(self.esp32),
            'color': ColorModule(self.esp32),
            'fault': FaultModule(self.esp32),
            'weight': WeightModule(self.esp32),
            'conveyor': ConveyorModule(self.esp32),
            'ocr': OCRModule(self.esp32),
            'metal': MetalModule(self.esp32)
        }
        
        # Session yönetimi
        self.current_session_id = None
        self.current_card_id = None
        self.session_active = False
        
        # Aktif modül
        self.active_module = None
        self.active_module_name = None
        
        # GUI oluştur
        self.create_gui()
        
        logger.info("Ana sistem başlatıldı")
    
    def setup_gpio(self):
        """GPIO pinlerini ayarla"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            GPIO.setup(START_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.setup(STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.setup(RELAY_PIN, GPIO.OUT)
            
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            self.buzzer_pwm = GPIO.PWM(BUZZER_PIN, 1000)
            self.buzzer_pwm.start(0)
            
            GPIO.output(RELAY_PIN, GPIO.LOW)
            self.last_start = GPIO.LOW
            self.last_stop = GPIO.LOW
            Thread(target=self.button_polling, daemon=True).start()
            
            logger.info("✓ GPIO hazır")
        except Exception as e:
            logger.error(f"❌ GPIO hatası: {e}")
            self.buzzer_pwm = None  # Hata olursa None bırak
    
    def button_polling(self):
        """Fiziksel buton kontrolü"""
        while True:
            try:
                # START butonu
                start = GPIO.input(START_PIN)
                if start == GPIO.HIGH and self.last_start == GPIO.LOW:
                    logger.info("🔵 START butonu")
                    if self.active_module_name and not self.active_module:
                        self.root.after(0, self.start_current_module)
                self.last_start = start
                
                # STOP butonu
                stop = GPIO.input(STOP_PIN)
                if stop == GPIO.HIGH and self.last_stop == GPIO.LOW:
                    logger.info("🔴 STOP butonu")
                    if self.active_module:
                        self.root.after(0, self.stop_current_module)
                self.last_stop = stop
                
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Button polling hatası: {e}")
                time.sleep(0.1)
    
    def buzzer_beep(self, duration=0.2, repeat=1):
        """Buzzer ses - Güvenli versiyon"""
        if self.buzzer_pwm is None:
            logger.warning("⚠️ Buzzer PWM mevcut değil")
            return
        pwm = self.buzzer_pwm
        
        def beep():
            try:
                for _ in range(repeat):
                    pwm.ChangeDutyCycle(50)
                    time.sleep(duration)
                    pwm.ChangeDutyCycle(0)
                    if repeat > 1:
                        time.sleep(0.1)
            except Exception as e:
                logger.error(f"Buzzer hatası: {e}")
                
        Thread(target=beep, daemon=True).start()
        
    def create_gui(self):
        """Ana GUI yapısı"""
        # Ana container
        main = tk.Frame(self.root, bg='#2c3e50')
        main.pack(fill=tk.BOTH, expand=True)
        
        # Sol menü
        self.create_menu(main)
        
        # Sağ içerik alanı
        self.content_frame = tk.Frame(main, bg='#ecf0f1')
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Ana sayfa göster
        self.show_home()
    
    def create_menu(self, parent):
        """Sol menü paneli"""
        menu = tk.Frame(parent, bg='#34495e', width=250)
        menu.pack(side=tk.LEFT, fill=tk.Y)
        menu.pack_propagate(False)
        
        # Başlık
        tk.Label(menu, text="EĞİTİM SİSTEMİ\nMODÜLLER", 
                font=("Arial", 14, "bold"), bg='#34495e', fg='white',
                pady=10).pack(fill=tk.X)
        
        # Donanım durumu
        esp32_text = "✓ SİSTEM KONTROL" if self.esp32.connected else "✗ SİSTEM KONTROL"
        esp32_color = '#27ae60' if self.esp32.connected else '#e74c3c'
        tk.Label(menu, text=esp32_text, font=("Arial", 8, "bold"),
                bg='#34495e', fg=esp32_color).pack(pady=2)
        
        nfc_text = "✓ NFC" if self.nfc.pn532 else "✗ NFC"
        nfc_color = '#27ae60' if self.nfc.pn532 else '#e74c3c'
        tk.Label(menu, text=nfc_text, font=("Arial", 8, "bold"),
                bg='#34495e', fg=nfc_color).pack(pady=2)
        
        # Session durumu
        self.session_label = tk.Label(menu, text="❌ Session Yok", 
                                     font=("Arial", 8, "bold"),
                                     bg='#34495e', fg='#e74c3c')
        self.session_label.pack(pady=3)
        
        # Son okunan kart ID
        self.card_id_label = tk.Label(menu, text="Kart ID: -", 
                                     font=("Arial", 7),
                                     bg='#34495e', fg='#95a5a6')
        self.card_id_label.pack(pady=1)
        
        tk.Frame(menu, bg='#7f8c8d', height=1).pack(fill=tk.X, pady=5)
        
        # Modül butonları
        modules = [
            ("🏠 Ana Sayfa", "home", "#3498db"),
            ("⚡ Akım & Güç", "power", MODULE_COLORS['power']),
            ("⚡ Enerji Üretimi", "production", MODULE_COLORS['production']),
            ("🎨 Renk Algılama", "color", MODULE_COLORS['color']),
            ("⚠️ Arıza Tespit", "fault", MODULE_COLORS['fault']),
            ("⚖️ Ağırlık Ölçüm", "weight", MODULE_COLORS['weight']),
            ("📦 Konveyör", "conveyor", MODULE_COLORS['conveyor']),
            ("🔩 Metal Algılama", "metal", MODULE_COLORS['metal']),
            ("🔍 OCR Okuma", "ocr", MODULE_COLORS['ocr']),
        ]
        
        self.menu_buttons = {}
        for text, mod_id, color in modules:
            btn = tk.Button(menu, text=text, font=("Arial", 11, "bold"),
                          bg=color, fg='white', relief=tk.FLAT,
                          command=lambda m=mod_id: self.switch_module(m),
                          height=1, cursor="hand2")
            btn.pack(fill=tk.X, padx=8, pady=3)
            self.menu_buttons[mod_id] = btn
        
        # Alt bilgi
        tk.Label(menu, text="\nNACİ TOPÇUOĞLU ÜNİVERSİTESİ\nMühendislik Fakültesi", 
                font=("Arial", 8), bg='#34495e', fg='#95a5a6',
                justify=tk.CENTER).pack(side=tk.BOTTOM, pady=5)
        
        # Çıkış
        tk.Button(menu, text="❌ ÇIKIŞ", font=("Arial", 10, "bold"),
                 bg='#c0392b', fg='white', relief=tk.FLAT,
                 command=self.exit_application, height=1).pack(
                 side=tk.BOTTOM, fill=tk.X, padx=8, pady=5)
        
    def switch_module(self, module_name):
        """Modül değiştir - Session state'ini tamamen sıfırla"""
        
        # Çalışan modül varsa durdur
        if self.active_module:
            if not messagebox.askyesno("Uyarı", 
                                    "Çalışan modül var! Durdurup devam edilsin mi?"):
                return
            self.stop_current_module()
        
        # ✅ Session varsa kapat ve STATE'İ TAMAMEN SIFIRLA
        if self.session_active:
            logger.info("ℹ️ Modül değişiyor, session kapatılıyor")
            self.stop_session()
            
            # 🎯 KRİTİK: State'i tamamen sıfırla
            self.session_active = False
            self.current_session_id = None
            self.current_card_id = None
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
            
            # 🔑 KRİTİK FİX: NFC okuyucunun kart hafızasını temizle
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False
            
            logger.info("✅ Session state ve NFC hafızası temizlendi")
        
        # ✅ Modül ismini değiştir
        self.active_module_name = module_name
        logger.info(f"📍 Aktif modül: {module_name}")
        
        # İçeriği temizle
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Yeni modülü göster
        if module_name == "home":
            self.show_home()
        elif module_name == "power":
            self.show_power_module()
        elif module_name == "production":
            self.show_production_module()
        elif module_name == "color":
            self.show_color_module()
        elif module_name == "fault":
            self.show_fault_module()
        elif module_name == "weight":
            self.show_weight_module()
        elif module_name == "conveyor":
            self.show_conveyor_module()
        elif module_name == "metal":
            self.show_metal_module()
        elif module_name == "ocr":
            self.show_ocr_module()
        
        logger.info(f"✅ {module_name.upper()} modülü hazır, NFC kart bekliyor...")
    
    def show_home(self):
        home = tk.Frame(self.content_frame, bg='#ecf0f1')
        home.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(home, text="🎓 ENDÜSTRİYEL EĞİTİM SİSTEMİ", 
                font=("Arial", 20, "bold"), bg='#ecf0f1', fg='#2c3e50',
                pady=15).pack()
        
        info = """
        Modüler Eğitim Sistemi
        
        ⚡ AKIM & GÜÇ (wc_id=1)
        - Akım ve güç ölçümü (tüketim)
        - Otomatik API entegrasyonu
        
        ⚡ ENERJİ ÜRETİMİ (wc_id=1)
        - Enerji üretimi ölçümü
        - ESP32: uretima= ve uretimw=
        
        📦 KONVEYÖR (wc_id=2)
        - Ürün geçiş sayımı
        - Hız analizi

        ⚠️ ARIZA TESPİT (wc_id=3)
        - Yangın, ses, titreşim sensörleri
        - Anlık uyarı sistemi
        
        ⚖️ AĞIRLIK ÖLÇÜM (wc_id=4)
        - Hassas tartım
        - İstatistiksel analiz

        🎨 RENK ALGILAMA (wc_id=5)
        - Kamera ile renk algılama
        - Otomatik ürün sayımı
        
        🔍 OCR OKUMA (Session Gerekmez)
        - Kamera ile yazı algılama
        - MANUEL OKUMA: OKU butonuna bas
        - Tesseract OCR motoru
        
        
        🔑 Her modül (OCR hariç) NFC kart gerektirir
        
        Sol menüden modül seçin!
        """
        
        tk.Label(home, text=info, font=("Arial", 10), 
                bg='#ecf0f1', fg='#34495e', justify=tk.LEFT,
                pady=10).pack()
    
    def show_power_module(self):
        """Güç modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text=" AKIM & GÜÇ", 
                font=("Arial", 18, "bold"), bg='#ecf0f1', 
                fg=MODULE_COLORS['power']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=12,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=12,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3)
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        cur_frame = tk.LabelFrame(display, text="AKIM (A)", 
                                 font=("Arial", 12, "bold"), bg='white')
        cur_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        self.power_current_label = tk.Label(cur_frame, text="0.00", 
                                           font=("Arial", 36, "bold"),
                                           bg='white', fg='#e74c3c')
        self.power_current_label.pack(pady=15)
        
        pow_frame = tk.LabelFrame(display, text="GÜÇ (W)", 
                                 font=("Arial", 12, "bold"), bg='white')
        pow_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        self.power_power_label = tk.Label(pow_frame, text="0.00", 
                                          font=("Arial", 36, "bold"),
                                          bg='white', fg='#27ae60')
        self.power_power_label.pack(pady=15)
        
        def update_power(data_type, value):
            if data_type == 'current':
                self.power_current_label.config(text=f"{value:.2f}")
            elif data_type == 'power':
                self.power_power_label.config(text=f"{value:.2f}")
        
        self.modules['power'].on_data_update = update_power
    
    def show_production_module(self):
        """Enerji Üretimi modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text="⚡ ENERJİ ÜRETİMİ", 
                font=("Arial", 18, "bold"), bg='#ecf0f1', 
                fg=MODULE_COLORS['production']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=12,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=12,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3)
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        cur_frame = tk.LabelFrame(display, text="ÜRETİLEN AK IM (A)", 
                                 font=("Arial", 12, "bold"), bg='white')
        cur_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        self.production_current_label = tk.Label(cur_frame, text="0.00", 
                                           font=("Arial", 36, "bold"),
                                           bg='white', fg='#f39c12')
        self.production_current_label.pack(pady=15)
        
        pow_frame = tk.LabelFrame(display, text="ÜRETİLEN GÜÇ (W)", 
                                 font=("Arial", 12, "bold"), bg='white')
        pow_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        self.production_power_label = tk.Label(pow_frame, text="0.00", 
                                          font=("Arial", 36, "bold"),
                                          bg='white', fg='#e67e22')
        self.production_power_label.pack(pady=15)
        
        def update_production(data_type, value):
            if data_type == 'production_current':
                self.production_current_label.config(text=f"{value:.2f}")
            elif data_type == 'production_power':
                self.production_power_label.config(text=f"{value:.2f}")
        
        self.modules['production'].on_data_update = update_production
    
    def show_color_module(self):
        """Renk modülü GUI - Renk seçimi ve kamera görüntüsü ile"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text="🎨 RENK ALGILAMA", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['color']).pack(pady=5)
        
        # Üst alan: Kontroller ve Renk Seçimi
        top_frame = tk.Frame(frame, bg='#ecf0f1')
        top_frame.pack(fill=tk.X, pady=5)
        
        # Sol: Kontrol butonları
        control = tk.Frame(top_frame, bg='#ecf0f1')
        control.pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                bg='#27ae60', fg='white', width=10,
                command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                bg='#e74c3c', fg='white', width=10,
                command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="🔄 SIFIRLA", font=("Arial", 10, "bold"),
                bg='#f39c12', fg='white', width=8,
                command=lambda: self.modules['color'].reset_counter()).pack(side=tk.LEFT, padx=5)
        
        # Sağ: Renk seçimi
        color_frame = tk.LabelFrame(top_frame, text="RENK SEÇİMİ", 
                                font=("Arial", 10, "bold"), bg='#ecf0f1')
        color_frame.pack(side=tk.RIGHT, padx=10)
        
        colors = [
            (" Kırmızı", "Kırmızı", "#e74c3c"),
            (" Sarı", "Sarı", "#fff203"),
            (" Mavi", "Mavi", "#3498db")
        ]
        
        self.color_selection_var = tk.StringVar(value="Kırmızı")
        self.color_buttons = {}
        
        for text, color_name, color_code in colors:
            btn = tk.Radiobutton(color_frame, text=text, 
                            variable=self.color_selection_var,
                            value=color_name,
                            font=("Arial", 10, "bold"),
                            bg='#ecf0f1', fg=color_code,
                            selectcolor='#bdc3c7',
                            command=lambda c=color_name: self.on_color_selected(c))
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.color_buttons[color_name] = btn
        
        # Ana görüntü alanı: Sol kamera, Sağ sayaç
        display_frame = tk.Frame(frame, bg='#ecf0f1')
        display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Sol: Kamera görüntüsü
        camera_container = tk.LabelFrame(display_frame, text="KAMERA GÖRÜNTÜSÜ",
                                        font=("Arial", 12, "bold"), bg='white',
                                        relief=tk.RIDGE, bd=3)
        camera_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.color_camera_label = tk.Label(camera_container, bg='black', 
                                        text="Kamera Yükleniyor...",
                                        font=("Arial", 12),
                                        fg='white')
        self.color_camera_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sağ: Ürün sayacı
        counter_frame = tk.LabelFrame(display_frame, text="ÜRÜN SAYACI",
                                    font=("Arial", 12, "bold"), bg='white',
                                    relief=tk.RIDGE, bd=3)
        counter_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        tk.Label(counter_frame, text="Algılanan Ürün", 
                font=("Arial", 12, "bold"), bg='white',
                fg=MODULE_COLORS['color']).pack(pady=10)
        
        self.color_count_label = tk.Label(counter_frame, text="0", 
                                        font=("Arial", 56, "bold"),
                                        bg='white', fg='#2c3e50')
        self.color_count_label.pack(pady=30)
        
        self.color_selected_label = tk.Label(counter_frame, 
                                            text="Seçili Renk:\n🔴 Kırmızı",
                                            font=("Arial", 11, "bold"), 
                                            bg='#ecf0f1', fg='#e74c3c')
        self.color_selected_label.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        def update_count(count):
            self.color_count_label.config(text=str(count))
        
        self.modules['color'].on_count_update = update_count
        
        # Kamera güncelleme döngüsünü başlat
        self.update_color_camera()

    def show_fault_module(self):
        """Arıza modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text=" ARIZA TESPİT", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['fault']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=10,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=10,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="🧹 TEMİZLE", font=("Arial", 10, "bold"),
                 bg='#f39c12', fg='white', width=8,
                 command=lambda: self.modules['fault'].clear_all_faults()).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='#ecf0f1')
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        fire_frame = tk.LabelFrame(display, text="🔥 YANGIN", 
                                  font=("Arial", 12, "bold"), bg='white',
                                  relief=tk.RIDGE, bd=3)
        fire_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        
        self.fault_fire_label = tk.Label(fire_frame, text="✓ Normal", 
                                         font=("Arial", 20, "bold"),
                                         bg='#27ae60', fg='white',
                                         relief=tk.RAISED, bd=5)
        self.fault_fire_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        voice_frame = tk.LabelFrame(display, text="🔊 SES", 
                                   font=("Arial", 12, "bold"), bg='white',
                                   relief=tk.RIDGE, bd=3)
        voice_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        
        self.fault_voice_label = tk.Label(voice_frame, text="✓ Normal", 
                                          font=("Arial", 20, "bold"),
                                          bg='#27ae60', fg='white',
                                          relief=tk.RAISED, bd=5)
        self.fault_voice_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vib_frame = tk.LabelFrame(display, text="📳 TİTREŞİM", 
                                 font=("Arial", 12, "bold"), bg='white',
                                 relief=tk.RIDGE, bd=3)
        vib_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        
        self.fault_vib_label = tk.Label(vib_frame, text="✓ Normal", 
                                        font=("Arial", 20, "bold"),
                                        bg='#27ae60', fg='white',
                                        relief=tk.RAISED, bd=5)
        self.fault_vib_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        def update_fault(fault_type, active):
            if fault_type == 'fire':
                if active:
                    self.fault_fire_label.config(bg='#e74c3c', text="🔥 YANGIN!")
                    self.buzzer_beep(duration=0.3, repeat=3)
                else:
                    self.fault_fire_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'voice':
                if active:
                    self.fault_voice_label.config(bg='#e74c3c', text="🔊 SES!")
                    self.buzzer_beep(duration=0.2, repeat=2)
                else:
                    self.fault_voice_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'vibration':
                if active:
                    self.fault_vib_label.config(bg='#e74c3c', text="📳 TİTREŞİM!")
                    self.buzzer_beep(duration=0.2, repeat=2)
                else:
                    self.fault_vib_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'all':
                self.fault_fire_label.config(bg='#27ae60', text="✓ Normal")
                self.fault_voice_label.config(bg='#27ae60', text="✓ Normal")
                self.fault_vib_label.config(bg='#27ae60', text="✓ Normal")
        
        self.modules['fault'].on_fault_update = update_fault
    
    def show_weight_module(self):
        """Ağırlık modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text=" AĞIRLIK ÖLÇÜMÜ ", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['weight']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=10,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=10,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⚖️ TARA", font=("Arial", 10, "bold"),
                 bg='#f39c12', fg='white', width=8,
                 command=lambda: self.modules['weight'].tare()).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3)
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        weight_frame = tk.Frame(display, bg='white')
        weight_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.weight_label = tk.Label(weight_frame, text="0.0", 
                                     font=("Arial", 64, "bold"),
                                     bg='white', fg='#27ae60')
        self.weight_label.pack()
        
        tk.Label(weight_frame, text="gram (g)", 
                font=("Arial", 16), bg='white', fg='#7f8c8d').pack(pady=5)
        
        stats_frame = tk.Frame(display, bg='white')
        stats_frame.pack(fill=tk.X, padx=15, pady=8)
        
        self.weight_stats_label = tk.Label(stats_frame, 
                                           text="Min: 0.0g | Max: 0.0g | Ort: 0.0g | Ölçüm: 0", 
                                           font=("Arial", 10),
                                           bg='white', fg='#7f8c8d')
        self.weight_stats_label.pack()
        
        def update_weight(weight):
            self.weight_label.config(text=f"{weight:.1f}")
            stats = self.modules['weight'].get_statistics()
            self.weight_stats_label.config(
                text=f"Min: {stats['min']:.1f}g | Max: {stats['max']:.1f}g | "
                     f"Ort: {stats['average']:.1f}g | Ölçüm: {stats['count']}"
            )
        
        self.modules['weight'].on_weight_update = update_weight
    
    def show_conveyor_module(self):
        """Konveyör modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text=" KONVEYÖR SİSTEMİ", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['conveyor']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=10,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=10,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="🔄 SIFIRLA", font=("Arial", 10, "bold"),
                 bg='#f39c12', fg='white', width=8,
                 command=lambda: self.modules['conveyor'].reset_counter()).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3)
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        count_frame = tk.Frame(display, bg='white')
        count_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        tk.Label(count_frame, text="GEÇEN ÜRÜN", 
                font=("Arial", 14, "bold"), bg='white',
                fg=MODULE_COLORS['conveyor']).pack(pady=8)
        
        self.conveyor_count_label = tk.Label(count_frame, text="0", 
                                             font=("Arial", 64, "bold"),
                                             bg='white', fg='#3498db')
        self.conveyor_count_label.pack(pady=15)
        
        stats_frame = tk.Frame(display, bg='#ecf0f1', relief=tk.SUNKEN, bd=2)
        stats_frame.pack(fill=tk.X, padx=15, pady=8)
        
        self.conveyor_stats_label = tk.Label(stats_frame, 
                                             text="Süre: 0s | Hız: 0 ürün/dk", 
                                             font=("Arial", 11, "bold"),
                                             bg='#ecf0f1', fg='#2c3e50')
        self.conveyor_stats_label.pack(pady=10)
        
        def update_conveyor(count):
            self.conveyor_count_label.config(text=str(count))
            stats = self.modules['conveyor'].get_statistics()
            self.conveyor_stats_label.config(
                text=f"Süre: {stats['runtime']:.1f}s | "
                     f"Hız: {stats['rate_per_minute']:.1f} ürün/dk"
            )
        
        self.modules['conveyor'].on_item_detected = update_conveyor
        
    def show_metal_module(self):
        """Metal Algılama modülü GUI"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text="🔩 METAL ALGILAMA", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['metal']).pack(pady=5)
        
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=10,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⏹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=10,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="🔄 SIFIRLA", font=("Arial", 10, "bold"),
                 bg='#f39c12', fg='white', width=8,
                 command=lambda: self.modules['metal'].reset_counter()).pack(side=tk.LEFT, padx=5)
        
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3)
        display.pack(fill=tk.BOTH, expand=True, pady=10)
        
        count_frame = tk.Frame(display, bg='white')
        count_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        tk.Label(count_frame, text="ALGILANAN METAL", 
                font=("Arial", 14, "bold"), bg='white',
                fg=MODULE_COLORS['metal']).pack(pady=8)
        
        self.metal_count_label = tk.Label(count_frame, text="0", 
                                          font=("Arial", 64, "bold"),
                                          bg='white', fg='#77a016')
        self.metal_count_label.pack(pady=15)
        
        stats_frame = tk.Frame(display, bg='#ecf0f1', relief=tk.SUNKEN, bd=2)
        stats_frame.pack(fill=tk.X, padx=15, pady=8)
        
        self.metal_stats_label = tk.Label(stats_frame, 
                                          text="Süre: 0s | Hız: 0 metal/dk", 
                                          font=("Arial", 11, "bold"),
                                          bg='#ecf0f1', fg='#2c3e50')
        self.metal_stats_label.pack(pady=10)
        
        def update_metal(count):
            self.metal_count_label.config(text=str(count))
            stats = self.modules['metal'].get_statistics()
            self.metal_stats_label.config(
                text=f"Süre: {stats['runtime']:.1f}s | "
                     f"Hız: {stats['rate_per_minute']:.1f} metal/dk"
            )
        
        self.modules['metal'].on_metal_detected = update_metal

    def on_nfc_card_detected(self, card_id):
        """NFC kart algılandığında - STRICT versiyon + Hata İyileştirmesi"""
        try:
            logger.info(f"✓ NFC: {card_id}")
            self.current_card_id = card_id
            self.card_id_label.config(text=f"Kart ID: {card_id}")
            self.buzzer_beep(duration=0.1, repeat=2)
            
            # Session yoksa başlat
            if not self.session_active:
                success = self.start_session(card_id)
                
                # ❌ Session başlatılamadıysa, kart hafızasını temizle ve yeniden oku
                if not success:
                    logger.info("🔄 Kart hafızası temizleniyor, tekrar okuma için hazır...")
                    time.sleep(0.5)
                    
                    # NFC hafızasını temizle
                    self.nfc.last_card_id = ""
                    self.nfc.current_card_id = ""
                    self.nfc.card_present = False
                    self.current_card_id = None
                    self.card_id_label.config(text="Kart ID: -")
                    
                    logger.info("✅ Hafıza temizlendi. Kartı tekrar okutabilirsiniz.")
                
            else:
                logger.info(f"ℹ️ Session zaten aktif (ID: {self.current_session_id})")
                messagebox.showinfo("Bilgi", 
                    f"Session zaten aktif!\n\nSession ID: {self.current_session_id}")
        
        except Exception as e:
            logger.error(f"❌ NFC card detected handler error: {e}")
            # Hata olsa bile NFC hafızasını temizle
            try:
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
            except:
                pass
    
    def start_session(self, card_id):
        """Session başlat - STRICT versiyon"""
        try:
            # Modül kontrolü
            if not self.active_module_name or self.active_module_name == 'home':
                logger.error("❌ Önce bir modül seçin!")
                messagebox.showerror("Hata", "Önce bir modül seçmelisiniz!")
                return False
            
            # WC_ID al
            wc_id = WC_IDS.get(self.active_module_name, 0)
            if wc_id == 0:
                logger.error(f"❌ Modül için wc_id bulunamadı: {self.active_module_name}")
                messagebox.showerror("Hata", f"Modül WC_ID bulunamadı!")
                return False
            
            # API Request - Session başlat
            url = API_ENDPOINTS['session_start']
            headers = {"apiKey": API_KEY}
            params = {
                "card_uid": card_id,
                "wc_id": wc_id
            }
            
            logger.info(f"📤 Session başlatılıyor: card={card_id}, wc_id={wc_id}")
            
            response = requests.post(url, params=params, headers=headers, timeout=10)
            
            logger.debug(f"📥 Response Status: {response.status_code}")
            
            if response.status_code not in [200, 201, 501]:
                logger.error(f"❌ Session başlatılamadı: HTTP {response.status_code}")
                messagebox.showerror("Hata", 
                    f"Session başlatılamadı!\nHTTP {response.status_code}\n\nLütfen API bağlantısını kontrol edin.")
                return False
            
            # ✅ Session başarıyla başladı, şimdi ID'yi almayı dene
            logger.info("⏳ API'nin session'ı kaydetmesi bekleniyor...")
            time.sleep(1.5)  # API'ye kaydetme zamanı ver
            
            # Session ID'yi al - KRİTİK NOKTA
            if not self.get_session_id(wc_id):
                logger.error("❌ Session başladı ama ID alınamadı!")
                messagebox.showerror("Kritik Hata", 
                    "Session başlatıldı ancak Session ID alınamadı!\n\n"
                    "Sistem başlatılamıyor. Lütfen tekrar deneyin.")
                
                # Session'ı kapat çünkü ID alamadık
                try:
                    requests.post(API_ENDPOINTS['session_end'], 
                                params={"session_id": 0}, 
                                headers=headers, timeout=5)
                except:
                    pass
                
                return False
            
            # ✅ HER İKİSİ DE BAŞARILI - Session aktif
            self.session_active = True
            self.session_label.config(text=f"✅ Session: {self.current_session_id}", fg='#27ae60')
            logger.info(f"✅ Session TAMAMEN başarılı: ID={self.current_session_id}, WC={wc_id}, Kart={card_id}")
            
            return True
                    
        except requests.exceptions.Timeout:
            logger.error("❌ Session başlatma timeout!")
            messagebox.showerror("Timeout", "API'ye bağlanılamadı (timeout)!")
            return False
        except Exception as e:
            logger.error(f"❌ Session error: {e}")
            messagebox.showerror("Hata", f"Session başlatılamadı:\n{str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_session_id(self, wc_id=None):
        """API'den session ID al - STRICT versiyon + NFC Cleanup"""
        response = None
        
        try:
            if wc_id is None:
                wc_id = WC_IDS.get(self.active_module_name, 0)
            
            headers = {'apiKey': API_KEY, 'Accept': 'application/json'}
            params = {'wcId': wc_id}
            
            logger.info(f"📤 Session ID isteniyor: wc_id={wc_id}")
            
            response = requests.get(
                API_ENDPOINTS['session_id'], 
                params=params, 
                headers=headers, 
                timeout=10
            )
            
            logger.debug(f"📥 Status: {response.status_code}, Body: '{response.text}'")
            
            if response.status_code != 200:
                logger.error(f"❌ Session ID API hatası: HTTP {response.status_code}")
                # 🔑 NFC hafızasını temizle
                self._cleanup_nfc_memory()
                return False
            
            # API direkt integer döndürüyor
            session_id = int(response.json())
            
            if session_id <= 0:
                logger.error(f"❌ Geçersiz Session ID: {session_id}")
                # 🔑 NFC hafızasını temizle
                self._cleanup_nfc_memory()
                return False
            
            # ✅ Geçerli ID alındı
            self.current_session_id = session_id
            logger.info(f"✅ Session ID alındı: {self.current_session_id}")
            return True
                    
        except ValueError as e:
            logger.error(f"❌ Session ID parse hatası: {e}")
            if response:
                logger.error(f"Response: '{response.text}'")
            # 🔑 NFC hafızasını temizle
            self._cleanup_nfc_memory()
            return False
        except Exception as e:
            logger.error(f"❌ Session ID hatası: {type(e).__name__}: {e}")
            if response:
                logger.error(f"Response: '{response.text}'")
            # 🔑 NFC hafızasını temizle
            self._cleanup_nfc_memory()
            return False
        
    def _cleanup_nfc_memory(self):
        """NFC hafızasını temizle - Yardımcı metod"""
        try:
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False
            logger.info("🔄 NFC hafızası temizlendi")
        except Exception as e:
            logger.warning(f"⚠️ NFC hafızası temizlenirken hata: {e}")
        
    def stop_session(self):
        """Session'ı sonlandır - İyileştirilmiş versiyon"""
        try:
            if not self.session_active:
                logger.warning("⚠️ Aktif session yok")
                # 🎯 Yine de state'i temizle
                self.current_session_id = None
                self.current_card_id = None
                self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
                self.card_id_label.config(text="Kart ID: -")
                
                # 🔑 NFC hafızasını da temizle
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
                
                return True
            
            if not self.current_session_id or self.current_session_id == 0:
                logger.warning("⚠️ Session ID yok, direkt kapatılıyor")
                # ✅ State'i temizle
                self.session_active = False
                self.current_session_id = None
                self.current_card_id = None
                self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
                
                # 🔑 NFC hafızasını da temizle
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
                
                return True
            
            url = API_ENDPOINTS['session_end']
            headers = {"apiKey": API_KEY}
            params = {"session_id": self.current_session_id}
            
            logger.info(f"📤 Session sonlandırılıyor: ID={self.current_session_id}")
            response = requests.post(url, params=params, headers=headers, timeout=10)
            
            logger.debug(f"📥 End Session Status: {response.status_code}")
            
            if response.status_code in [200, 201, 501]:
                # ✅ State'i TAMAMEN temizle
                self.session_active = False
                self.current_session_id = None
                self.current_card_id = None
                self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
                self.card_id_label.config(text="Kart ID: -")
                
                # 🔑 NFC hafızasını da temizle
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
                
                logger.info("✅ Session sonlandırıldı")
                return True
            else:
                logger.error(f"❌ Session sonlandırma hatası: {response.status_code}")
                
                # 🎯 API hatası olsa bile local state'i temizle
                self.session_active = False
                self.current_session_id = None
                self.current_card_id = None
                self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
                
                # 🔑 NFC hafızasını da temizle
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
                
                messagebox.showerror("Hata", 
                                f"Session sonlandırılamadı!\nHTTP {response.status_code}\n\nLocal state temizlendi.")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ Session end timeout")
            
            # 🎯 Timeout olsa bile local state'i temizle
            self.session_active = False
            self.current_session_id = None
            self.current_card_id = None
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
            
            # 🔑 NFC hafızasını da temizle
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False
            
            return False
        except Exception as e:
            logger.error(f"❌ Session end error: {e}")
            
            # 🎯 Her türlü hatada local state'i temizle
            self.session_active = False
            self.current_session_id = None
            self.current_card_id = None
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
            
            # 🔑 NFC hafızasını da temizle
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False
            
            return False
    
    def start_current_module(self):
        """Aktif modülü başlat - STRICT versiyon + OCR özel durum"""
        
        # 📦 ÖZEL DURUM: OCR modülü session gerektirmez
        if self.active_module_name == 'ocr':
            if self.active_module:
                logger.warning("⚠️ OCR modülü zaten çalışıyor!")
                messagebox.showwarning("Uyarı", "OCR modülü zaten çalışıyor!")
                return
            
            module_to_start = self.modules.get('ocr')
            if module_to_start:
                logger.info("▶ OCR modülü başlatılıyor (session gerekmez)")
                
                if module_to_start.start():
                    self.active_module = module_to_start
                    self.buzzer_beep(duration=0.1, repeat=1)
                    logger.info("✅ OCR modülü başlatıldı!")
                    messagebox.showinfo("Başarılı", "OCR modülü başlatıldı!")
                else:
                    logger.error("❌ OCR modülü başlatılamadı!")
                    messagebox.showerror("Hata", "OCR modülü başlatılamadı!\n\nTesseract kurulu mu?")
            return
        
        # 🔑 DIĞER MODÜLLER: Session gerekir
        
        # 1️⃣ Session kontrolü - MUTLAKA OLMALI
        if not self.session_active:
            logger.error("❌ Session aktif değil!")
            messagebox.showerror("Hata", "Session başlatılmadı!\n\nLütfen önce NFC kart okutun.")
            return
        
        # 2️⃣ Kart bilgisi kontrolü
        if not self.current_card_id:
            logger.error("❌ NFC kart bilgisi yok!")
            messagebox.showerror("Hata", "NFC kart bilgisi bulunamadı!")
            return
        
        # 3️⃣ Session ID kontrolü - KRİTİK
        if not self.current_session_id or self.current_session_id <= 0:
            logger.error(f"❌ Session ID geçersiz: {self.current_session_id}")
            messagebox.showerror("Kritik Hata", 
                f"Session ID geçersiz veya yok!\n\n"
                f"Mevcut ID: {self.current_session_id}\n\n"
                f"Sistem başlatılamıyor. Lütfen kartı tekrar okutun.")
            return
        
        # 4️⃣ Modül seçimi kontrolü
        if not self.active_module_name or self.active_module_name == 'home':
            logger.error("❌ Geçerli bir modül seçilmedi!")
            messagebox.showerror("Hata", "Lütfen önce bir modül seçin!")
            return
        
        # 5️⃣ Çift başlatma kontrolü
        if self.active_module:
            logger.warning("⚠️ Modül zaten çalışıyor!")
            messagebox.showwarning("Uyarı", "Modül zaten çalışıyor!")
            return
        
        # 6️⃣ Modülü al ve başlat
        module_to_start = self.modules.get(self.active_module_name)
        if not module_to_start:
            logger.error(f"❌ Modül bulunamadı: {self.active_module_name}")
            messagebox.showerror("Hata", "Modül bulunamadı!")
            return
        
        # ✅ TÜM KONTROLLER BAŞARILI - Modülü başlat
        logger.info(f"▶ Modül başlatılıyor: {self.active_module_name}")
        logger.info(f"   Session ID: {self.current_session_id}")
        logger.info(f"   Kart ID: {self.current_card_id}")
        
        if module_to_start.start(session_id=self.current_session_id):
            self.active_module = module_to_start
            self.buzzer_beep(duration=0.1, repeat=1)
            logger.info(f"✅ {self.active_module_name.upper()} başlatıldı!")
        else:
            logger.error("❌ Modül başlatılamadı!")
    
    def stop_current_module(self):
        """Aktif modülü durdur ve session'ı kapat"""
        if not self.active_module:
            logger.warning("⚠️ Çalışan modül yok!")
            return
        
        module_name = self.active_module_name
        
        # Önce modülü durdur
        logger.info(f"⏹ Modül durduruluyor: {module_name}")
        self.active_module.stop()
        self.active_module = None
        
        # Sonra session'ı kapat
        if self.session_active:
            if self.stop_session():
                self.buzzer_beep(duration=0.1, repeat=3)
                logger.info(f"✅ {module_name.upper()} durduruldu ve session sonlandırıldı!")
            else:
                logger.warning(f"⚠️ {module_name.upper()} durduruldu ama session sonlandırılamadı!")
        else:
            logger.info(f"✅ {module_name.upper()} durduruldu.")
    
    def exit_application(self):
        """Uygulamadan çık"""
        if messagebox.askokcancel("Çıkış", "Çıkmak istediğinize emin misiniz?"):
            try:
                # Aktif modülü durdur
                if self.active_module:
                    self.stop_current_module()
                
                # Donanımları kapat
                self.esp32.close()
                self.nfc.stop_reading()
                
                # Buzzer'ı kapat
                if self.buzzer_pwm:
                    self.buzzer_pwm.stop()
                
                # GPIO temizle
                GPIO.cleanup()
                
                # Pencereyi kapat
                self.root.destroy()
                logger.info("✅ Sistem kapatıldı")
                
            except Exception as e:
                logger.error(f"❌ Kapatma hatası: {e}")
                self.root.destroy()
    
    
    def on_color_selected(self, color_name):
        """Renk seçildiğinde"""
        self.modules['color'].set_color(color_name)
        
        # Label'ı güncelle
        color_icons = {
            "Kırmızı": ("🔴", "#e74c3c"),
            "Yeşil": ("🟢", "#27ae60"),
            "Mavi": ("🔵", "#3498db")
        }
        
        icon, color_code = color_icons.get(color_name, ("⚪", "#95a5a6"))
        self.color_selected_label.config(
            text=f"Seçili Renk:\n{icon} {color_name}",
            fg=color_code
        )
        
        logger.info(f"🎨 Renk seçildi: {color_name}")
    
    def update_color_camera(self):
        """Kamera görüntüsünü güncelle"""
        try:
            # Modül çalışıyorsa ve renk modülündeyse
            if (self.active_module_name == 'color' and 
                hasattr(self, 'color_camera_label') and 
                self.color_camera_label.winfo_exists()):
                
                # Frame al
                frame = self.modules['color'].get_camera_frame()
                
                if frame is not None:
                    # Boyutlandır (kamera alanına uygun)
                    height, width = frame.shape[:2]
                    max_width = 480
                    max_height = 360
                    
                    scale = min(max_width/width, max_height/height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    
                    import cv2
                    frame_resized = cv2.resize(frame, (new_width, new_height))
                    
                    # PIL Image'e çevir
                    from PIL import Image, ImageTk
                    img = Image.fromarray(frame_resized)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    # Göster
                    self.color_camera_label.config(image=photo, text="")
                    self.color_camera_label.image = photo  # Referansı tut
                
                # 30ms sonra tekrar çağır (30 FPS)
                self.root.after(30, self.update_color_camera)
                
        except Exception as e:
            logger.error(f"Kamera güncelleme hatası: {e}")
            # Hata olsa bile devam et
            if (self.active_module_name == 'color' and 
                hasattr(self, 'color_camera_label')):
                self.root.after(100, self.update_color_camera)
    
    def show_ocr_module(self):
        """OCR modülü GUI - Manuel okuma"""
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(frame, text="🔍 OCR YAZI ALGILAMA (MANUEL)", 
                font=("Arial", 18, "bold"), bg='#ecf0f1',
                fg=MODULE_COLORS['ocr']).pack(pady=5)
        
        # Kontrol butonları
        control = tk.Frame(frame, bg='#ecf0f1')
        control.pack(fill=tk.X, pady=5)
        
        tk.Button(control, text="▶ BAŞLAT", font=("Arial", 11, "bold"),
                 bg='#27ae60', fg='white', width=10,
                 command=self.start_current_module).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control, text="⎹ DURDUR", font=("Arial", 11, "bold"),
                 bg='#e74c3c', fg='white', width=10,
                 command=self.stop_current_module).pack(side=tk.LEFT, padx=5)
        
        # OKU butonu - BÜYÜK VE BELIRGIN
        self.ocr_read_button = tk.Button(control, text="📖 OKU", font=("Arial", 14, "bold"),
                 bg='#3498db', fg='white', width=12, height=1,
                 command=self.ocr_read_text,
                 relief=tk.RAISED, bd=3)
        self.ocr_read_button.pack(side=tk.LEFT, padx=10)
        
        tk.Button(control, text="🧹 TEMİZLE", font=("Arial", 10, "bold"),
                 bg='#f39c12', fg='white', width=8,
                 command=lambda: self.modules['ocr'].clear_text()).pack(side=tk.LEFT, padx=5)
        
        # Ana görüntü alanı - Üst: Kamera (küçük), Alt: Metin (büyük)
        display_frame = tk.Frame(frame, bg='#ecf0f1')
        display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Üst: Kamera görüntüsü (KÜÇÜLTÜLDÜ - 40% yükseklik)
        camera_container = tk.LabelFrame(display_frame, text="KAMERA GÖRÜNTÜSÜ",
                                        font=("Arial", 12, "bold"), bg='white',
                                        relief=tk.RIDGE, bd=3, height=250)
        camera_container.pack(side=tk.TOP, fill=tk.BOTH, expand=False, pady=(0, 10))
        camera_container.pack_propagate(False)  # Sabit yükseklik
        
        self.ocr_camera_label = tk.Label(camera_container, bg='black', 
                                        text="Kamera YükleNiyor...",
                                        font=("Arial", 12),
                                        fg='white')
        self.ocr_camera_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Alt: Algılanan metin (BÜYÜTÜLDÜ - 60% yükseklik)
        text_container = tk.LabelFrame(display_frame, text="ALGILANAN METİN",
                                      font=("Arial", 12, "bold"), bg='white',
                                      relief=tk.RIDGE, bd=3, height=300)
        text_container.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(10, 0))
        text_container.pack_propagate(False)  # Sabit yükseklik
        
        # Metin scroll alanı
        text_frame = tk.Frame(text_container, bg='white')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.ocr_text_display = tk.Text(text_frame, 
                                        font=("Arial", 14),
                                        bg='white', fg='#2c3e50',
                                        wrap=tk.WORD,
                                        yscrollcommand=scrollbar.set)
        self.ocr_text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.ocr_text_display.yview)
        
        # Başlangıç mesajı
        self.ocr_text_display.insert('1.0', "[BAŞLAT'a basın, sonra OKU butonuyla metin okuyun]")
        
        def update_text(text):
            self.ocr_text_display.delete('1.0', tk.END)
            self.ocr_text_display.insert('1.0', text if text else "[Metin algılanmadı]")
        
        def update_reading_status(is_reading):
            if is_reading:
                self.ocr_read_button.config(bg='#95a5a6', text="⏳ OKUYOR...", state=tk.DISABLED)
            else:
                self.ocr_read_button.config(bg='#3498db', text="📖 OKU", state=tk.NORMAL)
        
        self.modules['ocr'].on_text_update = update_text
        self.modules['ocr'].on_reading_status = update_reading_status
        
        # Kamera güncelleme döngüsünü başlat
        self.update_ocr_camera()
    
    def ocr_read_text(self):
        """OKU butonuna basıldığında çağrılır"""
        if not self.active_module or self.active_module_name != 'ocr':
            logger.warning("⚠️ OCR modülü aktif değil")
            return
        
        if self.modules['ocr'].is_busy():
            logger.warning("⚠️ OCR zaten çalışıyor")
            return
        
        logger.info("📖 OKU butonuna basıldı")
        self.modules['ocr'].read_text()
    
    def update_ocr_camera(self):
        """OCR kamera görüntüsünü güncelle"""
        try:
            # Modül çalışıyorsa ve OCR modülündeyse
            if (self.active_module_name == 'ocr' and 
                hasattr(self, 'ocr_camera_label') and 
                self.ocr_camera_label.winfo_exists()):
                
                # Frame al
                frame = self.modules['ocr'].get_camera_frame()
                
                if frame is not None:
                    # Boyutlandır (KÜÇÜK kamera için)
                    height, width = frame.shape[:2]
                    max_width = 480  # Küçültüldü
                    max_height = 230  # Küçültüldü
                    
                    scale = min(max_width/width, max_height/height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    
                    import cv2
                    frame_resized = cv2.resize(frame, (new_width, new_height))
                    
                    # PIL Image'e çevir
                    from PIL import Image, ImageTk
                    img = Image.fromarray(frame_resized)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    # Göster
                    self.ocr_camera_label.config(image=photo, text="")
                    self.ocr_camera_label.image = photo
                
                # 30ms sonra tekrar çağır
                self.root.after(30, self.update_ocr_camera)
                
        except Exception as e:
            logger.error(f"OCR kamera güncelleme hatası: {e}")
            if (self.active_module_name == 'ocr' and 
                hasattr(self, 'ocr_camera_label')):
                self.root.after(100, self.update_ocr_camera)
    
    def run(self):
        """Ana döngü"""
        self.root.mainloop()


if __name__ == "__main__":
    try:
        app = MainGUI()
        app.run()
    except KeyboardInterrupt:
        logger.info("⚠️ Program kullanıcı tarafından sonlandırıldı")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            GPIO.cleanup()
        except:
            pass