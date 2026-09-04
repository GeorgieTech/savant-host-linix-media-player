# Architecture — local jukebox

Keep one process and one library directory. Reliability beats features.

## One process

The existing `host-webui/server.py` already:

- binds `0.0.0.0:80`
- serves static files from its directory
- answers `GET /api/status`

Extend that process. Do **not** add a second systemd unit for audio unless the player cannot be a child of the web process.

```
browser  --HTTP-->  python3 server.py :80
                         |
                         +-- GET /           UI
                         +-- GET /api/status host stats
                         +-- GET /api/player now playing, queue
                         +-- POST /api/play|/pause|/stop|/next|/volume|/seek
                         |
                         +-- child: ffmpeg | paplay   (V0.1+)
```

Only one decoder child at a time. Stop = kill the child. Next = kill, start the next file. Pause = SIGSTOP the process group (ffmpeg + paplay); Resume = SIGCONT. Seek = kill and restart ffmpeg with `-ss`.

## Library

```
/data/music/
  Artist/Album/track.mp3
  something.flac
```

Scan on demand for `.mp3` `.flac` `.opus` `.ogg` `.wav` `.m4a`. Sort by path. Queue is that list in order unless we add shuffle later. V0.1 ships one demo file: `Saxophones getting louder.opus`.

`/data` is the 3.1 GB persistent partition. Leave headroom; a few hundred albums of MP3 is the right scale, not a FLAC archive of the whole collection.

## Players

V0.1 uses binaries already on the 9.4.6 image:

- **Decode:** `/usr/bin/ffmpeg` 4.2.2 (includes Opus)
- **Output:** `/usr/bin/paplay` → PulseAudio system daemon
- **Hardware sink:** S/PDIF only (`imx-spdif`). There is no analog headphone ALSA device on this board.

Pipeline: `ffmpeg -i file -filter:a volume=N -f wav - | paplay`

`mpg123` / `flac` are not installed. Do not `apt` on this Yocto image. Optional later: drop static **linux-armv7** `mpv` into `/data/opt`.

## Volume

Software gain in the player:

- mpg123: `-f` / software scale
- ffmpeg/mpv: volume filter or `--volume`

Do not depend on `amixer` until ALSA device names on this i.MX6 are confirmed. PulseAudio was a Savant dependency; it may be idle now.

## UI

Same visual language as the current lab page (dark panel, copper accent). Transport:

- Play
- Pause / Resume
- Stop
- Volume
- Next
- Seek bar (elapsed / duration) plus a progress ring on the HUD

Now-playing line under the buttons. No accounts, no websockets required: short polling of `/api/player` is enough. Position is wall-clock plus ffmpeg `out_time`, duration from `ffprobe` (ffmpeg Duration line as fallback).

## What we are not building (yet)

- Streaming from phones / Spotify
- Multi-room
- Gapless / ReplayGain science
- A second language (no Node on this board)
- Binding extra ports (80 is enough)

## Restore Savant (if needed)

Unmask `savant-startup-manager.service`, set default target back to `savant-host.target`, reboot. The 8.5 image is still on `mmcblk0p7`. This jukebox does not delete those slots.
