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

# Ekran çözünürlüğü (PORTRAIT kullanım - 320 genişlik, 480 yükseklik)
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
        print("[LCD] Reset başlandı...")
        GPIO.output(PIN_RST, 1)
        time.sleep(0.05)
        GPIO.output(PIN_RST, 0)
        time.sleep(0.05)
        GPIO.output(PIN_RST, 1)
        time.sleep(0.15)
        print("[LCD] Reset tamamlandı")

    def write_bus(self, val: int):
        # 8-bit değeri D0..D7 pinlerine bas
        for i, pin in enumerate(DATA_PINS):
            GPIO.output(pin, (val >> i) & 0x01)

    def pulse_wr(self):
        """WR pulsunu gönder (negedge strobe)."""
        GPIO.output(PIN_WR, 0)
        time.sleep(0.00001)  # 10 us delay
        GPIO.output(PIN_WR, 1)
        time.sleep(0.00001)  # 10 us delay

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
        # Minimal ILI9486 init
        print("[LCD] Init başlandı...")
        
        # Sleep Out
        self.write_command(0x11)
        time.sleep(0.12)
        print("[LCD] Sleep Out gönderildi")

        # Pixel format: 16-bit
        self.write_command(0x3A)
        self.write_data8(0x55)    # 16-bit/pixel
        print("[LCD] Pixel format: 16-bit")

        # Memory Access Control (MADCTL) - Portrait mode
        # Deneyin: 0x00, 0x80, 0x40, 0xC0 eğer yanlışsa
        self.write_command(0x36)
        self.write_data8(0x00)    # Try normal mode first
        print("[LCD] MADCTL: 0x00 (test mode)")

        # Frame Rate Control
        self.write_command(0xB1)
        self.write_data8(0x00)
        self.write_data8(0x1B)
        print("[LCD] Frame rate set")

        # Display ON
        self.write_command(0x29)
        time.sleep(0.05)
        print("[LCD] Display ON")
        
        print("[LCD] Init tamamlandı!")

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
        # RGB565: RRRRRGG GGGBBBBB
        # r: 5 bit (0-31), g: 6 bit (0-63), b: 5 bit (0-31)
        r5 = (r >> 3) & 0x1F
        g6 = (g >> 2) & 0x3F
        b5 = (b >> 3) & 0x1F
        return (r5 << 11) | (g6 << 5) | b5

    def fill_screen(self, r, g, b):
        """Tüm ekranı belirtilen renkle doldur."""
        color = self.rgb565(r, g, b)
        self.set_address_window(0, 0, TFT_WIDTH - 1, TFT_HEIGHT - 1)
        
        # CS ve RS pinlerini bir kez set et, tüm veriyi yaz
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)  # Data mode
        
        high_byte = (color >> 8) & 0xFF
        low_byte = color & 0xFF
        
        pixel_count = TFT_WIDTH * TFT_HEIGHT
        for _ in range(pixel_count):
            self.write_bus(high_byte)
            self.pulse_wr()
            self.write_bus(low_byte)
            self.pulse_wr()
        
        GPIO.output(PIN_CS, 1)

    def fill_rect(self, x, y, w, h, r, g, b):
        """Dikdörtgen alanı belirtilen renkle doldur."""
        if w <= 0 or h <= 0:
            return
        
        # Sınırları kontrol et
        if x >= TFT_WIDTH or y >= TFT_HEIGHT or x + w <= 0 or y + h <= 0:
            return
        
        # Kenarları kırp
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if x + w > TFT_WIDTH:
            w = TFT_WIDTH - x
        if y + h > TFT_HEIGHT:
            h = TFT_HEIGHT - y
        
        color = self.rgb565(r, g, b)
        self.set_address_window(x, y, x + w - 1, y + h - 1)
        
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)  # Data mode
        
        high_byte = (color >> 8) & 0xFF
        low_byte = color & 0xFF
        
        pixel_count = w * h
        for _ in range(pixel_count):
            self.write_bus(high_byte)
            self.pulse_wr()
            self.write_bus(low_byte)
            self.pulse_wr()
        
        GPIO.output(PIN_CS, 1)

    def draw_big_char(self, x, y, char, fg_r, fg_g, fg_b, bg_r=0, bg_g=0, bg_b=0, size=2):
        """Büyük karakterler (basit pixel-based, yavaş ama çalışır)."""
        # Basit 3x5 font büyütülmüş
        simple_font = {
            '0': ['###', '#.#', '#.#', '#.#', '###'],
            '1': ['..#', '..#', '..#', '..#', '###'],
            '2': ['###', '..#', '###', '#..', '###'],
            '3': ['###', '..#', '###', '..#', '###'],
            '4': ['#.#', '#.#', '###', '..#', '..#'],
            '5': ['###', '#..', '###', '..#', '###'],
            '6': ['###', '#..', '###', '#.#', '###'],
            '7': ['###', '..#', '..#', '..#', '..#'],
            '8': ['###', '#.#', '###', '#.#', '###'],
            '9': ['###', '#.#', '###', '..#', '###'],
            ':': ['...', '.#.', '...', '.#.', '...'],
            '/': ['..#', '..#', '...', '#..', '#..'],
            '-': ['...', '...', '###', '...', '...'],
            ' ': ['...', '...', '...', '...', '...'],
        }
        
        if char not in simple_font:
            return
        
        pattern = simple_font[char]
        
        for row_idx, row in enumerate(pattern):
            for col_idx, pixel in enumerate(row):
                px = x + col_idx * size
                py = y + row_idx * size
                
                if pixel == '#':
                    self.fill_rect(px, py, size, size, fg_r, fg_g, fg_b)
                else:
                    self.fill_rect(px, py, size, size, bg_r, bg_g, bg_b)

    def draw_text(self, x, y, text, fg_r, fg_g, fg_b, bg_r=0, bg_g=0, bg_b=0, size=2):
        """Büyük text çiz."""
        for i, char in enumerate(text):
            char_x = x + (i * (3 + 2) * size)  # 3 pixel genişlik + 2 pixel boşluk
            if char_x > TFT_WIDTH:
                break
            self.draw_big_char(char_x, y, char, fg_r, fg_g, fg_b, bg_r, bg_g, bg_b, size)

    def cleanup(self):
        GPIO.cleanup()