# savant-host-linix-media-player

Local jukebox for a recycled Savant SHC-2000 ARM Linux host. One process, files on disk, Gigawatt-skinned web page for Play / Pause / Stop / volume / next / seek / shuffle / replay, with optical or browser output.

This project is **not affiliated with Savant Systems**. The hardware is a former Smart Host whose Savant runtime has been stopped. The Linux image underneath is reused as a small LAN appliance.

## Goal

**Local jukebox — simplest, most reliable.**

- Music lives on the host at `/data/music`
- One Python process serves the UI on **port 80** and owns playback
- Browser on the LAN: Play, Pause, Stop, Next, seek, shuffle, replay, volume fade
- No cloud, no Savant app, no extra daemon if we can avoid it

## Current status — V0.6

Target host: **192.168.1.180** (`sav-001aae073afe0000`)

| Piece | State |
|---|---|
| Savant `startupManager` | Stopped, systemd unit **masked** |
| Boot target | `multi-user.target` |
| Web UI | [http://192.168.1.180/](http://192.168.1.180/) — Play / Pause / Stop / Next / shuffle / replay / volume fade / seek / library / upload / manage / settings |
| Code on host | `/data/www` |
| Library | `/data/music` (audio only; not stored in this git repo) |
| Tags | `/data/music/.library.json` (genre tags, on the host) |
| Playback | **Optical:** `ffmpeg` → `paplay` → TOSLINK. **Browser:** HTML5 audio from `/api/media` |
| Queue | Play from a picked track, then continue to the next (or shuffled bag) |
| Volume | Pulse sink fade; does not restart the decoder |
| Pause | SIGSTOP / SIGCONT on the decode+play process group |
| Seek | HUD bar + flux-capacitor ring; restart ffmpeg at `-ss` |
| Theme | **Gigawatt** — time-circuit HUD, red/green/amber LEDs, flux-Y visualizer |

Source of truth for the running page is `host-webui/` in this repo.

## Hardware (this box)

SHC-2000-00, i.MX6 Quad, 4× Cortex-A9 (`armv7l`), ~2 GB RAM, ~8 GB eMMC.

Full numbers: [docs/HOST.md](docs/HOST.md).  
How the pieces fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).  
How it was put on the box: [docs/DEPLOY.md](docs/DEPLOY.md).

## Playback plan

Prefer tools that already exist or a single `armv7` drop under `/data/opt`:

| Format | Player |
|---|---|
| MP3 | `mpg123` or `mpg321` |
| FLAC | `flac -d -c` piped to `aplay` |
| Fallback | `mpv` or `ffmpeg` static **armv7** build in `/data/opt` |

Volume is PulseAudio sink gain with a short fade. The decoder is not restarted when the slider moves.

## Host paths

```
/data/www          web UI + Python server (survives A/B root flashes)
/data/music        library (mp3 / flac)
/data/opt          optional armv7 binaries (mpv, ffmpeg, mpg123)
/etc/systemd/system/host-webui.service
```

`/` is the Savant Embedded Linux root. Do not store project files there.

## Layout of this repo

```
host-webui/     page + Python server currently running on port 80
docs/           hardware, architecture, deploy notes
LICENSE         MIT
```

## License

[MIT](LICENSE) © 2026 George Carrillo.
