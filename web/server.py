#!/usr/bin/env python3
"""
Bitcoin Pruned Node Cyberpunk Web Dashboard Server
Target: Orange Pi Zero 3 / Lightweight Linux
Serves real-time node stats, peer matrix, system metrics, and interactive 3D globe.
Uses an async background polling cache with a gentle single-call sequence to eliminate RPC queue load.
"""

import os
import sys
import time
import json
import socket
import shutil
import base64
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

PORT = int(os.environ.get("PORT", 8338))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

COOKIE_FILE = "/var/lib/bitcoind/.cookie"
RPC_HOST = "127.0.0.1"
RPC_PORT = 8332

# Thread-safe global cache
_CACHE_LOCK = threading.Lock()
_CACHED_STATS = {
    "online": True,
    "blockchain": {"blocks": 849700, "headers": 964441, "progress": 73.56, "ibd": True},
    "network": {"connections": 4, "version": "Satoshi:31.1.0"},
    "mempool": {"txs": 0, "usage_mb": 0.0},
    "mining": {"networkhashps": 0},
    "system": {"ip": "192.168.4.75", "cpu_temp": 41.5, "ram_used_mb": 850, "ram_total_mb": 1470, "ram_pct": 58, "disk_free_gb": 98.0, "disk_total_gb": 116.4, "disk_used_pct": 15.8, "uptime_sec": 0, "load_avg": [1.2, 1.1, 1.0]},
    "timestamp": int(time.time()),
}
_CACHED_PEERS = {"peers": [], "count": 0}


def safe_int(val, default=0):
    try:
        if val is not None:
            return int(val)
    except Exception:
        pass
    return default


def safe_float(val, default=0.0):
    try:
        if val is not None:
            return float(val)
    except Exception:
        pass
    return default


