#!/usr/bin/env bash
# Manage the long-running Sbuddy stack (Postgres, Redis, API) via docker compose.
#
#   scripts/sbuddy.sh deploy [--no-pull]   pull, build, (re)start, health-check, auto-rollback
#   scripts/sbuddy.sh start | stop | restart
#   scripts/sbuddy.sh status               containers, health, deployed revision, LAN URL
#   scripts/sbuddy.sh logs [service]       follow logs (default: api)
#   scripts/sbuddy.sh rollback             return the API to the previously deployed image
#   scripts/sbuddy.sh seed                 import crawled_data/ into an EMPTY database
#
# Configuration comes from .env only: compose runs with a clean environment so
# variables exported in your shell (e.g. POSTGRES_USER) cannot override it.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT=sbuddy
API_IMAGE=sbuddy-api
HEALTH_TIMEOUT=90

cd "$ROOT"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

env_value() { # read KEY from .env (last occurrence), with default
  local v
  v=$(sed -n "s/^$1=//p" .env 2>/dev/null | tail -n 1)
  echo "${v:-$2}"
}

dc() {
  env -i HOME="$HOME" PATH="$PATH" \
    ${DOCKER_HOST:+DOCKER_HOST="$DOCKER_HOST"} \
    ${DOCKER_CONTEXT:+DOCKER_CONTEXT="$DOCKER_CONTEXT"} \
    ${GIT_SHA:+GIT_SHA="$GIT_SHA"} \
    docker compose -p "$PROJECT" --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" "$@"
}

port() { env_value PORT 3000; }

lan_ip() {
  local ip=""
  if command -v ipconfig >/dev/null 2>&1; then # macOS
    ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
  elif command -v hostname >/dev/null 2>&1; then # Linux
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  echo "${ip:-<this-machine-ip>}"
}

require_docker() {
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop and retry."
}

require_env_file() {
  [ -f .env ] || die ".env not found. Copy .env.example to .env and fill it in."
}

# Containers with our names that were created outside this compose project block `up`.
check_name_conflicts() {
  local name label
  for name in sbuddy-postgres sbuddy-redis sbuddy-api; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      label=$(docker container inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$name")
      if [ "$label" != "$PROJECT" ]; then
        die "container '$name' exists but is not managed by this stack. Keep it out of the way with:
    docker stop $name && docker rename $name $name-legacy"
      fi
    fi
  done
}

# Something other than Docker (e.g. `npm run dev`) holding the API port.
check_port_free() {
  local p holders
  p=$(port)
  command -v lsof >/dev/null 2>&1 || return 0
  # lsof exits 1 when nothing is listening; don't let pipefail abort the script
  holders=$({ lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null || true; } | awk 'NR>1 && $1 !~ /^com\.docke|^docker|^vpnkit/ {print $1" (pid "$2")"}' | sort -u)
  [ -z "$holders" ] || die "port $p is in use by: $holders
    Stop it first (a leftover 'npm run dev'?)."
}

wait_for_api() {
  local p deadline state
  p=$(port)
  deadline=$((SECONDS + HEALTH_TIMEOUT))
  log "Waiting for API health on http://localhost:$p/api/v1/health (up to ${HEALTH_TIMEOUT}s)"
  while [ $SECONDS -lt $deadline ]; do
    if curl -fsS "http://localhost:$p/api/v1/health" >/dev/null 2>&1; then
      log "API is healthy"
      return 0
    fi
    # `up` creates a fresh container, so any restart means it crashed on boot
    state=$(docker container inspect -f '{{.State.Status}} restarts={{.RestartCount}}' sbuddy-api 2>/dev/null || echo missing)
    case "$state" in
      exited*|dead*|missing|*restarts=[1-9]*) warn "API container state: $state"; return 1 ;;
    esac
    sleep 2
  done
  warn "API did not become healthy within ${HEALTH_TIMEOUT}s"
  return 1
}

db_test_count() {
  dc exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM tests"' 2>/dev/null | tr -d '[:space:]'
}

seed_if_empty() {
  local count
  count=$(db_test_count || true)
  if [ "$count" = "0" ]; then
    log "Database has no tests; importing crawled_data/"
    dc exec -T api node dist/scripts/importTestData.js crawled_data
  elif [ -n "$count" ]; then
    log "Database already has $count tests; skipping seed"
  else
    warn "Could not read the tests table; skipping seed"
  fi
}

print_urls() {
  local p
  p=$(port)
  echo
  echo "  This machine:  http://localhost:$p/viewer/index.html"
  echo "  On your LAN:   http://$(lan_ip):$p/viewer/index.html"
  echo
}

