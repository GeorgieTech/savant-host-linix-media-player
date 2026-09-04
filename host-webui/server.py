#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("WEBUI_PORT", "80"))


def _cmd(args):
    try:
        return subprocess.check_output(args, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def meminfo():
    data = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                data[k] = int(v.strip().split()[0]) * 1024
    except Exception:
        return None
    total = data.get("MemTotal")
    avail = data.get("MemAvailable") or data.get("MemFree")
    if not total:
        return None
    return {"total": total, "used": total - (avail or 0)}


def disk_usage(path="/data"):
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        return {"total": total, "used": total - free, "path": path}
    except Exception:
        return None


def ipv4():
    out = _cmd(["ip", "-4", "-o", "addr", "show", "scope", "global"])
    for line in out.splitlines():
        parts = line.split()
        if "inet" in parts:
            idx = parts.index("inet")
            if idx + 1 < len(parts):
                return parts[idx + 1].split("/")[0]
    for cand in _cmd(["hostname", "-I"]).split():
        if cand and not cand.startswith("127."):
            return cand
    return ""


def savant_running():
    out = _cmd(["pgrep", "-f", "startupManager"])
    return bool(out)


def status():
    uptime = _cmd(["uptime", "-p"]) or _cmd(["uptime"])
    load = ""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load = " ".join(parts[:3])
    except Exception:
        pass
    return {
        "hostname": socket.gethostname(),
        "ip": ipv4(),
        "uptime": uptime,
        "load": load,
        "mem": meminfo(),
        "disk": disk_usage("/data"),
        "savant_running": savant_running(),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/status":
            body = json.dumps(status()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


if __name__ == "__main__":
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("host-webui listening on 0.0.0.0:%s serving %s" % (PORT, ROOT), flush=True)
    httpd.serve_forever()
