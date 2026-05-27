#!/usr/bin/env bash
# =============================================================
# DB Copilot — Stop all services
# Usage: ./scripts/stop.sh [--clean]
# --clean: also removes volumes (deletes all metadata)
# =============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CLEAN=false
for arg in "$@"; do
    case $arg in
        --clean) CLEAN=true ;;
    esac
done

if [ "$CLEAN" = true ]; then
    echo "  Stopping services and removing volumes (all data will be lost)..."
    docker compose down -v --remove-orphans
    echo " Services stopped and volumes removed."
else
    echo "🛑 Stopping DB Copilot services..."
    docker compose down --remove-orphans
    echo " Services stopped. Data volumes preserved."
    echo "   To remove data too, run: ./scripts/stop.sh --clean"
fi
