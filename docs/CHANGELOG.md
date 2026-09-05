# Changelog

Giggwatt on the recycled SHC-2000 at 192.168.1.180. Tags live on GitHub: https://github.com/GeorgieTech/savant-host-linix-media-player/releases

## Beta1 — freeze (2026-09-04)

Call the running product **Giggwatt Beta1**. Feature set is the V0.1–V0.7 line plus the AirPlay XML metadata parser. Beta2 is not started.

Docs on GitHub and in this folder were completed to match the live host:

- README, architecture, deploy, host, web UI, AirPlay runtime
- Honest “what we are not building”
- [BETA2.md](BETA2.md) handoff (RS-232 preamp idea, video passed, BT headphones not feasible)

Code tag: `beta1`. API `version` string: `Beta1`.

## V0.7 — AirPlay (tag `v0.7`)

- Settings → AirPlay On/Off. Box advertises as **Giggwatt**
- `shairport-sync` 3.3.7 armhf in `/data/opt/airplay`, Pulse `pa` backend → TOSLINK
- Local queue stops when an AirPlay session begins
- Follow-up commit: parse shairport **3.3 XML** metadata (`<item><type>…`) so the HUD shows title / artist / album. Pulse watchdog if metadata is silent. Dummy title **AirPlay** when audio is flowing without DMAP

## V0.6 — Giggwatt HUD (tag `v0.6`)

- Named the host **Giggwatt**
- Time-circuit HUD (destination / present / last departed), flux-Y visualizer, BTTF palette
- Darkened mobile play plate so title, seek, and transport stay readable

## V0.5 — optical or this browser (tag `v0.5`)

- Settings + HUD toggle: host TOSLINK vs HTML5 `/api/media` in the page that opened the UI
- Browser mode leaves the optical jack silent
- Route persisted in `/data/music/.settings.json`

## V0.4 — queue, fade, shuffle, replay (tag `v0.4`)

- Auto-advance to the next track (or shuffled bag)
- Pulse sink volume fade (decoder is not restarted)
- Shuffle and Replay (off / all / one)
- RAM left and disk left on `/data` in the HUD

## V0.3 — seek and pause (tag `v0.3`)

- Pause / resume via SIGSTOP / SIGCONT on the ffmpeg+paplay group
- Seek bar and flux-capacitor ring; restart ffmpeg at `-ss`
- Elapsed / duration on the HUD

## V0.2 — library manager

- Delete tracks
- Genre tags in `/data/music/.library.json`

## Earlier (untagged or folded into the HUD)

- Upload tab: drop audio onto the host from the HUD
- Full `/data/music` library in the HUD, tap-to-play
- Full-screen HUD with radial visualizer (later replaced by the Giggwatt skin)

## V0.1 — jukebox

- Python stdlib server on port 80
- Play / Stop / Next / volume
- `ffmpeg | paplay` to S/PDIF
- Savant launcher masked; files on `/data/www`
