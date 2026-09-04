#!/usr/bin/env python3
import cgi
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("WEBUI_PORT", "80"))
MUSIC_DIR = os.environ.get("MUSIC_DIR", "/data/music")
AUDIO_EXTS = {".mp3", ".flac", ".opus", ".ogg", ".wav", ".m4a", ".aac"}
RMS_RE = re.compile(r"RMS(?:_level| level dB:)\s*=?\s*(-?[\d.]+)")
MAX_UPLOAD = 90 * 1024 * 1024
LIBRARY_FILE = os.path.join(MUSIC_DIR, ".library.json")
GENRES = [
    "Pop",
    "Rock",
    "Hip-Hop",
    "R&B",
    "Electronic",
    "Jazz",
    "Classical",
    "Metal",
    "Country",
    "Soundtrack",
]


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
    out = _cmd(["pgrep", "-x", "startupManager"])
    return bool(out)


class Jukebox:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.index = 0
        self.volume = 80
        self.error = ""
        self.track = None
        self.rms = 0.0
        self.tags = {}
        self._load_tags()

    def _load_tags(self):
        try:
            with open(LIBRARY_FILE, "r") as fh:
                data = json.load(fh)
            self.tags = data.get("tags") or {}
        except Exception:
            self.tags = {}

    def _save_tags(self):
        os.makedirs(MUSIC_DIR, exist_ok=True)
        tmp = LIBRARY_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"tags": self.tags}, fh)
        os.replace(tmp, LIBRARY_FILE)

    def tracks(self):
        found = []
        if not os.path.isdir(MUSIC_DIR):
            return found
        for root, _dirs, names in os.walk(MUSIC_DIR):
            for name in names:
                ext = os.path.splitext(name)[1].lower()
                if ext in AUDIO_EXTS:
                    found.append(os.path.join(root, name))
        found.sort()
        return found

    def _alive(self):
        return self.proc is not None and self.proc.poll() is None

    def snapshot(self):
        with self.lock:
            tracks = self.tracks()
            if self.proc is not None and self.proc.poll() is not None:
                self.proc = None
            names = [os.path.relpath(p, MUSIC_DIR) for p in tracks]
            keep = set(names)
            if any(key not in keep for key in list(self.tags.keys())):
                self.tags = {k: v for k, v in self.tags.items() if k in keep}
                try:
                    self._save_tags()
                except Exception:
                    pass
            current = None
            if tracks:
                self.index %= len(tracks)
                current = os.path.relpath(tracks[self.index], MUSIC_DIR)
            return {
                "playing": self._alive(),
                "track": current,
                "index": self.index if tracks else -1,
                "tracks": names,
                "tags": dict(self.tags),
                "genres": GENRES,
                "volume": self.volume,
                "error": self.error,
                "rms": round(self.rms, 3) if self._alive() else 0.0,
                "backend": "ffmpeg | paplay",
            }

    def stop(self):
        with self.lock:
            self._stop_locked()
            self.error = ""
            return True

    def _stop_locked(self):
        if self.proc is None:
            return
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                pass
        try:
            self.proc.wait(timeout=2)
        except Exception:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except Exception:
                pass
        self.proc = None
        self.rms = 0.0

    def set_volume(self, value):
        try:
            vol = int(value)
        except (TypeError, ValueError):
            return False
        vol = max(0, min(100, vol))
        with self.lock:
            restart = self._alive()
            self.volume = vol
            if restart:
                return self._play_locked()
        return True

    def next_track(self):
        with self.lock:
            tracks = self.tracks()
            if not tracks:
                self.error = "no tracks in /data/music"
                return False
            self.index = (self.index + 1) % len(tracks)
            return self._play_locked()

    def play(self, index=None):
        with self.lock:
            if index is not None:
                try:
                    index = int(index)
                except (TypeError, ValueError):
                    self.error = "bad track index"
                    return False
                tracks = self.tracks()
                if index < 0 or index >= len(tracks):
                    self.error = "bad track index"
                    return False
                self.index = index
            return self._play_locked()

    def set_genre(self, index, genre):
        with self.lock:
            tracks = self.tracks()
            try:
                index = int(index)
            except (TypeError, ValueError):
                self.error = "bad track index"
                return False
            if index < 0 or index >= len(tracks):
                self.error = "bad track index"
                return False
            genre = (genre or "").strip()
            if genre and genre not in GENRES:
                self.error = "unknown genre"
                return False
            name = os.path.relpath(tracks[index], MUSIC_DIR)
            if genre:
                self.tags[name] = genre
            else:
                self.tags.pop(name, None)
            try:
                self._save_tags()
            except Exception as exc:
                self.error = str(exc)
                return False
            self.error = ""
            return True

    def delete_track(self, index):
        with self.lock:
            tracks = self.tracks()
            try:
                index = int(index)
            except (TypeError, ValueError):
                self.error = "bad track index"
                return False
            if index < 0 or index >= len(tracks):
                self.error = "bad track index"
                return False
            path = tracks[index]
            name = os.path.relpath(path, MUSIC_DIR)
            if self.track == path:
                self._stop_locked()
            try:
                os.remove(path)
            except Exception as exc:
                self.error = str(exc)
                return False
            self.tags.pop(name, None)
            try:
                self._save_tags()
            except Exception:
                pass
            leftover = self.tracks()
            if leftover:
                if index >= len(leftover):
                    self.index = 0
                else:
                    self.index = index
            else:
                self.index = 0
                self.track = None
            self.error = ""
            return True

    def _play_locked(self):
        tracks = self.tracks()
        if not tracks:
            self.error = "no tracks in /data/music"
            return False
        self.index %= len(tracks)
        path = tracks[self.index]
        self._stop_locked()
        gain = max(0.0, min(1.0, self.volume / 100.0))
        cmd = (
            "ffmpeg -nostdin -hide_banner -nostats -loglevel info -i %s "
            "-filter:a volume=%s,astats=length=0.05:metadata=1:reset=1 "
            "-ac 2 -ar 48000 -f wav - | paplay"
            % (shlex.quote(path), gain)
        )
        try:
            self.proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
        except Exception as exc:
            self.error = str(exc)
            self.proc = None
            self.rms = 0.0
            return False
        threading.Thread(target=self._meter, args=(self.proc,), daemon=True).start()
        self.track = path
        self.error = ""
        self.rms = 0.15
        return True

    def _meter(self, proc):
        try:
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace")
                match = RMS_RE.search(text)
                if match:
                    db = float(match.group(1))
                    amp = max(0.0, min(1.0, (db + 50.0) / 50.0))
                    with self.lock:
                        self.rms = amp
        except Exception:
            pass
        with self.lock:
            if self.proc is proc:
                self.proc = None
                self.rms = 0.0


