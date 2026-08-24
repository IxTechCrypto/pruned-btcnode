# pruned-btcnode ₿

A minimalist, high-efficiency **Pruned Bitcoin Core Node** and **Hardware Telemetry Monitor** engineered specifically for the **Orange Pi Zero 3 (1.5 GB RAM)** running Armbian or Orange Pi OS, paired with a **Waveshare 2.0-inch ST7789 SPI LCD** (240x320).

---

## ⚡ Key Features

- **Tuned for 1.5 GB RAM**: Tailored `dbcache`, `maxmempool`, `par=2`, and `zram-tools` swap configuration prevents OOM kills during Initial Block Download (IBD).
- **Headless Wi-Fi Setup via SD Card**: Drop or edit `wifi.conf` / `wifi.txt` in the root `/boot/` partition on any PC; the node auto-connects to Wi-Fi on boot without needing an Ethernet cable.
- **Minimal Disk Footprint**: Pruned node mode (`prune=550`) runs comfortably on standard MicroSD cards or compact external USB drives without needing an expensive multi-terabyte SSD.
- **Real-Time LCD Dashboard**: Live 240x320 status display rendering block height, sync percentage, peer count, mempool activity, storage, CPU temperature, RAM utilization, and active Wi-Fi IP address.
- **Automated 1-Command Setup**: Installs Bitcoin Core binary, configures ZRAM, enables hardware SPI overlays, sets up udev rules, and provisions systemd daemons.
- **Hardware Diagnostic Probe**: Includes `gpio_probe.py` to verify SPI1 chip select and test display/backlight lines.

---

## 📶 Headless Wi-Fi Configuration (SD Card / Root Config)

Because the Orange Pi Zero 3 wireless chip (Unisoc AW859A) does not reliably support SoftAP captive portal mode in the Linux kernel driver, this project uses an **SD Card Boot-Config** approach:

### How to Configure Wi-Fi on PC:
1. After flashing Armbian (or anytime you change networks), open the SD card boot partition on your PC.
2. Create or edit `wifi.conf` (a template is provided in [`wifi.conf.example`](wifi.conf.example)):
   ```ini
   WIFI_SSID="Your_Home_WiFi_Network"
   WIFI_PASSWORD="Your_Secret_Password"
   WIFI_COUNTRY="US"
   ```
3. Save the file to `/boot/wifi.conf` (or directly in the root of the repo).
4. Insert the SD card into the Orange Pi and power on. The `wifi-autoconnect.service` will automatically connect to your Wi-Fi network and display the acquired IP address on the LCD screen!

---

## 🛠 Hardware Wiring (Orange Pi Zero 3 Header)

The Orange Pi Zero 3 features a 26-pin physical expansion header. The Waveshare 2.0" ST7789 LCD connects as follows:

| Pin # | Header Pin Name | Allwinner H618 GPIO | LCD Pin | Function / Description |
| :---: | :--- | :--- | :---: | :--- |
| **1** or **17** | `3.3V` | 3.3V Power | **VCC** | 3.3V DC Power |
| **9** or **25** | `GND` | Ground | **GND** | Ground |
| **19** | `SPI1_MOSI` | `PH7` (Line 231) | **DIN** | SPI Data In / MOSI |
| **23** | `SPI1_CLK` | `PH6` (Line 230) | **CLK** | SPI Clock |
| **26** | `SPI1_CS1` | `PH9` (Line 233) | **CS** | Chip Select 1 (`/dev/spidev1.1`) |
| **22** | `GPIO_71` | `PC7` (Line 71) | **DC** | Data / Command Select |
| **18** | `GPIO_78` | `PC14` (Line 78) | **RST** | Hardware Reset |
| **16** | `GPIO_79` | `PC15` (Line 79) | **BL** | LCD Backlight Control |

> **Note on Chip Select**: On the Orange Pi Zero 3, Pin 26 routes to `PH9`, which is **SPI1 CS1** (`/dev/spidev1.1`). Ensure `spi1-cs1-spidev` overlay is active.

---

## 🚀 Quick Start (Automated Installation)

Clone this repository directly onto your Orange Pi Zero 3:

