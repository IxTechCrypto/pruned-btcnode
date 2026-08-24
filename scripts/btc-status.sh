#!/usr/bin/env bash
# ==============================================================================
# Bitcoin Node Quick Status Dashboard
# ==============================================================================

set -e

BITCOIN_CLI="${BITCOIN_CLI:-bitcoin-cli}"
CONF_FILE="/etc/bitcoin/bitcoin.conf"
COOKIE_FILE="/var/lib/bitcoind/.cookie"

CLI_OPTS=""
if [ -f "$CONF_FILE" ]; then
    CLI_OPTS="-conf=$CONF_FILE"
elif [ -f "$HOME/.bitcoin/bitcoin.conf" ]; then
    CLI_OPTS="-conf=$HOME/.bitcoin/bitcoin.conf"
fi

if [ -f "$COOKIE_FILE" ]; then
    CLI_OPTS="$CLI_OPTS -rpccookiefile=$COOKIE_FILE"
fi

echo "============================================================"
echo " ₿ Bitcoin Pruned Node Status (Orange Pi Zero 3)"
echo "============================================================"

# Check bitcoind service status
if systemctl is-active --quiet bitcoind; then
    echo " Daemon Status:      Active (Running)"
else
    echo " Daemon Status:      Inactive / Stopped"
fi

# Query RPC Info
if $BITCOIN_CLI $CLI_OPTS getblockchaininfo >/dev/null 2>&1; then
    INFO=$($BITCOIN_CLI $CLI_OPTS getblockchaininfo)
    NET=$($BITCOIN_CLI $CLI_OPTS getnetworkinfo)
    MEM=$($BITCOIN_CLI $CLI_OPTS getmempoolinfo)

    BLOCKS=$(echo "$INFO" | grep -o '"blocks": [0-9]*' | awk '{print $2}')
    HEADERS=$(echo "$INFO" | grep -o '"headers": [0-9]*' | awk '{print $2}')
    PROGRESS=$(echo "$INFO" | grep -o '"verificationprogress": [0-9.eE+-]*' | awk '{val = $2 * 100; if (val > 100) val = 100; printf "%.2f%%", val}')
    PRUNED=$(echo "$INFO" | grep -o '"pruned": [a-z]*' | awk '{print $2}')
    PEERS=$(echo "$NET" | grep -o '"connections": [0-9]*' | awk '{print $2}')
    VERSION=$(echo "$NET" | grep -o '"subversion": "[^"]*"' | cut -d'"' -f4)
    TXS=$(echo "$MEM" | grep -o '"size": [0-9]*' | awk '{print $2}')
    MEM_BYTES=$(echo "$MEM" | grep -o '"bytes": [0-9]*' | awk '{printf "%.2f MB", $2 / (1024*1024)}')

    echo " Client Version:     $VERSION"
    echo " Synced Blocks:      $BLOCKS / $HEADERS ($PROGRESS)"
    echo " Prune Mode:         $PRUNED"
    echo " Active Peers:       $PEERS"
    echo " Mempool:            $TXS transactions ($MEM_BYTES)"
else
    echo " RPC Status:         Connecting or Daemon Warming Caches..."
fi

echo "------------------------------------------------------------"
# Hardware Metrics
if [ -f "/sys/class/thermal/thermal_zone0/temp" ]; then
    TEMP=$(awk '{printf "%.1f°C", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
    echo " CPU Temperature:    $TEMP"
fi

echo " RAM & Swap Usage:"
free -h | awk 'NR<=2 {print "   " $0}'

echo " Disk Usage:"
df -h /var/lib/bitcoind 2>/dev/null || df -h /
echo "============================================================"
