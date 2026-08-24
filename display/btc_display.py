#!/usr/bin/env python3
"""
Bitcoin Pruned Node Telemetry Display Daemon
Target: Orange Pi Zero 3 (Allwinner H618) + Waveshare 2.0" ST7789 LCD (240x320)
"""

import os
import sys
import time
import socket
import shutil
import json
import urllib.request
import urllib.error
import base64
import subprocess
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

# Local ST7789 display controller
try:
    from display.st7789 import ST7789
except ImportError:
    try:
        from st7789 import ST7789
    except ImportError:
        ST7789 = None

# Display configuration
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 320
ROTATION = 0  # 0 = Portrait (240x320), 90 = Landscape (320x240)

# Colors (Cyberpunk / Modern Dark Palette)
COLOR_BG = (10, 14, 20)
COLOR_CARD_BG = (19, 24, 35)
COLOR_CARD_BORDER = (35, 45, 65)
COLOR_TEXT_WHITE = (240, 244, 250)
COLOR_TEXT_MUTED = (125, 138, 160)
COLOR_BTC_ORANGE = (247, 147, 26)
COLOR_ACCENT_CYAN = (0, 225, 255)
COLOR_GREEN = (46, 204, 113)
COLOR_YELLOW = (241, 196, 15)
COLOR_RED = (231, 76, 60)
COLOR_BAR_BG = (30, 38, 54)


