# Changelog

All notable changes to StatementXL will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-22

### Added
- **Core Features**
  - PDF upload and table extraction
  - Template mapping with conflict resolution
  - Excel export with formatting
  - Batch processing for multiple PDFs

- **Authentication & Security**
  - JWT authentication with refresh tokens
  - Role-based access control (RBAC)
  - Password strength validation
  - Rate limiting on all endpoints
  - Security headers (CSP, HSTS, etc.)
  - Input validation and sanitization

- **API**
  - RESTful API with OpenAPI documentation
  - Structured error responses with error codes
  - Request correlation IDs for tracing

- **Monitoring & Operations**
  - Health check endpoints (/health, /ready, /metrics)
  - Structured JSON logging
  - Database backup/restore scripts
  - CI/CD pipeline with GitHub Actions

- **Documentation**
  - Installation guide
  - Deployment guide
  - API documentation (Swagger)
  - Security checklist
  - QA test plan

### Infrastructure
- Docker support with multi-stage builds
- PostgreSQL database
- Redis caching
- Performance optimization with GZip compression

### Developer Experience
- Comprehensive unit tests
- Integration tests
- Performance testing with Locust
- Type hints throughout codebase

## [Unreleased]

### Planned
- Email notifications
- Organization/team support
- Advanced analytics dashboard
- Scheduled exports
