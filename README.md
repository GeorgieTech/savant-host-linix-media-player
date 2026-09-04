# savant-host-linix-media-player

Local jukebox for a recycled Savant SHC-2000 ARM Linux host. One process, files on disk, a tiny web page for Play / Stop / volume / next.

This project is **not affiliated with Savant Systems**. The hardware is a former Smart Host whose Savant runtime has been stopped. The Linux image underneath is reused as a small LAN appliance.

## Goal

**Local jukebox — simplest, most reliable.**

- Music lives on the host at `/data/music`
- One Python process serves the UI on **port 80** and owns playback
- Browser on the LAN: Play, Stop, software volume, Next
- No cloud, no Savant app, no extra daemon if we can avoid it

## Current status — V0.2

Target host: **192.168.1.180** (`sav-001aae073afe0000`)

| Piece | State |
|---|---|
| Savant `startupManager` | Stopped, systemd unit **masked** |
| Boot target | `multi-user.target` |
| Web UI | [http://192.168.1.180/](http://192.168.1.180/) — Play / Stop / Next / volume / library / upload / manage |
| Code on host | `/data/www` |
| Library | `/data/music` (audio only; not stored in this git repo) |
| Tags | `/data/music/.library.json` (genre tags, on the host) |
| Playback | `ffmpeg` decode → `paplay` (PulseAudio, S/PDIF sink on this board) |

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

Volume is software (player `--scale` / `ffmpeg -filter:a volume=`), not ALSA mixer, until we prove hardware volume is stable on this board.

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
