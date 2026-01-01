# StatementXL Administrator Guide

**Version:** 1.0.0  
**Last Updated:** December 31, 2025

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [User Management](#user-management)
5. [Organization Management](#organization-management)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Security](#security)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## System Requirements

### Minimum Requirements

- **CPU:** 4 cores
- **RAM:** 8GB
- **Storage:** 50GB SSD
- **OS:** Ubuntu 20.04+ / Windows Server 2019+ / macOS 11+

### Recommended for Production

- **CPU:** 8+ cores
- **RAM:** 16GB+
- **Storage:** 100GB+ SSD
- **OS:** Ubuntu 22.04 LTS

### Software Dependencies

- **Python:** 3.11+
- **Node.js:** 18+
- **PostgreSQL:** 14+
- **Redis:** 7+ (optional, for rate limiting)
- **Docker:** 24+ (optional)

---

## Installation

### Option 1: Docker Deployment (Recommended)

```bash
# Clone repository
git clone https://github.com/hicklax13/StatementXL_Version_2.git
cd StatementXL_Version_2

# Copy environment file
cp .env.example .env

# Edit environment variables
nano .env

# Start services
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create admin user
docker-compose exec backend python scripts/create_admin.py
```

### Option 2: Manual Installation

**Backend Setup:**

```bash
# Install Python dependencies
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up database
createdb statementxl
alembic upgrade head

# Start backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend Setup:**

```bash
# Install Node dependencies
cd frontend
npm install

# Build for production
npm run build

# Serve with nginx or similar
```

---

## Configuration

### Environment Variables

**Required Variables:**

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/statementxl

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Google Gemini API
GOOGLE_API_KEY=your-gemini-api-key

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@statementxl.com

# Application
APP_NAME=StatementXL
APP_ENV=production
DEBUG=false
ALLOWED_HOSTS=statementxl.com,www.statementxl.com

# CORS
CORS_ORIGINS=https://statementxl.com,https://www.statementxl.com

# File Upload
MAX_UPLOAD_SIZE=52428800  # 50MB in bytes
UPLOAD_DIR=/var/statementxl/uploads

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Sentry (optional)
SENTRY_DSN=https://...@sentry.io/...
```

**Optional Variables:**

```bash
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE=redis  # or memory

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Analytics
ANALYTICS_ENABLED=true

# Feature Flags
ENABLE_BATCH_UPLOAD=true
ENABLE_AI_SUGGESTIONS=true
```

### Database Configuration

**PostgreSQL Setup:**

```sql
-- Create database
CREATE DATABASE statementxl;

-- Create user
CREATE USER statementxl_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE statementxl TO statementxl_user;

-- Enable extensions
\c statementxl
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

**Connection Pooling:**

```python
# In config.py
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 40
SQLALCHEMY_POOL_TIMEOUT = 30
SQLALCHEMY_POOL_RECYCLE = 3600
```

---

## User Management

### Creating Users

**Via Admin Panel:**

1. Navigate to `/admin/users`
2. Click "Create User"
3. Fill in details (email, name, role)
4. Set initial password
5. Send welcome email

**Via CLI:**

```bash
# Create admin user
python scripts/create_admin.py \
  --email admin@example.com \
  --password SecurePassword123 \
  --name "Admin User"

# Create regular user
python scripts/create_user.py \
  --email user@example.com \
  --role analyst \
  --name "John Doe"
```

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full system access, user management, organization management |
| **Analyst** | Upload documents, create mappings, export files |
| **Viewer** | View documents and exports (read-only) |
| **API User** | API access only, no web interface |

### Managing User Accounts

**Activate/Deactivate:**

```bash
# Deactivate user
python scripts/manage_user.py --email user@example.com --deactivate

# Reactivate user
python scripts/manage_user.py --email user@example.com --activate
```

**Reset Password:**

```bash
# Generate password reset link
python scripts/reset_password.py --email user@example.com

# Or reset directly
python scripts/reset_password.py \
  --email user@example.com \
  --password NewPassword123
```

**Unlock Account:**

```bash
# Unlock after failed login attempts
python scripts/unlock_account.py --email user@example.com
```

---

## Organization Management

### Creating Organizations

**Via Admin Panel:**

1. Navigate to `/admin/organizations`
2. Click "Create Organization"
3. Enter organization details
4. Assign owner
5. Set subscription tier

**Via API:**

```bash
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "billing_email": "billing@acme.com"
  }'
```

### Managing Members

**Invite Member:**

```bash
python scripts/invite_member.py \
  --org acme-corp \
  --email colleague@example.com \
  --role member
```

**Remove Member:**

```bash
python scripts/remove_member.py \
  --org acme-corp \
  --email colleague@example.com
```

### Subscription Management

**Tiers:**

- **Free:** 10 documents/month, 1 user
- **Pro:** 100 documents/month, 5 users, priority support
- **Enterprise:** Unlimited documents, unlimited users, dedicated support

**Change Subscription:**

```bash
python scripts/change_subscription.py \
  --org acme-corp \
  --tier pro
```

---

## Monitoring & Logging

### Application Logs

**Log Locations:**

- **Application:** `/var/log/statementxl/app.log`
- **Access:** `/var/log/statementxl/access.log`
- **Error:** `/var/log/statementxl/error.log`
- **Audit:** `/var/log/statementxl/audit.log`

**Log Rotation:**

```bash
# /etc/logrotate.d/statementxl
/var/log/statementxl/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 statementxl statementxl
    sharedscripts
    postrotate
        systemctl reload statementxl
    endscript
}
```

### Monitoring Metrics

**Key Metrics to Monitor:**

- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (%)
- Database connections
- CPU usage
- Memory usage
- Disk usage
- Queue depth

**Prometheus Metrics:**

```
# Available at /metrics
http_requests_total
http_request_duration_seconds
db_connections_active
upload_processing_time_seconds
export_generation_time_seconds
```

### Health Checks

**Endpoints:**

- `/health` - Basic health check
- `/health/ready` - Readiness probe
- `/health/live` - Liveness probe

**Example Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  },
  "uptime_seconds": 86400
}
```

