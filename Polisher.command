#!/bin/bash
# Universal Rationale Polisher v2.0 — 1-Click macOS Launcher
cd "$(dirname "$0")" || exit 1

if [ -f ".env" ]; then
  set -a
  source ".env"
  set +a
fi

PORT="${POLISHER_PORT:-8080}"
echo "Starting Universal Rationale Polisher v2.0 on http://localhost:${PORT} ..."
(sleep 1.2 && open "http://localhost:${PORT}") &
exec python3 polisher.py
