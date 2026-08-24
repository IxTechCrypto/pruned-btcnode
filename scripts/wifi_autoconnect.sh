#!/usr/bin/env bash
# ==============================================================================
# Wi-Fi Auto-Connect Script for Orange Pi Zero 3
# Reads Wi-Fi credentials from /boot/wifi.conf, /boot/wifi.txt, or repo root
# ==============================================================================

set -e

CANDIDATE_PATHS=(
    "/boot/wifi.conf"
    "/boot/wifi.txt"
    "/boot/firmware/wifi.conf"
    "/boot/firmware/wifi.txt"
    "/etc/pruned-btcnode/wifi.conf"
    "/opt/pruned-btcnode/wifi.conf"
    "$(dirname "$0")/../wifi.conf"
)

FOUND_CONF=""
for p in "${CANDIDATE_PATHS[@]}"; do
    if [ -f "$p" ]; then
        FOUND_CONF="$p"
        break
    fi
done

if [ -z "$FOUND_CONF" ]; then
    echo "[INFO] No wifi.conf or wifi.txt file found. Skipping auto-connect."
    exit 0
fi

echo "[INFO] Found Wi-Fi configuration at: $FOUND_CONF"

# Source the configuration
# Strip carriage returns (\r) in case edited on Windows
CLEAN_CONF=$(mktemp)
tr -d '\r' < "$FOUND_CONF" > "$CLEAN_CONF"
source "$CLEAN_CONF"
rm -f "$CLEAN_CONF"

# Validation
if [ -z "$WIFI_SSID" ] || [ "$WIFI_SSID" = "Your_WiFi_SSID_Here" ]; then
    echo "[INFO] WIFI_SSID not configured in $FOUND_CONF. Skipping."
    exit 0
fi

echo "[INFO] Configuring Wi-Fi for SSID: '$WIFI_SSID'..."

# Set Wi-Fi Country if specified
if [ -n "$WIFI_COUNTRY" ] && command -v iw >/dev/null 2>&1; then
    echo "[INFO] Setting regulatory domain to $WIFI_COUNTRY..."
    iw reg set "$WIFI_COUNTRY" || true
fi

# Ensure Wi-Fi radio is unblocked
if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi || true
fi

# 1. Primary Method: NetworkManager (nmcli) - Standard on Armbian
if command -v nmcli >/dev/null 2>&1; then
    echo "[INFO] Using NetworkManager (nmcli)..."
    
    # Wait for NetworkManager daemon to be ready
    for i in {1..10}; do
        if nmcli general status >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Rescan available Wi-Fi access points
    nmcli device wifi rescan || true
    sleep 2

    # Check if a connection with this SSID already exists
    if nmcli -t -f NAME connection show | grep -Fxq "$WIFI_SSID"; then
        echo "[INFO] Connection '$WIFI_SSID' already exists. Updating credentials and reconnecting..."
        nmcli connection modify "$WIFI_SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$WIFI_PASSWORD"
        nmcli connection up "$WIFI_SSID" || true
    else
        echo "[INFO] Connecting to new network '$WIFI_SSID'..."
        if [ -n "$WIFI_PASSWORD" ] && [ "$WIFI_PASSWORD" != "Your_WiFi_Password_Here" ]; then
            nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD" || true
        else
            nmcli device wifi connect "$WIFI_SSID" || true
        fi
    fi

# 2. Fallback Method: wpa_supplicant
elif command -v wpa_cli >/dev/null 2>&1 && [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
    echo "[INFO] Using wpa_supplicant fallback..."
    WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    
    if ! grep -q "ssid=\"$WIFI_SSID\"" "$WPA_CONF"; then
        echo -e "\nnetwork={\n    ssid=\"$WIFI_SSID\"\n    psk=\"$WIFI_PASSWORD\"\n}" >> "$WPA_CONF"
        systemctl restart wpa_supplicant || true
    fi
fi

# Check connection status
sleep 3
WLAN_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || true)
if [ -n "$WLAN_IP" ]; then
    echo "[SUCCESS] Connected to Wi-Fi! IP Address (wlan0): $WLAN_IP"
else
    echo "[WARN] Wi-Fi configured, waiting for DHCP lease on wlan0..."
fi
