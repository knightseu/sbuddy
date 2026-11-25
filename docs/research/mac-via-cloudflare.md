# Serving the Sbuddy stack from the Mac through Cloudflare

Research for issue #47, a child of map #40. Checked 2026-11-24 against Cloudflare's own docs, plus read-only checks on the Mac and home network. It builds on:

- #41, Cloudflare Access and Registrar (`docs/research/cloudflare-access-registrar.md` on branch `research/cloudflare-access-registrar`).
- #45, cloud hosts (`docs/research/cloud-hosting.md` on branch `research/cloud-hosting`). Its best fit is Fly.io plus Neon Free.

**Question.** Can the Cloudflare domain point at the existing Docker Compose stack on the Mac (`scripts/sbuddy.sh`, API on port 3000) instead of a cloud host?

**Short answer.**

- **Yes, through Cloudflare Tunnel.** It needs no router change, no open port, no public IP and no dynamic DNS. It is free and is set up the same way whatever the home network does (CGNAT, a dynamic IP, IPv6).
- **A proxied A/AAAA record plus port forwarding also works, but it is worse here.** It needs a router change and a DDNS updater, it leaves a port open at home, and Cloudflare will not proxy port 3000. It is also unclear whether this connection can take inbound IPv4 at all (see §1).
- **Uptime is the weak point, not reachability.** The Mac is a Mac mini with system sleep off and restart after power failure on. But Docker Desktop starts only when a user signs in, so after a reboot the site stays down until someone logs in, unless auto-login is set (not checked). Home power, the ISP, and macOS updates are all single points of failure.
- **Compared with Fly.io + Neon:** both cost about $0. The Mac route needs less migration work, and the data and backups stay where they are. Fly + Neon has much better uptime and does not depend on the house.

## 1. This Mac and this network (read-only checks, 2026-11-24)

The public IP address is deliberately not recorded here.

| Check | Finding | How |
|---|---|---|
| Hardware | **Mac mini**, a desktop. No battery, so the lid and battery sleep rules don't apply. | `system_profiler SPHardwareDataType` (model name) |
| System sleep | `sleep 0`, so the system never sleeps. `displaysleep 10` and `disksleep 10` don't stop services. `powernap 1`, `womp 1` (wake on LAN), `tcpkeepalive 1`. | `pmset -g` |
| Restart after power loss | `autorestart 1`, so the Mac boots again by itself when power returns | `pmset -g` |
| LAN | IPv4 default route goes through `en1` to a private-range gateway. The Mac has a private IPv4 address (behind NAT). | `netstat -rn`, `ifconfig` |
| Public IPv4 | The echo service sees a **public IPv4** address, not one in the CGNAT range 100.64.0.0/10 | Cloudflare's own `https://1.1.1.1/cdn-cgi/trace` (sends nothing identifying) |
| Router's WAN IP | **Could not be read.** The router answered neither NAT-PMP (UDP 5351) nor UPnP IGD discovery. | read-only NAT-PMP "external address" and UPnP `GetExternalIPAddress` queries |
| Path to the internet | Hop 1 is the home gateway. **Hop 2 is also a private address**, and the public internet starts at hop 3. | `traceroute -n -m 4 1.1.1.1` (hops classified, not recorded) |
| IPv6 | The Mac has **global IPv6 addresses**: one stable ("secured") and several temporary. The public IPv6 check returned a global address, so native IPv6 works. | `ifconfig en1`, `https://[2606:4700:4700::1111]/cdn-cgi/trace` |

**Is it CGNAT?** This could not be settled.

- The proper test is to compare the router's WAN address with the public address, and the WAN address could not be read without logging into the router.
- A private second hop fits three cases: double NAT (an ISP gateway in front of the home router), carrier NAT, or an ISP that just numbers its internal routers privately.
- A public echo address does not rule out CGNAT, because the echo always shows the carrier's public address.
- **To settle it,** read the WAN IPv4 on the router's status page. If it equals the public IP, inbound IPv4 forwarding is possible. If it is private or in 100.64.0.0/10, it isn't.

