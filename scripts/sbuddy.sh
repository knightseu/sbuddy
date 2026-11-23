#!/usr/bin/env bash
# Manage the long-running Sbuddy stack (Postgres, Redis, API) via docker compose.
#
#   scripts/sbuddy.sh deploy [--no-pull]   pull, build, (re)start, health-check, auto-rollback
#   scripts/sbuddy.sh start | stop | restart
#   scripts/sbuddy.sh status               containers, health, deployed revision, LAN URL
#   scripts/sbuddy.sh logs [service]       follow logs (default: api)
#   scripts/sbuddy.sh rollback             return the API to the previously deployed image
#   scripts/sbuddy.sh seed                 import crawled_data/ into an EMPTY database
#   scripts/sbuddy.sh backup               pg_dump + mirror crawled_data/mathcounts (also before every deploy)
#   scripts/sbuddy.sh backups              list backups and the schedule
#   scripts/sbuddy.sh verify [file]        restore into a scratch DB, compare row counts
#   scripts/sbuddy.sh restore <file>       replace the live database with a backup
#   scripts/sbuddy.sh restore-data [dir]   copy crawled_data/mathcounts back from a backup mirror
#   scripts/sbuddy.sh schedule-backups     install the daily launchd job (unschedule-backups)
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

  # Before the new code touches the schema. Skipped only on a fresh, empty volume.
  if [ -n "$(db_test_count || true)" ]; then
    log "Backing up the database before deploying"
    do_backup pre-deploy >/dev/null || die "pre-deploy backup failed; nothing was deployed"
  fi

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
  backup_status_lines

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

# ---------------------------------------------------------------------------
# Database backups
#
# Backups are pg_dump custom-format files on the host, outside the Docker
# volume: $BACKUP_DIR (default ~/sbuddy-backups). If BACKUP_COPY_DIR is set
# (e.g. a Dropbox folder), each backup is also copied there so a copy lives
# off this machine. File names carry the kind, time and git revision:
#   sbuddy-<kind>-YYYYMMDD-HHMMSS-<sha>.dump
# Kinds: daily (scheduled), pre-deploy, pre-restore, manual.
# Retention: daily keeps 7 newest + newest of each of the 4 weeks before
# them; pre-deploy/pre-restore keep the 5 newest each; manual is never pruned.
#
# MATHCOUNTS data (crawled_data/mathcounts/: extracted Tests, review files and
# source PDFs) is gitignored, so it exists only on this machine. Every backup
# also mirrors it to <dir>/crawled_data/mathcounts/ in both places. The mirror
# never deletes, and a file that changed is first moved to
# <dir>/crawled_data/_replaced/<time>/, so a bad local edit can't overwrite the
# only good copy.
# ---------------------------------------------------------------------------

KEEP_DAILY=7
KEEP_WEEKLY=4
KEEP_PRE=5
STALE_HOURS=26
LAUNCHD_LABEL=com.sbuddy.backup
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"

expand_path() { case "$1" in "~") echo "$HOME" ;; "~/"*) echo "$HOME/${1#\~/}" ;; *) echo "$1" ;; esac; }
backup_dir()      { expand_path "$(env_value BACKUP_DIR "$HOME/sbuddy-backups")"; }
backup_copy_dir() { local d; d=$(env_value BACKUP_COPY_DIR ""); [ -z "$d" ] || expand_path "$d"; }

# psql in the postgres container against database $1 (empty: the app DB)
pg_sql() {
  local db="${1:-}"; shift
  dc exec -T -e PGDB="$db" postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${PGDB:-$POSTGRES_DB}" -tA "$@"' sh "$@"
}

# "table|rows" for every table in the public schema, exact counts
table_counts() {
  pg_sql "${1:-}" -c "SELECT table_name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text
    FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1"
}

notify_failure() { # best-effort desktop notification for unattended runs
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$1\" with title \"Sbuddy backup FAILED\"" >/dev/null 2>&1 || true
  fi
}

week_of() { # YYYYMMDD -> ISO year-week
  date -j -f %Y%m%d "$1" +%G-W%V 2>/dev/null || date -d "$1" +%G-W%V
}