class BitcoinNodeMonitor:
    def __init__(
        self,
        rpc_host="127.0.0.1",
        rpc_port=8332,
        cookie_path="/var/lib/bitcoind/.cookie",
        rpc_user=None,
        rpc_password=None,
        data_dir="/var/lib/bitcoind",
    ):
        self.rpc_url = f"http://{rpc_host}:{rpc_port}"
        self.cookie_path = os.path.expanduser(cookie_path)
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.data_dir = os.path.expanduser(data_dir)
        self.start_time = time.time()

    def _get_auth_header(self):
        if self.rpc_user and self.rpc_password:
            creds = f"{self.rpc_user}:{self.rpc_password}"
            return "Basic " + base64.b64encode(creds.encode()).decode()

        # Fallback to cookie auth
        for c in [self.cookie_path, os.path.expanduser("~/.bitcoin/.cookie")]:
            if os.path.exists(c):
                try:
                    with open(c, "r") as f:
                        creds = f.read().strip()
                    return "Basic " + base64.b64encode(creds.encode()).decode()
                except Exception:
                    pass

        return None

    def call_rpc(self, method, params=None):
        if params is None:
            params = []
        payload = json.dumps({"jsonrpc": "1.0", "id": "display", "method": method, "params": params}).encode("utf-8")

        headers = {"Content-Type": "text/plain"}
        auth = self._get_auth_header()
        if auth:
            headers["Authorization"] = auth

        req = urllib.request.Request(self.rpc_url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                return data.get("result")
        except Exception:
            return None

    def get_node_stats(self):
        blockchain = self.call_rpc("getblockchaininfo")
        network = self.call_rpc("getnetworkinfo")
        mempool = self.call_rpc("getmempoolinfo")

        if not blockchain or not network:
            return {"online": False}

        headers = blockchain.get("headers", 0)
        blocks = blockchain.get("blocks", 0)
        verif_progress = blockchain.get("verificationprogress", 0.0)
        pruned = blockchain.get("pruned", False)
        prune_target = blockchain.get("prune_target_size", 0)
        initial_block_download = blockchain.get("initialblockdownload", False)

        peers = network.get("connections", 0)
        subversion = network.get("subversion", "").replace("/", "")

        mempool_txs = mempool.get("size", 0) if mempool else 0
        mempool_bytes = mempool.get("bytes", 0) if mempool else 0

        return {
            "online": True,
            "blocks": blocks,
            "headers": headers,
            "progress": verif_progress * 100.0,
            "ibd": initial_block_download,
            "pruned": pruned,
            "prune_target_mb": prune_target // (1024 * 1024) if prune_target else 550,
            "peers": peers,
            "subversion": subversion,
            "mempool_txs": mempool_txs,
            "mempool_mb": mempool_bytes / (1024 * 1024),
        }

    def _get_interface_ip(self, ifname):
        try:
            out = subprocess.check_output(["ip", "-4", "addr", "show", ifname], stderr=subprocess.DEVNULL).decode()
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    return line.split()[1].split("/")[0]
        except Exception:
            pass
        return None

    def get_system_stats(self):
        # 1. IP & Interface
        ip = "No IP"
        net_type = "OFFLINE"
        
        wlan_ip = self._get_interface_ip("wlan0")
        eth_ip = self._get_interface_ip("eth0") or self._get_interface_ip("end0")

        if wlan_ip:
            ip = wlan_ip
            net_type = "Wi-Fi"
        elif eth_ip:
            ip = eth_ip
            net_type = "ETH"
        else:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                net_type = "NET"
                s.close()
            except Exception:
                ip = "127.0.0.1"

        # 2. CPU Temperature
        temp_c = 0.0
        for path in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"]:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        temp_c = float(f.read().strip()) / 1000.0
                        break
                except Exception:
                    pass

        # 3. RAM Info
        ram_used_mb = 0
        ram_total_mb = 1536
        ram_percent = 0.0
        try:
            with open("/proc/meminfo", "r") as f:
                mem = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem[key] = int(val)
                total = mem.get("MemTotal", 1536 * 1024)
                avail = mem.get("MemAvailable", total // 2)
                used = total - avail
                ram_used_mb = used // 1024
                ram_total_mb = total // 1024
                ram_percent = (used / total) * 100.0
        except Exception:
            pass

        # 4. Storage Info
        disk_free_gb = 0.0
        disk_total_gb = 0.0
        try:
            target = self.data_dir if os.path.exists(self.data_dir) else "/"
            usage = shutil.disk_usage(target)
            disk_free_gb = usage.free / (1024**3)
            disk_total_gb = usage.total / (1024**3)
        except Exception:
            pass

        # 5. Uptime
        uptime_sec = 0
        try:
            with open("/proc/uptime", "r") as f:
                uptime_sec = int(float(f.read().split()[0]))
        except Exception:
            uptime_sec = int(time.time() - self.start_time)

        uptime_str = str(timedelta(seconds=uptime_sec)).split(".")[0]

        return {
            "ip": ip,
            "net_type": net_type,
            "temp_c": temp_c,
            "ram_used_mb": ram_used_mb,
            "ram_total_mb": ram_total_mb,
            "ram_percent": ram_percent,
            "disk_free_gb": disk_free_gb,
            "disk_total_gb": disk_total_gb,
            "uptime": uptime_str,
        }


def draw_card(draw, x0, y0, x1, y1, fill=COLOR_CARD_BG, border=COLOR_CARD_BORDER):
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=border)


def draw_progress_bar(draw, x, y, width, height, percent, bar_color=COLOR_BTC_ORANGE, bg_color=COLOR_BAR_BG):
    percent = max(0.0, min(100.0, percent))
    draw.rectangle([x, y, x + width, y + height], fill=bg_color)
    fill_w = int((percent / 100.0) * width)
    if fill_w > 0:
        draw.rectangle([x, y, x + fill_w, y + height], fill=bar_color)


def render_dashboard(node_stats, sys_stats):
    img = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_large = ImageFont.load_default()
    font_med = ImageFont.load_default()
    font_small = ImageFont.load_default()

    try:
        ttf_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for p in ttf_paths:
            if os.path.exists(p):
                font_large = ImageFont.truetype(p, 18)
                font_med = ImageFont.truetype(p, 12)
                font_small = ImageFont.truetype(p, 10)
                break
    except Exception:
        pass

    # ================= 1. HEADER =================
    draw.rectangle([0, 0, SCREEN_WIDTH, 26], fill=(15, 20, 28))
    draw.text((6, 6), "₿ BITCOIN NODE", font=font_med, fill=COLOR_BTC_ORANGE)
    ip_label = f"{sys_stats['net_type']}: {sys_stats['ip']}"
    draw.text((115, 7), ip_label, font=font_small, fill=COLOR_ACCENT_CYAN if sys_stats['net_type'] == "Wi-Fi" else COLOR_TEXT_MUTED)
    draw.line([0, 26, SCREEN_WIDTH, 26], fill=COLOR_CARD_BORDER)

    # ================= 2. BLOCK SYNC CARD =================
    draw_card(draw, 6, 32, SCREEN_WIDTH - 6, 122)

    if node_stats["online"]:
        blocks = node_stats["blocks"]
        headers = node_stats["headers"]
        pct = node_stats["progress"]
        is_ibd = node_stats["ibd"] or pct < 99.99

        status_text = "SYNCING (IBD)" if is_ibd else "IN SYNC"
        status_color = COLOR_YELLOW if is_ibd else COLOR_GREEN

        draw.text((12, 38), "BLOCK HEIGHT", font=font_small, fill=COLOR_TEXT_MUTED)
        draw.text((145, 38), status_text, font=font_small, fill=status_color)

        draw.text((12, 52), f"#{blocks:,}", font=font_large, fill=COLOR_TEXT_WHITE)

        # Progress bar
        draw_progress_bar(draw, 12, 80, SCREEN_WIDTH - 36, 10, pct, bar_color=COLOR_BTC_ORANGE)
        draw.text((12, 96), f"Headers: {headers:,}", font=font_small, fill=COLOR_TEXT_MUTED)
        draw.text((160, 96), f"{pct:.2f}%", font=font_med, fill=COLOR_BTC_ORANGE)
    else:
        draw.text((12, 40), "BITCOIND DAEMON", font=font_small, fill=COLOR_TEXT_MUTED)
        draw.text((12, 60), "OFFLINE / STARTING...", font=font_med, fill=COLOR_RED)
        draw.text((12, 85), "Connecting / Warming...", font=font_small, fill=COLOR_TEXT_MUTED)

    # ================= 3. NETWORK & MEMPOOL CARD =================
    draw_card(draw, 6, 128, SCREEN_WIDTH - 6, 218)

    draw.text((12, 134), "PEERS", font=font_small, fill=COLOR_TEXT_MUTED)
    peers_str = f"{node_stats.get('peers', 0)} Active" if node_stats["online"] else "0"
    draw.text((12, 148), peers_str, font=font_med, fill=COLOR_ACCENT_CYAN)

    draw.text((120, 134), "MEMPOOL", font=font_small, fill=COLOR_TEXT_MUTED)
    mp_str = f"{node_stats.get('mempool_txs', 0):,} txs" if node_stats["online"] else "--"
    draw.text((120, 148), mp_str, font=font_med, fill=COLOR_TEXT_WHITE)

    draw.line([12, 172, SCREEN_WIDTH - 18, 172], fill=COLOR_CARD_BORDER)

    draw.text((12, 178), "STORAGE", font=font_small, fill=COLOR_TEXT_MUTED)
    prune_str = f"Pruned ({node_stats.get('prune_target_mb', 550)} MB)" if node_stats.get("pruned") else "Full Chain"
    draw.text((12, 192), prune_str, font=font_small, fill=COLOR_TEXT_WHITE)

    draw.text((120, 178), "DISK FREE", font=font_small, fill=COLOR_TEXT_MUTED)
    disk_str = f"{sys_stats['disk_free_gb']:.1f} / {sys_stats['disk_total_gb']:.1f} GB"
    draw.text((120, 192), disk_str, font=font_small, fill=COLOR_TEXT_WHITE)

    # ================= 4. HARDWARE & TELEMETRY =================
    draw_card(draw, 6, 224, SCREEN_WIDTH - 6, 314)

    # CPU Temp
    temp_c = sys_stats["temp_c"]
    temp_color = COLOR_GREEN if temp_c < 60 else (COLOR_YELLOW if temp_c < 75 else COLOR_RED)
    draw.text((12, 230), "CPU TEMP", font=font_small, fill=COLOR_TEXT_MUTED)
    draw.text((12, 244), f"{temp_c:.1f}°C", font=font_med, fill=temp_color)

    # RAM Usage
    draw.text((120, 230), "RAM (1.5GB)", font=font_small, fill=COLOR_TEXT_MUTED)
    ram_str = f"{sys_stats['ram_used_mb']}M / {sys_stats['ram_total_mb']}M"
    draw.text((120, 244), ram_str, font=font_med, fill=COLOR_TEXT_WHITE)

    # RAM Bar
    draw_progress_bar(draw, 120, 262, 100, 6, sys_stats["ram_percent"], bar_color=COLOR_ACCENT_CYAN)

    draw.line([12, 276, SCREEN_WIDTH - 18, 276], fill=COLOR_CARD_BORDER)

    draw.text((12, 284), "UPTIME", font=font_small, fill=COLOR_TEXT_MUTED)
    draw.text((12, 296), f"{sys_stats['uptime']}", font=font_small, fill=COLOR_TEXT_MUTED)

    ver_str = node_stats.get("subversion", "Core")
    draw.text((120, 284), "CLIENT", font=font_small, fill=COLOR_TEXT_MUTED)
    draw.text((120, 296), ver_str[:14], font=font_small, fill=COLOR_BTC_ORANGE)

    return img


def main():
    print("[INFO] Starting Bitcoin Pruned Node Display Daemon...")
    monitor = BitcoinNodeMonitor()

    display = None
    if ST7789 is not None:
        try:
            display = ST7789(
                width=SCREEN_WIDTH,
                height=SCREEN_HEIGHT,
                spi_bus=1,
                spi_device=1,  # CS1 (PH9) on Orange Pi Zero 3
                rotation=ROTATION,
            )
            print("[INFO] ST7789 display initialized on /dev/spidev1.1")
        except Exception as e:
            print(f"[WARN] Failed to open physical display: {e}. Running in headless/framebuffer dump mode.")

    refresh_interval = 3.0

    while True:
        try:
            node_stats = monitor.get_node_stats()
            sys_stats = monitor.get_system_stats()

            img = render_dashboard(node_stats, sys_stats)

            if display:
                display.display(img)

            try:
                img.save("/tmp/btc_display.png")
            except Exception:
                pass

        except KeyboardInterrupt:
            print("[INFO] Stopping display daemon.")
            if display:
                display.close()
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Telemetry loop error: {e}")

        time.sleep(refresh_interval)


if __name__ == "__main__":
    main()
