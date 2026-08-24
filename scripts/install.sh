#!/usr/bin/env bash
# ==============================================================================
# Automated Installer: Pruned Bitcoin Node on Orange Pi Zero 3 (1.5 GB RAM)
# ==============================================================================

set -e

BTC_VERSION="28.0"
BTC_ARCH="aarch64-linux-gnu"
BTC_TAR="bitcoin-${BTC_VERSION}-${BTC_ARCH}.tar.gz"
BTC_URL="https://bitcoincore.org/bin/bitcoin-core-${BTC_VERSION}/${BTC_TAR}"

DATA_DIR="/var/lib/bitcoind"
CONF_DIR="/etc/bitcoin"
APP_DIR="/opt/pruned-btcnode"

echo "===================================================================="
echo " Starting Installation: Bitcoin Core Pruned Node for Orange Pi Zero 3"
echo "===================================================================="

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run this installer with sudo or as root."
    exit 1
fi

# 1. Update and install dependencies (supports Debian Trixie & Bookworm)
echo "[1/9] Installing system dependencies..."
apt-get update -y

# Base tools and system libraries
apt-get install -y \
    curl \
    jq \
    python3 \
    python3-pip \
    python3-pil \
    zram-tools \
    network-manager \
    wireless-tools \
    rfkill \
    libevent-dev \
    fonts-dejavu-core \
    gpiod \
    libgpiod-dev || true

# Install Python spidev and gpiod (tries apt packages, falls back to pip)
apt-get install -y python3-spidev python3-libgpiod 2>/dev/null || \
apt-get install -y python3-spidev python3-gpiod 2>/dev/null || \
pip3 install --break-system-packages spidev gpiod 2>/dev/null || true

# 2. Configure ZRAM for 1.5 GB RAM
echo "[2/9] Configuring ZRAM swap (essential for Initial Block Download)..."
if [ -f "config/zram-tools.conf" ]; then
    cp config/zram-tools.conf /etc/default/zramswap 2>/dev/null || cp config/zram-tools.conf /etc/zram-tools/zram-tools.conf 2>/dev/null || true
fi
systemctl restart zramswap || true

# 3. Configure Orange Pi SPI Overlay
echo "[3/9] Checking SPI overlays in boot configuration..."
BOOT_CONF=""
if [ -f "/boot/orangepiEnv.txt" ]; then
    BOOT_CONF="/boot/orangepiEnv.txt"
elif [ -f "/boot/armbianEnv.txt" ]; then
    BOOT_CONF="/boot/armbianEnv.txt"
fi

if [ -n "$BOOT_CONF" ]; then
    if ! grep -q "spi1-cs1-spidev" "$BOOT_CONF"; then
        echo "Adding 'spi1-cs1-spidev' overlay to $BOOT_CONF..."
        if grep -q "overlays=" "$BOOT_CONF"; then
            sed -i 's/overlays=\(.*\)/overlays=\1 spi1-cs1-spidev/' "$BOOT_CONF"
        else
            echo "overlays=spi1-cs1-spidev" >> "$BOOT_CONF"
        fi
    else
        echo "SPI1 CS1 overlay already enabled in $BOOT_CONF."
    fi
fi

# 4. Configure Groups and Udev Rules
echo "[4/9] Configuring udev rules and device permissions..."
groupadd -f spi
groupadd -f gpio

if [ -f "config/99-spidev-gpio.rules" ]; then
    cp config/99-spidev-gpio.rules /etc/udev/rules.d/
    udevadm control --reload-rules && udevadm trigger || true
fi

# 5. Create Bitcoin User & Directories
echo "[5/9] Creating 'bitcoin' system user and data directories..."
if ! id "bitcoin" &>/dev/null; then
    useradd -r -m -d /home/bitcoin -s /bin/false bitcoin
fi
usermod -a -G spi,gpio bitcoin || true

mkdir -p "$DATA_DIR"
mkdir -p "$CONF_DIR"
mkdir -p /etc/pruned-btcnode

if [ -f "config/bitcoin.conf" ]; then
    cp config/bitcoin.conf "$CONF_DIR/bitcoin.conf"
fi

chown -R bitcoin:bitcoin "$DATA_DIR"
chown -R bitcoin:bitcoin "$CONF_DIR"
chmod 750 "$DATA_DIR"
chmod 640 "$CONF_DIR/bitcoin.conf"

# 6. Configure Wi-Fi Auto-Connect (from wifi.conf if present)
echo "[6/9] Setting up Wi-Fi auto-connect configuration..."
if [ -f "wifi.conf" ]; then
    cp wifi.conf /etc/pruned-btcnode/wifi.conf
    cp wifi.conf /boot/wifi.conf 2>/dev/null || true
fi

# 7. Download and Install Bitcoin Core Binary
echo "[7/9] Downloading Bitcoin Core v${BTC_VERSION} (${BTC_ARCH})..."
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"
curl -sSL -O "$BTC_URL"
tar -xzf "$BTC_TAR"
install -m 0755 -o root -g root "bitcoin-${BTC_VERSION}/bin/"* /usr/local/bin/
cd - >/dev/null
rm -rf "$TMP_DIR"

echo "Installed Bitcoin Core version:"
bitcoin-cli --version

# 8. Install Display Telemetry & Wi-Fi Files
echo "[8/9] Installing scripts and telemetry daemon..."
mkdir -p "$APP_DIR"
cp -r display "$APP_DIR/"
cp -r scripts "$APP_DIR/"
chown -R root:root "$APP_DIR"
chmod +x "$APP_DIR/display/btc_display.py"
chmod +x "$APP_DIR/scripts/"*.sh
chmod +x "$APP_DIR/scripts/"*.py

# 9. Install and Enable Systemd Services
echo "[9/9] Installing and enabling systemd services..."
if [ -f "systemd/bitcoind.service" ]; then
    cp systemd/bitcoind.service /etc/systemd/system/
fi
if [ -f "systemd/btc-display.service" ]; then
    cp systemd/btc-display.service /etc/systemd/system/
fi
if [ -f "systemd/wifi-autoconnect.service" ]; then
    cp systemd/wifi-autoconnect.service /etc/systemd/system/
fi

systemctl daemon-reload
systemctl enable wifi-autoconnect.service || true
systemctl enable bitcoind.service
systemctl enable btc-display.service

# Run Wi-Fi connect now if config exists
if [ -f "/etc/pruned-btcnode/wifi.conf" ] || [ -f "/boot/wifi.conf" ]; then
    bash "$APP_DIR/scripts/wifi_autoconnect.sh" || true
fi

echo "===================================================================="
echo " Installation Complete!"
echo " "
echo " Next Steps:"
echo " 1. If this is your first time enabling SPI, reboot the Orange Pi:"
echo "    sudo reboot"
echo " 2. Wi-Fi Configuration:"
echo "    You can edit /boot/wifi.conf (or put it directly on the SD card)"
echo "    to change Wi-Fi networks anytime without connecting an Ethernet cable."
echo " 3. Check status anytime:"
echo "    /opt/pruned-btcnode/scripts/btc-status.sh"
echo "===================================================================="
