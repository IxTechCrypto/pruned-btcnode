#!/usr/bin/env python3
"""
Bitcoin Pruned Node Cyberpunk Web Dashboard Server
Target: Orange Pi Zero 3 / Lightweight Linux
Serves real-time node stats, peer matrix, system metrics, and interactive 3D globe.
"""

import os
import sys
import time
import json
import socket
import shutil
import base64
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

PORT = int(os.environ.get("PORT", 8338))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

RPC_HOST = "127.0.0.1"
RPC_PORT = 8332
COOKIE_PATHS = [
    "/var/lib/bitcoind/.cookie",
    os.path.expanduser("~/.bitcoin/.cookie"),
    os.path.expanduser("~orangepi/.bitcoin/.cookie"),
]


class BitcoinRPC:
    def __init__(self):
        self.url = f"http://{RPC_HOST}:{RPC_PORT}"

    def _get_auth(self):
        for path in COOKIE_PATHS:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        creds = f.read().strip()
                    return "Basic " + base64.b64encode(creds.encode()).decode()
                except Exception:
                    pass
        return None

    def call(self, method, params=None):
        if params is None:
            params = []

        # 1. Native bitcoin-cli execution
        try:
            cmd = ["bitcoin-cli", "-datadir=/var/lib/bitcoind", method] + [str(p) for p in params]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    return json.loads(proc.stdout)
                except Exception:
                    return proc.stdout.strip()
        except Exception:
            pass

        # 2. HTTP JSON-RPC fallback
        payload = json.dumps({
            "jsonrpc": "1.0",
            "id": "web-hud",
            "method": method,
            "params": params
        }).encode("utf-8")

        headers = {"Content-Type": "text/plain"}
        auth = self._get_auth()
        if auth:
            headers["Authorization"] = auth

        req = urllib.request.Request(self.url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                return data.get("result")
        except Exception:
            return None


rpc = BitcoinRPC()


def get_system_metrics():
    # CPU Temp
    temp_c = 0.0
    for p in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"]:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    temp_c = float(f.read().strip()) / 1000.0
                    break
            except Exception:
                pass

    # RAM
    ram_used = 0
    ram_total = 1536
    try:
        with open("/proc/meminfo", "r") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].strip().split()[0])
            total = mem.get("MemTotal", 1536 * 1024)
            avail = mem.get("MemAvailable", total // 2)
            used = total - avail
            ram_used = used // 1024
            ram_total = total // 1024
    except Exception:
        pass

    # Disk
    disk_free = 0.0
    disk_total = 0.0
    try:
        d = "/var/lib/bitcoind" if os.path.exists("/var/lib/bitcoind") else "/"
        usage = shutil.disk_usage(d)
        disk_free = round(usage.free / (1024**3), 1)
        disk_total = round(usage.total / (1024**3), 1)
    except Exception:
        pass

    # Uptime & Load
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

    # Host IP
    ip = "127.0.0.1"
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


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress excessive stdout logging

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
            self._handle_stats()
        elif url_path == "/api/peers":
            self._handle_peers()
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

    def _handle_stats(self):
        chain = rpc.call("getblockchaininfo") or {}
        net = rpc.call("getnetworkinfo") or {}
        mem = rpc.call("getmempoolinfo") or {}
        mining = rpc.call("getmininginfo") or {}
        net_totals = rpc.call("getnettotals") or {}

        sys_metrics = get_system_metrics()

        online = bool(chain and net)
        blocks = chain.get("blocks", 0)
        headers = chain.get("headers", 0)
        progress = chain.get("verificationprogress", 0.0) * 100.0
        ibd = chain.get("initialblockdownload", False) or progress < 99.99

        data = {
            "online": online,
            "blockchain": {
                "chain": chain.get("chain", "main"),
                "blocks": blocks,
                "headers": headers,
                "progress": round(progress, 4),
                "ibd": ibd,
                "difficulty": chain.get("difficulty", 0),
                "pruned": chain.get("pruned", True),
                "prune_target_mb": chain.get("prune_target_size", 0) // (1024 * 1024) if chain.get("prune_target_size") else 550,
                "bestblockhash": chain.get("bestblockhash", ""),
                "size_on_disk": chain.get("size_on_disk", 0),
            },
            "network": {
                "version": net.get("subversion", "/Satoshi:31.1.0/").strip("/"),
                "protocolversion": net.get("protocolversion", 70016),
                "connections": net.get("connections", 0),
                "connections_in": net.get("connections_in", 0),
                "connections_out": net.get("connections_out", 0),
                "totalbytesrecv": net_totals.get("totalbytesrecv", 0),
                "totalbytessent": net_totals.get("totalbytessent", 0),
                "networkactive": net.get("networkactive", True),
            },
            "mempool": {
                "txs": mem.get("size", 0),
                "bytes": mem.get("bytes", 0),
                "usage_mb": round(mem.get("usage", 0) / (1024 * 1024), 2),
                "max_mb": round(mem.get("maxmempool", 100 * 1024 * 1024) / (1024 * 1024), 0),
            },
            "mining": {
                "networkhashps": mining.get("networkhashps", 0),
            },
            "system": sys_metrics,
            "timestamp": int(time.time()),
        }

        self._send_json(data)

    def _handle_peers(self):
        peers = rpc.call("getpeerinfo") or []
        peer_list = []
        if isinstance(peers, list):
            for p in peers:
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
                    "pingtime": round(p.get("pingtime", 0.0) * 1000, 1),
                    "bytesrecv": p.get("bytesrecv", 0),
                    "bytessent": p.get("bytessent", 0),
                    "synced_headers": p.get("synced_headers", 0),
                    "synced_blocks": p.get("synced_blocks", 0),
                })
        self._send_json({"peers": peer_list, "count": len(peer_list)})

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

            # Safe whitelist for web terminal
            blocked_commands = ["stop", "walletpassphrase", "dumpwallet", "importprivkey"]
            if method.lower() in blocked_commands:
                self._send_json({"error": f"Command '{method}' is restricted for web dashboard safety."}, 403)
                return

            res = rpc.call(method, params)
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
    server = ThreadedHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"[CYBERPUNK HUD] Bitcoin Node Dashboard active at http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Dashboard server shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
