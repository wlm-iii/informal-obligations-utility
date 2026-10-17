#!/usr/bin/env bash
# Compatibility wrapper; database lifecycle is shared with native Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
  init|start|stop|status) exec python3 "$ROOT/scripts/dev.py" "db-$1" ;;
  *) echo "Usage: $0 {init|start|stop|status}" >&2; exit 2 ;;
esac
