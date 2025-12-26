#!/bin/bash
# Complete Docker cleanup and rebuild script for StatementXL
# This script ensures no port conflicts or stale containers

echo "🧹 StatementXL Docker Reset Script"
echo "=================================="
echo ""

# Check if Docker is running with retry logic
echo "Checking if Docker Desktop is running..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker info >/dev/null 2>&1; then
        echo "✓ Docker is running and ready"
        echo ""
        break
    fi

    if [ $RETRY_COUNT -eq 0 ]; then
        echo "❌ Docker is not responding"
        echo ""
        echo "Please start Docker Desktop if it's not already running:"
        echo "  1. Open Docker Desktop application"
        echo "  2. Wait for it to fully start (green icon in system tray)"
        echo ""
        echo "Waiting for Docker to be ready... (this may take up to 60 seconds)"
    fi

    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo ""
    echo "❌ ERROR: Docker did not become ready after 60 seconds"
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Check if Docker Desktop is running (look for Docker icon in system tray)"
    echo "  2. Try restarting Docker Desktop"
    echo "  3. Check if virtualization is enabled in BIOS"
    echo "  4. Run 'docker info' manually to see detailed error"
    echo ""
    exit 1
fi

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

# Step 4: Kill any processes using required ports
echo "Step 4/6: Freeing up required ports..."
PORTS=(80 5432 6379 8000)

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash)
    echo "Detected Windows environment"
    for PORT in "${PORTS[@]}"; do
        # Find PIDs using the port
        PIDS=$(netstat -ano | grep ":$PORT " | grep "LISTENING" | awk '{print $5}' | sort -u)
        if [ -n "$PIDS" ]; then
            echo "⚠️  Port $PORT is in use. Attempting to free it..."
            for PID in $PIDS; do
                # Skip system process (PID 4)
                if [ "$PID" != "4" ] && [ "$PID" != "0" ]; then
                    echo "  Killing process $PID using port $PORT"
                    taskkill //F //PID $PID 2>/dev/null || echo "  Could not kill PID $PID (may require admin)"
                fi
            done
        else
            echo "✓ Port $PORT is available"
        fi
    done
else
    # Linux/macOS
    for PORT in "${PORTS[@]}"; do
        if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            PIDS=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
            echo "⚠️  Port $PORT is in use. Attempting to free it..."
            for PID in $PIDS; do
                echo "  Killing process $PID using port $PORT"
                kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || echo "  Could not kill PID $PID"
            done
        else
            echo "✓ Port $PORT is available"
        fi
    done
fi

# Wait a moment for ports to be fully released
sleep 2
echo "✓ Ports cleaned"
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
