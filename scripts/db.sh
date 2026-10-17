#!/usr/bin/env bash
# Isolated, disposable development database; never point this at production.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$ROOT/.local/postgres"
DATA="$BASE/data"
# PostgreSQL listens ONLY on loopback for the documented local URL.
PORT=54329
export PGCONNECT_TIMEOUT=5

require_cluster() {
  if [[ ! -f "$DATA/PG_VERSION" ]]; then
    echo "Run 'make db-init' first." >&2
    exit 1
  fi
}

case "${1:-}" in
  init)
    if [[ -f "$DATA/PG_VERSION" ]]; then
      echo "Cluster already exists at $DATA (left untouched)."
      exit 0
    fi
    mkdir -p "$BASE"
    chmod 700 "$BASE"
    # Trust is local development ONLY; data is owner-only and TCP is loopback.
    initdb -D "$DATA" --username=iou --auth-local=trust --auth-host=trust --encoding=UTF8 --locale=C
    ;;
  start)
    require_cluster
    if ! pg_ctl -D "$DATA" status >/dev/null 2>&1; then
      # Disable Unix sockets: repo paths may exceed the platform's socket path limit.
      pg_ctl -D "$DATA" -l "$BASE/server.log" \
        -o "-h 127.0.0.1 -p $PORT -k ''" -w start
    fi
    # Refuse to act on an unrelated service occupying the port.
    actual="$(psql -X -h 127.0.0.1 -p "$PORT" -U iou -d postgres -Atc 'SHOW data_directory')"
    if [[ "$actual" != "$DATA" ]]; then
      echo "Port $PORT is not serving this project's cluster; refusing to create a database." >&2
      exit 1
    fi
    exists="$(psql -X -h 127.0.0.1 -p "$PORT" -U iou -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = 'iou'")"
    if [[ "$exists" != 1 ]]; then
      createdb -h 127.0.0.1 -p "$PORT" -U iou iou
    fi
    echo "IOU database ready at 127.0.0.1:$PORT/iou (local development only)."
    ;;
  stop)
    require_cluster
    if pg_ctl -D "$DATA" status >/dev/null 2>&1; then
      pg_ctl -D "$DATA" -m fast -w stop
    else
      echo "Project database is already stopped."
    fi
    ;;
  status)
    require_cluster
    pg_ctl -D "$DATA" status
    ;;
  *)
    echo "Usage: $0 {init|start|stop|status}" >&2
    exit 2
    ;;
esac
