# Deploy notes

How this host was converted, and how to copy this repo onto it.

## What was already done on 192.168.1.180

1. Factory firmware was **Pro 8.5** (kernel 3.14.14).
2. Official Savant package `daVinci-9.4.6-b696-SmartHost.smhost2` was applied with the image `update.sh` (A/B: wrote p6/p8, booted p8).
3. Savant launcher was stopped and **masked**:

   ```
   systemctl mask savant-startup-manager.service
   systemctl set-default multi-user.target
   ```

4. Lab UI installed as systemd `host-webui.service`, files in `/data/www`, listening on port 80.

SSH user: `RPM`. Do not commit the password.

## Copy the web UI from this repo

From a machine on the same LAN:

```sh
scp -O host-webui/index.html host-webui/server.py RPM@192.168.1.180:/tmp/
ssh RPM@192.168.1.180
sudo -n /usr/bin/env bash -c '
  cp /tmp/index.html /tmp/server.py /data/www/
  systemctl restart host-webui.service
'
```

Open http://192.168.1.180/

`scp -O` is required against this OpenSSH if the client defaults to SFTP-only scp.

## Install the systemd unit (first time)

```sh
scp -O host-webui/host-webui.service RPM@192.168.1.180:/tmp/
# then as root on the host:
cp /tmp/host-webui.service /etc/systemd/system/host-webui.service
systemctl daemon-reload
systemctl enable --now host-webui.service
```

## Music library

```sh
ssh RPM@192.168.1.180 'sudo -n /usr/bin/env mkdir -p /data/music'
scp -O -r /path/to/album RPM@192.168.1.180:/tmp/album
# move into /data/music as root
```

`/data` is not world-writable; copy via `/tmp` then `mv`.

## Optional armv7 tools

Place static binaries in `/data/opt` and put that directory on `PATH` for `server.py` (or call them by absolute path):

```
/data/opt/mpg123
/data/opt/flac
/data/opt/aplay     # usually already on the image
/data/opt/mpv
/data/opt/ffmpeg
```

Builds must be **linux-armv7** / gnueabihf. Mac and x86_64 Linux binaries will not run.

## Constraints

- No `apt`. Image is Yocto, not Debian.
- Python 3.8.2 is on the box; use stdlib only for the server.
- ~2 GB RAM, 4× Cortex-A9: decode MP3/FLAC is fine; do not run a browser or Docker on the host.
- Port 80 is the UI. Savant’s old lighttpd on 8080 should stay dead.
