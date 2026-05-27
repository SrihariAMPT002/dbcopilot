#!/usr/bin/env bash
# =============================================================
# DB Copilot — Start the full stack
# Usage: ./scripts/start.sh [--build] [--dev]
# =============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BUILD_FLAG=""
DEV_MODE=false

for arg in "$@"; do
    case $arg in
        --build) BUILD_FLAG="--build" ;;
        --dev)   DEV_MODE=true ;;
    esac
done

# ── Check .env exists ────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "  .env not found — copying from .env.example"
    cp .env.example .env
    echo ""
    echo "🔑 Generating a fresh ENCRYPTION_KEY..."
    KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "REPLACE_ME")
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|your_fernet_key_here_generate_with_command_above|${KEY}|g" .env
    else
        sed -i "s|your_fernet_key_here_generate_with_command_above|${KEY}|g" .env
    fi
    echo " .env created with fresh encryption key."
    echo "   Review .env before continuing in production."
    echo ""
fi

echo "🚀 Starting DB Copilot..."
echo ""

if [ "$DEV_MODE" = true ]; then
    echo "📦 Development mode — code hot-reloading enabled"
    docker compose up $BUILD_FLAG
else
    docker compose up -d $BUILD_FLAG
    echo ""
    echo " DB Copilot is starting up!"
    echo ""
    echo "   🌐 Streamlit UI : http://localhost:8501"
    echo "    FastAPI Docs : http://localhost:8000/docs"
    echo "   🩺 Health Check : http://localhost:8000/health"
    echo ""
    echo "   View logs:  docker compose logs -f"
    echo "   Stop:       docker compose down"
fi
