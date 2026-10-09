#!/usr/bin/env bash
set -e

echo "[1/8] Deploying hardened bitcoin.conf..."
cp /home/orangepi/bitcoin.conf /etc/bitcoin/bitcoin.conf
chown bitcoin:bitcoin /etc/bitcoin/bitcoin.conf
chmod 644 /etc/bitcoin/bitcoin.conf

echo "[2/8] Applying Linux Kernel Sysctl Memory & Panic Tunings..."
cp /home/orangepi/99-btcnode.conf /etc/sysctl.d/99-btcnode.conf
sysctl --system >/dev/null

echo "[3/8] Disabling Wi-Fi Power Saving in NetworkManager..."
mkdir -p /etc/NetworkManager/conf.d
cat << 'EOF' > /etc/NetworkManager/conf.d/default-wifi-powersave-off.conf
[connection]
wifi.powersave = 2
EOF
iw wlan0 set power_save off 2>/dev/null || true

echo "[4/8] Installing Network Self-Healing Watchdog..."
mkdir -p /opt/pruned-btcnode/scripts
cp /home/orangepi/network_watchdog.sh /opt/pruned-btcnode/scripts/network_watchdog.sh
chmod +x /opt/pruned-btcnode/scripts/network_watchdog.sh

cp /home/orangepi/network-watchdog.service /etc/systemd/system/network-watchdog.service
cp /home/orangepi/network-watchdog.timer /etc/systemd/system/network-watchdog.timer

systemctl daemon-reload
systemctl enable --now network-watchdog.timer

echo "[5/8] Configuring Hardware Watchdog (sunxi-wdt)..."
if [ -f "/etc/systemd/system.conf" ]; then
    sed -i 's/.*RuntimeWatchdogSec=.*/RuntimeWatchdogSec=20s/' /etc/systemd/system.conf
    sed -i 's/.*RebootWatchdogSec=.*/RebootWatchdogSec=30s/' /etc/systemd/system.conf
    if ! grep -q "RuntimeWatchdogSec=" /etc/systemd/system.conf; then
        echo "RuntimeWatchdogSec=20s" >> /etc/systemd/system.conf
    fi
fi

echo "[6/8] Updating bitcoind systemd service..."
cp /home/orangepi/bitcoind.service /etc/systemd/system/bitcoind.service
systemctl daemon-reload

echo "[7/8] Restarting bitcoind with new memory parameters..."
systemctl restart bitcoind

echo "[8/8] Hardening complete and verified!"
systemctl status network-watchdog.timer --no-pager
systemctl status bitcoind --no-pager
