# Cloud hosts for the Sbuddy Docker image with Postgres under $10/month

Research for issue #45, a child of map #40. Checked 2026-11-24 against each provider's own docs and pricing pages. It builds on the Cloudflare Access findings from #41 (`docs/research/cloudflare-access-registrar.md` on branch `research/cloudflare-access-registrar`).

**Scope.** The question is which hosts can run the existing `Dockerfile` (Node 22 Express, port 3000, health check `/api/v1/health`) mostly as-is, with Postgres 15+ (17 MB today), for under about $10/month, behind a proxied Cloudflare record and Cloudflare Access. Cold starts are acceptable.

**Short answer.**

- **Cheapest overall: Fly.io app plus Neon Free Postgres, about $0/month.** A Fly Free plan with a card on file gets $5 of usage a month. One small Machine fits inside that even if it never stops. Neon Free is permanent, sleeps after 5 minutes, and wakes in a few hundred milliseconds.
- **All on one bill: Fly.io app plus Fly Managed Postgres Developer, about $4–8/month.** It stays at $0 only while total usage is under $5. Once usage passes $5, the whole month is billed from the first cent.
- **Render works but has drawbacks.** A free Render web service wakes in about a minute. Render's own free Postgres is deleted 30 days after creation plus a 14-day grace period. Render Basic Postgres ($6) plus a free web service fits the budget.
- **Out of budget or out of fit.** Koyeb now needs the $29 Pro plan for new sign-ups. Railway's Free plan has no custom domains, so it needs Hobby at $5. Supabase Free pauses after a week and has no backups. Cloud Run's only cheap custom-domain path is a Preview feature that Google says is not production-ready.
- **Redis: drop it.** No code calls it. `enhancedAuthService.ts` imports `redis` and never uses it, and `initializeDatabase()` already carries on when Redis is unavailable.
- **Validate the Access JWT on every host.** Even on hosts whose default URL can be switched off, the origin can still be reached without going through Cloudflare (see §2).

## Comparison table

Costs are for this app: one web instance of 256–512 MB, a 17 MB database and light traffic. Where a figure is my arithmetic from the listed rates and not a quoted price, it is marked *(est.)*.

| Host | Cheapest fitting setup | Monthly cost | Free tier and how long it lasts | Sleep / cold start | Default URL off? | Cloudflare proxy notes | Postgres pairing |
|---|---|---|---|---|---|---|---|
| **Fly.io** | `shared-cpu-1x` 512 MB, `auto_stop_machines = "stop"` | $0 while total usage is under $5 *(est.)*. Always-on 512 MB is $3.69. | Free plan "doesn't expire". $5 of usage a month with a card. | Stop: about 2 s or more. Suspend: a few hundred ms. | No documented switch | TXT ownership record, then HTTP-01 through the proxy. Set SSL to Full. | Own MPG Developer $4 (5 GB), or Neon Free |
| **Render** | Free web service | $0 web. With Render Postgres Basic-256mb: $6 + $0.30/GB. | Free web: 750 h/month, no expiry stated. Free Postgres expires after 30 days (+14-day grace). | Spins down after 15 min idle. About 1 min to spin up. | **Yes**, once a custom domain exists | Record must be DNS-only until the cert issues, then can be proxied. Set SSL to Full. | Own Basic $6 (PITR 3 days on Hobby), or Neon Free |
| **Railway** | Hobby plan | $5, including $5 of usage. Overage is billed on top. | Free plan ($1/month) has **no custom domains**, so it doesn't fit. Trial is 30 days. | Serverless sleeps 5–10 min after the last outbound traffic. The first request may get a 502. | Domain is opt-in ("Generate Domain") | SSL **Full, not Full (Strict)**. Only first-level subdomains can be proxied on Universal SSL. | Template Postgres on a volume (≈$0.15/GB), or Neon Free |
| **Koyeb** | Pro plan | $29 + usage | New users "must subscribe to one of our paid plans". The Free Instance is for older accounts. | Free Instance scales to zero after 1 h | Not checked (over budget) | Not checked | Own Postgres from $29.76/month, free 5 h |
| **Google Cloud Run** | Request-based billing, min instances 0 | $0 inside the free tier *(est.)*. Images over 0.5 GB cost about $0.10/GB-month. | Always-free monthly tier: 180,000 vCPU-s, 360,000 GiB-s, 2 M requests, 1 GB egress | Scales to zero. Cold start time not documented here. | **Yes** (`--no-default-url`, GA) | Custom domain needs a Preview domain mapping ("not production-ready") or a paid load balancer | No free Cloud SQL. Neon Free. |
| **Cloudflare Containers** | Workers Paid + `lite`/`basic` instance | $5 + usage, about $5–7 *(est.)* | No free option; needs Workers Paid | Sleeps on inactivity timeout. "Often in the 1-3 second range". | **Yes** (`workers_dev = false`; preview URLs are separate) | Same account, so no Orange-to-Orange issue | Neon Free (outbound TCP not verified) |

