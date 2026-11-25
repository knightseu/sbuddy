# Sbuddy Backend

AI-Powered Problem Recognition & Study System

## Features

🔍 **OCR Processing** - Convert photos to text using Surya OCR
🧠 **AI Problem Matching** - Identify problems using GPT-4
📚 **Problem Repository** - Organized database of problems by exam/subject
🔄 **Spaced Repetition** - Optimal review scheduling with SM-2 algorithm
🎮 **Gamification** - Points, levels, streaks, and achievements
💳 **Stripe Integration** - Subscription management
🏢 **Multi-tenancy** - Organization-level data isolation

## Quick Start

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

4. **Test the API**
   ```bash
   curl http://localhost:3000/api/v1/health
   ```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/profile` - Get user profile

### OCR & Problem Recognition
- `POST /api/v1/ocr/process` - Upload image for OCR processing
- `POST /api/v1/ocr/process-buffer` - Process base64 image data

### Problems
- `GET /api/v1/problems/search` - Search problems
- `POST /api/v1/problems` - Create new problem
- `POST /api/v1/problems/:id/answer` - Submit problem answer

### Study System
- `GET /api/v1/study/due-cards` - Get problems due for review
- `GET /api/v1/study/statistics` - User study statistics

### Gamification
- `GET /api/v1/gamification/score` - User score and level
- `GET /api/v1/gamification/leaderboard` - Top users leaderboard

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Mobile Apps   │    │    Web Client    │    │  Admin Panel    │
│  (iOS/Android)  │    │   (React/Vue)    │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    API Gateway/LB       │
                    │   (Express.js/Node)     │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                       │                        │
┌───────▼────────┐    ┌────────▼────────┐    ┌─────────▼────────┐
│  OCR Service   │    │ Problem Matcher │    │ Spaced Repetition│
│   (Surya)      │    │   (OpenAI)      │    │   (SM-2 Algo)    │
└────────────────┘    └─────────────────┘    └──────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Database Layer      │
                    │  PostgreSQL + Redis     │
                    └─────────────────────────┘
```

## Tech Stack

- **Backend**: Node.js + TypeScript + Express
- **Database**: PostgreSQL + Redis
- **OCR**: Surya OCR Service
- **AI**: OpenAI GPT-4
- **Payments**: Stripe
- **Auth**: JWT tokens

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test

# Build for production
npm run build

# Start production server
npm start

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Database Setup

The application automatically creates database tables on startup. Ensure PostgreSQL and Redis are running and accessible via the connection strings in your `.env` file.

## Environment Variables

Copy `.env.example` to `.env` and fill it in. It documents every variable; the server refuses to start if a required one is missing, so placeholder values are provided for external services (Stripe, OpenAI, OAuth, SMTP) that the test viewer doesn't use.

## Running as a Long-Lived Service

The full stack (Postgres, Redis, API, cloudflared) runs in Docker with `restart: unless-stopped` on the Mac mini. The viewer is public at **https://sbuddy.xuanlin.us** through Cloudflare Tunnel; see [docs/CLOUDFLARE_TUNNEL.md](docs/CLOUDFLARE_TUNNEL.md) and [ADR 0001](docs/adr/0001-public-viewer-via-cloudflare-tunnel-from-mac-mini.md). The full API is reachable only from the Mac itself at `http://localhost:3000`. Everything is driven by `scripts/sbuddy.sh`:

```bash
scripts/sbuddy.sh deploy             # pull (fast-forward), build, restart, health-check; auto-rollback on failure
scripts/sbuddy.sh deploy --no-pull   # deploy the working tree as-is
scripts/sbuddy.sh status             # containers, health, deployed git revision, URLs
scripts/sbuddy.sh logs [service]     # follow logs (default: api; also postgres, redis)
scripts/sbuddy.sh stop | start | restart
scripts/sbuddy.sh rollback           # return the API to the previously deployed image
scripts/sbuddy.sh seed               # import crawled_data/ (only into an empty database)
```

`npm run deploy` is a shortcut for `scripts/sbuddy.sh deploy`.

**First-time setup**

1. `cp .env.example .env` and set passwords and secrets (`openssl rand -hex 32`). Set `CLOUDFLARE_TUNNEL_TOKEN` (tunnel `sbuddy-mac`, see the tunnel doc).
2. `scripts/sbuddy.sh deploy --no-pull`. On an empty database this also imports the AMC tests. It starts cloudflared once the API is healthy.
3. Open `https://sbuddy.xuanlin.us/viewer/` from any device, or `http://localhost:3000/viewer/index.html` on the Mac (`status` prints both).