**Static or dynamic?** Not verified. A residential line with no static IP ordered should be assumed to be **dynamic**. The IPv6 prefix may change too (**unverified**).

**ISP terms.** The ISP was not identified.

- The gateway uses the default address of Xfinity gateways, but that is a hint, not proof.
- If it is Xfinity, the AUP prohibits running "dedicated, stand-alone equipment or servers from the Premises that provide network content", with examples including "web hosting". It makes an exception "for your personal and non-commercial residential use", and the boundary is not defined. Source: https://www.xfinity.com/corporate/customers/policies/highspeedinternetaup (revised February 1, 2021)
- A small, invite-only, non-commercial viewer plausibly falls under the personal-use exception, but that is a **judgement, not a ruling**.
- Tunnel makes only outbound connections, so it doesn't look like a listening server from the ISP's side. It doesn't change what the terms say, though.

## 2. Ways in

### (a) Proxied A/AAAA record to the home IP, with port forwarding and DDNS

**What it needs**

1. **Router port forward** from the WAN to the Mac. This is a router change, which this ticket did not make.
2. **A port Cloudflare will proxy.** HTTP: 80, 8080, 8880, 2052, 2082, 2086, 2095. HTTPS: 443, 2053, 2083, 2087, 2096, 8443. **3000 is not on the list**, so the compose port mapping or the forward has to translate to it (e.g. WAN 443 to Mac 3000). Ports outside the list need Spectrum, and "Spectrum for all TCP and UDP ports is only available on the Enterprise plan." Source: https://developers.cloudflare.com/fundamentals/reference/network-ports/
3. **TLS at the origin.** Cloudflare "strongly recommends using Full or Full (strict) modes". Flexible sends Cloudflare-to-origin traffic as plain HTTP over the internet. For Full (strict), the origin certificate "can be issued by a public CA like Let's Encrypt or by Cloudflare Origin CA". The Express app speaks plain HTTP, so a TLS terminator (a reverse proxy container) would have to be added. Source: https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/
4. **DDNS.** If the ISP changes the IP, you "need an automated solution to dynamically update your DNS records in Cloudflare". The options are a script that calls the DNS records API, or `ddclient`, "a third-party Perl client". Source: https://developers.cloudflare.com/dns/manage-dns-records/how-to/managing-dynamic-ip-addresses/
   - The script would need a Cloudflare API token stored on the Mac.
   - Between the IP changing and the record being updated, the site is down.
5. **IPv6 instead of IPv4 (if IPv4 turns out to be CGNAT or double NAT).**
   - A proxied AAAA record pointing at the Mac's stable IPv6 address would avoid NAT altogether. The router's IPv6 firewall would need an inbound allow rule, which is again a router change.
   - Cloudflare's IPv6 page says that when an origin has both, "Cloudflare will prefer the IPv4 address". It does not say outright that an AAAA-only origin serves IPv4 visitors. Source: https://developers.cloudflare.com/network/ipv6-compatibility/
   - Cloudflare is widely understood to proxy IPv4 visitors to IPv6-only origins, but **this is unverified** against a primary source.

**Security**

- A port is open on the home router, and anyone who finds the home IP can hit it directly, skipping Cloudflare and Access.
- **Allowlist Cloudflare's ranges.** Cloudflare says to "block all traffic that does not come from Cloudflare IP addresses". The list is at https://www.cloudflare.com/ips. "Cloudflare's IP ranges do not change frequently. When they do change, they are added to our list of IP ranges before being put into production." Source: https://developers.cloudflare.com/fundamentals/concepts/cloudflare-ip-addresses/
  - The router or the Mac would have to enforce this.
  - With Docker Desktop's port publishing, macOS's own firewall is not a clean way to filter by source (**unverified**). An allowlisting reverse proxy is more practical.
- **Authenticated Origin Pulls** (mTLS from Cloudflare to the origin) is available on **Free**. It needs Full or Full (strict) mode. Source: https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/
  - **Global AOP** "uses a Cloudflare-provided certificate shared across all accounts" and "only proves a request came from the Cloudflare network". Another Cloudflare customer could point their own zone at the home IP and pass the check.
  - **Zone-level or per-hostname AOP** with your own certificate closes that gap.
