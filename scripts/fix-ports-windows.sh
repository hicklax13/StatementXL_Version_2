#!/bin/bash
# Emergency Windows port cleanup script
# Run this if docker-compose fails with port allocation errors

echo "🔧 Windows Port Cleanup"
echo "======================="
echo ""

PORTS=(80 5432 6379 8000)

for PORT in "${PORTS[@]}"; do
    echo "Checking port $PORT..."
    PIDS=$(netstat -ano | grep ":$PORT " | grep "LISTENING" | awk '{print $5}' | sort -u)

    if [ -n "$PIDS" ]; then
        echo "⚠️  Port $PORT is in use by:"
        for PID in $PIDS; do
            PROCESS_NAME=$(tasklist //FI "PID eq $PID" //FO CSV //NH 2>/dev/null | cut -d',' -f1 | tr -d '"')
            echo "    PID $PID - $PROCESS_NAME"
        done

        echo "Attempting to kill processes on port $PORT..."
        for PID in $PIDS; do
            if [ "$PID" != "4" ] && [ "$PID" != "0" ]; then
                taskkill //F //PID $PID 2>/dev/null && echo "  ✓ Killed PID $PID" || echo "  ✗ Could not kill PID $PID (may need admin)"
            fi
        done
    else
        echo "✓ Port $PORT is free"
    fi
    echo ""
done

echo "✅ Port cleanup complete!"
echo ""
echo "Now run:"
echo "  docker-compose up --build -d"