**Updating later**: commit or merge changes, then run `scripts/sbuddy.sh deploy`. It refuses to run with uncommitted changes, pulls with `--ff-only`, keeps the previous image as `sbuddy-api:previous`, and rolls back automatically if the new API fails its health check.

**Notes**

- Configuration comes only from `.env`. The script runs compose in a clean environment, so variables exported in your shell (e.g. `POSTGRES_USER`) are ignored.
- Nothing listens on the network. The API, Postgres and Redis all publish on `127.0.0.1` only (`API_BIND_IP` sets the API's address). The public site comes in through the tunnel, which only connects outbound, and its ingress rules expose just the viewer. Don't port-forward anything.
- **No LAN access to the full API (since 2026-11-25).** Other devices at home use the public URL, which only serves the viewer. Binding `0.0.0.0` would also listen on the Mac's public IPv6 address. A LAN IP like `10.0.0.74` stops the API from starting when DHCP changes the address, and that takes the public site down too. To get LAN access back, set `API_BIND_IP` to the Mac's LAN IP *and* reserve it in the router.
- To survive reboots, enable Docker Desktop > Settings > General > *Start Docker Desktop when you sign in*, and keep the machine from sleeping. Docker Desktop still waits for someone to sign in, so the public site stays down after a reboot until then (#49).
- `npm run dev` and the stack both use port 3000. Stop the stack (`scripts/sbuddy.sh stop`) before running the dev server.
- The importer is not idempotent (re-running duplicates solutions), so `seed` only runs on an empty database.

### Database Backups

Users, study plans (including guest plans), progress, SRS cards and scores exist only in the Postgres volume. Problem data can be rebuilt from `crawled_data/`; the rest cannot, so back it up.

```bash
scripts/sbuddy.sh backup              # pg_dump now
scripts/sbuddy.sh backups             # list backups, last-backup age, schedule
scripts/sbuddy.sh verify [file]       # restore into a scratch DB and compare row counts with live (default: newest)
scripts/sbuddy.sh restore <file>      # replace the live DB (asks for confirmation; takes a pre-restore backup first)
scripts/sbuddy.sh schedule-backups    # daily launchd job at BACKUP_TIME (default 03:00); unschedule-backups removes it
```

- **Format and location**: `pg_dump -Fc` files in `BACKUP_DIR` (default `~/sbuddy-backups`, mode 700), outside the Docker volume, so `docker compose down -v` does not take them with it. Names carry kind, time and git revision: `sbuddy-daily-20261122-030000-3ecb72a.dump`.
- **Off-machine copy**: set `BACKUP_COPY_DIR` (e.g. a Dropbox folder) and every backup is copied there too. Dumps include password hashes and emails, so pick a private location. macOS may let the scheduled job write to a cloud-synced folder but not list it. The log then warns that the copy folder is not pruned; prune it by hand, or give `/bin/bash` Full Disk Access.
- **Retention**: `daily` keeps the 7 newest plus one per week for the 4 weeks before that. `pre-deploy` and `pre-restore` keep the 5 newest. `manual` backups are never pruned.
- **Before upgrades**: `deploy` takes a `pre-deploy` backup before the new API starts, and aborts if the backup fails.
- **Monitoring**: a failed scheduled run raises a macOS notification and is logged to `BACKUP_DIR/backup.log`. `status` and `backups` warn when the newest backup is older than 26 hours. The job only runs while the Mac is awake with Docker running; a run missed during sleep fires on wake.
- **Schema**: a dump contains its own schema. After a restore the API starts and creates any tables the dump predates (`CREATE TABLE IF NOT EXISTS`). If `npm run migrate` has been applied since the dump was taken, re-run it after restoring.
- **Restore drill**: run `scripts/sbuddy.sh verify` now and then. It proves the newest dump restores, without touching live data.

## AMC 10 Problem Scraping

Sbuddy includes a powerful web scraper for AMC 10 problems from Art of Problem Solving:

```bash
# Quick demo (no database required)
npm run scrape-amc:demo

# Import problems to database
npm run scrape-amc -- --year 2024 --test A --count 10
```

See [AMC Scraping Guide](docs/AMC_SCRAPING_GUIDE.md) for complete documentation.

## License

MIT