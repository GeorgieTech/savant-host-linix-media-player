#!/usr/bin/env python3
"""AirPlay 1 receiver wrapper around shairport-sync."""
import os
import subprocess
import threading
import time

META_PIPE = "/tmp/giggwatt-airplay.meta"


def _decode(raw):
    if not raw:
        return ""
    try:
        return raw.decode("utf-8").strip()
    except Exception:
        return raw.decode("utf-8", "replace").strip()


class AirPlay:
    def __init__(self, directory, on_begin=None):
        self.directory = directory
        self.on_begin = on_begin
        self.lock = threading.Lock()
        self.proc = None
        self.enabled = False
        self.active = False
        self.title = ""
        self.artist = ""
        self.album = ""
        self.client = ""
        self.error = ""
        self._meta_thread = None

    def available(self):
        return os.path.isfile(os.path.join(self.directory, "run-shairport"))

    def snapshot(self):
        with self.lock:
            running = self.proc is not None and self.proc.poll() is None
            if self.proc is not None and self.proc.poll() is not None:
                self.proc = None
                self.active = False
            title = self.title
            if self.active and not title:
                title = "AirPlay"
            return {
                "available": self.available(),
                "enabled": bool(self.enabled and running),
                "active": bool(self.active and running),
                "title": title,
                "artist": self.artist,
                "album": self.album,
                "client": self.client,
                "error": self.error,
            }

    def set_enabled(self, value):
        want = bool(value)
        with self.lock:
            self.enabled = want
            if want:
                return self._start_locked()
            self._stop_locked()
            self.error = ""
            return True

    def _start_locked(self):
        if not self.available():
            self.error = "AirPlay binary missing"
            return False
        if self.proc is not None and self.proc.poll() is None:
            self.error = ""
            return True
        env = os.environ.copy()
        env["PULSE_SERVER"] = env.get("PULSE_SERVER") or "unix:/run/pulse/native"
        cmd = os.path.join(self.directory, "run-shairport")
        try:
            self.proc = subprocess.Popen(
                [cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except Exception as exc:
            self.error = str(exc)
            self.proc = None
            return False
        self.error = ""
        self.active = False
        self._meta_thread = threading.Thread(target=self._meta_loop, daemon=True)
        self._meta_thread.start()
        return True

    def _stop_locked(self):
        proc = self.proc
        self.proc = None
        self.active = False
        self.title = ""
        self.artist = ""
        self.album = ""
        self.client = ""
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _meta_loop(self):
        while True:
            with self.lock:
                proc = self.proc
            if proc is None or proc.poll() is not None:
                return
            try:
                fd = os.open(META_PIPE, os.O_RDONLY)
            except OSError:
                time.sleep(0.25)
                continue
            fh = os.fdopen(fd, "rb")
            try:
                self._drain(fh)
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass

    def _drain(self, fh):
        while True:
            header = fh.readline()
            if not header:
                return
            length_line = fh.readline()
            if not length_line:
                return
            try:
                size = int(length_line.strip(), 16)
            except ValueError:
                continue
            payload = b""
            while len(payload) < size:
                chunk = fh.read(size - len(payload))
                if not chunk:
                    return
                payload += chunk
            key = header.decode("ascii", "replace").strip()
            self._apply(key, payload)

    def _apply(self, key, payload):
        text = _decode(payload)
        begin = False
        with self.lock:
            if key == "ssnc.pbeg":
                self.active = True
                begin = True
            elif key in ("ssnc.pend", "ssnc.pfls"):
                if key == "ssnc.pend":
                    self.active = False
                    self.title = ""
                    self.artist = ""
                    self.album = ""
            elif key == "ssnc.prsm":
                self.active = True
            elif key == "core.minm":
                self.title = text
                self.active = True
            elif key == "core.asar":
                self.artist = text
            elif key == "core.asal":
                self.album = text
            elif key in ("ssnc.snua", "ssnc.clip"):
                if text:
                    self.client = text
        if begin and self.on_begin:
            try:
                self.on_begin()
            except Exception:
                pass
