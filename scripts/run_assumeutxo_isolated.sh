#!/usr/bin/env bash
# ==============================================================================
# Isolated Low-Memory AssumeUTXO Snapshot Importer
# Designed specifically for Orange Pi Zero 3 (1.5 GB RAM)
# ==============================================================================

set -e

DATADIR="/var/lib/bitcoind"
SNAPSHOT_FILE="${DATADIR}/utxo-840000.dat"
CLI="bitcoin-cli -datadir=${DATADIR} -rpcclienttimeout=0"
LOG="/var/lib/bitcoind/assumeutxo_isolated.log"

echo "============================================================" | tee -a "$LOG"
echo " Isolated AssumeUTXO 840,000 Importer" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

# 1. Wait for aria2c download to complete
while [ ! -f "$SNAPSHOT_FILE" ] || [ -f "${SNAPSHOT_FILE}.aria2" ]; do
    echo "[$(date '+%T')] Waiting for snapshot download to finish..." | tee -a "$LOG"
    sleep 30
done

echo "[SUCCESS] Snapshot download completed: $(ls -lh $SNAPSHOT_FILE | awk '{print $5}')" | tee -a "$LOG"

# 2. Ensure permissions
chown bitcoin:bitcoin "$SNAPSHOT_FILE"
chmod 644 "$SNAPSHOT_FILE"

# 3. Stop any existing systemd bitcoind service
systemctl stop bitcoind 2>/dev/null || true
sleep 2

# 4. Start bitcoind in ISOLATED mode (0 network connections, capped dbcache, 1 validation thread)
echo "[INFO] Starting bitcoind in isolated low-memory mode..." | tee -a "$LOG"
sudo -u bitcoin /usr/local/bin/bitcoind -conf=/etc/bitcoin/bitcoin.conf -datadir="$DATADIR" -maxconnections=0 -dbcache=250 -par=1 -daemon

# 5. Wait for RPC to respond
echo "[INFO] Waiting for isolated bitcoind to warm up RPC..." | tee -a "$LOG"
until $CLI getblockchaininfo >/dev/null 2>&1; do
    sleep 2
done
echo "[SUCCESS] Isolated bitcoind is ready!" | tee -a "$LOG"

# 6. Trigger loadtxoutset
echo "[INFO] Invoking loadtxoutset on $SNAPSHOT_FILE (this will take 5-15 mins)..." | tee -a "$LOG"
RESULT=$($CLI loadtxoutset "$SNAPSHOT_FILE")
echo "[RESULT] $RESULT" | tee -a "$LOG"

# 7. Delete 9.2 GB snapshot file to free disk space immediately
echo "[INFO] Removing snapshot file..." | tee -a "$LOG"
rm -f "$SNAPSHOT_FILE"

# 8. Stop isolated daemon
echo "[INFO] Stopping isolated bitcoind..." | tee -a "$LOG"
$CLI stop 2>/dev/null || true
sleep 5

# 9. Start normal systemd services
echo "[INFO] Restarting bitcoind and web dashboard in normal mode..." | tee -a "$LOG"
systemctl start bitcoind
systemctl start btc-web
systemctl start btc-display 2>/dev/null || true

echo "============================================================" | tee -a "$LOG"
echo " AssumeUTXO Transition Completed! Active Height: #840,000+" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
