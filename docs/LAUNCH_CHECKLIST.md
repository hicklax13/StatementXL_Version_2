# StatementXL Launch Checklist

## Pre-Launch (T-7 Days)

### Infrastructure
- [ ] Production environment provisioned
- [ ] Database created and migrated
- [ ] Redis cache configured
- [ ] SSL certificates installed
- [ ] Domain DNS configured
- [ ] CDN configured (optional)

### Security
- [ ] JWT_SECRET_KEY is secure random value
- [ ] Database password is secure
- [ ] All secrets in environment variables
- [ ] CORS origins set to production domains
- [ ] HTTPS enforced (HSTS enabled)
- [ ] Security audit complete

### Monitoring
- [ ] Health check endpoint verified
- [ ] Logging configured
- [ ] Alerting rules set up
- [ ] Uptime monitoring active
- [ ] Error tracking (Sentry) configured

### Backups
- [ ] Database backup tested
- [ ] Restore procedure verified
- [ ] Backup schedule configured

## Launch Day (T-0)

### Final Checks
- [ ] All tests passing
- [ ] Performance acceptable
- [ ] No P0/P1 bugs open
- [ ] Documentation complete

### Deployment
- [ ] Create release tag: `git tag -a v1.0.0 -m "Initial release"`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Deploy to production
- [ ] Run database migrations
- [ ] Verify health check: `curl https://app.statementxl.com/health`

### Smoke Test
- [ ] Register new account
- [ ] Login
- [ ] Upload PDF
- [ ] View extraction
- [ ] Export to Excel
- [ ] Logout

### Communication
- [ ] Notify stakeholders
- [ ] Update status page
- [ ] Prepare support team

## Post-Launch (T+24 Hours)

### Monitor
- [ ] Check error rates
- [ ] Check response times
- [ ] Check database performance
- [ ] Review logs for anomalies

### Report
- [ ] Document any issues
- [ ] Create post-launch report
- [ ] Plan next iteration

## Rollback Procedure

If critical issues occur:

```bash
# 1. Switch traffic to maintenance page
# 2. Rollback deployment
docker-compose pull backend:previous
docker-compose up -d

# 3. Rollback database if needed
./scripts/restore.sh ./backups/latest.sql.gz

# 4. Verify
curl https://app.statementxl.com/health

# 5. Investigate and fix
```

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| On-Call Engineer | TBD | TBD |
| Technical Lead | TBD | TBD |
| Product Owner | TBD | TBD |
