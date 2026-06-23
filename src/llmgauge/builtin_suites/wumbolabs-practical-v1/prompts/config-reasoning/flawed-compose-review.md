Review this Docker Compose snippet for a download stack.

Context:
- `gluetun` should provide the VPN network namespace.
- `qbittorrent` should route through `gluetun`.
- The user wants conservative changes and verification before applying.
- Do not suggest wiping volumes or changing unrelated services.
- If `qbittorrent` uses `network_mode: service:gluetun`, it must not define its own `ports`; required exposed ports must be defined on `gluetun`.

Compose snippet:

services:
  gluetun:
    image: qmcgaw/gluetun:latest
    container_name: gluetun
    cap_add:
      - NET_ADMIN
    environment:
      - VPN_SERVICE_PROVIDER=protonvpn
      - SERVER_COUNTRIES=United States
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    volumes:
      - /nvme/appdata/gluetun:/gluetun

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    network_mode: bridge
    environment:
      - PUID=1000
      - PGID=1000
      - WEBUI_PORT=8080
    ports:
      - "8081:8080"
      - "6881:6881"
      - "6881:6881/udp"
    volumes:
      - /nvme/appdata/qbittorrent:/config
      - /nvme-downloads:/downloads
    restart: unless-stopped

Task:
Identify the practical risks and propose a safer minimal correction.

Requirements:
- Do not invent Docker Compose options.
- Do not claim this is the user's real current config.
- Explain why the current `qbittorrent` network mode is a problem.
- Explain why qBittorrent should not define `ports` when sharing Gluetun's network namespace.
- Put the qBittorrent WebUI exposure on `gluetun`.
- Do not expose BitTorrent peer ports unless the prompt proves they are needed.
- Provide a minimal corrected Compose snippet for only the relevant parts.
- Include read-only verification commands.
- Include rollback advice.