prune_backups() {
  local dir="$1" f kind n week weeks="" nweeks=0 files
  [ -n "$dir" ] && [ -d "$dir" ] || return 0
  # macOS privacy rules can let a launchd job write a folder but not list it
  if ! files=$(ls -1 "$dir" 2>/dev/null); then
    warn "cannot list $dir, so old backups there are not pruned (grant /bin/bash Full Disk Access, or prune by hand)"
    return 0
  fi
  for kind in pre-deploy pre-restore; do
    n=0
    for f in $(echo "$files" | grep -E "^sbuddy-$kind-[0-9]{8}-[0-9]{6}.*\.dump$" | sort -r); do
      n=$((n + 1)); [ $n -le $KEEP_PRE ] || rm -f "${dir:?}/${f:?}"
    done
  done
  n=0
  for f in $(echo "$files" | grep -E '^sbuddy-daily-[0-9]{8}-[0-9]{6}.*\.dump$' | sort -r); do
    n=$((n + 1))
    [ $n -le $KEEP_DAILY ] && continue
    week=$(week_of "$(echo "$f" | cut -d- -f3)")
    if [ $nweeks -lt $KEEP_WEEKLY ] && ! echo "$weeks" | grep -qw -- "$week"; then
      weeks="$weeks $week"; nweeks=$((nweeks + 1))
    else
      rm -f "${dir:?}/${f:?}"
    fi
  done
}

DATA_DIR="$ROOT/crawled_data/mathcounts"

# Mirror DATA_DIR into <backup root>/crawled_data/mathcounts/
mirror_data() {
  local root="$1" stamp
  [ -d "$DATA_DIR" ] || return 0
  stamp=$(date +%Y%m%d-%H%M%S)
  mkdir -p "$root/crawled_data/mathcounts" || return 1
  rsync -a --backup --backup-dir="$root/crawled_data/_replaced/$stamp" \
    "$DATA_DIR/" "$root/crawled_data/mathcounts/" || return 1
  log "Mirrored crawled_data/mathcounts to $root/crawled_data/mathcounts ($(du -sh "$root/crawled_data/mathcounts" | cut -f1 | tr -d ' '))" >&2
}

# Take a backup; prints the path of the new file on stdout.
do_backup() {
  local kind="$1" dir copy sha file tmp
  dir=$(backup_dir)
  mkdir -p "$dir"
  chmod 700 "$dir"
  sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  file="$dir/sbuddy-$kind-$(date +%Y%m%d-%H%M%S)-$sha.dump"
  tmp="$file.partial"
  if ! ( umask 077; dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$tmp" ); then
    rm -f "${tmp:?}"; warn "pg_dump failed"; return 1
  fi
  # A truncated or garbage file fails to list
  if ! dc exec -T postgres pg_restore --list < "$tmp" >/dev/null 2>&1; then
    rm -f "${tmp:?}"; warn "dump is not readable by pg_restore"; return 1
  fi
  mv "$tmp" "$file"
  log "Backup written: $file ($(du -h "$file" | cut -f1 | tr -d ' '))" >&2
  prune_backups "$dir"
  mirror_data "$dir" || { warn "could not mirror crawled_data/mathcounts to $dir"; return 1; }

  copy=$(backup_copy_dir)
  if [ -n "$copy" ]; then
    if mkdir -p "$copy" && cp "$file" "$copy/"; then
      log "Copied to $copy" >&2
      prune_backups "$copy"
    else
      warn "could not copy backup to BACKUP_COPY_DIR=$copy"
      return 1
    fi
    mirror_data "$copy" || { warn "could not mirror crawled_data/mathcounts to BACKUP_COPY_DIR=$copy"; return 1; }
  fi
  echo "$file"
}

latest_backup() {
  ls -1t "$(backup_dir)"/sbuddy-*.dump 2>/dev/null | head -n 1 || true
}

cmd_backup() {
  case "${1:-}" in
    --scheduled)
      echo "--- $(date '+%Y-%m-%d %H:%M:%S') scheduled backup"
      if ! docker info >/dev/null 2>&1; then
        notify_failure "Docker is not running"; die "Docker is not running"
      fi
      do_backup daily >/dev/null || { notify_failure "see $(backup_dir)/backup.log"; die "scheduled backup failed"; }
      ;;
    "") require_docker; do_backup manual >/dev/null ;;
    *) die "unknown option for backup: $1" ;;
  esac
}