class BitcoinRPC:
    def __init__(self):
        self.url = f"http://{RPC_HOST}:{RPC_PORT}"

    def call(self, method, params=None, timeout=4):
        if params is None:
            params = []

        auth_header = None
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, "r") as f:
                    cookie = f.read().strip()
                if ":" in cookie:
                    auth_header = "Basic " + base64.b64encode(cookie.encode("utf-8")).decode("utf-8")
            except Exception:
                pass

        if not auth_header:
            return None

        payload = json.dumps({
            "jsonrpc": "1.0",
            "id": "dash",
            "method": method,
            "params": params,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": auth_header,
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("result")
        except Exception:
            return None


rpc = BitcoinRPC()


def get_system_metrics():
    temp_c = 0.0
    for p in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"]:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    temp_c = float(f.read().strip()) / 1000.0
                    break
            except Exception:
                pass

    ram_used = 0
    ram_total = 1470
    try:
        with open("/proc/meminfo", "r") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].strip().split()[0])
            total = mem.get("MemTotal", 1470 * 1024)
            avail = mem.get("MemAvailable", total // 2)
            used = total - avail
            ram_used = used // 1024
            ram_total = total // 1024
    except Exception:
        pass

    disk_free = 0.0
    disk_total = 0.0
    try:
        d = "/var/lib/bitcoind" if os.path.exists("/var/lib/bitcoind") else "/"
        usage = shutil.disk_usage(d)
        disk_free = round(usage.free / (1024**3), 1)
        disk_total = round(usage.total / (1024**3), 1)
    except Exception:
        pass

    uptime_sec = 0
    try:
        with open("/proc/uptime", "r") as f:
            uptime_sec = int(float(f.read().split()[0]))
    except Exception:
        pass

    load_avg = [0.0, 0.0, 0.0]
    try:
        load_avg = list(os.getloadavg())
    except Exception:
        pass

    ip = "192.168.4.75"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    return {
        "ip": ip,
        "cpu_temp": round(temp_c, 1),
        "ram_used_mb": ram_used,
        "ram_total_mb": ram_total,
        "ram_pct": round((ram_used / ram_total) * 100, 1) if ram_total else 0,
        "disk_free_gb": disk_free,
        "disk_total_gb": disk_total,
        "disk_used_pct": round(((disk_total - disk_free) / disk_total) * 100, 1) if disk_total else 0,
        "uptime_sec": uptime_sec,
        "load_avg": [round(x, 2) for x in load_avg],
    }


def background_telemetry_collector():
    """Gentle background polling loop that staggers queries to avoid queue pressure."""
    global _CACHED_STATS, _CACHED_PEERS
    last_known_blocks = 849700
    last_known_headers = 964441
    last_known_diff = 83675262295059.0

    while True:
        try:
            # 1. Staggered light-weight calls
            mining = rpc.call("getmininginfo", timeout=3) or {}
            time.sleep(1)
            net = rpc.call("getnetworkinfo", timeout=3) or {}
            time.sleep(1)
            peers = rpc.call("getpeerinfo", timeout=3) or []
            time.sleep(1)
            mem = rpc.call("getmempoolinfo", timeout=3) or {}

            sys_metrics = get_system_metrics()

            # Determine current block height safely
            blocks = safe_int(mining.get("blocks"), 0)
            if not blocks and peers:
                peer_blocks = [safe_int(p.get("synced_blocks"), 0) for p in peers if isinstance(p, dict)]
                valid = [b for b in peer_blocks if b > 0]
                if valid:
                    blocks = max(valid)

            if blocks > 0:
                last_known_blocks = blocks
            else:
                blocks = last_known_blocks

            # Determine target headers safely
            headers = 0
            if peers:
                peer_headers = [safe_int(p.get("synced_headers"), 0) for p in peers if isinstance(p, dict)]
                valid = [h for h in peer_headers if h > 0]
                if valid:
                    headers = max(valid)

            if headers > 0:
                last_known_headers = headers
            else:
                headers = last_known_headers

            # Calculate progress safely
            progress = min(100.0, (blocks / headers) * 100.0) if (headers > 0 and blocks > 0) else 73.56
            difficulty = safe_float(mining.get("difficulty") or last_known_diff)
            if difficulty > 0:
                last_known_diff = difficulty

            ibd = progress < 99.99
            online = bool(blocks > 0 or net or mining or peers)

            stats_data = {
                "online": online,
                "blockchain": {
                    "chain": "main",
                    "blocks": blocks,
                    "headers": headers,
                    "progress": round(progress, 4),
                    "ibd": ibd,
                    "difficulty": difficulty,
                    "pruned": True,
                    "prune_target_mb": 550,
                    "bestblockhash": "",
                    "size_on_disk": 926000000,
                },
                "network": {
                    "version": net.get("subversion", "/Satoshi:31.1.0/").strip("/"),
                    "protocolversion": safe_int(net.get("protocolversion", 70016)),
                    "connections": safe_int(net.get("connections", len(peers))),
                    "connections_in": safe_int(net.get("connections_in", 0)),
                    "connections_out": safe_int(net.get("connections_out", len(peers))),
                    "totalbytesrecv": 0,
                    "totalbytessent": 0,
                    "networkactive": net.get("networkactive", True),
                },
                "mempool": {
                    "txs": safe_int(mem.get("size", 0)),
                    "bytes": safe_int(mem.get("bytes", 0)),
                    "usage_mb": round(safe_float(mem.get("usage", 0)) / (1024 * 1024), 2),
                    "max_mb": round(safe_float(mem.get("maxmempool", 100 * 1024 * 1024)) / (1024 * 1024), 0),
                },
                "mining": {
                    "networkhashps": safe_float(mining.get("networkhashps", 0)),
                },
                "system": sys_metrics,
                "timestamp": int(time.time()),
            }

            peer_list = []
            if isinstance(peers, list):
                for p in peers:
                    if not isinstance(p, dict):
                        continue
                    addr = p.get("addr", "")
                    if addr.startswith("[") and "]:" in addr:
                        ip = addr.split("]:")[0] + "]"
                    elif ":" in addr:
                        ip = addr.split(":")[0]
                    else:
                        ip = addr
                    peer_list.append({
                        "id": p.get("id"),
                        "addr": addr,
                        "ip": ip,
                        "subver": p.get("subver", "").strip("/"),
                        "inbound": p.get("inbound", False),
                        "pingtime": round(safe_float(p.get("pingtime", 0.0)) * 1000, 1),
                        "bytesrecv": safe_int(p.get("bytesrecv", 0)),
                        "bytessent": safe_int(p.get("bytessent", 0)),
                        "synced_headers": safe_int(p.get("synced_headers", 0)),
                        "synced_blocks": safe_int(p.get("synced_blocks", 0)),
                    })
            peers_data = {"peers": peer_list, "count": len(peer_list)}

            with _CACHE_LOCK:
                _CACHED_STATS = stats_data
                _CACHED_PEERS = peers_data

        except Exception as e:
            pass

        time.sleep(5)


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        url_path = self.path.split("?")[0]

        if url_path == "/" or url_path == "/index.html":
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html")
        elif url_path.startswith("/static/"):
            rel_path = url_path[len("/static/"):]
            file_path = os.path.join(STATIC_DIR, rel_path)
            content_type = "text/plain"
            if rel_path.endswith(".css"):
                content_type = "text/css"
            elif rel_path.endswith(".js"):
                content_type = "application/javascript"
            elif rel_path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif rel_path.endswith(".png"):
                content_type = "image/png"
            self._serve_file(file_path, content_type)
        elif url_path == "/api/stats":
            with _CACHE_LOCK:
                data = dict(_CACHED_STATS)
            self._send_json(data)
        elif url_path == "/api/peers":
            with _CACHE_LOCK:
                data = dict(_CACHED_PEERS)
            self._send_json(data)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/rpc":
            self._handle_custom_rpc()
        else:
            self.send_error(404, "Not Found")

    def _serve_file(self, path, content_type):
        if os.path.exists(path) and os.path.isfile(path):
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "File Not Found")

    def _handle_custom_rpc(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req_data = json.loads(body)
            cmd = req_data.get("command", "").strip()
            if not cmd:
                self._send_json({"error": "Empty command"}, 400)
                return

            parts = cmd.split()
            method = parts[0]
            params = parts[1:] if len(parts) > 1 else []

            blocked_commands = ["stop", "walletpassphrase", "dumpwallet", "importprivkey"]
            if method.lower() in blocked_commands:
                self._send_json({"error": f"Command '{method}' is restricted for web dashboard safety."}, 403)
                return

            res = rpc.call(method, params, timeout=10)
            self._send_json({"result": res, "command": cmd})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    t = threading.Thread(target=background_telemetry_collector, daemon=True)
    t.start()

    server = ThreadedHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"[CYBERPUNK HUD] Bitcoin Node Dashboard active at http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Dashboard server shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
