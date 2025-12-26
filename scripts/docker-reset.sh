#!/bin/bash
# Complete Docker cleanup and rebuild script for StatementXL
# This script ensures no port conflicts or stale containers

set -e

echo "🧹 StatementXL Docker Reset Script"
echo "=================================="
echo ""

# Step 1: Stop all StatementXL containers
echo "Step 1/6: Stopping all StatementXL containers..."
docker-compose down 2>/dev/null || true
docker stop statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>/dev/null || true
echo "✓ Containers stopped"
echo ""

# Step 2: Remove containers
echo "Step 2/6: Removing old containers..."
docker rm -f statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>/dev/null || true
echo "✓ Old containers removed"
echo ""

# Step 3: Remove networks
echo "Step 3/6: Cleaning up Docker networks..."
docker network rm statementxl_version_2_default 2>/dev/null || true
docker network prune -f
echo "✓ Networks cleaned"
echo ""

# Step 4: Verify ports are free
echo "Step 4/6: Verifying ports are available..."
PORTS=(80 5432 6379 8000)
PORTS_BLOCKED=false

for PORT in "${PORTS[@]}"; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        PROCESS=$(lsof -Pi :$PORT -sTCP:LISTEN -t 2>/dev/null || echo "unknown")
        echo "⚠️  Warning: Port $PORT is in use by process $PROCESS"
        PORTS_BLOCKED=true
    else
        echo "✓ Port $PORT is available"
    fi
done

if [ "$PORTS_BLOCKED" = true ]; then
    echo ""
    echo "❌ ERROR: Some required ports are still in use."
    echo "Run this command to find and stop blocking processes:"
    echo "  sudo lsof -i :80 -i :5432 -i :6379 -i :8000"
    echo ""
    echo "To force kill Docker processes on these ports:"
    echo "  docker ps -a | grep -E '(5432|6379|8000|80)' | awk '{print \$1}' | xargs -r docker rm -f"
    exit 1
fi
echo ""

# Step 5: Pull latest changes
echo "Step 5/6: Pulling latest code from GitHub..."
git pull origin claude/continue-previous-work-3FncS
echo "✓ Code updated"
echo ""

# Step 6: Build and start containers
echo "Step 6/6: Building and starting containers (this will take 5-10 minutes)..."
docker-compose up --build -d
echo ""

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
echo "This may take a few minutes..."
sleep 10

# Check status
echo ""
echo "📊 Container Status:"
docker-compose ps
echo ""

# Check if all containers are running
HEALTHY_COUNT=$(docker-compose ps | grep -c "Up" || true)
if [ "$HEALTHY_COUNT" -eq 4 ]; then
    echo "✅ SUCCESS! All 4 containers are running."
    echo ""
    echo "Next steps:"
    echo "1. Wait 2-3 minutes for backend to fully initialize"
    echo "2. Run: ./scripts/verify-deployment.sh"
    echo "3. Visit: http://localhost (frontend) and http://localhost:8000/docs (API)"
else
    echo "⚠️  Some containers may still be starting. Wait a few minutes and check:"
    echo "   docker-compose ps"
    echo ""
    echo "To view logs if there are issues:"
    echo "   docker-compose logs backend"
    echo "   docker-compose logs frontend"
fi
