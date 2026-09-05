# Deploy notes (Beta1)

How this host was converted, and how to copy this repo onto it.

Target: **192.168.1.180**. Never **192.168.1.40**.

SSH user: `RPM`. Do not commit the password. `sudo` NOPASSWD is only `/usr/bin/env` as root, not `sudo -u RPM`.

## What was already done on 192.168.1.180

1. Factory firmware was **Pro 8.5** (kernel 3.14.14).
2. Official Savant package `daVinci-9.4.6-b696-SmartHost.smhost2` was applied with the image `update.sh` (A/B: wrote p6/p8, booted p8).
3. Savant launcher was stopped and **masked**:

   ```
   systemctl mask savant-startup-manager.service
   systemctl set-default multi-user.target
   ```

4. Lab UI installed as systemd `host-webui.service`, files in `/data/www`, listening on port 80.
5. AirPlay runtime lives in `/data/opt/airplay` (binary + extra libs). The web process starts and stops it.
6. Avahi has a systemd drop-in so it is **not** `PartOf=` Savant startup. AirPlay mDNS needs avahi running.

## Copy the web UI from this repo (Beta1)

From this Mac, in the repo root. `scp -O` is required against this OpenSSH if the client defaults to SFTP-only scp.

```sh
scp -O \
  host-webui/index.html \
  host-webui/server.py \
  host-webui/airplay.py \
  RPM@192.168.1.180:/tmp/

ssh RPM@192.168.1.180
sudo -n /usr/bin/env bash -c '
  cp /tmp/index.html /tmp/server.py /tmp/airplay.py /data/www/
  systemctl restart host-webui.service
'
```

Open http://192.168.1.180/

`airplay.py` must sit next to `server.py` in `/data/www`. The AirPlay **binary tree** is separate (`/data/opt/airplay`).

## Install the systemd unit (first time)

```sh
scp -O host-webui/host-webui.service RPM@192.168.1.180:/tmp/
# then as root on the host:
cp /tmp/host-webui.service /etc/systemd/system/host-webui.service
systemctl daemon-reload
systemctl enable --now host-webui.service
```

The unit runs as `RPM`, group `audio`, `WorkingDirectory=/data/www`, `WEBUI_PORT=80`, `MUSIC_DIR=/data/music`, `PULSE_SERVER=unix:/run/pulse/native`, `CAP_NET_BIND_SERVICE` for port 80.

## AirPlay runtime (first time, or after replacing the tree)

The Yocto image has no `apt`. Debian `shairport-sync` 3.3.8+ needs glibc 2.34 / libssl3 and **will not run**. Beta1 uses **3.3.7-1 armhf** (glibc ≥ 2.29, OpenSSL 1.1.1) plus extra `.so` files this image does not ship.

Copy the tree from the repo:

```sh
scp -O -r host-webui/airplay RPM@192.168.1.180:/tmp/airplay
ssh RPM@192.168.1.180
sudo -n /usr/bin/env bash -c '
  mkdir -p /data/opt
  rm -rf /data/opt/airplay
  mv /tmp/airplay /data/opt/airplay
  chmod +x /data/opt/airplay/run-shairport /data/opt/airplay/shairport-sync
'
```

Host layout:

```
/data/opt/airplay/run-shairport          wrapper (LD_LIBRARY_PATH, -c conf)
/data/opt/airplay/shairport-sync         armv7 binary
/data/opt/airplay/shairport-sync.conf    name=Giggwatt, output_backend=pa, metadata pipe
/data/opt/airplay/lib/                   libconfig, libsoxr, libmosquitto, libjack, libgomp
```

`server.py` looks at `AIRPLAY_DIR` (default `/data/opt/airplay`). The wrapper must not be given `-c` twice; `run-shairport` already passes the conf. To stop the daemon later, use `pkill -x shairport-sync` — **not** `pkill -f`, which can match the SSH command line and kill the session.

After a code deploy of the metadata parser, skip or restart the iPhone/Mac AirPlay session so a fresh XML packet is written.

## Music library

```sh
ssh RPM@192.168.1.180 'sudo -n /usr/bin/env mkdir -p /data/music'
scp -O -r /path/to/album RPM@192.168.1.180:/tmp/album
# move into /data/music as root
```

`/data` is not world-writable; copy via `/tmp` then `mv`. Do not push `/data/music` or the local `Music/` folder to GitHub.

## Optional armv7 tools

Place static binaries in `/data/opt` and put that directory on `PATH` for `server.py` (or call them by absolute path):

```
/data/opt/mpg123
/data/opt/flac
/data/opt/aplay     # usually already on the image
/data/opt/mpv
/data/opt/ffmpeg
```

Builds must be **linux-armv7** / gnueabihf. Mac and x86_64 Linux binaries will not run. Beta1 does not need these; ffmpeg and paplay are already on the 9.4.6 image.

## Constraints

- No `apt`. Image is Yocto, not Debian.
- Python 3.8.2 is on the box; use stdlib only for the server.
- ~2 GB RAM, 4× Cortex-A9: decode MP3/FLAC is fine; do not run a browser or Docker on the host.
- Port 80 is the UI. Savant’s old lighttpd on 8080 should stay dead.
- `scp -O` from modern macOS/OpenSSH clients.
- Quote remote SSH commands; zsh glob and `===` will eat unquoted Python one-liners. Prefer scp of a script over `python3 -c` over SSH.
- Host key: `StrictHostKeyChecking=no` only if you already trust this box on the LAN.

## GitHub

Public repo: https://github.com/GeorgieTech/savant-host-linix-media-player

Beta1 tag: `beta1` (see [CHANGELOG.md](CHANGELOG.md)). Earlier point releases remain as `v0.3` … `v0.7`.
