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
                         +-- POST /api/play|/pause|/stop|/next|/volume|/seek|/shuffle|/repeat|/output
                         +-- GET  /api/media?name=  file stream (Range) for browser output
                         |
                         +-- child: ffmpeg | paplay   (V0.1+)
```

Only one decoder child at a time. Stop = kill the child. Next = kill, start the next file. End of track auto-advances the queue (sequential or shuffle). Pause = SIGSTOP the process group (ffmpeg + paplay); Resume = SIGCONT. Seek = kill and restart ffmpeg with `-ss`. Volume = Pulse sink fade, no decoder restart.

## Library

```
/data/music/
  Artist/Album/track.mp3
  something.flac
```

Scan on demand for `.mp3` `.flac` `.opus` `.ogg` `.wav` `.m4a`. Sort by path. Picking track N starts playback there and the rest of the library follows (wraps only if Replay all is on, or if you hit Next). Shuffle uses a random bag of remaining indices. Replay cycles off / all / one.

`/data` is the 3.1 GB persistent partition. Leave headroom; a few hundred albums of MP3 is the right scale, not a FLAC archive of the whole collection.

## Players

V0.1 uses binaries already on the 9.4.6 image:

- **Decode:** `/usr/bin/ffmpeg` 4.2.2 (includes Opus)
- **Output:** `/usr/bin/paplay` → PulseAudio system daemon
- **Hardware sink:** S/PDIF only (`imx-spdif`). There is no analog headphone ALSA device on this board.

Pipeline: `ffmpeg -i file -f wav - | paplay` (unity decode). Volume is PulseAudio sink gain.

`mpg123` / `flac` are not installed. Do not `apt` on this Yocto image. Optional later: drop static **linux-armv7** `mpv` into `/data/opt`.

## Volume

PulseAudio sink volume (`pactl set-sink-volume`), faded in small steps so the slider does not restart ffmpeg/paplay. Hardware ALSA mixer is still unused.

## UI

Giggwatt HUD (time circuits, red/green/amber LEDs). Transport:

- Play
- Pause / Resume
- Stop
- Next
- Shuffle
- Replay (off / all / one)
- Volume (fade)
- Seek bar (elapsed / duration) plus a progress ring on the HUD
- Audio out: host optical (TOSLINK) or this browser
- RAM left / disk left on `/data`

Output is a host setting (`/data/music/.settings.json`). Optical plays the room preamp. Browser streams the file to the page and leaves TOSLINK silent.

Now-playing line under the buttons. No accounts, no websockets required: short polling of `/api/player` is enough. Position is wall-clock plus ffmpeg `out_time`, duration from `ffprobe` (ffmpeg Duration line as fallback).

## What we are not building (yet)

- Streaming from phones / Spotify
- Multi-room
- Gapless / ReplayGain science
- A second language (no Node on this board)
- Binding extra ports (80 is enough)

## Restore Savant (if needed)

Unmask `savant-startup-manager.service`, set default target back to `savant-host.target`, reboot. The 8.5 image is still on `mmcblk0p7`. This jukebox does not delete those slots.
