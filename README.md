# pruned-btcnode ₿

A minimalist, high-efficiency **Pruned Bitcoin Core Node (v31.1)** with a **Cyberpunk Web Dashboard (3D Dot-Matrix Earth)** and **Hardware LCD Monitor** engineered specifically for the **Orange Pi Zero 3 (1.5 GB RAM)** running Armbian or Orange Pi OS.

---

## ⚡ Key Features

- **Latest Bitcoin Core v31.1**: Pre-configured with memory tuning (`dbcache=450`, `maxmempool=100`, `par=2`, `prune=550`) and active LZ4 ZRAM swap.
- **Cyberpunk Web Dashboard (Port 8334)**:
  - **Interactive 3D Dot-Matrix Earth Globe**: Rotating global P2P topology with live arc connections from your Orange Pi to peers worldwide.
  - **Hero Block Sync Telemetry**: Live block height counters, verification progress gauge, network difficulty, and mempool depth.
  - **Host Diagnostics**: Real-time Orange Pi Zero 3 CPU temperature, RAM + ZRAM utilization, and MicroSD storage meter.
  - **Browser RPC Command Console**: Execute `bitcoin-cli` queries directly from your web browser.
- **Headless Wi-Fi Setup via SD Card**: Drop or edit `wifi.conf` / `wifi.txt` in the root `/boot/` partition on any PC; the node auto-connects to Wi-Fi on boot without needing an Ethernet cable.
- **Minimal Disk Footprint**: Pruned node mode (`prune=550`) runs comfortably on standard MicroSD cards without needing an external multi-terabyte SSD.
- **2.0-inch Waveshare SPI LCD Support**: Live status display on `/dev/spidev1.1` (PH9 CS1).

---

## 🌐 Cyberpunk Web Dashboard Access

Once your node is booted and connected to your network, open your web browser to:

```text
http://<ORANGE_PI_IP>:8334
# Example: http://192.168.4.75:8334 or http://orangepizero3.local:8334
```

---

## 📶 Headless Wi-Fi Configuration (SD Card / Root Config)

1. Open the SD card boot partition on your PC.
2. Create or edit `wifi.conf` (template provided in [`wifi.conf.example`](wifi.conf.example)):
   ```ini
   WIFI_SSID="Your_Home_WiFi_Network"
   WIFI_PASSWORD="Your_Secret_Password"
   WIFI_COUNTRY="US"
   ```
3. Save to `/boot/wifi.conf` (or repo root) and insert into the Orange Pi.

---

## 🚀 Quick Start (Automated Installation)

Clone this repository directly onto your Orange Pi Zero 3:

```bash
git clone https://github.com/IxTechCrypto/pruned-btcnode.git
cd pruned-btcnode
sudo bash scripts/install.sh
sudo reboot
```

---

## 🖥 Terminal CLI Dashboard

To view an instant terminal summary over SSH:

```bash
/opt/pruned-btcnode/scripts/btc-status.sh
```

---

## 📁 Repository Structure

```
pruned-btcnode/
├── .gitignore
├── LICENSE                   # MIT License
├── README.md                 # Documentation & web dashboard guide
├── wifi.conf.example         # Wi-Fi configuration template for SD card / boot
├── config/
│   ├── bitcoin.conf          # Tuned Bitcoin Core configuration
│   ├── zram-tools.conf       # 1.5GB ZRAM swap configuration
│   └── 99-spidev-gpio.rules  # Udev permissions for non-root hardware access
├── display/
│   ├── btc_display.py        # 240x320 LCD telemetry renderer
│   └── st7789.py             # ST7789 SPI driver for Orange Pi Zero 3
├── web/
│   ├── server.py             # Ultra-lightweight multi-threaded JSON API & dashboard server
│   └── static/
│       ├── index.html        # Cyberpunk Web HUD
│       ├── style.css         # Glassmorphic neon theme
│       ├── globe.js          # Interactive 3D Dot-Matrix Earth Canvas
│       └── dashboard.js      # Real-time WebSocket/polling controller & RPC console
├── scripts/
│   ├── install.sh            # End-to-end setup script (Bitcoin Core v31.1)
│   ├── wifi_autoconnect.sh   # Boot-time Wi-Fi credential loader
│   ├── gpio_probe.py         # Hardware & pinout diagnostic probe
│   └── btc-status.sh         # Terminal CLI status monitor
└── systemd/
    ├── bitcoind.service      # Hardened Bitcoin daemon service
    ├── btc-display.service   # Display monitor daemon service
    ├── btc-web.service       # Cyberpunk Web Dashboard service (Port 8334)
    └── wifi-autoconnect.service # Auto-connects Wi-Fi before bitcoind starts
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