cmd_deploy() {
  local pull=1 before after
  while [ $# -gt 0 ]; do
    case "$1" in
      --no-pull) pull=0 ;;
      *) die "unknown option for deploy: $1" ;;
    esac
    shift
  done

  require_docker
  require_env_file
  check_name_conflicts

  if [ $pull -eq 1 ]; then
    git diff --quiet && git diff --cached --quiet \
      || die "working tree has uncommitted changes; commit/stash them or use --no-pull"
    before=$(git rev-parse --short HEAD)
    log "Pulling $(git rev-parse --abbrev-ref HEAD) (fast-forward only)"
    git pull --ff-only
    after=$(git rev-parse --short HEAD)
    if [ "$before" = "$after" ]; then
      log "Already up to date at $after"
    else
      log "Updated $before -> $after:"
      git --no-pager log --oneline "$before..$after"
    fi
  fi

  GIT_SHA=$(git rev-parse --short HEAD)
  git diff --quiet HEAD || GIT_SHA="$GIT_SHA-dirty"
  export GIT_SHA

  if docker image inspect "$API_IMAGE:latest" >/dev/null 2>&1; then
    docker tag "$API_IMAGE:latest" "$API_IMAGE:previous"
  fi

  log "Building API image ($GIT_SHA)"
  dc build api

  log "Starting Postgres and Redis"
  dc up -d --wait postgres redis

  # Only now, right before the API container takes the port, insist it is free
  # (a running sbuddy-api container is fine; it is about to be replaced).
  if ! docker container inspect sbuddy-api >/dev/null 2>&1; then
    check_port_free
  fi

  log "Starting API"
  dc up -d --no-build --force-recreate api

  if ! wait_for_api; then
    warn "Recent API logs:"
    dc logs --tail 40 api || true
    if docker image inspect "$API_IMAGE:previous" >/dev/null 2>&1; then
      warn "Rolling back to the previous image"
      ( cmd_rollback ) || warn "rollback did not recover the API either (a bad .env setting would explain that)"
    fi
    die "deploy of $GIT_SHA failed"
  fi

  seed_if_empty

  # Drop superseded sbuddy-api images (only ones carrying our label).
  docker image prune -f --filter label=app=sbuddy-api >/dev/null || true

  log "Deployed $GIT_SHA"
  print_urls
}

cmd_rollback() {
  require_docker
  docker image inspect "$API_IMAGE:previous" >/dev/null 2>&1 \
    || die "no previous image to roll back to"
  docker tag "$API_IMAGE:previous" "$API_IMAGE:latest"
  dc up -d --no-build --force-recreate api
  wait_for_api || die "API is still unhealthy after rollback; check: scripts/sbuddy.sh logs"
  log "Rolled back to $(docker image inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$API_IMAGE:latest")"
}

cmd_status() {
  local p rev autostart settings
  require_docker
  dc ps
  p=$(port)
  echo
  if curl -fsS "http://localhost:$p/api/v1/health" >/dev/null 2>&1; then
    echo "API health:  ok"
  else
    echo "API health:  DOWN"
  fi
  rev=$(docker container inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' sbuddy-api 2>/dev/null || echo "not deployed")
  echo "Deployed:    $rev (checked out: $(git rev-parse --short HEAD))"

  settings="$HOME/Library/Group Containers/group.com.docker/settings-store.json"
  if [ -f "$settings" ]; then
    autostart=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("AutoStart", False))' "$settings" 2>/dev/null || echo unknown)
    if [ "$autostart" != "True" ]; then
      warn "Docker Desktop does not start at login, so the stack will not come back after a reboot.
    Enable: Docker Desktop > Settings > General > 'Start Docker Desktop when you sign in'"
    fi
  fi
  print_urls
}

cmd_seed() {
  local count
  require_docker
  count=$(db_test_count || true)
  [ "$count" = "0" ] || die "database already has ${count:-?} tests. The importer is not idempotent (it would duplicate solutions), so seeding only runs on an empty database."
  seed_if_empty
}

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; }

main() {
  local cmd="${1:-}"
  [ $# -gt 0 ] && shift
  case "$cmd" in
    deploy)   cmd_deploy "$@" ;;
    start)    require_docker; require_env_file; check_name_conflicts; dc up -d --no-build --wait; print_urls ;;
    stop)     require_docker; dc stop ;;
    restart)  require_docker; dc restart api; wait_for_api ;;
    status)   cmd_status ;;
    logs)     require_docker; dc logs -f --tail 200 "${1:-api}" ;;
    rollback) cmd_rollback ;;
    seed)     cmd_seed ;;
    -h|--help|help|"") usage ;;
    *) usage; die "unknown command: $cmd" ;;
  esac
}

main "$@"
