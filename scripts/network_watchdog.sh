#!/usr/bin/env bash
# ==============================================================================
# Network Self-Healing Watchdog for Orange Pi Zero 3 (Unisoc UWE5622 Wi-Fi)
# Prevents wpa_supplicant driver stalls & BSSID blacklisting
# ==============================================================================

GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n 1)
if [ -z "$GATEWAY" ]; then
    GATEWAY="192.168.4.1"
fi

FAIL_FILE="/tmp/wifi_watchdog_fails"
FAIL_COUNT=0
if [ -f "$FAIL_FILE" ]; then
    FAIL_COUNT=$(cat "$FAIL_FILE" 2>/dev/null || echo 0)
fi

# Ping default router gateway
if ping -c 1 -W 2 "$GATEWAY" >/dev/null 2>&1 || ping -c 1 -W 2 "8.8.8.8" >/dev/null 2>&1; then
    # Reset fail count on success
    echo 0 > "$FAIL_FILE"
    exit 0
else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "$FAIL_COUNT" > "$FAIL_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WIFI WATCHDOG] Gateway $GATEWAY unreachable (Fail count: $FAIL_COUNT/3)" >> /var/log/network_watchdog.log
fi

if [ "$FAIL_COUNT" -ge 3 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WIFI WATCHDOG] 3 consecutive network failures. Resetting Wi-Fi association..." >> /var/log/network_watchdog.log
    echo 0 > "$FAIL_FILE"
    
    # 1. Disable powersave if enabled
    iw wlan0 set power_save off 2>/dev/null || true
    
    # 2. Re-trigger NetworkManager / wpa_supplicant reassociation
    nmcli device disconnect wlan0 2>/dev/null || true
    sleep 2
    nmcli device connect wlan0 2>/dev/null || systemctl restart NetworkManager 2>/dev/null || true
fi
