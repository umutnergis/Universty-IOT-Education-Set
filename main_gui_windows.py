

# -*- coding: utf-8 -*-
"""
main_gui_windows.py

A Windows-friendly test version of the Raspberry Pi MES GUI.
Hardware/network interactions are simulated so the GUI can be tested on Windows.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import logging
import random

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Minimal config replacements for testing ---
API_KEY = "TEST_API_KEY"
API_ENDPOINTS = {"session_start": "", "session_end": "", "session_id": ""}
MODULE_COLORS = {
    'power': '#3498db', 'production': '#f39c12', 'color': '#e74c3c',
    'fault': '#9b59b6', 'weight': '#27ae60', 'conveyor': '#2980b9',
    'metal': '#77a016', 'ocr': '#34495e'
}
WC_IDS = {
    'power': 1, 'production': 1, 'conveyor': 2, 'fault': 3,
    'weight': 4, 'color': 5, 'metal': 6, 'ocr': 0
}

# --- Dummy / Simulated Hardware & Modules for Windows testing ---

class DummyPWM:
    def __init__(self, pin=None, freq=1000):
        self._dc = 0
    def start(self, dc):
        self._dc = dc
    def ChangeDutyCycle(self, dc):
        self._dc = dc
    def stop(self):
        self._dc = 0

class DummyESP32:
    def __init__(self, port=None, baud=115200):
        self.connected = True
    def start_reading(self):
        logger.info("DummyESP32: started")
    def close(self):
        logger.info("DummyESP32: closed")

class DummyNFC:
    def __init__(self):
        self.pn532 = True
        self.last_card_id = ""
        self.current_card_id = ""
        self.card_present = False
        self.on_card_detected = None
        self._running = False
    def start_reading(self):
        self._running = True
    def stop_reading(self):
        self._running = False

# Base Module with common behaviors
class BaseModule:
    def __init__(self, esp=None):
        self.esp = esp
        self.running = False
    def start(self, session_id=None):
        self.running = True
        return True
    def stop(self):
        self.running = False
    def get_camera_frame(self):
        # Return a PIL Image for GUI display if possible
        if not PIL_AVAILABLE:
            return None
        img = Image.new("RGB", (640, 480), color=(100, 100, 100))
        d = ImageDraw.Draw(img)
        d.text((10, 10), f"{self.__class__.__name__}\nRunning={self.running}", fill=(255,255,255))
        return img

class PowerModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_data_update = None
        self._thread = None
    def start(self, session_id=None):
        if not super().start(session_id): return False
        def loop():
            while self.running:
                cur = random.uniform(0.0, 5.0)
                pwr = cur * random.uniform(10.0, 50.0)
                if self.on_data_update:
                    self.on_data_update('current', cur)
                    self.on_data_update('power', pwr)
                time.sleep(1.0)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return True

class ProductionModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_data_update = None
    def start(self, session_id=None):
        super().start(session_id)
        def loop():
            while self.running:
                cur = random.uniform(0.0, 3.0)
                pwr = cur * random.uniform(20.0, 60.0)
                if self.on_data_update:
                    self.on_data_update('production_current', cur)
                    self.on_data_update('production_power', pwr)
                time.sleep(1.2)
        threading.Thread(target=loop, daemon=True).start()
        return True

class ColorModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.count = 0
        self.on_count_update = None
        self._color = "Kırmızı"
    def reset_counter(self):
        self.count = 0
        if self.on_count_update: self.on_count_update(self.count)
    def set_color(self, color_name):
        self._color = color_name
    def start(self, session_id=None):
        super().start(session_id)
        def loop():
            while self.running:
                # simulate detection
                self.count += random.choice([0,0,1])
                if self.on_count_update:
                    self.on_count_update(self.count)
                time.sleep(0.8)
        threading.Thread(target=loop, daemon=True).start()
        return True

class FaultModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_fault_update = None
    def clear_all_faults(self):
        if self.on_fault_update:
            self.on_fault_update('all', False)

class WeightModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_weight_update = None
        self._values = []
    def tare(self):
        self._values = []
    def start(self, session_id=None):
        super().start(session_id)
        def loop():
            while self.running:
                w = random.uniform(0.0, 500.0)
                self._values.append(w)
                if len(self._values) > 100:
                    self._values.pop(0)
                if self.on_weight_update:
                    self.on_weight_update(w)
                time.sleep(0.7)
        threading.Thread(target=loop, daemon=True).start()
        return True
    def get_statistics(self):
        if not self._values:
            return {'min':0.0,'max':0.0,'average':0.0,'count':0}
        return {'min':min(self._values),'max':max(self._values),'average': sum(self._values)/len(self._values),'count':len(self._values)}

class ConveyorModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_item_detected = None
        self._count = 0
        self._start_time = None
    def reset_counter(self):
        self._count = 0
        self._start_time = time.time()
    def start(self, session_id=None):
        super().start(session_id)
        self._start_time = time.time()
        def loop():
            while self.running:
                if random.random() < 0.4:
                    self._count += 1
                    if self.on_item_detected:
                        self.on_item_detected(self._count)
                time.sleep(0.6)
        threading.Thread(target=loop, daemon=True).start()
        return True
    def get_statistics(self):
        runtime = (time.time() - self._start_time) if self._start_time else 0.0
        rpm = (self._count / runtime * 60.0) if runtime > 0 else 0.0
        return {'runtime': runtime, 'rate_per_minute': rpm}

class MetalModule(ConveyorModule):
    def __init__(self, esp=None):
        super().__init__(esp)

class OCRModule(BaseModule):
    def __init__(self, esp=None):
        super().__init__(esp)
        self.on_text_update = None
        self.on_reading_status = None
        self._busy = False
    def is_busy(self):
        return self._busy
    def read_text(self):
        if self._busy: return
        self._busy = True
        if self.on_reading_status: self.on_reading_status(True)
        def work():
            time.sleep(1.2)
            sample = "Örnek OCR Metni:\n1234 ABCD\nTarih: 2025-11-19"
            if self.on_text_update: self.on_text_update(sample)
            self._busy = False
            if self.on_reading_status: self.on_reading_status(False)
        threading.Thread(target=work, daemon=True).start()
        return True

# --- Main GUI adapted for Windows testing ---
class MainGUI:
    """Windows-testable GUI with simulated hardware/network"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MES Eğitim Sistemi - Windows Test")
        self.root.geometry("1100x700")
        self.root.configure(bg='#2c3e50')
        self.root.bind('<Escape>', lambda e: self.exit_application())

        # Simulated hardware
        self.buzzer_pwm = DummyPWM()
        self.esp32 = DummyESP32()
        self.nfc = DummyNFC()
        self.nfc.on_card_detected = self.on_nfc_card_detected

        # Modules
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

        # Session state
        self.current_session_id = None
        self.current_card_id = None
        self.session_active = False
        self.active_module = None
        self.active_module_name = None

        self.create_gui()
        logger.info("Windows test GUI ready")

    def buzzer_beep(self, duration=0.1, repeat=1):
        logger.info("Beep (simulated)")
        # no real sound on Windows; simulate via log

    def create_gui(self):
        main = tk.Frame(self.root, bg='#2c3e50')
        main.pack(fill=tk.BOTH, expand=True)
        self.create_menu(main)
        self.content_frame = tk.Frame(main, bg='#ecf0f1')
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.show_home()

    def create_menu(self, parent):
        menu = tk.Frame(parent, bg='#34495e', width=260)
        menu.pack(side=tk.LEFT, fill=tk.Y)
        menu.pack_propagate(False)
        tk.Label(menu, text="EĞİTİM SİSTEMİ\nMODÜLLER",
                 font=("Arial", 14, "bold"), bg='#34495e', fg='white',
                 pady=10).pack(fill=tk.X)
        esp32_text = "✓ SİSTEM KONTROL" if self.esp32.connected else "✗ SİSTEM KONTROL"
        esp32_color = '#27ae60' if self.esp32.connected else '#e74c3c'
        tk.Label(menu, text=esp32_text, font=("Arial", 8, "bold"),
                 bg='#34495e', fg=esp32_color).pack(pady=2)
        nfc_text = "✓ NFC (Sim)" if self.nfc.pn532 else "✗ NFC"
        nfc_color = '#27ae60' if self.nfc.pn532 else '#e74c3c'
        tk.Label(menu, text=nfc_text, font=("Arial", 8, "bold"),
                 bg='#34495e', fg=nfc_color).pack(pady=2)

        self.session_label = tk.Label(menu, text="❌ Session Yok",
                                      font=("Arial", 8, "bold"),
                                      bg='#34495e', fg='#e74c3c')
        self.session_label.pack(pady=3)

        self.card_id_label = tk.Label(menu, text="Kart ID: -",
                                      font=("Arial", 7),
                                      bg='#34495e', fg='#95a5a6')
        self.card_id_label.pack(pady=1)

        tk.Frame(menu, bg='#7f8c8d', height=1).pack(fill=tk.X, pady=5)

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

        # Simulate NFC card button for Windows testing
        tk.Button(menu, text="🔁 Simulate NFC Card", font=("Arial", 10),
                  bg='#16a085', fg='white', command=self._simulate_nfc).pack(fill=tk.X, padx=8, pady=5)

        tk.Label(menu, text="\nNACİ TOPÇUOĞLU ÜNİVERSİTESİ\nMühendislik Fakültesi",
                font=("Arial", 8), bg='#34495e', fg='#95a5a6',
                justify=tk.CENTER).pack(side=tk.BOTTOM, pady=5)

        tk.Button(menu, text="❌ ÇIKIŞ", font=("Arial", 10, "bold"),
                 bg='#c0392b', fg='white', relief=tk.FLAT,
                 command=self.exit_application, height=1).pack(
                 side=tk.BOTTOM, fill=tk.X, padx=8, pady=5)

    def _simulate_nfc(self):
        card_id = f"SIM-{random.randint(1000,9999)}"
        logger.info(f"Simulating NFC card: {card_id}")
        # Call handler directly
        self.on_nfc_card_detected(card_id)

    def switch_module(self, module_name):
        if self.active_module:
            if not messagebox.askyesno("Uyarı", "Çalışan modül var! Durdurup devam edilsin mi?"):
                return
            self.stop_current_module()
        if self.session_active:
            logger.info("Closing existing session due to module switch")
            self.stop_session()
            self.session_active = False
            self.current_session_id = None
            self.current_card_id = None
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False

        self.active_module_name = module_name
        logger.info(f"Active module: {module_name}")
        for widget in self.content_frame.winfo_children():
            widget.destroy()

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

    def show_home(self):
        home = tk.Frame(self.content_frame, bg='#ecf0f1')
        home.pack(fill=tk.BOTH, expand=True)
        tk.Label(home, text="🎓 ENDÜSTRİYEL EĞİTİM SİSTEMİ (Windows Test)",
                font=("Arial", 18, "bold"), bg='#ecf0f1', fg='#2c3e50',
                pady=15).pack()
        info = ("Sol menüden modül seçin.\n\n"
                "Use 'Simulate NFC Card' to create a fake NFC card and start sessions.\n"
                "Modules simulate data for GUI testing.")
        tk.Label(home, text=info, font=("Arial", 11),
                 bg='#ecf0f1', fg='#34495e', justify=tk.LEFT,
                 pady=10).pack()

    # The following show_* methods are simplified and reuse original layout but rely on simulated modules
    def show_power_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text=" AKIM & GÜÇ", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['power']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3); display.pack(fill=tk.BOTH, expand=True, pady=10)
        cur_frame = tk.LabelFrame(display, text="AKIM (A)", font=("Arial", 12, "bold"), bg='white'); cur_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.power_current_label = tk.Label(cur_frame, text="0.00", font=("Arial", 32, "bold"), bg='white', fg='#e74c3c'); self.power_current_label.pack(pady=15)
        pow_frame = tk.LabelFrame(display, text="GÜÇ (W)", font=("Arial", 12, "bold"), bg='white'); pow_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.power_power_label = tk.Label(pow_frame, text="0.00", font=("Arial", 32, "bold"), bg='white', fg='#27ae60'); self.power_power_label.pack(pady=15)
        def update_power(data_type, value):
            if data_type == 'current':
                self.power_current_label.config(text=f"{value:.2f}")
            elif data_type == 'power':
                self.power_power_label.config(text=f"{value:.2f}")
        self.modules['power'].on_data_update = update_power

    def show_production_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text="⚡ ENERJİ ÜRETİMİ", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['production']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3); display.pack(fill=tk.BOTH, expand=True, pady=10)
        cur_frame = tk.LabelFrame(display, text="ÜRETİLEN AKIM (A)", font=("Arial", 12, "bold"), bg='white'); cur_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.production_current_label = tk.Label(cur_frame, text="0.00", font=("Arial", 32, "bold"), bg='white', fg='#f39c12'); self.production_current_label.pack(pady=15)
        pow_frame = tk.LabelFrame(display, text="ÜRETİLEN GÜÇ (W)", font=("Arial", 12, "bold"), bg='white'); pow_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.production_power_label = tk.Label(pow_frame, text="0.00", font=("Arial", 32, "bold"), bg='white', fg='#e67e22'); self.production_power_label.pack(pady=15)
        def update_production(data_type, value):
            if data_type == 'production_current':
                self.production_current_label.config(text=f"{value:.2f}")
            elif data_type == 'production_power':
                self.production_power_label.config(text=f"{value:.2f}")
        self.modules['production'].on_data_update = update_production

    def show_color_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text="🎨 RENK ALGILAMA", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['color']).pack(pady=5)
        top_frame = tk.Frame(frame, bg='#ecf0f1'); top_frame.pack(fill=tk.X, pady=5)
        control = tk.Frame(top_frame, bg='#ecf0f1'); control.pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="🔄 SIFIRLA", command=lambda: self.modules['color'].reset_counter(), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        color_frame = tk.LabelFrame(top_frame, text="RENK SEÇİMİ", font=("Arial", 10, "bold"), bg='#ecf0f1'); color_frame.pack(side=tk.RIGHT, padx=10)
        colors = [("Kırmızı","Kırmızı","#e74c3c"),("Sarı","Sarı","#fff203"),("Mavi","Mavi","#3498db")]
        self.color_selection_var = tk.StringVar(value="Kırmızı")
        for text,color_name,color_code in colors:
            tk.Radiobutton(color_frame, text=text, variable=self.color_selection_var, value=color_name, command=lambda c=color_name: self.on_color_selected(c), bg='#ecf0f1', fg=color_code, selectcolor='#bdc3c7').pack(side=tk.LEFT, padx=5, pady=5)
        display_frame = tk.Frame(frame, bg='#ecf0f1'); display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        camera_container = tk.LabelFrame(display_frame, text="KAMERA GÖRÜNTÜSÜ", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3); camera_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.color_camera_label = tk.Label(camera_container, bg='black', text="Kamera Yükleniyor...", font=("Arial",12), fg='white'); self.color_camera_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        counter_frame = tk.LabelFrame(display_frame, text="ÜRÜN SAYACI", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3); counter_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0))
        tk.Label(counter_frame, text="Algılanan Ürün", font=("Arial", 12, "bold"), bg='white', fg=MODULE_COLORS['color']).pack(pady=10)
        self.color_count_label = tk.Label(counter_frame, text="0", font=("Arial", 44, "bold"), bg='white', fg='#2c3e50'); self.color_count_label.pack(pady=30)
        self.color_selected_label = tk.Label(counter_frame, text="Seçili Renk:\n🔴 Kırmızı", font=("Arial", 11, "bold"), bg='#ecf0f1', fg='#e74c3c'); self.color_selected_label.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        def update_count(count):
            self.color_count_label.config(text=str(count))
        self.modules['color'].on_count_update = update_count
        self.update_color_camera()

    def show_fault_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text=" ARIZA TESPİT", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['fault']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="🧹 TEMİZLE", command=lambda: self.modules['fault'].clear_all_faults(), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='#ecf0f1'); display.pack(fill=tk.BOTH, expand=True, pady=10)
        fire_frame = tk.LabelFrame(display, text="🔥 YANGIN", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3); fire_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        self.fault_fire_label = tk.Label(fire_frame, text="✓ Normal", font=("Arial", 20, "bold"), bg='#27ae60', fg='white', relief=tk.RAISED, bd=5); self.fault_fire_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        voice_frame = tk.LabelFrame(display, text="🔊 SES", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3); voice_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        self.fault_voice_label = tk.Label(voice_frame, text="✓ Normal", font=("Arial", 20, "bold"), bg='#27ae60', fg='white', relief=tk.RAISED, bd=5); self.fault_voice_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        vib_frame = tk.LabelFrame(display, text="📳 TİTREŞİM", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3); vib_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        self.fault_vib_label = tk.Label(vib_frame, text="✓ Normal", font=("Arial", 20, "bold"), bg='#27ae60', fg='white', relief=tk.RAISED, bd=5); self.fault_vib_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        def update_fault(fault_type, active):
            if fault_type == 'fire':
                if active:
                    self.fault_fire_label.config(bg='#e74c3c', text="🔥 YANGIN!")
                else:
                    self.fault_fire_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'voice':
                if active:
                    self.fault_voice_label.config(bg='#e74c3c', text="🔊 SES!")
                else:
                    self.fault_voice_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'vibration':
                if active:
                    self.fault_vib_label.config(bg='#e74c3c', text="📳 TİTREŞİM!")
                else:
                    self.fault_vib_label.config(bg='#27ae60', text="✓ Normal")
            elif fault_type == 'all':
                self.fault_fire_label.config(bg='#27ae60', text="✓ Normal")
                self.fault_voice_label.config(bg='#27ae60', text="✓ Normal")
                self.fault_vib_label.config(bg='#27ae60', text="✓ Normal")
        self.modules['fault'].on_fault_update = update_fault

    def show_weight_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text=" AĞIRLIK ÖLÇÜMÜ ", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['weight']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⚖️ TARA", command=lambda: self.modules['weight'].tare(), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3); display.pack(fill=tk.BOTH, expand=True, pady=10)
        weight_frame = tk.Frame(display, bg='white'); weight_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        self.weight_label = tk.Label(weight_frame, text="0.0", font=("Arial", 44, "bold"), bg='white', fg='#27ae60'); self.weight_label.pack()
        tk.Label(weight_frame, text="gram (g)", font=("Arial", 16), bg='white', fg='#7f8c8d').pack(pady=5)
        stats_frame = tk.Frame(display, bg='white'); stats_frame.pack(fill=tk.X, padx=15, pady=8)
        self.weight_stats_label = tk.Label(stats_frame, text="Min: 0.0g | Max: 0.0g | Ort: 0.0g | Ölçüm: 0", font=("Arial", 10), bg='white', fg='#7f8c8d'); self.weight_stats_label.pack()
        def update_weight(weight):
            self.weight_label.config(text=f"{weight:.1f}")
            stats = self.modules['weight'].get_statistics()
            self.weight_stats_label.config(text=f"Min: {stats['min']:.1f}g | Max: {stats['max']:.1f}g | Ort: {stats['average']:.1f}g | Ölçüm: {stats['count']}")
        self.modules['weight'].on_weight_update = update_weight

    def show_conveyor_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text=" KONVEYÖR SİSTEMİ", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['conveyor']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="🔄 SIFIRLA", command=lambda: self.modules['conveyor'].reset_counter(), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3); display.pack(fill=tk.BOTH, expand=True, pady=10)
        count_frame = tk.Frame(display, bg='white'); count_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        tk.Label(count_frame, text="GEÇEN ÜRÜN", font=("Arial", 14, "bold"), bg='white', fg=MODULE_COLORS['conveyor']).pack(pady=8)
        self.conveyor_count_label = tk.Label(count_frame, text="0", font=("Arial", 44, "bold"), bg='white', fg='#3498db'); self.conveyor_count_label.pack(pady=15)
        stats_frame = tk.Frame(display, bg='#ecf0f1', relief=tk.SUNKEN, bd=2); stats_frame.pack(fill=tk.X, padx=15, pady=8)
        self.conveyor_stats_label = tk.Label(stats_frame, text="Süre: 0s | Hız: 0 ürün/dk", font=("Arial", 11, "bold"), bg='#ecf0f1', fg='#2c3e50'); self.conveyor_stats_label.pack(pady=10)
        def update_conveyor(count):
            self.conveyor_count_label.config(text=str(count))
            stats = self.modules['conveyor'].get_statistics()
            self.conveyor_stats_label.config(text=f"Süre: {stats['runtime']:.1f}s | Hız: {stats['rate_per_minute']:.1f} ürün/dk")
        self.modules['conveyor'].on_item_detected = update_conveyor

    def show_metal_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text="🔩 METAL ALGILAMA", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['metal']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⏹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="🔄 SIFIRLA", command=lambda: self.modules['metal'].reset_counter(), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        display = tk.Frame(frame, bg='white', relief=tk.RIDGE, bd=3); display.pack(fill=tk.BOTH, expand=True, pady=10)
        count_frame = tk.Frame(display, bg='white'); count_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        tk.Label(count_frame, text="ALGILANAN METAL", font=("Arial", 14, "bold"), bg='white', fg=MODULE_COLORS['metal']).pack(pady=8)
        self.metal_count_label = tk.Label(count_frame, text="0", font=("Arial", 44, "bold"), bg='white', fg='#77a016'); self.metal_count_label.pack(pady=15)
        stats_frame = tk.Frame(display, bg='#ecf0f1', relief=tk.SUNKEN, bd=2); stats_frame.pack(fill=tk.X, padx=15, pady=8)
        self.metal_stats_label = tk.Label(stats_frame, text="Süre: 0s | Hız: 0 metal/dk", font=("Arial", 11, "bold"), bg='#ecf0f1', fg='#2c3e50'); self.metal_stats_label.pack(pady=10)
        def update_metal(count):
            self.metal_count_label.config(text=str(count))
            stats = self.modules['metal'].get_statistics()
            self.metal_stats_label.config(text=f"Süre: {stats['runtime']:.1f}s | Hız: {stats['rate_per_minute']:.1f} metal/dk")
        self.modules['metal'].on_metal_detected = update_metal

    def on_nfc_card_detected(self, card_id):
        logger.info(f"Simulated NFC detected: {card_id}")
        self.current_card_id = card_id
        self.card_id_label.config(text=f"Kart ID: {card_id}")
        self.buzzer_beep()
        if not self.session_active:
            success = self.start_session(card_id)
            if not success:
                # cleanup
                self.nfc.last_card_id = ""
                self.nfc.current_card_id = ""
                self.nfc.card_present = False
                self.current_card_id = None
                self.card_id_label.config(text="Kart ID: -")
        else:
            messagebox.showinfo("Bilgi", f"Session zaten aktif!\nSession ID: {self.current_session_id}")

    def start_session(self, card_id):
        # Simulate API session start
        if not self.active_module_name or self.active_module_name == 'home':
            messagebox.showerror("Hata", "Önce bir modül seçmelisiniz!")
            return False
        wc_id = WC_IDS.get(self.active_module_name, 0)
        if wc_id == 0 and self.active_module_name != 'ocr':
            messagebox.showerror("Hata", "Modül WC_ID bulunamadı!")
            return False
        logger.info(f"Simulating session start for card={card_id}, wc_id={wc_id}")
        time.sleep(0.6)
        # Simulate success and create session id
        self.current_session_id = random.randint(1000, 9999) if self.active_module_name != 'ocr' else 0
        self.current_card_id = card_id
        self.session_active = True if self.active_module_name != 'ocr' else False
        if self.session_active:
            self.session_label.config(text=f"✅ Session: {self.current_session_id}", fg='#27ae60')
        else:
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
        return True

    def get_session_id(self, wc_id=None):
        # For testing return current existing id
        if self.current_session_id and self.current_session_id > 0:
            return True
        return False

    def stop_session(self):
        if not self.session_active:
            # cleanup anyway
            self.current_session_id = None
            self.current_card_id = None
            self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
            self.card_id_label.config(text="Kart ID: -")
            self.nfc.last_card_id = ""
            self.nfc.current_card_id = ""
            self.nfc.card_present = False
            return True
        # simulate stop
        logger.info(f"Simulating session end: ID={self.current_session_id}")
        time.sleep(0.4)
        self.session_active = False
        self.current_session_id = None
        self.current_card_id = None
        self.session_label.config(text="❌ Session Yok", fg='#e74c3c')
        self.card_id_label.config(text="Kart ID: -")
        self.nfc.last_card_id = ""
        self.nfc.current_card_id = ""
        self.nfc.card_present = False
        return True

    def start_current_module(self):
        if self.active_module_name == 'ocr':
            if self.active_module:
                messagebox.showwarning("Uyarı", "OCR modülü zaten çalışıyor!")
                return
            module_to_start = self.modules.get('ocr')
            if module_to_start and module_to_start.start():
                self.active_module = module_to_start
                self.buzzer_beep()
                messagebox.showinfo("Başarılı", "OCR modülü başlatıldı!")
            return
        if not self.session_active:
            messagebox.showerror("Hata", "Session başlatılmadı!\nLütfen önce NFC kart okutun.")
            return
        if not self.current_card_id:
            messagebox.showerror("Hata", "NFC kart bilgisi bulunamadı!")
            return
        if not self.current_session_id or self.current_session_id <= 0:
            messagebox.showerror("Kritik Hata", "Session ID geçersiz veya yok! Kartı tekrar okutun.")
            return
        if not self.active_module_name or self.active_module_name == 'home':
            messagebox.showerror("Hata", "Lütfen önce bir modül seçin!")
            return
        if self.active_module:
            messagebox.showwarning("Uyarı", "Modül zaten çalışıyor!")
            return
        module_to_start = self.modules.get(self.active_module_name)
        if not module_to_start:
            messagebox.showerror("Hata", "Modül bulunamadı!")
            return
        if module_to_start.start(session_id=self.current_session_id):
            self.active_module = module_to_start
            self.buzzer_beep()
            logger.info(f"{self.active_module_name} started (simulated)")

    def stop_current_module(self):
        if not self.active_module:
            logger.warning("Çalışan modül yok")
            return
        module_name = self.active_module_name
        logger.info(f"Stopping module (simulated): {module_name}")
        self.active_module.stop()
        self.active_module = None
        if self.session_active:
            if self.stop_session():
                self.buzzer_beep()
                logger.info(f"{module_name} stopped and session ended (simulated)")
            else:
                logger.warning(f"{module_name} stopped but session end failed")
        else:
            logger.info(f"{module_name} stopped (no session)")

    def exit_application(self):
        if messagebox.askokcancel("Çıkış", "Çıkmak istediğinize emin misiniz?"):
            try:
                if self.active_module:
                    self.stop_current_module()
            except Exception:
                pass
            self.root.destroy()

    def on_color_selected(self, color_name):
        self.modules['color'].set_color(color_name)
        color_icons = {"Kırmızı": ("🔴", "#e74c3c"), "Yeşil": ("🟢", "#27ae60"), "Mavi": ("🔵", "#3498db")}
        icon, color_code = color_icons.get(color_name, ("⚪", "#95a5a6"))
        self.color_selected_label.config(text=f"Seçili Renk:\n{icon} {color_name}", fg=color_code)
        logger.info(f"Renk seçildi (sim): {color_name}")

    def _pil_to_photo(self, pil_img, max_w=None, max_h=None):
        if not PIL_AVAILABLE or pil_img is None:
            return None
        img = pil_img
        if max_w and max_h:
            img.thumbnail((max_w, max_h), Image.ANTIALIAS)
        return ImageTk.PhotoImage(img)

    def update_color_camera(self):
        try:
            if (self.active_module_name == 'color' and hasattr(self, 'color_camera_label') and self.color_camera_label.winfo_exists()):
                frame = self.modules['color'].get_camera_frame()
                if frame is not None and PIL_AVAILABLE:
                    photo = self._pil_to_photo(frame, max_w=480, max_h=360)
                    if photo:
                        self.color_camera_label.config(image=photo, text="")
                        self.color_camera_label.image = photo
                self.root.after(200, self.update_color_camera)
        except Exception as e:
            logger.error(f"Kamera güncelleme hatası (sim): {e}")
            if hasattr(self, 'color_camera_label'):
                self.root.after(500, self.update_color_camera)

    def show_ocr_module(self):
        frame = tk.Frame(self.content_frame, bg='#ecf0f1'); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        tk.Label(frame, text="🔍 OCR YAZI ALGILAMA (MANUEL)", font=("Arial", 16, "bold"), bg='#ecf0f1', fg=MODULE_COLORS['ocr']).pack(pady=5)
        control = tk.Frame(frame, bg='#ecf0f1'); control.pack(fill=tk.X, pady=5)
        tk.Button(control, text="▶ BAŞLAT", command=self.start_current_module, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="⎹ DURDUR", command=self.stop_current_module, bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        self.ocr_read_button = tk.Button(control, text="📖 OKU", command=self.ocr_read_text, bg='#3498db', fg='white'); self.ocr_read_button.pack(side=tk.LEFT, padx=10)
        tk.Button(control, text="🧹 TEMİZLE", command=lambda: self.modules['ocr'].on_text_update and self.modules['ocr'].on_text_update(""), bg='#f39c12').pack(side=tk.LEFT, padx=5)
        display_frame = tk.Frame(frame, bg='#ecf0f1'); display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        camera_container = tk.LabelFrame(display_frame, text="KAMERA GÖRÜNTÜSÜ", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3, height=200); camera_container.pack(side=tk.TOP, fill=tk.BOTH, expand=False, pady=(0,10)); camera_container.pack_propagate(False)
        self.ocr_camera_label = tk.Label(camera_container, bg='black', text="Kamera Yükleniyor...", font=("Arial",12), fg='white'); self.ocr_camera_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_container = tk.LabelFrame(display_frame, text="ALGILANAN METİN", font=("Arial", 12, "bold"), bg='white', relief=tk.RIDGE, bd=3, height=260); text_container.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(10,0)); text_container.pack_propagate(False)
        text_frame = tk.Frame(text_container, bg='white'); text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = tk.Scrollbar(text_frame); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ocr_text_display = tk.Text(text_frame, font=("Arial", 12), bg='white', fg='#2c3e50', wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.ocr_text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.config(command=self.ocr_text_display.yview)
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
        self.update_ocr_camera()

    def ocr_read_text(self):
        if not self.active_module or self.active_module_name != 'ocr':
            messagebox.showwarning("Uyarı", "OCR modülü aktif değil")
            return
        if self.modules['ocr'].is_busy():
            messagebox.showwarning("Uyarı", "OCR zaten çalışıyor")
            return
        self.modules['ocr'].read_text()

    def update_ocr_camera(self):
        try:
            if (self.active_module_name == 'ocr' and hasattr(self, 'ocr_camera_label') and self.ocr_camera_label.winfo_exists()):
                frame = self.modules['ocr'].get_camera_frame()
                if frame is not None and PIL_AVAILABLE:
                    photo = self._pil_to_photo(frame, max_w=480, max_h=230)
                    if photo:
                        self.ocr_camera_label.config(image=photo, text="")
                        self.ocr_camera_label.image = photo
                self.root.after(300, self.update_ocr_camera)
        except Exception as e:
            logger.error(f"OCR camera update error (sim): {e}")
            if hasattr(self, 'ocr_camera_label'):
                self.root.after(500, self.update_ocr_camera)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MainGUI()
    app.run()