Database add-ons, with each pricing page as the source:

| Database | Free tier | Cheapest paid | Backups / PITR on that tier | Lasts |
|---|---|---|---|---|
| **Neon** | 1 GB per project, 100 CU-hours per project per month, 5 GB egress, scales to zero after 5 min | Launch: $0.106/CU-hour + $0.35/GB-month, no minimum | Free: 6-hour history window (1 GB limit). "Instant restore" isn't on Free. | "permanent (not a trial)" |
| **Supabase** | 500 MB, 2 active projects, pauses after 1 week of inactivity | Pro from $25 (over budget) | Free: automatic backups "Not included" | Permanent, but pauses |
| **Fly MPG** | Developer plan counts against the Free plan's $5 | Developer $4, 256 MB, storage included up to 5 GB | Backups included. PITR restore exists, but retention isn't documented. | — |
| **Render Postgres** | Free: 1 GB, no backups | Basic-256mb $6 + $0.30/GB storage | PITR 3 days (Hobby). Logical exports kept 7 days. | Free expires after 30 days |

## 1. Cost, free tier, cold starts

### Fly.io

- **Free plan.** "You get $1 of credit with no credit card, and $5 of usage every month once you add a card." The $5 covers Machines, volumes, data transfer and the $4 Managed Postgres Developer plan. Source: https://docs.fly.io/about/pricing
- **It doesn't expire, but going over is expensive.** The Free plan "doesn't expire". The no-card $1 is one-time and lasts 7 days. Fly emails you when $1 or less of the month's $5 is left. When the $5 runs out, the org moves to Pay As You Go and the whole month is billed "at standard rates from the first cent, not just the usage above $5". Limits: up to 3 Machines, 5 GB volumes, 1 MPG cluster on the Developer plan, no other members. Each card can be on only one org's Free plan. Source: https://docs.fly.io/about/free-plan
- **Machine prices** (30 days always-on, `iad`/`ewr`): `shared-cpu-1x` 256 MB $2.19, 512 MB $3.69, 1 GB $6.70. Stopped Machines cost $0.15/GB-month of rootfs. Egress is $0.02/GB in North America and Europe. A shared IPv4 and the first 10 certificates are free. Source: https://docs.fly.io/about/pricing
- **Managed Postgres.** Developer plan: "$4.00/month", shared-1x CPU, 256 MB, storage included (1 GB initially, 5 GB cap), no connection pooling. The next plan up is Basic at $38. Postgres 16 or 17 only, with no in-place major upgrades. Source: https://docs.fly.io/mpg
- **Sleep.** `auto_stop_machines = "stop"` or `"suspend"`, `auto_start_machines = true`, `min_machines_running = 0`. This is the default for `fly launch`. Resuming from suspend takes a few hundred ms. A cold start from stopped takes about 2 s or more. Source: https://docs.fly.io/launch/autostop-autostart
- **Cost estimate for this app** *(est.)*:
  - Fly app plus Neon: even a 512 MB Machine that never stops ($3.69) stays under $5, so the bill is $0.
  - Fly app plus MPG Developer: $4 + $3.69 = $7.69 always-on, which is over $5 and so billed in full. With auto-stop, the Machine might cost well under $1, putting the total near $4.5, which is $0 but close to the edge.

### Render