---

## Backup & Recovery

### Database Backups

**Automated Daily Backups:**

```bash
# /etc/cron.daily/statementxl-backup
#!/bin/bash
BACKUP_DIR=/var/backups/statementxl
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
pg_dump statementxl | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup uploads
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /var/statementxl/uploads

# Keep last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

**Manual Backup:**

```bash
# Database
pg_dump statementxl > backup.sql

# Uploads
tar -czf uploads_backup.tar.gz /var/statementxl/uploads
```

### Restore from Backup

**Database Restore:**

```bash
# Stop application
systemctl stop statementxl

# Restore database
psql statementxl < backup.sql

# Restart application
systemctl start statementxl
```

**Uploads Restore:**

```bash
tar -xzf uploads_backup.tar.gz -C /
```

### Disaster Recovery

**Recovery Time Objective (RTO):** 1 hour  
**Recovery Point Objective (RPO):** 24 hours

**Recovery Steps:**

1. Provision new server
2. Install dependencies
3. Restore database from backup
4. Restore uploaded files
5. Update DNS records
6. Verify functionality

---

## Security

### SSL/TLS Configuration

**Nginx Configuration:**

```nginx
server {
    listen 443 ssl http2;
    server_name statementxl.com;

    ssl_certificate /etc/letsencrypt/live/statementxl.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/statementxl.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Firewall Rules

```bash
# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow PostgreSQL (only from localhost)
ufw allow from 127.0.0.1 to any port 5432

# Enable firewall
ufw enable
```

### Security Audits

**Weekly Tasks:**

- Review access logs for suspicious activity
- Check failed login attempts
- Verify SSL certificate expiration
- Run dependency vulnerability scans

**Monthly Tasks:**

- Update dependencies
- Review user permissions
- Audit API keys
- Test backup restoration

**Quarterly Tasks:**

- Penetration testing
- Security code review
- Update security documentation

---

## Troubleshooting

### Common Issues

**Issue: Database Connection Errors**

```bash
# Check PostgreSQL status
systemctl status postgresql

# Check connection
psql -U statementxl_user -d statementxl -h localhost

# Check logs
tail -f /var/log/postgresql/postgresql-14-main.log
```

**Issue: High Memory Usage**

```bash
# Check memory usage
free -h

# Check application memory
ps aux | grep uvicorn

# Restart application
systemctl restart statementxl
```

**Issue: Slow Upload Processing**

```bash
# Check queue depth
redis-cli llen upload_queue

# Check worker status
systemctl status statementxl-worker

# Restart workers
systemctl restart statementxl-worker
```

**Issue: Failed Exports**

```bash
# Check export logs
tail -f /var/log/statementxl/export.log

# Check disk space
df -h

# Clear old exports
find /var/statementxl/exports -mtime +7 -delete
```

### Debug Mode

**Enable Debug Logging:**

```bash
# Edit .env
DEBUG=true
LOG_LEVEL=DEBUG

# Restart application
systemctl restart statementxl
```

**View Debug Logs:**

```bash
tail -f /var/log/statementxl/app.log | grep DEBUG
```

---

## Maintenance

### Regular Maintenance Tasks

**Daily:**

- Monitor system health
- Check error logs
- Verify backups completed

**Weekly:**

- Review performance metrics
- Clean up old files
- Update dependencies (security patches)

**Monthly:**

- Database optimization
- Review user accounts
- Capacity planning

### Database Maintenance

**Vacuum Database:**

```sql
VACUUM ANALYZE;
```

**Reindex:**

```sql
REINDEX DATABASE statementxl;
```

**Check Table Sizes:**

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Cleanup Scripts

**Remove Old Uploads:**

```bash
# Delete uploads older than 90 days
find /var/statementxl/uploads -mtime +90 -delete
```

**Remove Old Exports:**

```bash
# Delete exports older than 7 days
find /var/statementxl/exports -mtime +7 -delete
```

**Clean Database:**

```sql
-- Delete old audit logs (older than 1 year)
DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '1 year';

-- Delete failed documents (older than 30 days)
DELETE FROM documents WHERE status = 'failed' AND created_at < NOW() - INTERVAL '30 days';
```

---

## Appendix

### Useful Commands

```bash
# Check application status
systemctl status statementxl

# View logs
journalctl -u statementxl -f

# Restart application
systemctl restart statementxl

# Check database connections
psql -U statementxl_user -d statementxl -c "SELECT count(*) FROM pg_stat_activity;"

# Check disk usage
du -sh /var/statementxl/*

# Test email configuration
python scripts/test_email.py --to admin@example.com
```

### Support Contacts

- **Technical Support:** <support@statementxl.com>
- **Security Issues:** <security@statementxl.com>
- **Emergency:** +1-555-STATEMENT

---

**Administrator Guide Version:** 1.0.0  
**Last Updated:** December 31, 2025
