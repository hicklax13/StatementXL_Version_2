# StatementXL Testing Guide

## Overview

This guide provides comprehensive testing instructions for StatementXL before deployment.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (for local testing)
- Redis 7+ (optional, for caching tests)

## Testing Phases

### Phase 1: Code Validation ✅ COMPLETED

**Status**: All checks passed during code review

- [x] All Python files syntax validated
- [x] No import errors in core modules
- [x] TypeScript configurations valid
- [x] Docker configurations verified
- [x] CI/CD pipeline structure confirmed
- [x] Documentation reviewed and corrected

**Fixes Applied**:
- Corrected date in CHANGELOG.md (2024 → 2025)
- Corrected copyright year in LICENSE (2024 → 2025)
- Added missing Alembic migration configuration

---

### Phase 2: Local Unit Testing

**Requirements**:
```bash
pip install -r requirements.txt
```

**Run Unit Tests**:
```bash
# All unit tests
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/unit/ --cov=backend --cov-report=html

# Specific test files
python -m pytest tests/unit/test_auth.py -v
python -m pytest tests/unit/test_validators.py -v
python -m pytest tests/unit/test_exceptions.py -v
```

**Expected Results**:
- All authentication tests pass
- All validation tests pass
- Exception handling tests pass

---

### Phase 3: Integration Testing

**Requirements**:
- PostgreSQL running on localhost:5432
- Optional: Redis running on localhost:6379

**Setup Database**:
```bash
# Create test database
createdb statementxl_test

# Run migrations
DATABASE_URL=postgresql://user:pass@localhost:5432/statementxl_test \
  alembic upgrade head
```

**Run Integration Tests**:
```bash
# All integration tests
python -m pytest tests/integration/ -v

# Specific integration tests
python -m pytest tests/integration/test_health.py -v
python -m pytest tests/integration/test_auth_api.py -v
```

**Expected Results**:
- Health endpoints respond correctly
- Authentication flow works end-to-end
- Database connections established

---

### Phase 4: Docker Build Testing ⚠️ REQUIRES DOCKER

**Build All Images**:
```bash
# Clean build (recommended for first time)
docker-compose build --no-cache

# Quick rebuild
docker-compose build
```

**Expected Output**:
- Backend image builds successfully (~5-10 minutes)
- Frontend image builds successfully (~3-5 minutes)
- No build errors
- All dependencies installed correctly

**Verify Images**:
```bash
docker images | grep statementxl
```

Should show:
- `statementxl_backend`
- `statementxl_frontend`

---

### Phase 5: Docker Compose Stack Testing ⚠️ REQUIRES DOCKER

**Start Stack**:
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

**Expected Services**:
- ✅ postgres (healthy)
- ✅ redis (healthy)
- ✅ backend (healthy)
- ✅ frontend (healthy)

**Health Checks**:
```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"2.0.0"}

# Backend readiness
curl http://localhost:8000/ready
# Expected: {"status":"ready","database":"connected","cache":"connected"}

# Frontend
curl http://localhost/
# Expected: HTML response

# API docs
curl http://localhost:8000/docs
# Expected: Swagger UI HTML
```

---

### Phase 6: Functional Smoke Tests ⚠️ REQUIRES DOCKER

**Test Authentication Flow**:
```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!","full_name":"Test User"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!"}'

# Save the access_token from response
TOKEN="<access_token>"

# Get user profile
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Test File Upload**:
```bash
# Upload a test PDF
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf"
```

**Test Template Library**:
```bash
# List templates
curl http://localhost:8000/api/v1/library/templates \
  -H "Authorization: Bearer $TOKEN"
```

---

### Phase 7: Performance Testing ⚠️ REQUIRES DOCKER

**Install Locust**:
```bash
pip install locust
```

**Run Load Tests**:
```bash
# Start Locust with web UI
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Access Locust UI at http://localhost:8089
# Configure:
# - Number of users: 10-100
# - Spawn rate: 5-10 users/second
# - Run time: 5-10 minutes
```

**Monitor During Load Test**:
```bash
# Check container resource usage
docker stats

# Watch backend logs
docker-compose logs -f backend

# Check database connections
docker-compose exec postgres psql -U statementxl -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

**Expected Performance**:
- p95 response time < 500ms for GET requests
- p95 response time < 2000ms for POST requests
- No 500 errors under normal load
- Stable memory usage
- CPU usage < 80% under load

---

### Phase 8: Security Testing

**Dependency Audit**:
```bash
# Python packages
pip install pip-audit
pip-audit

# Node packages
cd frontend
npm audit
npm audit fix
```

**OWASP ZAP Scan**:
```bash
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t http://localhost:8000
```

