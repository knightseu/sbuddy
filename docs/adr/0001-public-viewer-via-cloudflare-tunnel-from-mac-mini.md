---
status: accepted
---

# Serve the public viewer from the Mac mini through Cloudflare Tunnel, with no Access

The Sbuddy viewer goes online at `https://sbuddy.xuanlin.us`. The existing Docker Compose stack on the Mac mini serves it, with `cloudflared` running as a fourth compose service. `cloudflared` opens outbound connections to Cloudflare and gets requests back over them. So nothing on the home router is opened, and the home IP never appears in DNS. Running it this way costs about $0, needs the smallest migration, and keeps the live database and `sbuddy.sh backup` on one machine. The price is that the site is up only while the house and the Mac are (decided in #46, using research from #41, #45 and #47).

The site is public with no Cloudflare Access and no login. Every visitor is a browser guest, as on the LAN. Instead of a login, the protection is a deliberately small public surface. Tunnel ingress rules expose only the static viewer pages, `/api/v1/viewer/*` and `/api/v1/health`, and return 404 for every other path. One Cloudflare rate-limiting rule limits study-plan writes. The rest of the API (auth, OCR, problem CRUD, imports) isn't public (decided in #43).

## Considered options

- **Cloud host plus managed database** (Fly.io plus Neon, Render). It would stay up without depending on the house. It was rejected for now because managed Postgres can cost $30 or more a month, and the data would have to be split from the content pipeline. It's parked in #48 (P9). Revisit only if home uptime or the ISP's terms become a real problem.
- **Port forwarding plus an A/AAAA record at the home IP.** This was rejected. It publishes the home IP, exposes the Mac directly to internet scanners, needs certificates managed on the Mac, and breaks whenever the ISP changes the IP.
- **Cloudflare Access with an email allow-list and a one-time PIN.** It was chosen at first, then reversed in #43. The owner wants the viewer open to anyone with the URL. Adding Access later only takes dashboard configuration, plus validating the Access JWT at the origin.

## Consequences

- **Ingress rules are the security boundary.** A new public route has to be added to the tunnel's ingress rules on purpose. A new non-viewer route is unreachable from outside by default, and that's intended.
- **Guest IDs can be forged** (`X-Guest-ID`). Anyone who learns another guest's ID can edit that guest's study plans. This is accepted until multi-user support (#6). Recovery relies on backups.
- **A reboot takes the site down until someone logs in,** because Docker Desktop starts at login. That's tracked in #49.
- **The API port is published on `127.0.0.1` only (2026-11-25).** `0.0.0.0` also listened on the Mac's public Xfinity IPv6 address. A LAN-IP bind fails to start when DHCP changes the address, which also takes the public site down (the API container won't run). So the full API is reachable only from the Mac itself, and other home devices use the public viewer. The tunnel never used that port.
- **Cloudflare decrypts the traffic.** It ends TLS at its edge, so it can see the plaintext of requests. That's acceptable for public study content.
