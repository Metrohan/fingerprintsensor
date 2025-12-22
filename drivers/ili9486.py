# ili9486.py
# 3.5" 8-bit TFT LCD Shield için basit ILI9486 driver (Raspberry Pi GPIO)
# Ekran yatay (480x320) olacak şekilde ayarlandı.
#
# Ek olarak:
# - 5x7 bitmap font ile draw_char / draw_text fonksiyonları eklendi.

import RPi.GPIO as GPIO
import time
import os
import sys

# Parent dizini path'e ekle (logger için)
DRIVER_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(DRIVER_DIR)
sys.path.insert(0, BASE_DIR)

from logger import setup_logger

# Logger oluştur
log = setup_logger("lcd")

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


# 5x7 büyük harf / rakam fontu (kolon bazlı)
# Her karakter 5 sütun, her sütunda 7 bit (LSB = üst piksel)
FONT_5x7 = {
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
    '1': [0x04, 0x02, 0x3F, 0x00, 0x00],
    '2': [0x32, 0x49, 0x49, 0x49, 0x26],
    '3': [0x22, 0x41, 0x49, 0x49, 0x36],
    '4': [0x0F, 0x08, 0x08, 0x3E, 0x08],
    '5': [0x27, 0x45, 0x45, 0x45, 0x39],
    '6': [0x3E, 0x49, 0x49, 0x49, 0x30],
    '7': [0x01, 0x01, 0x39, 0x05, 0x03],
    '8': [0x36, 0x49, 0x49, 0x49, 0x36],
    '9': [0x06, 0x49, 0x49, 0x49, 0x3E],
    'A': [0x3E, 0x09, 0x09, 0x09, 0x3E],
    'B': [0x3F, 0x49, 0x49, 0x49, 0x36],
    'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
    'D': [0x3F, 0x41, 0x41, 0x22, 0x1C],
    'E': [0x3F, 0x49, 0x49, 0x49, 0x41],
    'F': [0x3F, 0x09, 0x09, 0x09, 0x01],
    'G': [0x3E, 0x41, 0x49, 0x49, 0x3A],
    'H': [0x3F, 0x08, 0x08, 0x08, 0x3F],
    'I': [0x00, 0x41, 0x3F, 0x41, 0x00],
    'J': [0x20, 0x40, 0x40, 0x40, 0x3F],
    'K': [0x3F, 0x08, 0x0C, 0x12, 0x21],
    'L': [0x3F, 0x40, 0x40, 0x40, 0x40],
    'M': [0x3F, 0x02, 0x04, 0x02, 0x3F],
    'N': [0x3F, 0x02, 0x04, 0x08, 0x3F],
    'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
    'P': [0x3F, 0x09, 0x09, 0x09, 0x06],
    'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E],
    'R': [0x3F, 0x09, 0x19, 0x29, 0x46],
    'S': [0x26, 0x49, 0x49, 0x49, 0x32],
    'T': [0x01, 0x01, 0x3F, 0x01, 0x01],
    'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
    'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
    'W': [0x3F, 0x20, 0x10, 0x20, 0x3F],
    'X': [0x21, 0x12, 0x0C, 0x12, 0x21],
    'Y': [0x07, 0x08, 0x30, 0x08, 0x07],
    'Z': [0x21, 0x31, 0x29, 0x25, 0x23],
    ':': [0x00, 0x36, 0x36, 0x00, 0x00],
    '/': [0x20, 0x10, 0x08, 0x04, 0x02],
    '-': [0x08, 0x08, 0x08, 0x08, 0x08],
    '.': [0x00, 0x60, 0x60, 0x00, 0x00]
}


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
        # 0x28: Yatay yön + BGR
        self.write_command(0x36)
        self.write_data8(0x28)

        # Display ON
        self.write_command(0x29)
        time.sleep(0.05)

    def set_address_window(self, x0, y0, x1, y1):
        # Bounds clamp
        if x0 < 0: x0 = 0
        if y0 < 0: y0 = 0
        if x1 >= TFT_WIDTH: x1 = TFT_WIDTH - 1
        if y1 >= TFT_HEIGHT: y1 = TFT_HEIGHT - 1

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

    # ----------------- PIXEL & TEXT FONKSIYONLARI -----------------

    def draw_pixel(self, x, y, r, g, b):
        """Tek piksel çiz."""
        if x < 0 or x >= TFT_WIDTH or y < 0 or y >= TFT_HEIGHT:
            return
        color = self.rgb565(r, g, b)
        self.set_address_window(x, y, x, y)
        GPIO.output(PIN_CS, 0)
        GPIO.output(PIN_RS, 1)
        # high byte
        self.write_bus((color >> 8) & 0xFF)
        self.pulse_wr()
        # low byte
        self.write_bus(color & 0xFF)
        self.pulse_wr()
        GPIO.output(PIN_CS, 1)

    def _normalize_char(self, ch: str) -> str:
        """Türkçe karakterleri en yakın Latin'e çevir, küçükleri büyüt."""
        tr_map = {
            'ç': 'C', 'Ç': 'C',
            'ğ': 'G', 'Ğ': 'G',
            'ı': 'I', 'İ': 'I',
            'ö': 'O', 'Ö': 'O',
            'ş': 'S', 'Ş': 'S',
            'ü': 'U', 'Ü': 'U',
        }
        if ch in tr_map:
            return tr_map[ch]
        ch = ch.upper()
        if ch not in FONT_5x7:
            return ' '  # desteklenmeyen karakter
        return ch

    def draw_char(self, x, y, ch, fr, fg, fb, br, bg, bb, size=1, paint_bg=True):
        """
        5x7 fontla tek karakter çiz.
        (fr,fg,fb) = yazı rengi, (br,bg,bb) = arka plan
        size = ölçek (1,2,3…)
        """
        ch = self._normalize_char(ch)
        pattern = FONT_5x7.get(ch, FONT_5x7[' '])

        # Karakter boyutu
        char_w = 5 * size
        char_h = 7 * size

        # Sütun sütun piksel çiz
        for col in range(5):
            col_bits = pattern[col]
            for row in range(7):
                pixel_on = (col_bits >> row) & 0x01
                if not pixel_on:
                    if not paint_bg:
                        continue  # Arka planı işlemeyerek daha hızlı çiz
                    color = (br, bg, bb)
                else:
                    color = (fr, fg, fb)

                if size == 1:
                    self.draw_pixel(x + col, y + row, *color)
                else:
                    self.fill_rect(x + col * size,
                                   y + row * size,
                                   size,
                                   size,
                                   *color)

        # Sağda 1 kolonluk boşluk bırakmak için fonksiyon bunu döndürmez ama
        # draw_text bunu hesaba katar.

    def draw_text(self, x, y, text, fr, fg, fb, br, bg, bb, size=1, paint_bg=True):
        """
        Metni (x,y)'den itibaren çiz.
        text: string
        fr,fg,fb : yazı rengi
        br,bg,bb : arka plan rengi
        size: ölçek (1,2,3…)
        """
        # Clear the area before drawing new text
        if paint_bg:
            self.fill_rect(x, y, (5 + 1) * size * len(text), 8 * size, br, bg, bb)

        cursor_x = x
        cursor_y = y
        step_x = (5 + 1) * size  # 5 columns + 1 space

        for ch in text:
            if ch == '\n':
                cursor_x = x
                cursor_y += 8 * size
                continue

            if cursor_x + 5 * size >= TFT_WIDTH:
                # end of line, move down
                cursor_x = x
                cursor_y += 8 * size

            self.draw_char(cursor_x, cursor_y, ch,
                           fr, fg, fb,
                           br, bg, bb,
                           size=size,
                           paint_bg=paint_bg)
            cursor_x += step_x

    def draw_text_center(self, y, text, fr, fg, fb, br, bg, bb, size=1, paint_bg=True):
        """Yatay merkezde metin çiz. draw_text üzerindeki ince bir sarmalayıcı."""
        if text is None:
            text = ""
        step_x = (5 + 1) * size
        text_width = len(text) * step_x
        start_x = max((TFT_WIDTH - text_width) // 2, 0)
        self.draw_text(start_x, y, text, fr, fg, fb, br, bg, bb, size=size, paint_bg=paint_bg)

    def draw_image(self, x, y, image_path):
        """
        PNG resmini ekranda belirtilen (x,y) konumundan çiz.
        Resim ekran boyutuna göre otomatik ölçeklenir.
        """
        import os
        if not os.path.exists(image_path):
            log.error(f"Image file not found: {image_path}")
            return False
            
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            log.error("PIL/numpy not available, skipping image draw")
            return False

        try:
            img = Image.open(image_path)
            img = img.convert("RGB")
            
            # Ekran boyutuna sığdır
            target_w = TFT_WIDTH - x
            target_h = TFT_HEIGHT - y
            img_w, img_h = img.size
            
            # Eğer resim ekran boyutundan farklıysa, ölçekle
            if img_w != target_w or img_h != target_h:
                img = img.resize((target_w, target_h), Image.LANCZOS)
                log.debug(f"Image resized from {img_w}x{img_h} to {target_w}x{target_h}")
            
            img_w, img_h = img.size
            arr = np.array(img, dtype=np.uint8)
            self.set_address_window(x, y, x + img_w - 1, y + img_h - 1)
            GPIO.output(PIN_CS, 0)
            GPIO.output(PIN_RS, 1)
            # RGB888 -> RGB565 batch
            arr565 = (((arr[:,:,0].astype(np.uint16) & 0xF8) << 8) | 
                      ((arr[:,:,1].astype(np.uint16) & 0xFC) << 3) | 
                      ((arr[:,:,2].astype(np.uint16) & 0xF8) >> 3)).flatten()
            for i in range(0, len(arr565)):
                color = int(arr565[i])  # numpy int -> Python int
                self.write_bus((color >> 8) & 0xFF)
                self.pulse_wr()
                self.write_bus(color & 0xFF)
                self.pulse_wr()
            GPIO.output(PIN_CS, 1)
            log.info(f"Image loaded: {image_path} ({img_w}x{img_h})")
            return True
        except Exception as e:
            log.error(f"Error loading image {image_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def cleanup(self):
        GPIO.cleanup()