- **Free web service.** It spins down after 15 minutes without inbound traffic and takes "about one minute" to spin up. It gets 750 free instance hours per workspace per month and is suspended once they run out. Custom domains and managed TLS are allowed. There are no persistent disks, no shell, a single instance, and Render "may restart the service at any time". Source: https://render.com/docs/free
- **Free Postgres.** 1 GB. It "expire[s] 30 days after creation", then has a 14-day grace period before deletion. One per workspace, with no backups. Source: https://render.com/docs/free
- **Paid prices.** The Hobby workspace is $0/month plus compute and includes 5 GB of bandwidth, then $0.15/GB. A Starter web service is $7/month (512 MB). Postgres Basic-256mb is $6/month, with storage at $0.30/GB. Source: https://render.com/pricing
- **Cost estimate** *(est.)*: free web plus Basic-256mb with 1 GB of storage comes to about $6.30. Starter web plus Basic Postgres comes to about $13.30, which is over budget.

### Railway

- **Plans.** Free is $0 with $1 of usage a month: 1 project, 3 services, 0.5 GB RAM per service and a 0.5 GB volume. Services sleep when idle. **No custom domains.** Hobby is $5/month including $5 of usage, with 2 custom domains per service. Source: https://docs.railway.com/pricing/free-plan and https://railway.com/pricing
- **Rates.** RAM about $10/GB-month, CPU about $20/vCPU-month (both billed per second), volumes about $0.15/GB-month, egress $0.05/GB. Source: https://railway.com/pricing
- **Sleep.** A service is "considered inactive after 5 minutes" without outbound packets, so it sleeps after about 5–10 minutes. The waking request "may" return a 502. Sleep is triggered by outbound inactivity, so an open DB connection keeps the service awake. Source: https://docs.railway.com/reference/app-sleeping and https://docs.railway.com/pricing/free-plan
- **Cost estimate** *(est.)*: on Hobby, the app (about 0.25 GB always-on, about $2.50) plus template Postgres (similar) comes to roughly $5–6. That is about the $5 floor, plus a little if RAM runs higher. Actual RAM use isn't measured.

### Koyeb

- **Plans.** Koyeb agreed to join Mistral AI (announced 2026-02-17). "The Starter plan will soon be removed and new users will instead need to subscribe to the Pro, Scale, or Enterprise plan… You'll need a valid payment method and must subscribe to one of our paid plans to get started." Source: https://www.koyeb.com/blog/koyeb-is-joining-mistral-ai-to-build-the-future-of-ai-infrastructure
- **Pro price.** $29/month including $10 of compute. Postgres Small is $29.76/month. Source: https://www.koyeb.com/pricing
- **Free Instance.** It still exists in the docs (512 MB, 0.1 vCPU, scales to zero after 1 h, Frankfurt or Washington D.C. only, one per org, last updated 2026-05-27), but new sign-ups can't reach it. Source: https://www.koyeb.com/docs/reference/instances
- **Verdict.** Over budget. The rest of the ticket's questions were not researched for Koyeb.

### Google Cloud Run

- **Free tier (request-based billing).** 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 M requests a month, plus 1 GB of egress from North America. This is the ongoing Free Tier, separate from the $300 / 90-day trial. Source: https://docs.cloud.google.com/free/docs/free-cloud-features
- **Rates beyond the free tier** (us-central1, request-based): active CPU $0.000024/vCPU-s, memory $0.0000025/GiB-s, requests $0.40 per million. Source: https://cloud.google.com/run/pricing
- **Image storage.** Artifact Registry gives 0.5 GB free, then $0.000136986/GiB-hour (about $0.10/GiB-month). Source: https://cloud.google.com/artifact-registry/pricing
- **No free Postgres.** Cloud SQL has only a 30-day free trial instance, so Postgres must come from elsewhere (Neon). Source: https://docs.cloud.google.com/free/docs/free-cloud-features
- **Cold start.** The time for this image was not found in Google's docs. **Unverified.**

### Cloudflare Containers

- **Price.** Containers need Workers Paid ($5/month minimum). Each month includes 25 GiB-hours of memory, 375 vCPU-minutes and 200 GB-hours of disk. Beyond that: $0.0000025/GiB-s memory, $0.000020/vCPU-s CPU (active use only), $0.00000007/GB-s disk. Egress in North America and Europe is $0.025/GB after 1 TB. Sources: https://developers.cloudflare.com/containers/pricing/ and https://developers.cloudflare.com/workers/platform/pricing/
- **Instance types.** `lite` is 1/16 vCPU, 256 MiB, 2 GB. `basic` is 1/4 vCPU, 1 GiB, 4 GB. Source: https://developers.cloudflare.com/containers/pricing/
- **How it runs.** Requests reach the container through a Worker and a Durable Object. That is a small amount of new code (a Worker shim plus `wrangler.jsonc`), not a rewrite. An inactivity timeout stops the container. Cold starts "can often be in the 1-3 second range". Disk is ephemeral. Sources: https://developers.cloudflare.com/containers/ and https://developers.cloudflare.com/containers/faq/
- **Cost estimate** *(est.)*: `basic` running 2 h/day is about 60 GiB-h, giving roughly $0.30 of memory overage. `lite` running 24/7 is about $1.40. The total is about $5–7.

