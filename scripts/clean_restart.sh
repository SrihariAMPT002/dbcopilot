#!/bin/bash
# Clean restart: reset containers and rebuild

echo "🧹 Stopping containers..."
docker compose down

echo "🗑️  Removing volumes..."
docker volume rm dbcopilot_postgres_data dbcopilot_qdrant_data 2>/dev/null || true

echo "🔨 Building fresh containers..."
docker compose up --build

echo "✅ Containers started!"
echo ""
echo "🌐 Access services:"
echo "   • API: http://localhost:8000"
echo "   • Docs: http://localhost:8000/docs"
echo "   • Streamlit: http://localhost:8501"
