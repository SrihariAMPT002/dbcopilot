#!/bin/bash
# Quick test: Verify API is running and endpoints are accessible

echo "🧪 Testing DB Copilot API..."
echo ""

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "✅ API is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ API failed to start"
        exit 1
    fi
    sleep 2
done

echo ""
echo "📊 Testing endpoints..."
echo ""

# Test health
echo "1️⃣  Health check:"
curl -s http://localhost:8000/health | jq '.status'
echo ""

# Test connections list
echo "2️⃣  List connections:"
curl -s http://localhost:8000/api/v1/connections | jq 'length'
echo "   (connections found)"
echo ""

# If there are connections, test sync on first one
FIRST_DB=$(curl -s http://localhost:8000/api/v1/connections | jq '.[0].id' 2>/dev/null)
if [ ! -z "$FIRST_DB" ] && [ "$FIRST_DB" != "null" ]; then
    echo "3️⃣  Testing sync on connection $FIRST_DB..."
    curl -s -X POST http://localhost:8000/api/v1/connections/$FIRST_DB/sync | jq '.message'
    echo ""
    
    echo "4️⃣  Checking schemas after sync:"
    SCHEMA_COUNT=$(curl -s http://localhost:8000/api/v1/metadata/databases/$FIRST_DB/schemas | jq 'length')
    echo "   Schemas found: $SCHEMA_COUNT"
    echo ""
    
    echo "5️⃣  Diagnostic info:"
    curl -s http://localhost:8000/api/v1/metadata/diagnose/$FIRST_DB | jq '{tables_count, schemas_count, recommendation}'
fi

echo ""
echo "✅ API test complete!"
