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
                         +-- POST /api/play|/stop|/next|/volume
                         |
                         +-- child: mpg123 | flac|aplay | mpv
```

Only one decoder child at a time. Stop = kill the child. Next = kill, start the next file.

## Library

```
/data/music/
  Artist/Album/track.mp3
  something.flac
```

Scan on demand (or at start) for `.mp3` / `.flac`. Sort by path. Queue is that list in order unless we add shuffle later.

`/data` is the 3.1 GB persistent partition. Leave headroom; a few hundred albums of MP3 is the right scale, not a FLAC archive of the whole collection.

## Players (in order)

1. **MP3** — `mpg123` or `mpg321` if present (`which mpg123`).
2. **FLAC** — `flac -d -c file.flac | aplay -t wav -`.
3. **Anything else** — `/data/opt/mpv` or `/data/opt/ffmpeg` (static **linux-armv7**). Drop-in only; do not try to `apt` on this Yocto image.

If none of the tools exist, the API returns a clear error. The UI does not pretend it is playing.

## Volume

Software gain in the player:

- mpg123: `-f` / software scale
- ffmpeg/mpv: volume filter or `--volume`

Do not depend on `amixer` until ALSA device names on this i.MX6 are confirmed. PulseAudio was a Savant dependency; it may be idle now.

## UI

Same visual language as the current lab page (dark panel, copper accent). Add four controls only:

- Play
- Stop
- Volume
- Next

Now-playing line under the buttons. No accounts, no websockets required: short polling of `/api/player` is enough.

## What we are not building (yet)

- Streaming from phones / Spotify
- Multi-room
- Gapless / ReplayGain science
- A second language (no Node on this board)
- Binding extra ports (80 is enough)

## Restore Savant (if needed)

Unmask `savant-startup-manager.service`, set default target back to `savant-host.target`, reboot. The 8.5 image is still on `mmcblk0p7`. This jukebox does not delete those slots.
