# host-webui

Python 3.8 stdlib HTTP server plus a single HTML page. This is what currently runs on the SHC-2000 at `192.168.1.180:80`.

- `GET /` — status page
- `GET /api/status` — JSON: hostname, ip, uptime, load, mem, disk, `savant_running`

Jukebox controls will be added here, not in a second service. See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
