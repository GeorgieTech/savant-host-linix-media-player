# Architecture — local jukebox (Beta1)

Keep one process and one library directory. Reliability beats features.

Beta1 freezes this shape. Do not add a second systemd unit for audio. AirPlay is a **child** of the web process, started and stopped from Settings.

## One process

`host-webui/server.py` binds `0.0.0.0:80`, serves the HUD, and owns playback.

```
browser  --HTTP-->  python3 server.py :80
                         |
                         +-- GET /                 Giggwatt HUD
                         +-- GET /api/status       host stats
                         +-- GET /api/player       now playing, queue, airplay snapshot
                         +-- POST /api/play|/pause|/stop|/next|/volume|/seek|/shuffle|/repeat|/output|/airplay
                         +-- POST /api/tag|/delete|/upload
                         +-- GET  /api/media?name= file stream (Range) for browser output
                         |
                         +-- child: ffmpeg | paplay     optical queue
                         +-- child: shairport-sync      optional AirPlay 1 → Pulse → TOSLINK
```

Only one decoder child at a time. Stop = kill the child. Next = kill, start the next file. End of track auto-advances the queue (sequential or shuffle). Pause = SIGSTOP the process group (ffmpeg + paplay); Resume = SIGCONT. Seek = kill and restart ffmpeg with `-ss`. Volume = Pulse sink fade, no decoder restart.

When an AirPlay session **begins**, the jukebox queue is stopped so two sources do not share the S/PDIF sink.

## Library

```
/data/music/
  Artist/Album/track.mp3
  something.flac
```

Scan on demand for `.mp3` `.flac` `.opus` `.ogg` `.wav` `.m4a` `.aac`. Sort by path. Picking track N starts playback there and the rest of the library follows (wraps only if Replay all is on, or if you hit Next). Shuffle uses a random bag of remaining indices. Replay cycles off / all / one.

Genre tags live in `/data/music/.library.json`. Output route and AirPlay-wanted live in `/data/music/.settings.json`. Neither file is in git.

`/data` is the 3.1 GB persistent partition. Leave headroom; a few hundred albums of MP3 is the right scale, not a FLAC archive of the whole collection.

## Players

Beta1 uses binaries already on the 9.4.6 image, plus one dropped-in AirPlay tree:

- **Decode:** `/usr/bin/ffmpeg` 4.2.2 (includes Opus)
- **Output:** `/usr/bin/paplay` → PulseAudio system daemon
- **Hardware sink:** S/PDIF only (`imx-spdif`). There is no analog headphone ALSA device on this board
- **AirPlay:** `/data/opt/airplay/run-shairport` → `shairport-sync` 3.3.7, Pulse `pa` backend

Optical pipeline: `ffmpeg -i file -f wav - | paplay` (unity decode). Volume is PulseAudio sink gain.

`mpg123` / `flac` are not installed. Do not `apt` on this Yocto image.

## Volume

PulseAudio sink volume (`pactl set-sink-volume`), faded in small steps so the slider does not restart ffmpeg/paplay. Hardware ALSA mixer is still unused.

## Output route

Host setting, persisted in `.settings.json`:

| Mode | What happens |
|---|---|
| `optical` | Queue plays TOSLINK into the room preamp |
| `browser` | HUD streams `/api/media` with HTTP Range; TOSLINK stays silent |

AirPlay always plays **optical**, regardless of the queue route. Turn AirPlay off in Settings when you want the queue alone.

## AirPlay 1

Settings → AirPlay On/Off. `POST /api/airplay` `{ "enabled": true }`.

- Advertise name: **Giggwatt** (Avahi / mDNS). Avahi must stay up; it used to be `PartOf=` Savant startup and needed a systemd drop-in so it survives with the launcher masked
- Protocol: **AirPlay 1** (ALAC). Not AirPlay 2
- Audio: shairport-sync → Pulse application name `Giggwatt AirPlay` → `imx-spdif`
- Metadata FIFO: `/tmp/giggwatt-airplay.meta`

shairport-sync **3.3.7** writes **XML items**, not the newer `type.code` line protocol:

```
<item><type>73736e63</type><code>70626567</code><length>N</length>
<data encoding="base64">…</data></item>
```

`airplay.py` parses that with a regex, decodes fourcc type/code (`ssnc.pbeg`, `core.minm`, `core.asar`, `core.asal`, `ssnc.pend`, …), and base64 payloads as UTF-8 or UTF-16.

The FIFO is opened `O_RDWR` **before** Popen so shairport’s write side does not get `ENXIO`. A Pulse watchdog (`pactl list sink-inputs` looking for `Giggwatt AirPlay` / shairport) marks the session active if metadata is silent. If the session is active and there is no title, the HUD shows **AirPlay**.

Apple Music and iTunes usually send DMAP title/artist/album. YouTube and Safari often send audio only.

## UI

Giggwatt HUD (time circuits, red/green/amber LEDs). Transport:

- Play / Pause / Resume / Stop / Next
- Shuffle
- Replay (off / all / one)
- Volume (fade)
- Seek bar (elapsed / duration) plus a progress ring on the HUD
- Audio out: host optical (TOSLINK) or this browser
- Settings: same output toggle, plus AirPlay On/Off
- RAM left / disk left on `/data`
- AIRPLAY chip when a session is active
- Darkened mobile play plate so title, seek, and transport stay readable

Now-playing line under the buttons. No accounts, no websockets: short polling of `/api/player` is enough. Position is wall-clock plus ffmpeg `out_time`, duration from `ffprobe` (ffmpeg Duration line as fallback).

## What we are not building in Beta1

- AirPlay 2
- Spotify Connect / other cloud streamers
- Bluetooth A2DP headphones (radio is BLE/HCI only)
- Video
- Multi-room, gapless, ReplayGain
- RS-232 / IR / GPIO / relay control
- A second language (no Node on this board)
- Binding extra ports (80 is enough)

See [BETA2.md](BETA2.md) for what might come next. That file is a handoff, not a commitment.

## Restore Savant (if needed)

Unmask `savant-startup-manager.service`, set default target back to `savant-host.target`, reboot. The 8.5 image is still on `mmcblk0p7`. This jukebox does not delete those slots.
