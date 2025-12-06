# ili9486.py
# Basit ILI9486 8-bit paralel driver (Raspberry Pi GPIO)

import RPi.GPIO as GPIO
import time

# Senin bağlantına göre data pinleri (D0..D7)
DATA_PINS = [12, 13, 19, 20, 21, 6, 5, 26]  # D0..D7

# Kontrol pinleri
PIN_RS  = 16   # LCD_RS / DC
PIN_CS  = 24   # LCD_CS
PIN_WR  = 4    # LCD_WR (yeni: GPIO4 / Pin7)
PIN_RST = 17   # LCD_RST

# Sabitler
TFT_WIDTH  = 320
TFT_HEIGHT = 480

class ILI9486:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        # data pinleri output
        for p in DATA_PINS:
            GPIO.setup(p, GPIO.OUT)
        # control pinleri output
        for p in [PIN_RS, PIN_CS, PIN_WR, PIN_RST]:
            GPIO.setup(p, GPIO.OUT)

        GPIO.output(PIN_CS, 1)
        GPIO.output(PIN_WR, 1)
        GPIO.output(PIN_RS, 1)

        self.reset()
        self.init_lcd()

    def reset(self):
        GPIO.output(PIN_RST, 1)
        time.sleep(0.05)
        GPIO.output(PIN_RST, 0)
        time.sleep(0.05)
        GPIO.output(PIN_RST, 1)
        time.sleep(0.15)

    def write_bus(self, val: int):
        # 8-bit değeri D0..D7 pinlerine bas
        for i, pin in enumerate(DATA_PINS):
            GPIO.output(pin, (val >> i) & 0x01)

    def pulse_wr(self):
        GPIO.output(PIN_WR, 0)
        # çok kısa delay yeter
        GPIO.output(PIN_WR, 1)

    def write_command(self, cmd: int):
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 0)   # command
        self.write_bus(cmd & 0xFF)
        self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def write_data8(self, data: int):
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)   # data
        self.write_bus(data & 0xFF)
        self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def write_data16(self, val: int):
        # 16-bit RGB565 data: high, low
        self.write_data8((val >> 8) & 0xFF)
        self.write_data8(val & 0xFF)

    def init_lcd(self):
        # Minimal ILI9486 init (birçok modülde çalışıyor)
        self.write_command(0x11)  # Sleep Out
        time.sleep(0.12)

        # Pixel format
        self.write_command(0x3A)
        self.write_data8(0x55)    # 16-bit/pixel

        # Memory Access Control
        self.write_command(0x36)
        # Panel yönü: 0x48, 0x28 vs. denenecek
        self.write_data8(0x48)    # MX, BGR

        # Display ON
        self.write_command(0x29)
        time.sleep(0.05)

    def set_address_window(self, x0, y0, x1, y1):
        # Column addr set
        self.write_command(0x2A)
        self.write_data8((x0 >> 8) & 0xFF)
        self.write_data8(x0 & 0xFF)
        self.write_data8((x1 >> 8) & 0xFF)
        self.write_data8(x1 & 0xFF)

        # Page addr set
        self.write_command(0x2B)
        self.write_data8((y0 >> 8) & 0xFF)
        self.write_data8(y0 & 0xFF)
        self.write_data8((y1 >> 8) & 0xFF)
        self.write_data8(y1 & 0xFF)

        # Memory write
        self.write_command(0x2C)

    def rgb565(self, r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3)

    def fill_screen(self, r, g, b):
        color = self.rgb565(r, g, b)
        self.set_address_window(0, 0, TFT_WIDTH - 1, TFT_HEIGHT - 1)
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)
        for _ in range(TFT_WIDTH * TFT_HEIGHT):
            self.write_bus((color >> 8) & 0xFF)
            self.pulse_wr()
            self.write_bus(color & 0xFF)
            self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def fill_rect(self, x, y, w, h, r, g, b):
        color = self.rgb565(r, g, b)
        self.set_address_window(x, y, x + w - 1, y + h - 1)
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)
        for _ in range(w * h):
            self.write_bus((color >> 8) & 0xFF)
            self.pulse_wr()
            self.write_bus(color & 0xFF)
            self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def cleanup(self):
        GPIO.cleanup()