PLAYER = Jukebox()


def status():
    uptime = _cmd(["uptime", "-p"]) or _cmd(["uptime"])
    load = ""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load = " ".join(parts[:3])
    except Exception:
        pass
    body = {
        "hostname": socket.gethostname(),
        "ip": ipv4(),
        "uptime": uptime,
        "load": load,
        "mem": meminfo(),
        "disk": disk_usage("/data"),
        "savant_running": savant_running(),
        "player": PLAYER.snapshot(),
    }
    return body


def _json(handler, payload, code=200):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        return {}


def _safe_music_name(name):
    name = os.path.basename((name or "").replace("\\", "/").strip())
    if not name or name in (".", "..") or ".." in name:
        return None
    ext = os.path.splitext(name)[1].lower()
    if ext not in AUDIO_EXTS:
        return None
    return name


def save_uploads(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    disk = disk_usage("/data")
    if disk and length > max(0, disk["total"] - disk["used"] - 40 * 1024 * 1024):
        return None, "not enough free space on /data"
    if length > MAX_UPLOAD * 8:
        return None, "upload too large"
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(length),
        },
        keep_blank_values=True,
    )
    if "file" not in form:
        return None, "no file field"
    raw = form["file"]
    items = raw if isinstance(raw, list) else [raw]
    saved = []
    errors = []
    os.makedirs(MUSIC_DIR, exist_ok=True)
    for item in items:
        filename = getattr(item, "filename", None)
        if not filename:
            continue
        name = _safe_music_name(filename)
        if not name:
            errors.append("rejected %s" % os.path.basename(filename))
            continue
        dest = os.path.join(MUSIC_DIR, name)
        tmp = dest + ".part"
        try:
            with open(tmp, "wb") as out:
                shutil.copyfileobj(item.file, out)
                size = out.tell()
            if size == 0:
                os.remove(tmp)
                errors.append("%s empty" % name)
                continue
            if size > MAX_UPLOAD:
                os.remove(tmp)
                errors.append("%s exceeds 90 MB" % name)
                continue
            os.replace(tmp, dest)
            saved.append({"name": name, "bytes": size})
        except Exception as exc:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            errors.append("%s: %s" % (name, exc))
    return {"saved": saved, "errors": errors, "player": PLAYER.snapshot(), "disk": disk_usage("/data")}, None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            _json(self, status())
            return
        if path == "/api/player":
            _json(self, PLAYER.snapshot())
            return
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/upload":
            payload, err = save_uploads(self)
            if err:
                _json(self, {"error": err}, 400)
                return
            code = 200 if payload.get("saved") else 400
            _json(self, payload, code)
            return
        data = _read_json(self)
        if path == "/api/play":
            ok = PLAYER.play(index=data.get("index"))
            _json(self, PLAYER.snapshot(), 200 if ok else 409)
            return
        if path == "/api/stop":
            PLAYER.stop()
            _json(self, PLAYER.snapshot())
            return
        if path == "/api/next":
            ok = PLAYER.next_track()
            _json(self, PLAYER.snapshot(), 200 if ok else 409)
            return
        if path == "/api/volume":
            ok = PLAYER.set_volume(data.get("volume"))
            _json(self, PLAYER.snapshot(), 200 if ok else 400)
            return
        if path == "/api/tag":
            ok = PLAYER.set_genre(data.get("index"), data.get("genre"))
            _json(self, PLAYER.snapshot(), 200 if ok else 400)
            return
        if path == "/api/delete":
            ok = PLAYER.delete_track(data.get("index"))
            _json(self, PLAYER.snapshot(), 200 if ok else 400)
            return
        _json(self, {"error": "not found"}, 404)


if __name__ == "__main__":
    os.makedirs(MUSIC_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        "host-webui listening on 0.0.0.0:%s serving %s music=%s"
        % (PORT, ROOT, MUSIC_DIR),
        flush=True,
    )
    httpd.serve_forever()
