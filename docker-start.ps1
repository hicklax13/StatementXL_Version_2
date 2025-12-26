# StatementXL Docker Reset Script (PowerShell)
# Windows-native script for managing Docker containers

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "StatementXL Docker Reset (PowerShell)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking if Docker Desktop is running..." -ForegroundColor Yellow
try {
    docker info *>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not responding"
    }
    Write-Host "✓ Docker is running and ready" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ ERROR: Docker Desktop is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure:" -ForegroundColor Yellow
    Write-Host "  1. Docker Desktop is running"
    Write-Host "  2. Docker Desktop shows 'Engine running'"
    Write-Host "  3. Wait 30 seconds after starting Docker Desktop"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 1: Stop and remove old containers
Write-Host "Step 1/5: Stopping old containers..." -ForegroundColor Yellow
docker-compose down 2>$null
docker stop statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>$null
docker rm -f statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>$null
Write-Host "✓ Old containers stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Remove networks
Write-Host "Step 2/5: Cleaning networks..." -ForegroundColor Yellow
docker network rm statementxl_version_2_default 2>$null
docker network prune -f
Write-Host "✓ Networks cleaned" -ForegroundColor Green
Write-Host ""

# Step 3: Check and free ports
Write-Host "Step 3/5: Freeing up required ports..." -ForegroundColor Yellow

$ports = @(80, 5432, 6379, 8000)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $pid = $conn.OwningProcess
            if ($pid -ne 4 -and $pid -ne 0) {
                Write-Host "  Killing process $pid using port $port" -ForegroundColor Cyan
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "  ✓ Port $port is available" -ForegroundColor Green
    }
}

Write-Host "✓ Ports cleaned" -ForegroundColor Green
Write-Host ""

# Step 4: Build and start containers
Write-Host "Step 4/5: Building and starting containers..." -ForegroundColor Yellow
Write-Host "This will take 5-10 minutes..." -ForegroundColor Cyan
Write-Host ""
docker-compose up --build -d

# Step 5: Check status
Write-Host ""
Write-Host "Step 5/5: Checking container status..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host ""
docker-compose ps
Write-Host ""

# Check if containers are running
$running = docker-compose ps | Select-String "Up"
if ($running) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "SUCCESS! Containers are running." -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Wait 2-3 minutes for services to initialize"
    Write-Host "  2. Visit http://localhost (frontend)"
    Write-Host "  3. Visit http://localhost:8000/docs (API)"
    Write-Host ""
} else {
    Write-Host "⚠️  Some containers may still be starting." -ForegroundColor Yellow
    Write-Host "Wait a few minutes and run: docker-compose ps" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To view logs:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs backend"
    Write-Host "  docker-compose logs frontend"
    Write-Host ""
}

Read-Host "Press Enter to exit"