- **Access JWT validation in the app** (from #41) is still needed as the final check either way.

**Verdict.** This is the most work and the most exposure, and it may not even be possible over IPv4 on this line.

### (b) Cloudflare Tunnel (`cloudflared`)

**How it works**

- "`cloudflared` initiates an outbound connection through your firewall from the origin to the Cloudflare global network." You can "block all inbound traffic". Source: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
- Each tunnel keeps "four long-lived connections to two Cloudflare data centers". Source: https://developers.cloudflare.com/tunnel/
- Outbound traffic goes to `region1.v2.argotunnel.com` and `region2.v2.argotunnel.com` on **port 7844**, TCP/UDP (`http2`/`quic`). Port 443 is optional, for updates and Access JWT validation. A normal home router allows this without any change. Source: https://developers.cloudflare.com/tunnel/configuration/
- **Works behind CGNAT, double NAT, or a changing IP.** No public IP or DNS updater is needed, because the connection is outbound (same source).

**Cost**

- "any organization can use the secure, outbound-only connection feature of the product at no cost." Source: https://blog.cloudflare.com/tunnel-for-everyone/ (2021-04-15)
- The docs say Tunnel is "Available on all plans" (https://developers.cloudflare.com/tunnel/). The Zero Trust plans page lists "Application Connector Software: Included" on Free (https://www.cloudflare.com/plans/sase-zero-trust.md).
- No current Cloudflare docs page states the $0 price in so many words. It rests on the 2021 blog post (**treat as likely, not verified against a current pricing page**).
- "Tunnels for Platforms" is a separate paid product. Every account gets 1,000 tunnels at no cost before it applies (search-result summary of https://developers.cloudflare.com/tunnel/features/tunnels-for-platforms/, **not read directly**).

**Setup** (remotely managed). Source: https://developers.cloudflare.com/tunnel/get-started/

1. In the dashboard, go to Networking > Tunnels > Create Tunnel. Run the install command it shows.
2. Add a route: Published application, hostname, and Service URL.
3. "Cloudflare automatically creates a DNS record pointing the hostname to your tunnel subdomain", a CNAME to `<UUID>.cfargotunnel.com`. Source: https://developers.cloudflare.com/tunnel/concepts/routing/
4. "The cfargotunnel.com subdomain only proxies traffic for DNS records in the same Cloudflare account." Someone who learns the UUID cannot reuse the tunnel from another account. Source: same page.

**Running it unattended: two options**

- **As a compose service.** The run command is `docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TUNNEL_TOKEN>` (https://developers.cloudflare.com/tunnel/get-started/).
  - Added to `docker-compose.yml` with `restart: unless-stopped`, the Service URL would be `http://api:3000`. Compose containers "can reach each other using the service name directly" (https://docs.docker.com/compose/how-tos/networking/).
  - `sbuddy.sh deploy/stop/status` would then manage it with the rest of the stack, and the token goes in `.env`.
  - It shares Docker Desktop's lifetime (see §3).
- **As a launchd service.** `sudo cloudflared service install` installs a **launch daemon** that "start[s] whenever your system boots". Without sudo it is a launch agent that starts at login. Logs go to `/Library/Logs/com.cloudflare.cloudflared.{out,err}.log`. Source: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/macos/
  - The Service URL would be `http://localhost:3000`.
  - The tunnel comes up at boot, but the API behind it still waits for Docker. Visitors would then get an origin error instead of a tunnel error, so this gains little.

**Security**

- No inbound port is open at home. The compose file already publishes the API on `0.0.0.0:3000` for the LAN, and that stays LAN-only.
- Access is set up as in #41, a Self-hosted app on the tunnel hostname.
- The tunnel can enforce Access itself. The `access: { required: true, teamName, audTag }` origin parameter "Requires `cloudflared` to validate the Cloudflare Access JWT prior to proxying traffic to your origin." Source: https://developers.cloudflare.com/tunnel/reference/origin-parameters/
  - With that set, a request without a valid Access token never reaches Express.
  - App-side JWT validation (from #41) is still worth keeping as defence in depth, and it supplies `email`.
- AOP doesn't apply. It is "incompatible with Cloudflare Tunnel, because Tunnel has no inbound listener". Source: https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/
- IP allowlisting is not needed either, because nothing listens publicly.

**Verdict.** Clearly the better way in from the Mac.

### (c) Other options

- **Quick Tunnels** (`try.cloudflare.com`). A random hostname with no account. Cloudflare says these are "for testing and development, not for deploying a production website" (search-result summary of https://blog.cloudflare.com/a-free-argo-tunnel-for-your-next-project/, **not read directly**). It also can't use our domain or Access, so it is not a fit.
- **Hybrid.** Host the viewer on Fly + Neon (#45) and keep the Mac as the pipeline and backup machine, pushing data to Neon. That is the data-flow ticket's decision, noted here only because it removes the home-uptime problem.
- **Third-party tunnels** (Tailscale Funnel, ngrok, and others) were **not researched**. They would not put Cloudflare Access in front unless chained behind Cloudflare, which adds a hop for no gain.

## 3. Uptime on the Mac

| Event | Effect with Tunnel | Effect with port forwarding | Source |
|---|---|---|---|
| Mac sleeps | Not expected: `sleep 0` on a desktop | Same | `pmset -g` |
| Power cut | The Mac boots by itself (`autorestart 1`). After that, see "reboot". | Same, and the IP may also change | `pmset -g` |
| Reboot (e.g. a macOS update) | Docker Desktop starts only "when you sign in to your machine" (setting off by default), so compose, including a compose `cloudflared`, stays down until someone signs in, unless auto-login is on. While `cloudflared` is down, visitors see **error 1033**: Cloudflare "cannot find a healthy `cloudflared` instance". | Origin unreachable (5xx error from Cloudflare) | https://docs.docker.com/desktop/settings-and-maintenance/settings/, https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1033/ |
| Home IP changes | No effect | Down until DDNS updates the record | https://developers.cloudflare.com/dns/manage-dns-records/how-to/managing-dynamic-ip-addresses/ |
| ISP or router outage | Down | Down | — |
| Cloudflare data center or connection loss | The other tunnel connections take over: "If any connection, server, or data center goes offline, your resources remain available." Up to 25 replicas per tunnel (needs a second machine). | n/a | https://developers.cloudflare.com/tunnel/configuration/ |

**For unattended running:**

- **Done already:** sleep is off and restart after power loss is on.
- **Still to do:**
  - Enable "Start Docker Desktop when you sign in". Whether macOS auto-login is on was **not checked**, and FileVault, if on, blocks auto-login (**unverified**).
  - Run `cloudflared` in compose.
  - Think about when macOS installs updates.

**Measured uptime of this Mac:** unknown. Nothing here records how often it reboots or loses power.

## 4. Data flow and backups

- **Data flow.** Postgres, `crawled_data/`, and the figures are already on the Mac next to the vision and import pipeline. Nothing moves:
  - no `pg_dump`/restore to a cloud database,
  - no question of how gitignored figures reach a remote build (#45 §6),
  - no Postgres version change (stays on 15).
- **Backups.** `sbuddy.sh backup`, the pre-deploy backups and the daily launchd job (`schedule-backups`) keep working unchanged. Compare #45, where Neon Free keeps only 6 hours of history and a new nightly `pg_dump` job is needed.
- **Redis.** It can stay as it is. #45 found nothing calls it.

## Side-by-side: Mac via Tunnel vs Fly.io + Neon Free

| | Mac + Cloudflare Tunnel | Fly.io + Neon Free (#45) |
|---|---|---|
| Monthly cost | $0 (Tunnel free, per the 2021 Cloudflare post), plus home electricity | ~$0 inside Fly's $5 allowance. Card on file, and the whole month is billed if usage passes $5. |
| Domain and Access | Same: domain ~$11–14/yr, Access Free (#41) | Same |
| Uptime | Tied to the house: power, ISP, macOS reboots. Docker needs a sign-in after a reboot. Single machine. | Data-center hosting. Cold start ~2 s (Fly stopped), Neon wake a few hundred ms. |
| Reachability on this network | Works regardless of CGNAT or a dynamic IP | Not affected |
| Origin bypass | None: no inbound port, and `cloudflared` can require the Access JWT | `*.fly.dev` can't be turned off. App-side JWT validation is **required**. |
| Migration effort | Small: one compose service, a token in `.env`, a dashboard tunnel and an Access app | Medium: `fly launch`/`fly.toml`, Neon project, dump and restore, `DATABASE_URL`/SSL, deploy from the Mac to include figures |
| Data flow | Pipeline and DB on the same machine, nothing to sync | The pipeline on the Mac has to push to Neon. The sync method is still open. |
| Backups | `sbuddy.sh backup` and the daily launchd job unchanged | Neon Free history is 6 h. A new scheduled `pg_dump` is needed. |
| Postgres version | 15, unchanged | Neon 14–17. Use client tools from the target version. |
| Exposure of home network | Outbound tunnel only | None |
| ISP terms | Possibly in tension with a residential AUP (ISP unconfirmed) | n/a |
| Performance | Home upload bandwidth and Mac CPU (not measured). Cloudflare caches the PNG/SVG figures by default (#41 §3). | Shared 512 MB VM, egress $0.02/GB |

## Recommendation for this stack

1. **If the Mac route is chosen, use Cloudflare Tunnel, not port forwarding.** Run `cloudflare/cloudflared` as a fourth service in `docker-compose.yml` (`restart: unless-stopped`, `TUNNEL_TOKEN` from `.env`, route to `http://api:3000`), so `sbuddy.sh` manages it with the rest of the stack.
   - Protect the hostname with the #41 Access app.
   - Set the tunnel's `access.required` with the team name and AUD tag.
   - Keep the app-side JWT check.
   - No router change, no DDNS, and the CGNAT question becomes irrelevant.
2. **Before relying on it,** make the Mac recover from a reboot unattended:
   - turn on "Start Docker Desktop when you sign in",
   - decide on auto-login (FileVault trade-off),
   - accept that a home power or ISP outage takes the site down.
   - Optionally add a Cloudflare notification for the tunnel going down. Its availability on Free is **not checked**.
3. **Choosing between the two.**
   - **The Mac route** suits a small invite-only viewer where occasional downtime is acceptable. It is cheapest in effort and keeps data and backups as they are.
   - **Fly.io + Neon** is better if the viewer must stay up when the house doesn't, or if serving from home is unwelcome under the ISP's terms.
   - **Moving later is cheap.** The domain, Access app and JWT middleware carry over unchanged, so starting on the Mac and moving to Fly costs little.
4. **Don't use option (a)** unless Tunnel becomes unavailable. If it is ever used, it needs the router WAN check, a TLS terminator, Cloudflare-IP allowlisting, zone-level AOP with your own certificate, and DDNS.

## Not verified

- **CGNAT or double NAT:** the router's WAN address could not be read. Check the router status page.
- **Whether the public IPv4 or IPv6 prefix changes:** assumed dynamic.
- **Which ISP this is,** and how its terms apply. The Xfinity AUP is quoted only because the gateway address matches Xfinity's default.
- **Tunnel's $0 price on a current Cloudflare pricing page.** It rests on the 2021 blog post, "Available on all plans" and "Application Connector Software: Included".
- **Tunnels for Platforms and Quick Tunnels wording:** taken from search summaries, not read directly.
- **Proxied AAAA-only origin serving IPv4 visitors:** not stated on the Cloudflare page read.
- **On the Mac:** macOS auto-login and FileVault state, and the real reboot and power-loss frequency.
- **Home upload bandwidth.**
- **Whether Docker Desktop's published ports can be cleanly filtered by source IP** with the macOS firewall.
- **Cloudflare tunnel-health notifications on the Free plan.**
