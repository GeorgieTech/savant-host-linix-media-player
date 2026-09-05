# Beta2 — coming soon

This is a **handoff**, not a spec. Do not start Beta2 work until it is asked for. Beta1 stays frozen.

## What Beta1 already is

Leave this alone unless Beta2 explicitly replaces it:

- One Python 3.8 process on port 80 (`/data/www`)
- Library on `/data/music`
- Optical (`ffmpeg | paplay`) and this-browser (`/api/media`) routes
- Queue, pause, seek, Pulse fade, shuffle, replay
- Giggwatt time-circuit HUD
- AirPlay 1 (`shairport-sync` 3.3.7) to TOSLINK, Settings toggle, HUD now-playing from XML metadata

## Hard limits (do not fight these)

| Item | Why |
|---|---|
| AirPlay 2 | Receiver is AirPlay 1 only. This CPU / image will not grow an AirPlay 2 stack in-place |
| Bluetooth headphones | Radio is BLE / HCI. No A2DP, no Pulse Bluetooth. One UART is the BT HCI — leave it alone |
| Analog headphone jack | Board audio out is TOSLINK (`imx-spdif`) only |
| `apt` / Node / Docker | Yocto 9.4.6, ~2 GB RAM, 1.7 GB root. Stdlib Python and dropped-in armv7 binaries only |
| Live Savant system | Never touch **192.168.1.40** |

## Passed for now

- **Video** — this is an audio jukebox. Do not add a video player unless that is the Beta2 request.
- **Spotify Connect / other cloud streamers**
- **Multi-room, gapless, ReplayGain, cover art** (AirPlay cover art is currently off in `shairport-sync.conf`)

## Strongest unused hardware (if Beta2 goes here)

The SHC-2000 rear **RS-232** jacks are real ±12 V control ports, not USB-TTL. i.MX UARTs are `/dev/ttymxc*`.

Best first app, if we get the preamp **make and model**:

1. HUD **Play** or an **AirPlay begin** → preamp power on, select the Giggwatt input, unmute
2. **Stop** / AirPlay end → optional mute or power-off after a timeout (decide later)

Same ports could later drive a rack display, lighting, or projector. That is extra, not the killer app.

Do **not** put control traffic on the Bluetooth UART.

## When Beta2 starts

- Keep the Beta1 tag as the last known-good jukebox
- New work on `main` after `beta1`
- Update this file into a real spec only when the next slice is chosen
- Deploy notes stay in [DEPLOY.md](DEPLOY.md): `scp -O`, `/usr/bin/env` sudo, no `pkill -f shairport-sync`

## Local folder

Working copy:

`/Users/georgecarrillo/Documents/AI Apps/Savant 2.0/Media Player`

GitHub:

https://github.com/GeorgieTech/savant-host-linix-media-player