backup_age_hours() { # hours since the newest backup, empty if none
  local f; f=$(latest_backup)
  [ -n "$f" ] || return 0
  echo $(( ($(date +%s) - $(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")) / 3600 ))
}

backup_status_lines() {
  local f age
  f=$(latest_backup); age=$(backup_age_hours)
  if [ -z "$f" ]; then
    echo "Last backup: NONE in $(backup_dir)"
  else
    echo "Last backup: $(basename "$f") (${age}h ago)"
  fi
  if [ -f "$LAUNCHD_PLIST" ]; then
    echo "Schedule:    daily at $(backup_time) (launchd $LAUNCHD_LABEL)"
  else
    echo "Schedule:    NOT installed (scripts/sbuddy.sh schedule-backups)"
  fi
  if [ -z "$f" ] || [ "$age" -ge $STALE_HOURS ]; then
    warn "no backup in the last ${STALE_HOURS}h"
  fi
}

cmd_backups() {
  local dir; dir=$(backup_dir)
  echo "Backup dir:  $dir"
  [ -z "$(backup_copy_dir)" ] || echo "Copy dir:    $(backup_copy_dir)"
  echo
  ls -1lht "$dir"/sbuddy-*.dump 2>/dev/null | awk '{n=split($NF,p,"/"); print "  "$5"\t"$6" "$7" "$8"\t"p[n]}' || true
  echo
  backup_status_lines
}

resolve_backup_file() { # arg may be a path or a bare file name in BACKUP_DIR
  local f="${1:-}"
  [ -n "$f" ] || f=$(latest_backup)
  [ -n "$f" ] || die "no backups found in $(backup_dir)"
  if [ ! -f "$f" ] && [ -f "$(backup_dir)/$f" ]; then f="$(backup_dir)/$f"; fi
  [ -f "$f" ] || die "backup file not found: $f"
  echo "$f"
}

# Restore a dump into a scratch database, then compare its row counts
# with the live database. Nothing live is touched.
cmd_verify() {
  local file scratch live restored rc=0 t a b
  require_docker
  file=$(resolve_backup_file "${1:-}")
  scratch="$(env_value POSTGRES_DB sbuddy_db)_verify"
  log "Verifying $(basename "$file") in scratch database $scratch"
  pg_sql postgres -q -c "DROP DATABASE IF EXISTS $scratch" -c "CREATE DATABASE $scratch" >/dev/null
  if ! dc exec -T -e PGDB="$scratch" postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$PGDB" --no-owner --exit-on-error' < "$file"; then
    pg_sql postgres -q -c "DROP DATABASE IF EXISTS $scratch" >/dev/null || true
    die "pg_restore failed: this backup is NOT restorable"
  fi
  restored=$(table_counts "$scratch")
  live=$(table_counts "" 2>/dev/null || true)
  pg_sql postgres -q -c "DROP DATABASE IF EXISTS $scratch" >/dev/null

  printf '\n  %-28s %10s %10s\n' TABLE BACKUP LIVE
  for t in $( (echo "$restored"; echo "$live") | cut -d'|' -f1 | grep . | sort -u); do
    a=$(echo "$restored" | awk -F'|' -v t="$t" '$1==t{print $2}')
    b=$(echo "$live"     | awk -F'|' -v t="$t" '$1==t{print $2}')
    printf '  %-28s %10s %10s%s\n' "$t" "${a:--}" "${b:--}" "$([ "$a" = "$b" ] || echo '   <- differs')"
    [ -n "$a" ] || rc=1
  done
  echo
  [ $rc -eq 0 ] || warn "some live tables are not in the backup (new since it was taken, or a partial dump)"
  log "Backup restores cleanly. Count differences are expected for rows written since it was taken."
}

# Replace the live database with a backup. Takes a pre-restore backup first.
cmd_restore() {
  local file="" yes=0 db answer arg
  require_docker
  for arg in "$@"; do
    case "$arg" in
      --yes) yes=1 ;;
      *) file="$arg" ;;
    esac
  done
  [ -n "$file" ] || die "usage: scripts/sbuddy.sh restore [--yes] <file>   (see: scripts/sbuddy.sh backups)"
  file=$(resolve_backup_file "$file")
  db=$(env_value POSTGRES_DB sbuddy_db)

  echo "This REPLACES database '$db' with:"
  echo "    $file"
  echo "The API is stopped during the restore. A pre-restore backup is taken first."
  if [ $yes -eq 0 ]; then
    printf 'Type "restore" to continue: '
    read -r answer
    [ "$answer" = "restore" ] || die "aborted"
  fi

  dc up -d --wait postgres
  do_backup pre-restore >/dev/null || die "pre-restore backup failed; nothing was changed"

  log "Stopping API"
  dc stop api
  log "Recreating database $db"
  pg_sql postgres -q -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" -c "CREATE DATABASE $db" >/dev/null
  log "Restoring"
  if ! dc exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < "$file"; then
    die "restore failed. The database is incomplete and the API is stopped.
    Retry, or go back to the pre-restore backup with: scripts/sbuddy.sh restore $(latest_backup)"
  fi
  log "Starting API (it creates any tables the backup predates)"
  dc start api
  wait_for_api || die "API is unhealthy after restore; check: scripts/sbuddy.sh logs"
  log "Restored $(basename "$file")"
}

# Copy MATHCOUNTS data back from a backup mirror. Adds and overwrites files,
# never deletes; afterwards re-import with: npm run import:mathcounts
cmd_restore_data() {
  local root="${1:-}" src answer
  if [ -z "$root" ]; then
    root=$(backup_dir)
    [ -d "$root/crawled_data/mathcounts" ] || root=$(backup_copy_dir)
  fi
  src="$root/crawled_data/mathcounts"
  [ -d "$src" ] || die "no mirror at $src"
  echo "This copies $src"
  echo "     into   $DATA_DIR"
  echo "Files present in both are overwritten by the backup copy; nothing is deleted."
  printf 'Type "restore" to continue: '
  read -r answer
  [ "$answer" = "restore" ] || die "aborted"
  mkdir -p "$DATA_DIR"
  rsync -a "$src/" "$DATA_DIR/"
  log "Restored crawled_data/mathcounts ($(du -sh "$DATA_DIR" | cut -f1 | tr -d ' ')). Re-import with: npm run import:mathcounts"
}

backup_time() {
  local t; t=$(env_value BACKUP_TIME 03:00)
  echo "$t" | grep -Eq '^([01][0-9]|2[0-3]):[0-5][0-9]$' || die "BACKUP_TIME must be HH:MM, got: $t"
  echo "$t"
}

cmd_schedule_backups() {
  local t h m dir
  [ "$(uname)" = Darwin ] || die "schedule-backups uses launchd (macOS). On Linux, add a cron entry:
    0 3 * * * $ROOT/scripts/sbuddy.sh backup --scheduled >> $(backup_dir)/backup.log 2>&1"
  t=$(backup_time); h=$((10#${t%:*})); m=$((10#${t#*:}))
  dir=$(backup_dir); mkdir -p "$dir" "$(dirname "$LAUNCHD_PLIST")"
  cat > "$LAUNCHD_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LAUNCHD_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$ROOT/scripts/sbuddy.sh</string>
    <string>backup</string>
    <string>--scheduled</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$PATH</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer></dict>
  <key>StandardOutPath</key><string>$dir/backup.log</string>
  <key>StandardErrorPath</key><string>$dir/backup.log</string>
</dict>
</plist>
PLIST
  launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
  log "Daily backup scheduled at $t (a run missed while asleep fires on wake). Log: $dir/backup.log"
  log "Trigger one now with: launchctl kickstart gui/$(id -u)/$LAUNCHD_LABEL"
}

cmd_unschedule_backups() {
  launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" 2>/dev/null || true
  rm -f "${LAUNCHD_PLIST:?}"
  log "Daily backup schedule removed"
}

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; }

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
    backup)   cmd_backup "$@" ;;
    backups)  cmd_backups ;;
    verify)   cmd_verify "$@" ;;
    restore)  cmd_restore "$@" ;;
    restore-data) cmd_restore_data "$@" ;;
    schedule-backups)   cmd_schedule_backups ;;
    unschedule-backups) cmd_unschedule_backups ;;
    -h|--help|help|"") usage ;;
    *) usage; die "unknown command: $cmd" ;;
  esac
}

main "$@"
