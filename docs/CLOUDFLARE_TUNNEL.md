# How the Cloudflare Tunnel works

This page explains how `https://sbuddy.xuanlin.us` reaches the Sbuddy app running on the Mac mini at home. For why this approach was chosen, see [ADR 0001](adr/0001-public-viewer-via-cloudflare-tunnel-from-mac-mini.md).

## The problem: nobody outside can reach a home machine

The Mac mini sits behind the home router, which does **NAT** (Network Address Translation). Every device in the house shares one public IPv4 address. The router remembers which device started each outgoing conversation, so it knows where to send the replies.

When a stranger on the internet tries to *start* a new connection to the house, the router has no record of it and can't tell which device it's for. So it drops the connection. That's a good default, but it also means nobody outside can reach the app.

The traditional fix is **port forwarding**: you tell the router "send everything that arrives on port 443 to the Mac." That works, but it has real costs:

- It publishes the home IP in DNS.
- It exposes the Mac directly to every bot scanning the internet.
- You have to manage TLS certificates on the Mac.
- It breaks when the ISP changes your IP.

## The idea: the connection starts from inside

The router blocks *incoming* connections but allows *outgoing* ones, which is how every browser in the house works. A tunnel uses that.

A small program, `cloudflared`, runs on the Mac and connects *out* to Cloudflare, then keeps those connections open. Requests from visitors travel *back down* the connections that are already open. It's like calling a friend and leaving the line open so they can keep talking to you. They never need to call you.

```
 Visitor's browser               Cloudflare edge                      Home network
 ─────────────────               ───────────────                      ────────────
                                                         ┌──── router (NAT: drops unsolicited inbound) ────┐
 https://sbuddy.xuanlin.us                               │                                                 │
        │                                                │   cloudflared ─────► api:3000 (Express)         │
        │ 1. DNS lookup → a Cloudflare IP                │        ▲                                        │
        ▼                                                │        │ 0. cloudflared dialled OUT at startup  │
   [ HTTPS; TLS ends here ] ◄══════ persistent outbound connections (QUIC) ═══╝    and keeps it open      │
        2. "Which tunnel serves this hostname?"          │                                                 │
        3. Check the ingress rules; send the request     │                                                 │
           down an open connection ────────────────────► │  4. cloudflared calls http://api:3000          │
                                                         │     and returns the response                    │
                                                         └─────────────────────────────────────────────────┘
```

## How it works, step by step

1. **Start-up.** `cloudflared` reads a *tunnel token*, a secret that identifies this tunnel. It then opens about four long-lived connections to two nearby Cloudflare data centres. It uses **QUIC** (a protocol that runs over UDP, port 7844) and falls back to **HTTP/2 over TCP** if UDP is blocked. Two data centres means the site stays up if one fails.
2. **DNS.** `sbuddy.xuanlin.us` is a proxied CNAME pointing to `<tunnel-id>.cfargotunnel.com`. A visitor's DNS lookup returns a *Cloudflare* IP address, never the home IP.
3. **A request arrives.** The browser connects to Cloudflare over HTTPS. Cloudflare holds the certificate for the domain, so TLS ends there and the Mac needs no certificate. Cloudflare then applies its security rules, including the rate limit on study-plan writes, and checks the tunnel's **ingress rules**. These are an ordered list, along the lines of:
   - `/api/v1/viewer/*` → `http://api:3000`
   - `/api/v1/health` → `http://api:3000`
   - the static viewer pages → `http://api:3000`
   - everything else → 404
4. **Multiplexing.** Cloudflare sends the request down one of the open connections as a new *stream*. Many visitors' requests share the same few connections at once, the same way HTTP/2 carries many requests over one connection. `cloudflared` receives the stream and makes an ordinary plain-HTTP request to `api:3000` on the Docker Compose network. It then sends the response back up the same stream.

## Questions and answers

### How does Cloudflare know the home IP?

Nobody tells it. Cloudflare just sees the source address of the connection `cloudflared` opens, the same way any website sees the IP of a browser that connects to it. That address is the router's public IP.

Cloudflare doesn't *route* by IP, though. It routes by **tunnel ID**: "requests for this hostname go down whichever connections tunnel X currently has open." So:

