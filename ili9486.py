# ili9486.py
# Basit ILI9486 8-bit paralel driver (Raspberry Pi GPIO için)
# Ekran yatay (480x320) olacak şekilde ayarlanmıştır.

import RPi.GPIO as GPIO
import time

# Senin bağlantına göre data pinleri (D0..D7)
DATA_PINS = [12, 13, 19, 20, 21, 6, 5, 26]  # D0..D7 (GPIO numaraları)

# Kontrol pinleri
PIN_RS  = 16   # LCD_RS / DC
PIN_CS  = 24   # LCD_CS
PIN_WR  = 4    # LCD_WR (GPIO4 / Pin 7)
PIN_RST = 17   # LCD_RST

# Ekran çözünürlüğü (YATAY kullanım)
TFT_WIDTH  = 480
TFT_HEIGHT = 320


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
        # Minimal ILI9486 init – çoğu 3.5" modülde çalışır
        # Sleep Out
        self.write_command(0x11)
        time.sleep(0.12)

        # Pixel format: 16-bit
        self.write_command(0x3A)
        self.write_data8(0x55)    # 16-bit/pixel

        # Memory Access Control (MADCTL)
        # 0x28: Yatay yön + BGR (gerekirse 0xE8 / 0x48 / 0x88 gibi değerler denenebilir)
        self.write_command(0x36)
        self.write_data8(0x28)

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

    def draw_char(self, x, y, char, fg_r, fg_g, fg_b, bg_r=0, bg_g=0, bg_b=0):
        """5x7 piksel font kullanarak bir karakter çiz."""
        # Basit 5x7 font - sadece ASCII harf ve rakamlar
        font_5x7 = {
            ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
            '0': [0x1E, 0x21, 0x21, 0x21, 0x1E],
            '1': [0x08, 0x0C, 0x08, 0x08, 0x1C],
            '2': [0x1E, 0x21, 0x04, 0x08, 0x1F],
            '3': [0x1F, 0x04, 0x0E, 0x21, 0x1E],
            '4': [0x04, 0x0C, 0x14, 0x1F, 0x04],
            '5': [0x1F, 0x20, 0x1E, 0x01, 0x1E],
            '6': [0x0E, 0x10, 0x1E, 0x11, 0x0E],
            '7': [0x1F, 0x01, 0x02, 0x04, 0x08],
            '8': [0x0E, 0x11, 0x0E, 0x11, 0x0E],
            '9': [0x0E, 0x11, 0x0F, 0x01, 0x0E],
            ':': [0x00, 0x08, 0x00, 0x08, 0x00],
            '.': [0x00, 0x00, 0x00, 0x08, 0x00],
            '/': [0x01, 0x02, 0x04, 0x08, 0x10],
            '-': [0x00, 0x00, 0x1F, 0x00, 0x00],
        }
        
        if char not in font_5x7:
            return
        
        pattern = font_5x7[char]
        for col in range(5):
            byte = pattern[col]
            for row in range(7):
                if (byte >> row) & 1:
                    # Ön plan rengi
                    self._draw_pixel(x + col, y + row, fg_r, fg_g, fg_b)
                else:
                    # Arka plan rengi
                    self._draw_pixel(x + col, y + row, bg_r, bg_g, bg_b)

    def _draw_pixel(self, x, y, r, g, b):
        """Tekil piksel çiz (yavaş, ama basit)."""
        if x < 0 or x >= TFT_WIDTH or y < 0 or y >= TFT_HEIGHT:
            return
        self.set_address_window(x, y, x, y)
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)
        color = self.rgb565(r, g, b)
        self.write_bus((color >> 8) & 0xFF)
        self.pulse_wr()
        self.write_bus(color & 0xFF)
        self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def draw_text(self, x, y, text, fg_r, fg_g, fg_b, bg_r=0, bg_g=0, bg_b=0, scale=1):
        """Text çiz (5x7 font, scale ile büyüt)."""
        for i, char in enumerate(text):
            char_x = x + (i * 6 * scale)
            if char_x > TFT_WIDTH:
                break
            if scale == 1:
                self.draw_char(char_x, y, char, fg_r, fg_g, fg_b, bg_r, bg_g, bg_b)
            else:
                # Scaled versiyon (basit)
                self.draw_char_scaled(char_x, y, char, fg_r, fg_g, fg_b, bg_r, bg_g, bg_b, scale)

    def draw_char_scaled(self, x, y, char, fg_r, fg_g, fg_b, bg_r=0, bg_g=0, bg_b=0, scale=2):
        """Büyütülmüş karakter çiz."""
        font_5x7 = {
            ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
            '0': [0x1E, 0x21, 0x21, 0x21, 0x1E],
            '1': [0x08, 0x0C, 0x08, 0x08, 0x1C],
            '2': [0x1E, 0x21, 0x04, 0x08, 0x1F],
            '3': [0x1F, 0x04, 0x0E, 0x21, 0x1E],
            '4': [0x04, 0x0C, 0x14, 0x1F, 0x04],
            '5': [0x1F, 0x20, 0x1E, 0x01, 0x1E],
            '6': [0x0E, 0x10, 0x1E, 0x11, 0x0E],
            '7': [0x1F, 0x01, 0x02, 0x04, 0x08],
            '8': [0x0E, 0x11, 0x0E, 0x11, 0x0E],
            '9': [0x0E, 0x11, 0x0F, 0x01, 0x0E],
            ':': [0x00, 0x08, 0x00, 0x08, 0x00],
            '.': [0x00, 0x00, 0x00, 0x08, 0x00],
            '/': [0x01, 0x02, 0x04, 0x08, 0x10],
            '-': [0x00, 0x00, 0x1F, 0x00, 0x00],
        }
        
        if char not in font_5x7:
            return
        
        pattern = font_5x7[char]
        for col in range(5):
            byte = pattern[col]
            for row in range(7):
                if (byte >> row) & 1:
                    color = self.rgb565(fg_r, fg_g, fg_b)
                else:
                    color = self.rgb565(bg_r, bg_g, bg_b)
                # Büyütülmüş dikdörtgen çiz
                self.fill_rect(x + col * scale, y + row * scale, scale, scale, 
                              (color >> 11) & 0x1F, (color >> 5) & 0x3F, color & 0x1F)

    def cleanup(self):
        GPIO.cleanup()