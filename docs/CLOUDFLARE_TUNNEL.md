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

- **IPv6.** NAT only applies to IPv4. Xfinity gives each device its own public IPv6 address, and the Mac mini has several (`2601:600:…`). For IPv6, the only thing standing between the internet and the Mac is the router's IPv6 firewall. Xfinity gateways block unsolicited inbound IPv6 by default. However, Docker currently publishes port 3000 on **all interfaces, IPv6 included**. So if that firewall were ever relaxed, the whole API (not just the viewer) would be reachable from the internet. The fix (#44) is to publish port 3000 only on `127.0.0.1` or the LAN IPv4 address. `cloudflared` reaches the app over the internal Docker network and doesn't use the published port.
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
| Connector | `cloudflared` service in `docker-compose.yml`, reading `CLOUDFLARE_TUNNEL_TOKEN` from `.env` |
| API port | Published only on `API_BIND_IP` (the Mac's LAN IPv4, `10.0.0.74`), so it's not reachable over IPv6 |

**Keep the LAN IP fixed.** If DHCP gives the Mac a different address, the API container can't bind `API_BIND_IP` and won't start. Reserve `10.0.0.74` for the Mac mini in the router's DHCP settings, or update `.env` if the address changes.

**Rotating the token.** If the token leaks, refresh the tunnel's token in the dashboard, or with the API: `PATCH /accounts/{id}/cfd_tunnel/{id}` with a new `tunnel_secret`. Then update `CLOUDFLARE_TUNNEL_TOKEN` in `.env` and run `docker compose up -d cloudflared`.

**Checking it from outside:** `curl -I https://sbuddy.xuanlin.us/api/v1/health` should return 200, and `/api/v1/auth/register` should return 404.