- The home IP never appears in DNS, and visitors never learn it.
- If the ISP changes the home IP, `cloudflared` reconnects from the new address and carries on. No dynamic DNS is needed.
- The address does show up in your own Cloudflare dashboard, as the "origin IP" of each tunnel connector. That's only visible to the account owner.

### How do I control what traffic goes in and out?

There are separate layers, and each controls a different path:

| Layer | Controls | Where it's set |
|---|---|---|
| **Cloudflare DNS** | Which hostnames point at the tunnel at all | Cloudflare dashboard / API |
| **Cloudflare security rules** (WAF, rate limiting) | What is blocked or throttled *before* it reaches the tunnel | Cloudflare dashboard / API |
| **Tunnel ingress rules** | Which hostnames and paths are forwarded to which local service; everything else gets 404 | Tunnel config (managed remotely in Cloudflare) |
| **Cloudflare Access** (not used) | Who must log in before getting through | Zero Trust dashboard |
| **Router NAT / firewall** | Inbound traffic to the home IP that doesn't come through the tunnel | Router admin (Xfinity app / gateway) |
| **Docker port publishing** | Which interfaces on the Mac expose the app port (`3000`) | `docker-compose.yml` `ports:` |
| **macOS firewall** | Which apps on the Mac accept inbound connections | System Settings → Network → Firewall |

The tunnel only needs **outbound** access: UDP/TCP 7844 to Cloudflare, plus 443 for its API. It needs no inbound port at all.

### Does traffic that doesn't come from Cloudflare still get through?

**Through the tunnel: no.** Only Cloudflare can send requests down the tunnel. The connections are encrypted and authenticated with the tunnel token, so nobody else can inject anything into them.

**Directly to the home IP: the tunnel changes nothing.** It doesn't open anything, so whatever the router blocks today stays blocked. Two things are worth checking, though:

- **IPv6.** NAT only applies to IPv4. Xfinity gives each device its own public IPv6 address, and the Mac mini has several (`2601:600:…`). For IPv6, the only thing standing between the internet and the Mac is the router's IPv6 firewall. Xfinity gateways block unsolicited inbound IPv6 by default. However, Docker's default `0.0.0.0` publishing listens on **all interfaces, IPv6 included**. So with it, a relaxed firewall would expose the whole API (not just the viewer) to the internet. That's why port 3000 is now published only on `127.0.0.1` (see *Why the API port is bound to `127.0.0.1`*). `cloudflared` reaches the app over the internal Docker network and doesn't use the published port.
- **Port forwards and UPnP.** Check that the router has no port forwards. Also check that UPnP is off, or that you trust every device using it. UPnP lets devices on the network open ports on the router by themselves.

## Limits worth knowing

- **Cloudflare sees the plaintext.** TLS ends at Cloudflare, so Cloudflare can read the traffic. That's fine for public study content.
- **If the house is down, the site is down.** That includes a power cut, an internet outage, a reboot, or Docker not running. Cloudflare can only pass traffic to a machine that's there to answer. Recovery after a reboot is tracked in #49.
- **The ingress rules are the security boundary.** A route that isn't listed is unreachable from outside, and that's deliberate. A new public route has to be added on purpose.

## Current setup

The tunnel config is managed remotely: it lives in Cloudflare, not in this repo. Change it in the Zero Trust dashboard (Networks → Tunnels → `sbuddy-mac`) or through the API.

| Piece | Value |
|---|---|
| Tunnel | `sbuddy-mac` (`cec580a5-2fe4-43ff-a0ed-7bf62b1b497d`), config managed remotely |
| DNS | `sbuddy.xuanlin.us` CNAME → `<tunnel-id>.cfargotunnel.com`, proxied |
| Ingress (in order) | `^/viewer(/.*)?$`, `^/test-images/`, `^/api/v1/viewer/`, `^/api/v1/health$` → `http://api:3000`; everything else → `http_status:404` |
| Redirect rule | `/` → `https://sbuddy.xuanlin.us/viewer/` (302) |
| Rate-limit rule | POST/PUT/DELETE under `/api/v1/viewer/study-plans`: 20 requests per 10 s per IP, then blocked (429) for 10 s |
| Connector | `cloudflared` service in `docker-compose.yml`, reading `CLOUDFLARE_TUNNEL_TOKEN` from `.env`. `sbuddy.sh deploy` starts it after the API is healthy |
| API port | Published only on `127.0.0.1` (`API_BIND_IP`), so it's reachable from the Mac itself and nowhere else |

