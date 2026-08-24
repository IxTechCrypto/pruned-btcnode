"""
ST7789 SPI LCD Display Driver for Waveshare 2.0" 240x320 LCD
Target: Orange Pi Zero 3 (Allwinner H618 / sun50i-h616)

Pinout (Physical 26-pin Header):
  - CS:  Pin 26 -> PH9  (spidev1.1)
  - DC:  Pin 22 -> PC7  (gpiochip0 line 71, or PC10 line 74)
  - RST: Pin 18 -> PC14 (gpiochip0 line 78)
  - BL:  Pin 16 -> PC15 (gpiochip0 line 79)
  - CLK: Pin 23 -> SPI1_CLK
  - DIN: Pin 19 -> SPI1_MOSI
"""

import time
import os
import sys

try:
    import spidev
except ImportError:
    spidev = None

try:
    import gpiod
except ImportError:
    gpiod = None

# ST7789 Commands
ST7789_NOP = 0x00
ST7789_SWRESET = 0x01
ST7789_SLPIN = 0x10
ST7789_SLPOUT = 0x11
ST7789_NORON = 0x13
ST7789_INVOFF = 0x20
ST7789_INVON = 0x21
ST7789_DISPOFF = 0x28
ST7789_DISPON = 0x29
ST7789_CASET = 0x2A
ST7789_RASET = 0x2B
ST7789_RAMWR = 0x2C
ST7789_MADCTL = 0x36
ST7789_COLMOD = 0x3A

# Default GPIO line offsets on Allwinner H618 gpiochip0
DEFAULT_DC_LINE = 71   # PC7 (or 74 / PC10 depending on header rev)
DEFAULT_RST_LINE = 78  # PC14
DEFAULT_BL_LINE = 79   # PC15