## 2. Default URL and the Access JWT

Turning off the default URL is defence in depth, not a substitute for checking the JWT. Each of these hosts routes by hostname at a shared edge. Someone who sends our custom hostname straight to the host's edge, without going through Cloudflare, would still reach the app. This is my inference from how these edges route; none of these docs addresses it. #41's advice stands: middleware should reject requests without a valid `Cf-Access-Jwt-Assertion`, and exempt only `/api/v1/health`.

| Host | Can the default URL be turned off? | Source |
|---|---|---|
| Fly.io | No documented setting. Community posts (not official) say it can't be disabled and suggest rejecting the `*.fly.dev` Host in middleware. | https://community.fly.io/t/is-it-possible-to-disable-the-fly-dev-subdomain-for-an-app/5863 (forum, unofficial) |
| Render | Yes: "If your service has at least one custom domain, you can disable the service's default `onrender.com` subdomain." It then returns 404. | https://render.com/docs/custom-domains |
| Railway | A `*.up.railway.app` domain is added only when you click "Generate Domain", and custom domains are added separately. Whether a custom domain works with no Railway domain at all was **not verified**. | https://docs.railway.com/networking/domains/working-with-domains |
| Cloud Run | Yes: `gcloud run services update SERVICE --no-default-url`. It breaks Google callers that use the default URL (Scheduler, Pub/Sub, uptime checks), and custom domains should be mapped first. | https://docs.cloud.google.com/run/docs/securing/ingress |
| Cloudflare Containers | Yes: `workers_dev = false` in the Wrangler file. Preview, version and deployment URLs are separate. Access can protect `workers.dev` and preview URLs. | https://developers.cloudflare.com/workers/configuration/routing/workers-dev/ |

## 3. Custom domain and TLS behind a proxied Cloudflare record

- **Fly.io.** With the orange cloud on, verify ownership with a `_fly-ownership` TXT record. After that, "Fly.io can issue certificates using the HTTP-01 challenge through Cloudflare's proxy". Use SSL mode Full or Full (Strict), because Flexible loops. If HTTP-01 gets blocked, import a Cloudflare Origin Certificate instead. Source: https://docs.fly.io/networking/custom-domain
- **Render.** Keep the record "DNS only" until the dashboard shows the certificate as issued, then switch it to Proxied. Use SSL mode Full and remove AAAA records, because Render doesn't support IPv6. Source: https://render.com/docs/configure-cloudflare-dns
  - Render's page mentions an "orange to orange setup" for wildcard domains, which suggests its edge is on Cloudflare. That is **not confirmed** by Render.
  - Under O2O, our zone's settings, including Access, run first (see #41). Whether Access works with a Render origin should be checked on the first deploy.
- **Railway.**
  - Add both the CNAME and the TXT record. Set SSL to **Full, not Full (Strict)** ("Strict mode will not work as intended").
  - Enable Universal SSL. A proxied hostname deeper than one subdomain level needs Advanced Certificate Manager. For proxied domains Railway "may not always be able to issue a certificate", but Cloudflare-to-Railway traffic uses the `*.up.railway.app` certificate.
  - Source: https://docs.railway.com/networking/domains/working-with-domains
- **Cloud Run.**
  - Free direct mapping is Preview: "not production-ready". It is limited to about 10 regions (including us-central1, us-east1, us-east4, us-west1). Third-party CDNs "might inadvertently intercept validation requests", and Cloudflare's "Always use https" must be off.
  - The production options are a global external Application Load Balancer or Firebase Hosting. Source: https://docs.cloud.google.com/run/docs/mapping-custom-domains
  - Pointing a proxied CNAME straight at `*.run.app` would need a Host-header override, and Cloudflare Origin Rules offer that only on Enterprise. Source: https://developers.cloudflare.com/rules/origin-rules/
  - The load balancer's monthly cost was not checked, but it is commonly well over this budget (**unverified**).
