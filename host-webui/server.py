#!/usr/bin/env python3
import cgi
import json
import os
import random
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from airplay import AirPlay

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("WEBUI_PORT", "80"))
MUSIC_DIR = os.environ.get("MUSIC_DIR", "/data/music")
AUDIO_EXTS = {".mp3", ".flac", ".opus", ".ogg", ".wav", ".m4a", ".aac"}
RMS_RE = re.compile(r"RMS(?:_level| level dB:)\s*=?\s*(-?[\d.]+)")
DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
OUT_RE = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")
MAX_UPLOAD = 90 * 1024 * 1024
VERSION = "Beta1"
AIRPLAY_DIR = os.environ.get("AIRPLAY_DIR", "/data/opt/airplay")
REPEAT_MODES = ("off", "all", "one")
OUTPUTS = ("optical", "browser")
PULSE_SINK = os.environ.get("PULSE_SINK", "@DEFAULT_SINK@")
LIBRARY_FILE = os.path.join(MUSIC_DIR, ".library.json")
SETTINGS_FILE = os.path.join(MUSIC_DIR, ".settings.json")
MIME = {
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
}
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


def _hms(match):
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


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
    return {"total": total, "used": total - (avail or 0), "free": avail or 0}


def disk_usage(path="/data"):
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        return {"total": total, "used": total - free, "free": free, "path": path}
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
        self.paused = False
        self.offset = 0.0
        self.t0 = 0.0
        self.hold = 0.0
        self.duration = 0.0
        self.durations = {}
        self.generation = 0
        self.shuffle = False
        self.repeat = "off"
        self.bag = []
        self.vol_actual = 80
        self.vol_target = 80
        self.output = "optical"
        self.session = False
        self.airplay_wanted = False
        self._load_tags()
        self._load_settings()
        self._apply_pulse_volume(self.volume)
        threading.Thread(target=self._fade_loop, daemon=True).start()

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

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, "r") as fh:
                data = json.load(fh)
            out = data.get("output")
            if out in OUTPUTS:
                self.output = out
            self.airplay_wanted = bool(data.get("airplay"))
        except Exception:
            self.output = "optical"
            self.airplay_wanted = False

    def _save_settings(self):
        os.makedirs(MUSIC_DIR, exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"output": self.output, "airplay": bool(self.airplay_wanted)}, fh)
        os.replace(tmp, SETTINGS_FILE)

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
        if self.output == "browser":
            return bool(self.session)
        return self.proc is not None and self.proc.poll() is None

    def _position_locked(self):
        if self.paused or not self._alive():
            pos = self.hold
        else:
            pos = self.offset + (time.monotonic() - self.t0)
        if self.duration > 0:
            pos = min(pos, self.duration)
        return round(max(0.0, pos), 2)

    def _probe_duration(self, path):
        if path in self.durations:
            return self.durations[path]
        out = _cmd(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )
        try:
            dur = float(out)
            if dur > 0:
                self.durations[path] = dur
                return dur
        except (TypeError, ValueError):
            pass
        try:
            proc = subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-i", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=8,
            )
            match = DUR_RE.search(proc.stderr or "")
            if match:
                dur = _hms(match)
                if dur > 0:
                    self.durations[path] = dur
                    return dur
        except Exception:
            pass
        return 0.0

    def snapshot(self):
        with self.lock:
            tracks = self.tracks()
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
            alive = self._alive()
            paused = bool(self.paused and alive)
            playing = bool(alive and not paused)
            position = self._position_locked()
            duration = round(self.duration, 2)
            return {
                "playing": playing,
                "paused": paused,
                "track": current,
                "index": self.index if tracks else -1,
                "tracks": names,
                "tags": dict(self.tags),
                "genres": GENRES,
                "volume": self.volume,
                "error": self.error,
                "rms": round(self.rms, 3) if playing else 0.0,
                "position": position,
                "duration": duration,
                "shuffle": self.shuffle,
                "repeat": self.repeat,
                "output": self.output,
                "outputs": list(OUTPUTS),
                "backend": "browser" if self.output == "browser" else "ffmpeg | paplay",
                "version": VERSION,
                "airplay": AIRPLAY.snapshot() if AIRPLAY is not None else {"available": False, "enabled": False, "active": False},
            }

    def stop(self):
        with self.lock:
            self.generation += 1
            self._stop_locked()
            self.error = ""
            return True

    def _stop_locked(self):
        self.session = False
        if self.proc is None:
            self.paused = False
            self.offset = 0.0
            self.hold = 0.0
            self.rms = 0.0
            return
        try:
            pgid = os.getpgid(self.proc.pid)
            if self.paused:
                try:
                    os.killpg(pgid, signal.SIGCONT)
                except Exception:
                    pass
            os.killpg(pgid, signal.SIGTERM)
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
        self.paused = False
        self.offset = 0.0
        self.hold = 0.0

    def _apply_pulse_volume(self, vol):
        vol = max(0, min(100, int(vol)))
        try:
            subprocess.check_call(
                ["pactl", "set-sink-volume", PULSE_SINK, "%s%%" % vol],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def _fade_loop(self):
        while True:
            with self.lock:
                target = self.vol_target
                actual = self.vol_actual
            if actual == target:
                time.sleep(0.03)
                continue
            delta = target - actual
            step = max(1, min(6, abs(delta) // 8 or 1))
            if abs(delta) <= step:
                actual = target
            elif delta > 0:
                actual += step
            else:
                actual -= step
            self._apply_pulse_volume(actual)
            with self.lock:
                self.vol_actual = actual
            time.sleep(0.02)

    def set_volume(self, value):
        try:
            vol = int(value)
        except (TypeError, ValueError):
            return False
        vol = max(0, min(100, vol))
        with self.lock:
            self.volume = vol
            self.vol_target = vol
            self.error = ""
        return True

    def _reshuffle_locked(self, n, current):
        ids = [i for i in range(n) if i != current]
        random.shuffle(ids)
        self.bag = ids

    def _next_index_locked(self, wrap, skip_repeat_one=False):
        tracks = self.tracks()
        n = len(tracks)
        if n <= 0:
            return None
        if self.repeat == "one" and not skip_repeat_one:
            return self.index
        if self.shuffle:
            valid = []
            for item in self.bag:
                if 0 <= item < n and item != self.index:
                    valid.append(item)
            self.bag = valid
            if not self.bag:
                if not (self.repeat == "all" or wrap):
                    return None
                self._reshuffle_locked(n, self.index)
            if not self.bag:
                return 0 if n == 1 else (self.index + 1) % n
            return self.bag.pop(0)
        nxt = self.index + 1
        if nxt >= n:
            if self.repeat == "all" or wrap:
                return 0
            return None
        return nxt

    def next_track(self):
        with self.lock:
            tracks = self.tracks()
            if not tracks:
                self.error = "no tracks in /data/music"
                return False
            nxt = self._next_index_locked(wrap=True, skip_repeat_one=True)
            if nxt is None:
                self.error = "end of queue"
                return False
            self.index = nxt
            return self._play_locked()

    def set_shuffle(self, value=None):
        with self.lock:
            if value is None:
                self.shuffle = not self.shuffle
            else:
                self.shuffle = bool(value)
            tracks = self.tracks()
            if self.shuffle and tracks:
                self._reshuffle_locked(len(tracks), self.index if tracks else 0)
            else:
                self.bag = []
            self.error = ""
            return True

    def set_repeat(self, value=None):
        with self.lock:
            if value in REPEAT_MODES:
                self.repeat = value
            else:
                idx = REPEAT_MODES.index(self.repeat) if self.repeat in REPEAT_MODES else 0
                self.repeat = REPEAT_MODES[(idx + 1) % len(REPEAT_MODES)]
            self.error = ""
            return True

    def set_output(self, value):
        if value not in OUTPUTS:
            self.error = "unknown output"
            return False
        with self.lock:
            if value == self.output:
                self.error = ""
                return True
            was_playing = self._alive()
            pos = self._position_locked() if was_playing else 0.0
            paused = bool(self.paused and was_playing)
            self.output = value
            try:
                self._save_settings()
            except Exception as exc:
                self.error = str(exc)
                return False
            self.generation += 1
            self._stop_locked()
            if not was_playing:
                self.error = ""
                return True
            if value == "browser":
                tracks = self.tracks()
                if tracks:
                    self.index %= len(tracks)
                    self.track = tracks[self.index]
                    if self.duration <= 0:
                        self.duration = self._probe_duration(self.track)
                self.session = True
                self.paused = paused
                self.offset = pos
                self.hold = pos
                self.t0 = time.monotonic()
                self.error = ""
                return True
            ok = self._play_locked(start=pos)
            if ok and paused:
                return self._pause_locked()
            return ok

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
                if self.shuffle:
                    self._reshuffle_locked(len(tracks), index)
                return self._play_locked(start=0.0)
            if self.paused and self._alive():
                return self._resume_locked()
            if self._alive():
                self.error = ""
                return True
            return self._play_locked(start=0.0)

    def pause(self):
        with self.lock:
            if self.paused and self._alive():
                self.error = ""
                return True
            if not self._alive():
                self.error = "nothing playing"
                return False
            return self._pause_locked()

    def seek(self, seconds=None, ratio=None):
        with self.lock:
            tracks = self.tracks()
            if not tracks:
                self.error = "no tracks in /data/music"
                return False
            path = tracks[self.index % len(tracks)]
            if self.duration <= 0:
                self.duration = self._probe_duration(path)
            try:
                if seconds is not None:
                    pos = float(seconds)
                elif ratio is not None:
                    pos = float(ratio) * (self.duration or 0.0)
                else:
                    self.error = "missing seek target"
                    return False
            except (TypeError, ValueError):
                self.error = "bad seek target"
                return False
            if pos < 0:
                pos = 0.0
            if self.duration > 0:
                pos = min(pos, max(0.0, self.duration - 0.15))
            if self.output == "browser":
                if not self.session:
                    return self._play_locked(start=pos)
                self.offset = pos
                self.hold = pos
                self.t0 = time.monotonic()
                self.error = ""
                return True
            return self._play_locked(start=pos)

    def _pause_locked(self):
        self.hold = self._position_locked()
        if self.output != "browser":
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGSTOP)
            except Exception as exc:
                self.error = str(exc)
                return False
        self.paused = True
        self.rms = 0.0
        self.error = ""
        return True

    def _resume_locked(self):
        if self.output != "browser":
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGCONT)
            except Exception as exc:
                self.error = str(exc)
                return False
        self.t0 = time.monotonic() - (self.hold - self.offset)
        self.paused = False
        self.rms = 0.15
        self.error = ""
        return True

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
            self.durations.pop(path, None)
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

    def _play_locked(self, start=0.0):
        tracks = self.tracks()
        if not tracks:
            self.error = "no tracks in /data/music"
            return False
        self.index %= len(tracks)
        path = tracks[self.index]
        try:
            start = float(start or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        if start < 0:
            start = 0.0
        self.duration = self._probe_duration(path)
        if self.duration and start >= max(0.0, self.duration - 0.2):
            start = 0.0
        keep_hold = start
        self.generation += 1
        gen = self.generation
        self._stop_locked()
        if self.output == "browser":
            self.session = True
            self.track = path
            self.offset = start
            self.hold = keep_hold
            self.t0 = time.monotonic()
            self.paused = False
            self.error = ""
            self.rms = 0.2
            return True
        ss = "-ss %.3f " % start if start > 0.04 else ""
        cmd = (
            "ffmpeg -nostdin -hide_banner -nostats -loglevel info -progress pipe:2 %s-i %s "
            "-filter:a astats=length=0.05:metadata=1:reset=1 "
            "-ac 2 -ar 48000 -f wav - | paplay"
            % (ss, shlex.quote(path))
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
        threading.Thread(target=self._meter, args=(self.proc, gen), daemon=True).start()
        self._apply_pulse_volume(self.volume)
        self.vol_actual = self.volume
        self.vol_target = self.volume
        self.track = path
        self.offset = start
        self.hold = keep_hold
        self.t0 = time.monotonic()
        self.paused = False
        self.error = ""
        self.rms = 0.15
        return True

    def _advance_locked(self):
        nxt = self._next_index_locked(wrap=False)
        if nxt is None:
            return False
        self.index = nxt
        return self._play_locked(start=0.0)

    def _meter(self, proc, gen):
        try:
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace")
                dur = DUR_RE.search(text)
                out = OUT_RE.search(text)
                match = RMS_RE.search(text)
                with self.lock:
                    if self.generation != gen or self.proc is not proc:
                        continue
                    if dur and self.duration <= 0:
                        self.duration = _hms(dur)
                        self.durations[self.track] = self.duration
                    if out and not self.paused:
                        elapsed = _hms(out)
                        self.t0 = time.monotonic() - elapsed
                    if match:
                        db = float(match.group(1))
                        amp = max(0.0, min(1.0, (db + 50.0) / 50.0))
                        self.rms = amp
        except Exception:
            pass
        with self.lock:
            if self.generation != gen or self.proc is not proc:
                return
            self.proc = None
            self.rms = 0.0
            self.paused = False
            if self.duration:
                self.hold = self.duration
            else:
                self.hold = self.offset + max(0.0, time.monotonic() - self.t0)
            self._advance_locked()


AIRPLAY = None
PLAYER = Jukebox()
AIRPLAY = AirPlay(AIRPLAY_DIR, on_begin=PLAYER.stop)


def ensure_avahi():
    if _cmd(["systemctl", "is-active", "avahi-daemon"]) == "active":
        return True
    _cmd(["sudo", "-n", "/usr/bin/env", "systemctl", "start", "avahi-daemon.socket"])
    _cmd(["sudo", "-n", "/usr/bin/env", "systemctl", "start", "avahi-daemon"])
    return _cmd(["systemctl", "is-active", "avahi-daemon"]) == "active"


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


def _safe_media_path(name):
    name = (name or "").replace("\\", "/").lstrip("/")
    if not name or name in (".", "..") or ".." in name.split("/"):
        return None
    ext = os.path.splitext(name)[1].lower()
    if ext not in AUDIO_EXTS:
        return None
    root = os.path.realpath(MUSIC_DIR)
    full = os.path.realpath(os.path.join(MUSIC_DIR, name))
    if full != root and not full.startswith(root + os.sep):
        return None
    if not os.path.isfile(full):
        return None
    return full


def send_media(handler, full, head=False):
    size = os.path.getsize(full)
    ext = os.path.splitext(full)[1].lower()
    mime = MIME.get(ext, "application/octet-stream")
    start = 0
    end = size - 1
    code = 200
    rng = handler.headers.get("Range") or ""
    if rng.startswith("bytes=") and size > 0:
        spec = rng.split("=", 1)[1].split("-")
        try:
            if spec[0]:
                start = int(spec[0])
            if len(spec) > 1 and spec[1]:
                end = int(spec[1])
        except ValueError:
            handler.send_error(400, "bad range")
            return
        end = min(end, size - 1)
        if start < 0 or start > end:
            handler.send_response(416)
            handler.send_header("Content-Range", "bytes */%s" % size)
            handler.end_headers()
            return
        code = 206
    length = end - start + 1
    handler.send_response(code)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(length))
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Cache-Control", "private, max-age=120")
    if code == 206:
        handler.send_header("Content-Range", "bytes %s-%s/%s" % (start, end, size))
    handler.end_headers()
    if head:
        return
    with open(full, "rb") as fh:
        fh.seek(start)
        left = length
        while left > 0:
            chunk = fh.read(min(65536, left))
            if not chunk:
                break
            handler.wfile.write(chunk)
            left -= len(chunk)


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
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            _json(self, status())
            return
        if path == "/api/player":
            _json(self, PLAYER.snapshot())
            return
        if path == "/api/media":
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or [""])[0]
            full = _safe_media_path(name)
            if not full:
                _json(self, {"error": "not found"}, 404)
                return
            send_media(self, full, head=False)
            return
        return super().do_GET()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/media":
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or [""])[0]
            full = _safe_media_path(name)
            if not full:
                self.send_error(404)
                return
            send_media(self, full, head=True)
            return
        return super().do_HEAD()

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
        if path == "/api/pause":
            ok = PLAYER.pause()
            _json(self, PLAYER.snapshot(), 200 if ok else 409)
            return
        if path == "/api/seek":
            ok = PLAYER.seek(seconds=data.get("seconds"), ratio=data.get("ratio"))
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
        if path == "/api/shuffle":
            PLAYER.set_shuffle(data.get("shuffle"))
            _json(self, PLAYER.snapshot())
            return
        if path == "/api/repeat":
            PLAYER.set_repeat(data.get("repeat"))
            _json(self, PLAYER.snapshot())
            return
        if path == "/api/output":
            ok = PLAYER.set_output(data.get("output"))
            _json(self, PLAYER.snapshot(), 200 if ok else 400)
            return
        if path == "/api/airplay":
            want = data.get("enabled")
            if want is None:
                want = data.get("airplay")
            PLAYER.airplay_wanted = bool(want)
            try:
                PLAYER._save_settings()
            except Exception:
                pass
            if PLAYER.airplay_wanted:
                ensure_avahi()
            ok = AIRPLAY.set_enabled(PLAYER.airplay_wanted)
            _json(self, PLAYER.snapshot(), 200 if ok else 409)
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
    if PLAYER.airplay_wanted:
        ensure_avahi()
        AIRPLAY.set_enabled(True)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        "host-webui listening on 0.0.0.0:%s serving %s music=%s"
        % (PORT, ROOT, MUSIC_DIR),
        flush=True,
    )
    httpd.serve_forever()