```bash
git clone https://github.com/your-username/pruned-btcnode.git
cd pruned-btcnode

# Copy and set your Wi-Fi credentials
cp wifi.conf.example wifi.conf
nano wifi.conf

# Run the automated installer
sudo bash scripts/install.sh
```

If this is your first time enabling the SPI overlay on the board, perform a quick reboot:
```bash
sudo reboot
```

After reboot, all background services (`bitcoind`, `btc-display`, `wifi-autoconnect`) start automatically. You can check status anytime:
```bash
sudo systemctl status bitcoind
sudo systemctl status btc-display
sudo systemctl status wifi-autoconnect
```

---

## 🖥 Terminal Dashboard & CLI Tools

To view an instant terminal summary over SSH without looking at the physical screen:

```bash
/opt/pruned-btcnode/scripts/btc-status.sh
```

Output preview:
```text
============================================================
 ₿ Bitcoin Pruned Node Status (Orange Pi Zero 3)
============================================================
 Daemon Status:       ● Active (Running)
 Client Version:     /Satoshi:28.0.0/
 Synced Blocks:      884,120 / 884,120 (100.00%)
 Prune Mode:         true (550 MB)
 Active Peers:       14
 Mempool:            8,420 transactions (18.40 MB)
------------------------------------------------------------
 CPU Temperature:    47.8°C
 RAM & Swap Usage:
               total        used        free      shared  buff/cache   available
   Mem:        1.4Gi       620Mi       410Mi       8.0Mi       380Mi       750Mi
   Swap:       1.4Gi       120Mi       1.3Gi
============================================================
```

---

## 🔍 Hardware & Display Diagnostics

If the screen is blank or you are troubleshooting header wiring, run the diagnostic utility:

```bash
# Display hardware information and detect SPI / GPIO lines
python3 scripts/gpio_probe.py

# Blink the display backlight 5 times to confirm BL pin wiring
python3 scripts/gpio_probe.py --blink

# Send RGB color test pattern to LCD
python3 scripts/gpio_probe.py --test-display
```

---

## 🧠 Memory & Performance Architecture

Running a full validation node on 1.5 GB of RAM requires careful resource budgeting:

1. **`dbcache=450`**: Allocates 450 MB of RAM for the UTXO database cache during Initial Block Download. Once synchronized, memory footprint drops significantly.
2. **`maxmempool=100`**: Caps the unconfirmed transaction pool at 100 MB (down from 300 MB default), preventing mempool spikes from starving the system.
3. **`par=2`**: Limits parallel signature verification threads to 2, balancing throughput while minimizing thread contention and temporary stack allocations on the 4-core Allwinner H618.
4. **`zram-tools` (LZ4 compressed swap)**: Configures 100% of RAM (1536 MB) as ultra-fast compressed swap in RAM. This absorbs validation bursts without thrashing the SD card.

---

## 📁 Repository Structure

```
pruned-btcnode/
├── .gitignore
├── LICENSE                   # MIT License
├── README.md                 # Documentation & wiring guide
├── wifi.conf.example         # Wi-Fi configuration template for SD card / boot
├── config/
│   ├── bitcoin.conf          # Tuned Bitcoin Core configuration
│   ├── zram-tools.conf       # 1.5GB ZRAM swap configuration
│   └── 99-spidev-gpio.rules  # Udev permissions for non-root hardware access
├── display/
│   ├── btc_display.py        # Real-time LCD telemetry renderer with Wi-Fi IP display
│   └── st7789.py             # Orange Pi Zero 3 ST7789 SPI driver
├── scripts/
│   ├── install.sh            # End-to-end setup script
│   ├── wifi_autoconnect.sh   # Boot-time Wi-Fi credential loader
│   ├── gpio_probe.py         # Hardware & pinout diagnostic probe
│   └── btc-status.sh         # Terminal CLI status monitor
└── systemd/
    ├── bitcoind.service      # Hardened Bitcoin daemon service
    ├── btc-display.service   # Display monitor daemon service
    └── wifi-autoconnect.service # Auto-connects Wi-Fi before bitcoind starts
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
