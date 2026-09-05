# Giggwatt Beta1

Repo: [`GeorgieTech/savant-host-linix-media-player`](https://github.com/GeorgieTech/savant-host-linix-media-player).

**Giggwatt** is a local LAN jukebox on a recycled Savant SHC-2000 ARM Linux host. One Python process, files on disk, a time-circuit HUD, optical TOSLINK or this-browser output, and optional AirPlay 1 from an iPhone or Mac.

This project is **not affiliated with Savant Systems**. The hardware is a former Smart Host whose Savant runtime has been stopped. The Linux image underneath is reused as a small LAN appliance.

**Beta1 is a freeze.** The feature set on this tag is what we ship now. **Beta2 is coming soon** and is not started — see [docs/BETA2.md](docs/BETA2.md).

## Goal

**Local jukebox — simplest, most reliable.**

- Music lives on the host at `/data/music` (not in this git repo)
- One Python process serves the UI on **port 80** and owns playback
- Browser on the LAN: Play, Pause, Stop, Next, seek, shuffle, replay, volume fade
- Optional AirPlay 1 receiver, toggled in Settings, plays the same TOSLINK jack
- No cloud, no Savant app, no extra daemon unless a child of that one process

## Current status — Beta1

Target host: **192.168.1.180** (`sav-001aae073afe0000`)

Live UI: [http://192.168.1.180/](http://192.168.1.180/)

| Piece | State |
|---|---|
| Name | **Giggwatt** |
| Freeze | **Beta1** (V0.1–V0.7 line, including AirPlay HUD metadata) |
| Savant `startupManager` | Stopped, systemd unit **masked** |
| Boot target | `multi-user.target` |
| Web UI | Play / Pause / Stop / Next / shuffle / replay / volume fade / seek / library / upload / manage / settings |
| Code on host | `/data/www` |
| Library | `/data/music` (audio only; gitignored) |
| Tags | `/data/music/.library.json` (genre tags, on the host) |
| Settings | `/data/music/.settings.json` (optical vs browser, AirPlay on/off) |
| Playback | **Optical:** `ffmpeg` → `paplay` → TOSLINK. **Browser:** HTML5 audio from `/api/media` |
| Queue | Play from a picked track, then continue (or shuffled bag). Replay: off / all / one |
| Volume | Pulse sink fade; does not restart the decoder |
| Pause | SIGSTOP / SIGCONT on the decode+play process group |
| Seek | HUD bar + flux-capacitor ring; restart ffmpeg at `-ss` |
| AirPlay | Optional `shairport-sync` 3.3.7 (AirPlay 1) → Pulse → TOSLINK. HUD shows the iPhone/Mac track when metadata is sent |
| Theme | Time-circuit HUD, red/green/amber LEDs, flux-Y visualizer, darkened mobile play plate |
| Stats | Host, IP, uptime, RAM left, disk left on `/data` |

Source of truth for the running page is `host-webui/` in this repo.

## What Beta1 can do

- Browse `/data/music`, tap to play, upload, delete, genre-tag
- Optical room playback or private playback in the browser that opened the HUD
- AirPlay 1: Settings → AirPlay **On**. The box advertises as **Giggwatt**. Audio hits TOSLINK. The HUD shows title / artist / album when the sender includes DMAP metadata (Apple Music, iTunes). YouTube / Safari often send audio only — the HUD then shows **AirPlay**
- Starting an AirPlay session stops the local jukebox queue so two sources do not fight the sink

## What Beta1 is not

These are out of scope for this freeze. Some are hardware limits, some are passed, some wait for Beta2.

- **AirPlay 2** — this receiver is AirPlay 1 (ALAC over the classic protocol)
- **Spotify Connect / cloud streaming**
- **Bluetooth headphones** — the radio is BLE / HCI only; there is no A2DP stack or Pulse Bluetooth module on this image
- **Video** — passed; this is an audio jukebox
- **Multi-room, gapless, ReplayGain**
- **RS-232 / IR / GPIO / relay** — present on the chassis, unused by Beta1
- A second language or extra HTTP ports (Python 3.8 stdlib on port 80 only)

Do **not** use **192.168.1.40** (live Carrillos Resident Savant system). This repo’s host is **192.168.1.180**.

## Hardware (this box)

SHC-2000-00, i.MX6 Quad, 4× Cortex-A9 (`armv7l`), ~2 GB RAM, ~8 GB eMMC. Audio out is **S/PDIF TOSLINK only** (`imx-spdif`). There is no analog headphone jack in ALSA.

Full numbers: [docs/HOST.md](docs/HOST.md).  
How the pieces fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).  
How it was put on the box: [docs/DEPLOY.md](docs/DEPLOY.md).  
Version history: [docs/CHANGELOG.md](docs/CHANGELOG.md).  
Beta2 handoff: [docs/BETA2.md](docs/BETA2.md).

## Host paths

```
/data/www                 web UI + Python server (survives A/B root flashes)
/data/www/airplay.py      AirPlay wrapper (XML metadata + Pulse watchdog)
/data/music               library (mp3 / flac / opus / ogg / wav / m4a)
/data/opt/airplay         shairport-sync 3.3.7 + extra libs (not Debian-apt on this Yocto image)
/etc/systemd/system/host-webui.service
```

`/` is the Savant Embedded Linux root. Do not store project files there.

## Layout of this repo

```
README.md           this file — Beta1 landing page
docs/               hardware, architecture, deploy, changelog, Beta2
host-webui/         page + Python server currently running on port 80
  airplay.py        AirPlay 1 child + HUD metadata
  airplay/          armv7 shairport-sync runtime copied to /data/opt/airplay
LICENSE             MIT
Music/              local library copy on this Mac (gitignored, never pushed)
```

## License

[MIT](LICENSE) © 2026 George Carrillo.
