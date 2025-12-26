@echo off
REM Windows batch script to reset and start Docker containers
REM Use this if Git Bash has Docker communication issues

echo.
echo ====================================
echo StatementXL Docker Reset (Windows)
echo ====================================
echo.

REM Check if Docker is running
echo Checking if Docker Desktop is running...
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker Desktop is not running or not accessible!
    echo.
    echo Please ensure:
    echo   1. Docker Desktop is running
    echo   2. Docker Desktop shows "Engine running"
    echo   3. Wait 30 seconds after starting Docker Desktop
    echo.
    pause
    exit /b 1
)
echo OK: Docker is running and ready
echo.

REM Stop and remove old containers
echo Step 1/5: Stopping old containers...
docker-compose down 2>nul
docker stop statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>nul
docker rm -f statementxl_backend statementxl_frontend statementxl_postgres statementxl_redis 2>nul
echo OK: Old containers stopped
echo.

REM Remove networks
echo Step 2/5: Cleaning networks...
docker network rm statementxl_version_2_default 2>nul
docker network prune -f
echo OK: Networks cleaned
echo.

REM Check and free ports
echo Step 3/5: Checking ports...
echo Checking port 5432...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5432" ^| findstr "LISTENING"') do (
    echo Killing process %%a on port 5432
    taskkill /F /PID %%a 2>nul
)
echo Checking port 6379...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":6379" ^| findstr "LISTENING"') do (
    echo Killing process %%a on port 6379
    taskkill /F /PID %%a 2>nul
)
echo Checking port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Killing process %%a on port 8000
    taskkill /F /PID %%a 2>nul
)
echo Checking port 80...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":80 " ^| findstr "LISTENING"') do (
    echo Killing process %%a on port 80
    taskkill /F /PID %%a 2>nul
)
echo OK: Ports cleaned
echo.

REM Build and start containers
echo Step 4/5: Building and starting containers...
echo This will take 5-10 minutes...
echo.
docker-compose up --build -d
echo.

REM Wait and check status
echo Step 5/5: Checking container status...
timeout /t 10 /nobreak >nul
echo.
docker-compose ps
echo.

REM Check if successful
docker-compose ps | findstr "Up" >nul
if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS! Containers are running.
    echo ========================================
    echo.
    echo Next steps:
    echo   1. Wait 2-3 minutes for services to initialize
    echo   2. Visit http://localhost
    echo   3. Visit http://localhost:8000/docs
    echo.
) else (
    echo.
    echo WARNING: Some containers may still be starting.
    echo Wait a few minutes and run: docker-compose ps
    echo.
    echo To view logs:
    echo   docker-compose logs backend
    echo   docker-compose logs frontend
    echo.
)

pause
