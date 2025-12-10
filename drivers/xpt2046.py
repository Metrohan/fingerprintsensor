# xpt2046.py
# Basit XPT2046 dokunmatik driver (SPI)

import spidev
import RPi.GPIO as GPIO
import time

# Bağlantı (senin şemana göre)
PIN_IRQ = 7   # T_IRQ
PIN_CS  = 8   # T_CS (SPI0_CE0)

class XPT2046:
    def __init__(self, spi_bus=0, spi_dev=0, max_speed=2000000):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_IRQ, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_CS, GPIO.OUT)
        GPIO.output(PIN_CS, 1)

        self.spi = spidev.SpiDev()
        try:
            self.spi.open(spi_bus, spi_dev)  # bus=0, dev=0 → CE0
            self.spi.max_speed_hz = max_speed
            self.spi.mode = 0b00
        except Exception as e:
            print(f"SPI açma hatası: {e}")
            print("SPI modülünün yüklenmiş olduğundan emin olun: sudo raspi-config")
            raise

    def is_touched(self):
        # IRQ düşük ise dokunma var
        return GPIO.input(PIN_IRQ) == 0

    def read_raw(self):
        """
        X,Y ham değer okuma.
        12 bit değer döner (0..4095).
        """
        def read_channel(cmd):
            GPIO.output(PIN_CS, 0)
            # Command: 8 bit, ardından okuma: 16 bit (2 byte)
            r = self.spi.xfer2([cmd, 0x00, 0x00])
            GPIO.output(PIN_CS, 1)
            # Sonuç: r[1] high byte (8 bit), r[2] low byte (8 bit)
            # 12-bit değer: (r[1] << 4) | (r[2] >> 4)
            val = ((r[1] << 4) | (r[2] >> 4)) & 0xFFF
            return val

        # XPT2046: Koordinatları swap et (0xD0=Y axis, 0x90=X axis)
        y_raw = read_channel(0xD0)
        x_raw = read_channel(0x90)
        return x_raw, y_raw

    def read_point(self, samples=5):
        """
        Basit filtreli dokunma noktası (ortalama).
        Dokunulmamışsa None döner.
        """
        if not self.is_touched():
            return None

        xs = []
        ys = []
        for _ in range(samples):
            if not self.is_touched():
                break
            x, y = self.read_raw()
            xs.append(x)
            ys.append(y)
            time.sleep(0.01)

        if not xs:
            return None

        return sum(xs) / len(xs), sum(ys) / len(ys)

    def cleanup(self):
        self.spi.close()
        GPIO.cleanup()