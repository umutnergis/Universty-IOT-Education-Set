#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ortak Konfigürasyon Dosyası
Tüm modüller bu ayarları kullanır
"""

START_PIN = 12
STOP_PIN = 13
BUZZER_PIN = 19
RELAY_PIN = 26


UART_PORT = '/dev/ttyUSB0'
UART_BAUDRATE = 9600


API_BASE_URL = "http://gaunmes.pkeylabs.io/api/v1"
API_KEY = "8E4579A1-C3C6-4223-90FE-FBE59B7DDFE6"


API_ENDPOINTS = {
    'session_start': f"{API_BASE_URL}/session/startSession",
    'session_end': f"{API_BASE_URL}/session/endSession",
    'session_id': f"{API_BASE_URL}/session/currentSessionId",
    'energy': f"{API_BASE_URL}/energy",     
    'product': f"{API_BASE_URL}/prodEvent",       
    'fault': f"{API_BASE_URL}/faultEvent",        
    'weight': f"{API_BASE_URL}/prodEvent",      
    'conveyor': f"{API_BASE_URL}/prodEvent",
    'wc_id_name': f"{API_BASE_URL}/workCenter"
}


WC_IDS = {
    'power': 15,     
    'production': 1,  # Enerji Üretimi (power ile aynı wc_id)
    'color': 5,      
    'fault': 3,      
    'weight': 4,     
    'conveyor': 2,
    'ocr': 0, # OCR için wc_id yok (session gerekmez)
    'metal':2
}

MODULE_COLORS = {
    'power': '#e74c3c',
    'production': '#f39c12',  # Enerji Üretimi (turuncu)
    'color': '#9b59b6',
    'fault': '#e67e22',
    'weight': '#27ae60',
    'conveyor': '#3498db',
    'ocr': '#16a085',  # OCR (yeşil-mavi)
    'metal': '#77a016' 
}

LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
