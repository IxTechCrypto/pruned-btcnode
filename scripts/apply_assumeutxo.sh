#!/usr/bin/env bash
# ==============================================================================
# Automated AssumeUTXO Snapshot Loader for Bitcoin Core v31.1
# ==============================================================================

set -e

SNAPSHOT_DIR="/home/orangepi/snapshots"
SNAPSHOT_FILE="${SNAPSHOT_DIR}/utxo-840000.dat"
CLI="bitcoin-cli -datadir=/var/lib/bitcoind -rpcclienttimeout=0"

echo "============================================================"
echo " Starting AssumeUTXO 840,000 Loader"
echo "============================================================"

# Wait for aria2c download to finish if in progress
while [ ! -f "$SNAPSHOT_FILE" ] || [ -f "${SNAPSHOT_FILE}.aria2" ]; do
    echo "[INFO] Waiting for utxo-840000.dat download to complete..."
    sleep 30
done

echo "[INFO] Snapshot file confirmed: $(ls -lh $SNAPSHOT_FILE | awk '{print $5}')"

# Ensure bitcoin user has read access
chmod 644 "$SNAPSHOT_FILE"

echo "[INFO] Loading UTXO snapshot into Bitcoin Core via RPC..."
$CLI loadtxoutset "$SNAPSHOT_FILE"

echo "[SUCCESS] UTXO snapshot loaded into Bitcoin Core!"

echo "[INFO] Removing 9.1 GB snapshot file to free disk space..."
rm -f "$SNAPSHOT_FILE"

echo "[INFO] Restarting bitcoind and web dashboard..."
systemctl restart bitcoind
systemctl restart btc-web
systemctl restart btc-display 2>/dev/null || true

echo "============================================================"
echo " AssumeUTXO Transition Complete! Active Height: #840,000+"
echo "============================================================"