- **Cloudflare Containers.** The Worker is attached to a hostname in our own zone, so there is no Orange-to-Orange question. Access applies as for any proxied hostname (#41).

## 4. Redis: drop it

- **The code.** `src/models/database.ts` creates a Redis client and tries `redis.connect()` inside its own `try/catch`. On failure it logs "Redis connection failed (optional for development)" and carries on with Postgres.
- **The only importer.** `src/services/enhancedAuthService.ts` imports `redis` on line 3 but never calls it. No other file in `src` references it.
- **The change.** Leaving `REDIS_URL` unset in the cloud already works, at the cost of a warning at startup. Removing the client and the import is a two-file change.
- **Free Redis, if it is ever needed.**
  - Upstash Free: 500K commands/month, 256 MB, 1 database, 10 GB bandwidth. Source: https://upstash.com/pricing/redis
  - Render Free Key Value: in-memory only and lost on restart. Source: https://render.com/docs/free
- **Sessions.** `express-session` is used in `src/index.ts`, with no store configured, so sessions live in memory. They are lost when an instance stops or sleeps. With Access doing the login, that only matters if the viewer depends on server sessions. Not checked in depth.

## 5. Backups, PITR and loading the existing dump

**Backups on each option**

- **Neon Free.** A 6-hour history window (1 GB limit); "Instant restore" isn't on Free. Source: https://neon.com/pricing
- **Fly MPG.** "All plans include backups." `fly mpg restore <ID> --pitr-time <RFC3339>` or `--backup-id` restores into a new cluster (v2 clusters, flyctl v0.4.80+, changelog 2026-08-10). Neither page states the retention window (**unverified**). Sources: https://docs.fly.io/mpg and https://fly.io/changelog/managed-postgres-point-in-time-restore/
- **Render Postgres.** PITR covers 3 days on Hobby and 7 days on Pro, and restores into a new instance. Logical backups are kept 7 days. The Free plan has no recovery and no logical backups. Source: https://render.com/docs/postgresql-backups
- **Railway volumes.** Daily, weekly or monthly backups, kept 6, 27 and 89 days, at volume pricing. The docs don't say which plans include them. No PITR is described. Source: https://docs.railway.com/volumes/backups
- **Supabase Free.** No automatic backups. PITR is a $100/month add-on. Source: https://supabase.com/pricing

None of the free or cheap tiers gives more than a few days of history. Whichever is chosen, a scheduled `pg_dump` to somewhere we control (R2, or the Mac) should replace `sbuddy.sh backup`. That belongs to the data-move ticket.

**Restoring the LAN Postgres 15 dump.** Use client tools from the target's major version or newer. Neon says an older `pg_restore` refuses a newer server. Source: https://neon.com/docs/import/migrate-from-postgres

- **Neon.**
  - Dump with `pg_dump -Fc -v -d <src> -f dump`.
  - Restore with `pg_restore -v -O -d <neon-unpooled-url> dump`.
  - Use the **unpooled** connection string. Supports Postgres 14–17. Source: https://neon.com/docs/import/migrate-from-postgres
- **Fly MPG.**
  - Dump with `pg_dump --no-owner --no-acl -f dump.sql <src>`.
  - Restore with `fly mpg connect <CLUSTER_ID> -f dump.sql -- -q --single-transaction`.
  - A pg_dump 17+ run against a PG 16 cluster needs its `SET transaction_timeout` line removed. Other tools go through `fly mpg proxy`.
  - Source: https://docs.fly.io/mpg/import
- **Render.** Restore only into an empty database, using the external URL. Use `psql` for a plain dump and `pg_restore` for a directory dump. Versions 13–18 are offered. Sources: https://render.com/docs/postgresql-backups and https://render.com/docs/postgresql-creating-connecting
- **Supabase.** Use `pg_restore --no-owner --no-privileges --format=directory` through the **session pooler** on port 5432. Source: https://supabase.com/docs/guides/platform/migrating-to-supabase/postgres

## 6. Deploying, and what the image really contains

Measured from the local `sbuddy-api:latest` image (433 MB, `docker history`):

- **The image doesn't hold 450 MB of `crawled_data`.** `.dockerignore` already excludes `crawled_data/mathcounts/_*` (`_sources` 239 MB, `_work` 198 MB). The `COPY crawled_data` layer is **13.9 MB**, and the figures copied into `public/` add 7.8 MB.
- **The biggest avoidable layer is `chown -R nodejs:nodejs /app`, at 69.4 MB.** It rewrites every file copied before it. Using `COPY --chown=nodejs:nodejs` (and `mkdir`/`chown` only on `uploads`) would remove it.
- **The rest** is the base image plus `npm ci --omit=dev` (48.9 MB).
- **Git-based builds would ship without the figures.** The MATHCOUNTS Tests and figures are gitignored (`crawled_data/mathcounts/*` and `public/test-images/mathcounts/` in `.gitignore`). A build from GitHub would have the AMC JSON but none of those figures. These deploy paths include gitignored files:
  - **Fly:** `fly deploy` builds on a remote builder by default from the local directory. `--local-only` uses the Mac's Docker, and `--image` deploys a prebuilt image. Source: https://docs.fly.io/flyctl/deploy
  - **Railway:** `railway up` "Respects your `.gitignore`" unless `--no-gitignore` is passed. Source: https://docs.railway.com/cli/up
  - **Render:** can deploy a prebuilt registry image, but then "Services deployed from prebuilt images don't support auto-deploys". Source: https://render.com/docs/web-services
  - **Cloudflare Containers:** `wrangler deploy` with `image = "./Dockerfile"` builds from the local directory. Source: https://developers.cloudflare.com/containers/
  - **Cloud Run:** push an image built on the Mac to Artifact Registry and deploy it, rather than using `--source`. Not checked: whether `--source` also skips gitignored files.
- **GitHub Actions** only works once the figures (and the MATHCOUNTS JSON) come from somewhere other than git, for example R2 or a release artifact. That is the data-flow ticket's decision. Until then, deploy from the Mac.

## Recommendation for this stack

1. **Fly.io (`shared-cpu-1x` 512 MB, auto-stop) + Neon Free Postgres: about $0/month.**
   - Fits inside Fly's $5 monthly allowance even if the Machine never stops.
   - Neon Free is permanent and has the smallest cold start of the database options (a few hundred ms). Fly wakes in about 2 s.
   - The image runs as-is. Deploy from the Mac with `fly deploy` (local context, so the figures are included).
   - The `*.fly.dev` URL can't be turned off, so JWT validation in the app is required. It is needed anyway (§2).
   - Put Neon in the AWS region nearest Fly's (e.g. `iad`/us-east-1). Add a nightly `pg_dump`, because Neon Free keeps only 6 hours of history.
   - A card must be on file, and the bill turns into full Pay As You Go from the first cent if usage passes $5.
2. **Fly.io + Fly Managed Postgres Developer: about $4–8/month.**
   - One provider, a private network, and managed backups with PITR restore.
   - With auto-stop, the total sits just under $5, so $0. That gives no margin, though: any month over $5 bills the full amount, for example about $7.69 if the Machine runs always-on.
   - Choose this if a second vendor (Neon) is unwanted.

**Runner-up: Render free web + Render Basic-256mb Postgres, about $6.30/month.**

- Its strengths are the ones Fly lacks: the default URL can be switched off, and PITR covers 3 days.
- The free web service's ~1-minute spin-up after 15 idle minutes is the weakest cold start here. Pairing Render with Render's free Postgres isn't viable, because it is deleted after 30 days plus a 14-day grace period.

## Not verified

- **Fly.**
  - MPG backup and PITR retention window: not stated in Fly's docs.
  - Whether `*.fly.dev` can be disabled: only forum posts, which say it can't.
- **Railway.**
  - Whether a custom domain works with no `*.up.railway.app` domain generated.
  - Which plans include volume backups.
  - The ~$5–6/month estimate: depends on measured RAM.
- **Render.** Whether its edge is on Cloudflare, so that Orange-to-Orange applies, and whether Access then behaves normally.
- **Cloud Run.**
  - Cold start time for this image.
  - Whether Preview domain mapping issues a certificate behind a proxied record.
  - The external load balancer's monthly price.
- **Cloudflare Containers.**
  - Outbound TCP from a container to Neon.
  - Whether `lite` (256 MiB) has enough memory for the app.
- **All estimates marked *(est.)*.** Arithmetic from the published rates, not quoted prices. The app's real memory and active hours haven't been measured.
- **Koyeb.** Only cost was researched. Everything after that wasn't, because the plan is over budget.
