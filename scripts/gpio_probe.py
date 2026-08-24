#!/usr/bin/env python3
"""
Orange Pi Zero 3 Hardware Probe & Display Test Utility
Use this script to verify SPI1 (/dev/spidev1.1) and libgpiod line controls.
"""

import sys
import os
import time
import argparse

try:
    from display.st7789 import ST7789
except ImportError:
    try:
        from st7789 import ST7789
    except ImportError:
        ST7789 = None

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

    # 1. Model Info
    model_path = "/sys/firmware/devicetree/base/model"
    if os.path.exists(model_path):
        with open(model_path, "r") as f:
            print(f"Board Model: {f.read().strip()}")
    else:
        print("Board Model: Unknown / non-Linux")

    # 2. Kernel & Architecture
    print(f"Platform: {sys.platform} ({os.uname().machine if hasattr(os, 'uname') else 'N/A'})")

    # 3. SPI Devices
    spidevs = [os.path.join("/dev", f) for f in os.listdir("/dev") if f.startswith("spidev")] if os.path.exists("/dev") else []
    print(f"SPI Devices Found: {spidevs if spidevs else 'NONE (Enable spi1-cs1-spidev in /boot/orangepiEnv.txt)'}")

    # 4. GPIO Chips
    if gpiod is not None:
        print(f"libgpiod version: {getattr(gpiod, '__version__', 'unknown')}")
        chips = [os.path.join("/dev", f) for f in os.listdir("/dev") if f.startswith("gpiochip")] if os.path.exists("/dev") else []
        for c in chips:
            try:
                chip = gpiod.Chip(c)
                print(f"  - {c}: {chip.name()} ({chip.label()}) with {chip.num_lines()} lines")
                chip.close()
            except Exception as e:
                print(f"  - {c}: Error opening ({e})")
    else:
        print("libgpiod: NOT INSTALLED (Run: sudo apt-get install python3-gpiod)")
    print("=" * 60)


def blink_backlight(gpiochip="/dev/gpiochip0", bl_pin=79, count=5):
    if gpiod is None:
        print("[ERROR] libgpiod is required for GPIO control.")
        return

    print(f"[INFO] Blinking Backlight on {gpiochip} line {bl_pin} ({count} cycles)...")
    try:
        chip = gpiod.Chip(gpiochip)
        line = chip.get_line(bl_pin)
        line.request(consumer="probe_bl", type=gpiod.LINE_REQ_DIR_OUT)

        for i in range(count):
            line.set_value(1)
            print(f"  Cycle {i+1}: ON")
            time.sleep(0.5)
            line.set_value(0)
            print(f"  Cycle {i+1}: OFF")
            time.sleep(0.5)

        line.set_value(1) # Leave on
        line.release()
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

        # Draw graphic card test
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
