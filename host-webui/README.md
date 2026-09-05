# host-webui (Beta1)

Python 3.8 stdlib HTTP server plus a single HTML page. This is what currently runs on the SHC-2000 at `192.168.1.180:80`.

Copy `index.html`, `server.py`, and `airplay.py` to `/data/www`. The AirPlay binary tree goes to `/data/opt/airplay` — see [airplay/README.md](airplay/README.md) and [../docs/DEPLOY.md](../docs/DEPLOY.md).

API `version` is `Beta1`.

## Page

- `GET /` — Giggwatt HUD (time circuits, library, manage, upload, settings, transport)
- `GET /bg-gigawatt.jpg` — optional steel/LED backdrop (copy next to index.html if present)

Tabs: Library, Manage, Upload, Settings.

Settings:

- Audio out: **Host optical** or **This browser**
- AirPlay: **On** / **Off** — advertises as **Giggwatt**. Audio is TOSLINK. HUD shows the track when the sender includes metadata

## JSON API

| Method | Path | Body / query | Notes |
|---|---|---|---|
| GET | `/api/status` | | hostname, ip, uptime, load, mem, disk, `savant_running`, `version` |
| GET | `/api/player` | | now playing, pause, position, duration, volume, shuffle, repeat, output, tags, `airplay` snapshot |
| GET | `/api/media` | `?name=` | audio file stream with HTTP Range (browser output) |
| POST | `/api/play` | `{index?}` | start or resume; picking an index continues the queue from there |
| POST | `/api/pause` | | freeze ffmpeg+paplay (SIGSTOP) |
| POST | `/api/stop` | | kill decoder |
| POST | `/api/next` | | next in queue / shuffle bag |
| POST | `/api/seek` | `{seconds}` or `{ratio}` | jump in the current track |
| POST | `/api/volume` | `{volume}` | Pulse sink fade 0–100 |
| POST | `/api/shuffle` | `{shuffle}` | on/off |
| POST | `/api/repeat` | `{repeat}` | `off` / `all` / `one` |
| POST | `/api/output` | `{output}` | `optical` / `browser` |
| POST | `/api/airplay` | `{enabled}` | start/stop shairport-sync |
| POST | `/api/tag` | | genre tag |
| POST | `/api/delete` | | remove a library file |
| POST | `/api/upload` | multipart | drop onto `/data/music` (max ~90 MB per file) |

`/api/player` includes `airplay`: `{available, enabled, active, title, artist, album, client, error}`.

Polling `/api/player` is enough. No websockets.

## Environment

| Variable | Default |
|---|---|
| `WEBUI_PORT` | `80` |
| `MUSIC_DIR` | `/data/music` |
| `PULSE_SERVER` | `unix:/run/pulse/native` |
| `PULSE_SINK` | `@DEFAULT_SINK@` |
| `AIRPLAY_DIR` | `/data/opt/airplay` |

See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