**Rotating the token.** If the token leaks, refresh the tunnel's token in the dashboard, or with the API: `PATCH /accounts/{id}/cfd_tunnel/{id}` with a new `tunnel_secret`. Then update `CLOUDFLARE_TUNNEL_TOKEN` in `.env` and run `docker compose up -d cloudflared`.

**Checking it from outside:** `curl -I https://sbuddy.xuanlin.us/api/v1/health` should return 200, and `/api/v1/auth/register` should return 404.

## Why the API port is bound to `127.0.0.1`

There are two separate ways in, and they don't depend on each other:

- **The public path:** browser → Cloudflare → tunnel → `cloudflared` → `api:3000`. This runs entirely inside Docker's internal network. It doesn't use the published port, so the bind address has no effect on the public site.
- **The LAN path:** a device in the house connects to `http://<mac-lan-ip>:3000`. The `ports:` line in `docker-compose.yml` exists only for this. Through it you get the *whole* API, not just the viewer: auth, imports, OCR, and so on.

A published port has to name the address it listens on, and there are three practical choices:

| Bind address | Who can reach port 3000 | Trade-off |
|---|---|---|
| `0.0.0.0` (the old default) | Every interface, including the Mac's **public IPv6 addresses** | Only the Xfinity IPv6 firewall keeps the internet away from the full API. That's one layer, and it isn't ours to control. |
| A LAN IPv4, e.g. `10.0.0.74` | Devices on the home LAN, over IPv4 only | If DHCP gives the Mac a new IP (say `10.0.0.101` after a reboot), Docker fails with `bind: can't assign requested address`. The API won't start, and the public site returns 502. You'd need a DHCP reservation. |
| `127.0.0.1` (current) | Only the Mac itself | No IP dependency. Phones and laptops at home use the public URL, which shows only the viewer. |

Docker has no "LAN only" setting; the only way to say that is to name the LAN address. Chosen on 2026-11-25: `127.0.0.1`. Full-API access from other devices at home wasn't needed. Nothing on the Mac depends on the LAN port either: the scripts use `docker compose exec`, and local tools can use `localhost:3000`. If LAN access is needed again, set `API_BIND_IP` to the LAN IP *and* reserve that IP in DHCP.

## Change log

- **2026-11-25: tunnel live.** The API was first published on `10.0.0.74` instead of `0.0.0.0`, to close the IPv6 exposure.
- **2026-11-25: API bound to `127.0.0.1`.** A reboot that gives the Mac a new DHCP address (e.g. `10.0.0.101`) would have stopped the API from starting, and the public site would have returned 502. LAN access to the full API was dropped. Home devices use the public URL.

## Open items

These are known gaps, left on purpose for now:

- **Tunnel token exposure.** The token was handled in an agent session during setup on 2026-11-25. If you'd rather it had never left the machine, rotate it (see *Rotating the token*).
- **The rest of #44 is not done, and the viewer doesn't need it yet:**
  - CORS is still `origin: '*'`. The viewer only calls its own origin, and its API takes no cookies or credentials, so a cross-site page gains nothing.
  - Express `trust proxy` isn't set, so `req.ip` is the `cloudflared` container for public requests. That only matters for the in-app `rateLimiter`, which guards non-public routes. Cloudflare does the public rate limiting.
  - `FRONTEND_URL`, `API_URL` and `SESSION_COOKIE_SECURE` are unchanged. They're only used by OAuth and email flows, which aren't exposed.

  Revisit all of these before any non-viewer route goes public, or when accounts arrive (#6).
- **Unattended restart (#49).** Docker Desktop starts only when someone logs in to the Mac, so after a reboot the site stays down until someone signs in.
- **`cloudflared` image is `latest`.** Each `docker compose pull` or recreate can pick up a new version. Pin a tag, such as `cloudflare/cloudflared:<version>`, if you want to upgrade only when you choose.