class ST7789:
    def __init__(
        self,
        width=240,
        height=320,
        spi_bus=1,
        spi_device=1,
        spi_speed_hz=40000000,
        dc_pin=DEFAULT_DC_LINE,
        rst_pin=DEFAULT_RST_LINE,
        bl_pin=DEFAULT_BL_LINE,
        gpiochip="/dev/gpiochip0",
        rotation=0,
    ):
        self.width = width
        self.height = height
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.spi_speed_hz = spi_speed_hz
        self.dc_pin = dc_pin
        self.rst_pin = rst_pin
        self.bl_pin = bl_pin
        self.gpiochip_path = gpiochip
        self.rotation = rotation

        self.spi = None
        self.chip = None
        self.gpiod_v2_request = None
        self.dc_line = None
        self.rst_line = None
        self.bl_line = None

        self._init_hardware()

    def _init_hardware(self):
        # 1. Initialize SPI
        if spidev is not None:
            try:
                self.spi = spidev.SpiDev()
                self.spi.open(self.spi_bus, self.spi_device)
                self.spi.max_speed_hz = self.spi_speed_hz
                self.spi.mode = 0b00  # Mode 0
            except Exception as e:
                print(f"[WARN] Failed to open SPI device: {e}")
        else:
            print("[WARN] spidev library not found. Running in simulation mode.")

        # 2. Initialize GPIO (Supports both libgpiod v1.x and v2.x)
        if gpiod is not None and os.path.exists(self.gpiochip_path):
            try:
                # Check for libgpiod 1.x vs 2.x
                if hasattr(gpiod, "Chip"):
                    self.chip = gpiod.Chip(self.gpiochip_path)
                    
                    if hasattr(self.chip, "get_line"):
                        # libgpiod 1.x API
                        self.dc_line = self.chip.get_line(self.dc_pin)
                        self.dc_line.request(consumer="st7789_dc", type=gpiod.LINE_REQ_DIR_OUT)

                        self.rst_line = self.chip.get_line(self.rst_pin)
                        self.rst_line.request(consumer="st7789_rst", type=gpiod.LINE_REQ_DIR_OUT)

                        self.bl_line = self.chip.get_line(self.bl_pin)
                        self.bl_line.request(consumer="st7789_bl", type=gpiod.LINE_REQ_DIR_OUT)
                    elif hasattr(self.chip, "request_lines"):
                        # libgpiod 2.x API
                        from gpiod.line import Direction, Value
                        config = {
                            self.dc_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
                            self.rst_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
                            self.bl_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
                        }
                        self.gpiod_v2_request = self.chip.request_lines(consumer="st7789", config=config)
            except Exception as e:
                print(f"[WARN] libgpiod initialization failed: {e}")
        else:
            print("[WARN] libgpiod not available or gpiochip device node not found.")

        self.reset()
        self.init_display()
        self.set_backlight(True)

    def _set_dc(self, val: int):
        if self.dc_line:
            self.dc_line.set_value(val)
        elif self.gpiod_v2_request:
            from gpiod.line import Value
            self.gpiod_v2_request.set_value(self.dc_pin, Value.ACTIVE if val else Value.INACTIVE)

    def _set_rst(self, val: int):
        if self.rst_line:
            self.rst_line.set_value(val)
        elif self.gpiod_v2_request:
            from gpiod.line import Value
            self.gpiod_v2_request.set_value(self.rst_pin, Value.ACTIVE if val else Value.INACTIVE)

    def set_backlight(self, on: bool):
        if self.bl_line:
            self.bl_line.set_value(1 if on else 0)
        elif self.gpiod_v2_request:
            from gpiod.line import Value
            self.gpiod_v2_request.set_value(self.bl_pin, Value.ACTIVE if on else Value.INACTIVE)

    def reset(self):
        self._set_rst(1)
        time.sleep(0.01)
        self._set_rst(0)
        time.sleep(0.05)
        self._set_rst(1)
        time.sleep(0.05)

    def command(self, cmd: int):
        self._set_dc(0)
        if self.spi:
            self.spi.writebytes([cmd])

    def data(self, val):
        self._set_dc(1)
        if self.spi:
            if isinstance(val, int):
                self.spi.writebytes([val])
            elif isinstance(val, (bytes, bytearray, list)):
                chunk_size = 4096
                for i in range(0, len(val), chunk_size):
                    chunk = val[i : i + chunk_size]
                    self.spi.writebytes(list(chunk) if isinstance(chunk, (bytes, bytearray)) else chunk)

    def init_display(self):
        self.command(ST7789_SWRESET)
        time.sleep(0.15)

        self.command(ST7789_SLPOUT)
        time.sleep(0.12)

        # 16-bit color (RGB565)
        self.command(ST7789_COLMOD)
        self.data(0x55)

        # Memory data access control (rotation)
        self.command(ST7789_MADCTL)
        if self.rotation == 0:
            self.data(0x00)
        elif self.rotation == 90:
            self.data(0x70)
        elif self.rotation == 180:
            self.data(0xC0)
        elif self.rotation == 270:
            self.data(0xA0)
        else:
            self.data(0x00)

        self.command(ST7789_INVON)
        time.sleep(0.01)

        self.command(ST7789_NORON)
        time.sleep(0.01)

        self.command(ST7789_DISPON)
        time.sleep(0.02)

    def set_window(self, x0, y0, x1, y1):
        self.command(ST7789_CASET)
        self.data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self.command(ST7789_RASET)
        self.data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self.command(ST7789_RAMWR)

    def display(self, image):
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))

        img_rgb = image.convert("RGB")
        raw_data = img_rgb.tobytes()

        buf = bytearray(self.width * self.height * 2)
        idx = 0
        for i in range(0, len(raw_data), 3):
            r = raw_data[i]
            g = raw_data[i + 1]
            b = raw_data[i + 2]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buf[idx] = (rgb565 >> 8) & 0xFF
            buf[idx + 1] = rgb565 & 0xFF
            idx += 2

        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.data(buf)

    def clear(self, color=(0, 0, 0)):
        r, g, b = color
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        hi = (rgb565 >> 8) & 0xFF
        lo = rgb565 & 0xFF
        pixel_bytes = bytes([hi, lo]) * (self.width * self.height)

        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.data(pixel_bytes)

    def close(self):
        self.set_backlight(False)
        if self.spi:
            self.spi.close()
        if self.dc_line:
            self.dc_line.release()
        if self.rst_line:
            self.rst_line.release()
        if self.bl_line:
            self.bl_line.release()
        if self.gpiod_v2_request:
            self.gpiod_v2_request.release()
        if self.chip:
            self.chip.close()
