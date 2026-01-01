# Production Deployment Checklist

**Application:** StatementXL v1.0.0  
**Date:** December 31, 2025  
**Status:** ✅ Ready for Production

---

## Pre-Deployment Checklist

### Environment Configuration

- [x] All environment variables documented
- [x] Production `.env` file prepared
- [x] Database credentials secured
- [x] API keys configured
- [x] CORS origins set to production domains

### Security

- [x] HTTPS/SSL certificates ready
- [x] Security headers configured
- [x] Rate limiting enabled
- [x] JWT secrets are unique and secure
- [x] No hardcoded credentials in code

### Database

- [x] PostgreSQL 14+ installed
- [x] Database created
- [x] Migrations ready (`alembic upgrade head`)
- [x] Connection pooling configured
- [x] Backup procedures documented

### Application

- [x] Frontend builds successfully
- [x] Backend passes all checks
- [x] All dependencies installed
- [x] Static assets optimized

---

## Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 nodejs npm postgresql nginx
```

### 2. Clone Repository

```bash
git clone https://github.com/hicklax13/StatementXL_Version_2.git
cd StatementXL_Version_2
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with production values
```

### 4. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

### 5. Frontend Build

```bash
cd frontend
npm install
npm run build
```

### 6. Start Services

```bash
# Backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with systemd
sudo systemctl start statementxl
```

### 7. Configure Nginx

```nginx
server {
    listen 443 ssl;
    server_name statementxl.com;
    
    location / {
        root /var/www/statementxl/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

---

## Post-Deployment Verification

- [ ] Access <https://statementxl.com>
- [ ] Test login/register
- [ ] Upload test PDF
- [ ] Verify export download
- [ ] Check database connectivity
- [ ] Monitor error logs

---

## Rollback Plan

```bash
# If issues found, rollback:
git checkout v0.9.0
sudo systemctl restart statementxl
```

---

**Deployment Status:** ✅ Ready
