# Docker Troubleshooting Guide

## Quick Fix: Port Conflict Errors

If you see errors like:
```
Bind for 0.0.0.0:5432 failed: port is already allocated
```

**Solution:** Use the automated reset script:

```bash
./scripts/docker-reset.sh
```

This script will:
1. Stop all StatementXL containers
2. Remove old containers and networks
3. Verify all ports are free
4. Pull latest code
5. Rebuild and start fresh containers

---

## Common Issues

### 1. Port Already Allocated

**Symptoms:**
- `Bind for 0.0.0.0:5432 failed: port is already allocated`
- `Bind for 0.0.0.0:6379 failed: port is already allocated`

**Cause:** Old Docker containers or local services using the same ports.

**Solution:**

```bash
# Option A: Use the reset script (recommended)
./scripts/docker-reset.sh

# Option B: Manual cleanup
docker-compose down
docker stop $(docker ps -aq --filter "name=statementxl")
docker rm $(docker ps -aq --filter "name=statementxl")
docker-compose up --build -d
```

**Find what's using a port:**
```bash
# Linux/macOS
sudo lsof -i :5432
sudo lsof -i :6379
sudo lsof -i :8000
sudo lsof -i :80

# Windows (PowerShell)
netstat -ano | findstr :5432
netstat -ano | findstr :6379
```

### 2. Backend Container Keeps Restarting

**Symptoms:**
- Backend shows "Restarting" status
- `docker-compose ps` shows backend as unhealthy

**Solution:**

```bash
# Check backend logs
docker-compose logs backend

# Common fixes:
# 1. Missing Python dependencies
./scripts/docker-reset.sh

# 2. Database connection issues
docker-compose logs postgres
# Ensure postgres is healthy before backend starts
```

### 3. Frontend Build Fails

**Symptoms:**
- `npm run build` fails during Docker build
- TypeScript compilation errors

**Solution:**

```bash
# Pull latest code (fixes are already committed)
git pull origin claude/continue-previous-work-3FncS
./scripts/docker-reset.sh
```

### 4. Database Migration Errors

**Symptoms:**
- Backend logs show Alembic errors
- Tables not created

**Solution:**

```bash
# Run migrations manually
docker-compose exec backend alembic upgrade head

# Or rebuild with fresh database
docker-compose down -v  # WARNING: Deletes all data
docker-compose up --build -d
```

### 5. Volume Permission Issues

**Symptoms:**
- Cannot write to `/app/uploads`
- Permission denied errors

**Solution:**

```bash
# Fix upload directory permissions
docker-compose exec backend chown -R statementxl:statementxl /app/uploads
```

---

## Switching Between Branches

When switching Git branches, **always** rebuild Docker:

```bash
git checkout <branch-name>
./scripts/docker-reset.sh
```

**Why?** Different branches may have:
- Different dependencies (requirements.txt, package.json)
- Different database schemas
- Different environment variables

---

## Complete Fresh Start

To completely reset everything (deletes all data):

```bash
# Stop and remove everything
docker-compose down -v

# Remove all StatementXL images
docker rmi statementxl_version_2-backend statementxl_version_2-frontend

# Rebuild from scratch
docker-compose up --build -d
```

---

## Verification Commands

After starting containers, verify everything is working:

```bash
# Check container status (all should be "Up (healthy)")
docker-compose ps

# Check logs for errors
docker-compose logs backend --tail=50
docker-compose logs frontend --tail=50

# Run automated verification
./scripts/verify-deployment.sh

# Test API health
curl http://localhost:8000/health

# Test frontend
curl http://localhost
```

---

## Docker Desktop Issues (Windows/macOS)

### WSL 2 Integration (Windows)

Ensure WSL 2 integration is enabled:
1. Open Docker Desktop Settings
2. Resources → WSL Integration
3. Enable integration with your WSL distro

### Resource Limits

If containers are slow or crashing:
1. Open Docker Desktop Settings
2. Resources
3. Increase CPUs to 4+ and Memory to 8GB+

### File Sharing

Ensure your project directory is accessible:
1. Docker Desktop Settings
2. Resources → File Sharing
3. Add your project path

---

## Getting Help

If issues persist:

1. **Collect logs:**
   ```bash
   docker-compose logs > docker-logs.txt
   ```

2. **Check system resources:**
   ```bash
   docker system df
   docker stats
   ```

3. **Verify Docker version:**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **Review recent commits:**
   ```bash
   git log -5 --oneline
   ```

Include this information when asking for help.
