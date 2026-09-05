# AirPlay runtime (Beta1)

armv7 `shairport-sync` **3.3.7** plus the shared libraries this Yocto image does not ship.

Installed on the host as `/data/opt/airplay`. The web UI starts and stops it from Settings (`POST /api/airplay`). Wrapper: `run-shairport`.

This is **AirPlay 1** (ALAC). Not AirPlay 2. Audio goes to Pulse (`output_backend = "pa"`), application name **Giggwatt AirPlay**, then TOSLINK.

## Why 3.3.7

The 9.4.6 image is glibc 2.31 / OpenSSL 1.1.1. Debian `shairport-sync` 3.3.8+ needs libc 2.34 and libssl3 and will not load. 3.3.7-1 armhf is the newest that fits.

Do not `apt` on this box. Extra libs live in `lib/`:

- libconfig
- libsoxr (+ libgomp)
- libmosquitto
- libjack (linked; unused at runtime)

glib, Pulse, ALSA, Avahi, and OpenSSL 1.1 are already on the image.

## Conf (summary)

`shairport-sync.conf`:

- `name = "Giggwatt"`
- `output_backend = "pa"`
- metadata pipe `/tmp/giggwatt-airplay.meta`
- `include_cover_art = "no"`
- session interruption allowed

Avahi must be running for mDNS. It was `PartOf=` Savant startup; a systemd drop-in keeps it alive with the launcher masked.

## Metadata (HUD now-playing)

3.3.7 writes **XML**, not the later `ssnc.pbeg` line protocol. `../airplay.py` parses:

```
<item><type>73736e63</type><code>70626567</code><length>N</length>
<data encoding="base64">…</data></item>
```

Fourcc keys: `ssnc.pbeg` / `pend` / `prsm`, `core.minm` / `asar` / `asal`, `ssnc.snam` / `snua` / `clip`.

The FIFO is created and opened `O_RDWR` before the daemon starts so writes do not get `ENXIO`. If metadata is quiet, a Pulse `sink-inputs` watchdog still marks the session active. No title → HUD shows **AirPlay**.

After replacing `airplay.py` on the host, skip or restart the phone/Mac session so a new XML packet arrives.

## Stop / debug

```
pkill -x shairport-sync
```

Do **not** `pkill -f shairport-sync` from an SSH command whose cmdline contains that string.

Binary build string includes: `libdaemon-OpenSSL-Avahi-ALSA-jack-pa-dummy-stdout-pipe-soxr-convolution-metadata-mqtt-dbus-mpris`. D-Bus/MPRIS warnings on this image are ignorable.
