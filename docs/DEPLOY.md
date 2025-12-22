# StatementXL Deployment Guide

## Deployment Options

### 1. Docker Compose (Recommended)

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose logs -f

# Update
docker-compose down
git pull
docker-compose up --build -d
```

### 2. Kubernetes

See `deploy/k8s/` for Kubernetes manifests.

### 3. Cloud Platforms

- **AWS**: Use ECS or EKS
- **GCP**: Use Cloud Run or GKE
- **Azure**: Use Container Apps or AKS

## Pre-Deployment Checklist

- [ ] Set `JWT_SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] Configure `DATABASE_URL`
- [ ] Set `CORS_ORIGINS` to production domains
- [ ] Enable `ENABLE_HSTS=true`
- [ ] Configure SMTP for emails
- [ ] Set up monitoring/alerting
- [ ] Configure backup schedule
- [ ] Test rollback procedure

## Database Migrations

```bash
# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Check current version
alembic current
```

## SSL/TLS Setup

Use a reverse proxy (nginx, Traefik) or load balancer for SSL termination.

Example nginx config:
```nginx
server {
    listen 443 ssl;
    server_name app.statementxl.com;
    
    ssl_certificate /etc/letsencrypt/live/app.statementxl.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.statementxl.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:80;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000;
    }
}
```

## Monitoring

Endpoints for monitoring:
- `GET /health` - Basic liveness check
- `GET /ready` - Full readiness check
- `GET /metrics` - Application metrics

## Scaling

### Horizontal Scaling
- Backend: Stateless, scale freely
- Frontend: Static files, scale with CDN
- Database: Use read replicas
- Cache: Redis cluster

### Resource Limits
```yaml
resources:
  backend:
    cpu: 1-2 cores
    memory: 512MB-2GB
  frontend:
    cpu: 0.25-0.5 cores
    memory: 128MB-256MB
```