**Manual Security Checks**:
- [ ] SQL injection tests (use `' OR '1'='1`)
- [ ] XSS tests (inject `<script>alert('XSS')</script>`)
- [ ] CSRF token validation
- [ ] Rate limiting verification
- [ ] JWT token expiration
- [ ] Password strength enforcement

---

### Phase 9: Database Migration Testing

**Test Forward Migration**:
```bash
# Check current version
docker-compose exec backend alembic current

# Create test migration
docker-compose exec backend alembic revision \
  --autogenerate -m "test migration"

# Apply migration
docker-compose exec backend alembic upgrade head
```

**Test Rollback**:
```bash
# Rollback one version
docker-compose exec backend alembic downgrade -1

# Reapply
docker-compose exec backend alembic upgrade head
```

---

### Phase 10: Backup and Restore Testing

**Test Backup**:
```bash
# Create backup
./scripts/backup.sh ./test-backups

# Verify backup file exists
ls -lh ./test-backups/
```

**Test Restore**:
```bash
# Stop services
docker-compose down

# Restore database
./scripts/restore.sh ./test-backups/statementxl_backup_XXXXXX.sql.gz

# Restart services
docker-compose up -d

# Verify data
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

---

## Test Failure Troubleshooting

### Common Issues

**Port Already in Use**:
```bash
# Find process
lsof -i :8000

# Kill it
kill -9 <PID>
```

**Database Connection Failed**:
```bash
# Check PostgreSQL status
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

**Backend Won't Start**:
```bash
# Check backend logs
docker-compose logs backend

# Common issues:
# - Missing environment variables
# - Database not ready
# - Port conflict
```

**Frontend Build Failed**:
```bash
# Check Node version
node --version  # Should be 20+

# Clear npm cache
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## Success Criteria

All tests must pass before production deployment:

### Critical ✅
- [x] Code syntax validation
- [ ] Docker images build successfully
- [ ] All containers start and become healthy
- [ ] Health check endpoints respond
- [ ] Authentication flow works
- [ ] Database migrations work
- [ ] Backup/restore tested

### Important
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] No critical security vulnerabilities
- [ ] Performance benchmarks met
- [ ] No memory leaks during load test

### Nice to Have
- [ ] Load test with 100+ concurrent users
- [ ] OWASP ZAP scan clean
- [ ] Frontend E2E tests pass
- [ ] Cross-browser testing complete

---

## Next Steps After Testing

Once all tests pass:

1. **Create Release Tag**:
   ```bash
   git tag -a v1.0.0 -m "Production release v1.0.0"
   git push origin v1.0.0
   ```

2. **Deploy to Staging**:
   - Use deployment guide: `docs/DEPLOY.md`
   - Run smoke tests on staging
   - Monitor for 24-48 hours

3. **Production Deployment**:
   - Follow launch checklist: `docs/LAUNCH_CHECKLIST.md`
   - Enable monitoring and alerting
   - Have rollback plan ready

4. **Post-Deployment**:
   - Monitor error rates
   - Check performance metrics
   - Review logs for anomalies
   - Gather user feedback

---

## Testing in CI/CD

The `.github/workflows/ci.yml` pipeline automatically runs:
- Backend unit tests
- Frontend type checking
- Docker builds
- Security scans

Ensure all CI checks pass before merging to main.

---

## Manual Testing Checklist

Use this for manual QA testing:

### User Registration
- [ ] Can register with valid email/password
- [ ] Cannot register with weak password
- [ ] Cannot register with duplicate email
- [ ] Receives welcome email (if configured)

### User Login
- [ ] Can login with correct credentials
- [ ] Cannot login with wrong password
- [ ] Rate limiting works after failed attempts
- [ ] JWT token received and valid

### File Upload
- [ ] Can upload PDF files
- [ ] Cannot upload non-PDF files
- [ ] File size limits enforced
- [ ] Upload progress indicator works

### Data Extraction
- [ ] PDF tables detected correctly
- [ ] OCR works on scanned PDFs
- [ ] Classification assigns correct categories
- [ ] Mapping to template works

### Excel Export
- [ ] Can export extracted data
- [ ] Excel file downloads correctly
- [ ] Formatting preserved
- [ ] Data accuracy verified

### UI/UX
- [ ] All pages load without errors
- [ ] Navigation works
- [ ] Responsive on mobile
- [ ] No console errors
- [ ] Loading states shown

---

## Support

If tests fail or you need assistance:
- Check logs: `docker-compose logs`
- Review troubleshooting section above
- Consult documentation in `/docs`
- Check GitHub issues: https://github.com/anthropics/claude-code/issues
