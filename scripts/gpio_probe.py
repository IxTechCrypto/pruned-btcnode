#!/usr/bin/env bash
#!/usr/bin/env python3
"""
Orange Pi Zero 3 Hardware Probe & Display Test Utility
"""

import sys
import os
import time
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from display.st7789 import ST7789, find_main_gpiochip
except ImportError:
    ST7789 = None
    find_main_gpiochip = lambda: "/dev/gpiochip1"

try:
    import gpiod
except ImportError:
    gpiod = None

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


def probe_system():
    print("=" * 60)
    print("Orange Pi Zero 3 Hardware Probe")
    print("=" * 60)

    model_path = "/sys/firmware/devicetree/base/model"
    if os.path.exists(model_path):
        with open(model_path, "r") as f:
            print(f"Board Model: {f.read().strip()}")

    print(f"Platform: {sys.platform} ({os.uname().machine if hasattr(os, 'uname') else 'N/A'})")

    spidevs = [os.path.join("/dev", f) for f in os.listdir("/dev") if f.startswith("spidev")] if os.path.exists("/dev") else []
    print(f"SPI Devices Found: {spidevs}")

    if gpiod is not None:
        print(f"libgpiod version: {getattr(gpiod, '__version__', 'unknown')}")
        chips = [os.path.join("/dev", f) for f in sorted(os.listdir("/dev")) if f.startswith("gpiochip")] if os.path.exists("/dev") else []
        for c in chips:
            try:
                chip = gpiod.Chip(c)
                lines = chip.get_info().num_lines if hasattr(chip, "get_info") else chip.num_lines()
                label = chip.get_info().name if hasattr(chip, "get_info") else chip.name()
                print(f"  - {c}: ({label}) with {lines} lines")
                chip.close()
            except Exception as e:
                print(f"  - {c}: Error opening ({e})")
    print("=" * 60)


def blink_backlight(gpiochip=None, bl_pin=79, count=5):
    if gpiod is None:
        print("[ERROR] libgpiod is required for GPIO control.")
        return

    chip_path = gpiochip or find_main_gpiochip()
    print(f"[INFO] Blinking Backlight on {chip_path} line {bl_pin} ({count} cycles)...")
    try:
        chip = gpiod.Chip(chip_path)
        if hasattr(chip, "request_lines"):
            import gpiod.line as gline
            settings = gpiod.LineSettings(direction=gline.Direction.OUTPUT, output_value=gline.Value.ACTIVE)
            req = chip.request_lines(consumer="probe_bl", config={bl_pin: settings})
            for i in range(count):
                req.set_value(bl_pin, gline.Value.ACTIVE)
                print(f"  Cycle {i+1}: ON")
                time.sleep(0.5)
                req.set_value(bl_pin, gline.Value.INACTIVE)
                print(f"  Cycle {i+1}: OFF")
                time.sleep(0.5)
            req.set_value(bl_pin, gline.Value.ACTIVE)
            req.release()
        chip.close()
        print("[SUCCESS] Backlight test complete.")
    except Exception as e:
        print(f"[ERROR] Backlight test failed: {e}")


def test_display():
    if ST7789 is None:
        print("[ERROR] ST7789 driver module not loaded.")
        return

    print("[INFO] Initializing ST7789 screen and drawing test pattern...")
    try:
        disp = ST7789(width=240, height=320, spi_bus=1, spi_device=1)

        colors = [
            ((247, 147, 26), "Bitcoin Orange"),
            ((46, 204, 113), "Green"),
            ((52, 152, 219), "Blue"),
            ((231, 76, 60), "Red"),
        ]

        for color, name in colors:
            print(f"  Filling screen with {name}...")
            disp.clear(color)
            time.sleep(1.0)

        if Image is not None:
            img = Image.new("RGB", (240, 320), (15, 20, 28))
            draw = ImageDraw.Draw(img)
            draw.rectangle([10, 10, 230, 310], outline=(247, 147, 26), fill=(25, 30, 42))
            draw.text((30, 50), "BITCOIN NODE", fill=(247, 147, 26))
            draw.text((30, 80), "ORANGE PI ZERO 3", fill=(255, 255, 255))
            draw.text((30, 110), "TEST PATTERN OK", fill=(46, 204, 113))
            disp.display(img)
            time.sleep(2.0)

        print("[SUCCESS] Display test completed successfully.")
    except Exception as e:
        print(f"[ERROR] Display test failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Orange Pi Zero 3 Hardware Probe")
    parser.add_argument("--blink", action="store_true", help="Blink display backlight")
    parser.add_argument("--test-display", action="store_true", help="Cycle colors on ST7789 LCD")
    args = parser.parse_args()

    probe_system()

    if args.blink:
        blink_backlight()
    if args.test_display:
        test_display()


if __name__ == "__main__":
    main()
