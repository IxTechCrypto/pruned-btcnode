import os
import sys
import time
import spidev
import gpiod
import gpiod.line as gline
from PIL import Image, ImageDraw

print("=== Screen Diagnostic Test ===")

# Check SPI devices
spidevs = [f for f in os.listdir("/dev") if f.startswith("spidev")]
print(f"Available SPI devices: {spidevs}")

chip = gpiod.Chip("/dev/gpiochip1")
print(f"Opened GPIO chip: {chip.get_info().name} with {chip.get_info().num_lines} lines")

# Let's inspect relevant GPIO lines
for line_no, name in [(71, "PC7 (DC opt 1)"), (74, "PC10 (DC opt 2)"), (78, "PC14 (RST)"), (79, "PC15 (BL)")]:
    linfo = chip.get_line_info(line_no)
    print(f"  Line {line_no} [{name}]: name={linfo.name}, used={linfo.used}, consumer={linfo.consumer}")

# Stop display service if running
os.system("systemctl stop btc-display 2>/dev/null")

# Test configurations
settings_out_high = gpiod.LineSettings(direction=gline.Direction.OUTPUT, output_value=gline.Value.ACTIVE)
settings_out_low = gpiod.LineSettings(direction=gline.Direction.OUTPUT, output_value=gline.Value.INACTIVE)

# Request lines 71, 74, 78, 79
req = chip.request_lines(
    consumer="debug_test",
    config={
        71: settings_out_low,
        74: settings_out_low,
        78: settings_out_high,
        79: settings_out_high,
    }
)

print("[INFO] Backlight (Line 79) set to HIGH.")

# Try sending color fill on both /dev/spidev1.0 and /dev/spidev1.1 with both DC candidates
def test_send(dev_name, dc_pin):
    bus, device = 1, int(dev_name.split(".")[1])
    print(f"\n---> Testing on /dev/spidev1.{device} with DC=Line {dc_pin} (RST=78, BL=79)...")
    
    spi = spidev.SpiDev()
    spi.open(bus, device)
    spi.max_speed_hz = 24000000
    spi.mode = 0b00
    
    # Hardware Reset
    req.set_value(78, gline.Value.ACTIVE)
    time.sleep(0.01)
    req.set_value(78, gline.Value.INACTIVE)
    time.sleep(0.05)
    req.set_value(78, gline.Value.ACTIVE)
    time.sleep(0.05)
    
    def cmd(c):
        req.set_value(dc_pin, gline.Value.INACTIVE)
        spi.writebytes([c])
        
    def data(d):
        req.set_value(dc_pin, gline.Value.ACTIVE)
        if isinstance(d, int):
            spi.writebytes([d])
        else:
            for i in range(0, len(d), 4096):
                spi.writebytes(list(d[i:i+4096]))

    cmd(0x01) # SWRESET
    time.sleep(0.15)
    cmd(0x11) # SLPOUT
    time.sleep(0.12)
    cmd(0x3A) # COLMOD 16-bit
    data(0x55)
    cmd(0x36) # MADCTL
    data(0x00)
    cmd(0x21) # INVON
    time.sleep(0.01)
    cmd(0x13) # NORON
    time.sleep(0.01)
    cmd(0x29) # DISPON
    time.sleep(0.02)

    # Set Window 240x320
    cmd(0x2A)
    data([0x00, 0x00, 0x00, 0xEF])
    cmd(0x2B)
    data([0x00, 0x00, 0x01, 0x3F])
    cmd(0x2C)
    
    # Send Bright Orange Fill
    r, g, b = (247, 147, 26)
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    hi = (rgb565 >> 8) & 0xFF
    lo = rgb565 & 0xFF
    pixels = bytes([hi, lo]) * (240 * 320)
    data(pixels)
    print(f"Sent 240x320 Orange fill to /dev/spidev1.{device} using DC={dc_pin}!")
    spi.close()

# Test spidev1.1 and spidev1.0 with DC=71 and DC=74
for spidev_dev in ["spidev1.1", "spidev1.0"]:
    for dc in [71, 74]:
        try:
            test_send(spidev_dev, dc)
            time.sleep(1.0)
        except Exception as e:
            print(f"Error testing {spidev_dev} with DC {dc}: {e}")

req.release()
chip.close()
print("\n=== Test Finished ===")
