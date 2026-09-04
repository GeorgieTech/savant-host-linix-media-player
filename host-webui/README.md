# host-webui

Python 3.8 stdlib HTTP server plus a single HTML page. This is what currently runs on the SHC-2000 at `192.168.1.180:80`.

- `GET /` — Gigawatt HUD (time circuits, library, manage, upload, transport)
- `GET /bg-gigawatt.jpg` — optional steel/LED backdrop (copy next to index.html)
- `GET /api/status` — JSON: hostname, ip, uptime, load, mem, disk, `savant_running`, player
- `GET /api/player` — now playing, pause, position, duration, volume, shuffle, repeat, output, tags
- `GET /api/media?name=` — audio file stream with HTTP Range (browser output)
- `POST /api/play` `{index?}` — start or resume; picking an index continues the queue from there
- `POST /api/pause` — freeze ffmpeg+paplay
- `POST /api/seek` `{seconds}` or `{ratio}` — jump in the current track
- `POST /api/stop` `/api/next` `/api/volume` `/api/shuffle` `/api/repeat` `/api/output`
- `POST /api/tag` `/api/delete` `/api/upload`

See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
