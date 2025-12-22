# StatementXL Installation Guide

## Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 20 or higher
- **PostgreSQL**: 15 or higher (or use Docker)
- **Redis**: 7 or higher (optional, for caching)

## Quick Install (Docker)

The fastest way to run StatementXL:

```bash
# Clone the repository
git clone https://github.com/your-repo/statementxl.git
cd statementxl

# Start all services
docker-compose up --build -d

# Verify
curl http://localhost:8000/health
```

Access the app at http://localhost

## Manual Installation

### 1. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start server
python -m uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Database Setup

**Option A: Docker PostgreSQL**
```bash
docker run -d \
  --name statementxl-postgres \
  -e POSTGRES_USER=statementxl \
  -e POSTGRES_PASSWORD=statementxl \
  -e POSTGRES_DB=statementxl \
  -p 5432:5432 \
  postgres:15-alpine
```

**Option B: Local PostgreSQL**
```sql
CREATE USER statementxl WITH PASSWORD 'your-password';
CREATE DATABASE statementxl OWNER statementxl;
```

### 4. Redis (Optional)

```bash
docker run -d --name statementxl-redis -p 6379:6379 redis:7-alpine
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| JWT_SECRET_KEY | Yes | Secret for JWT tokens |
| REDIS_URL | No | Redis connection string |
| SMTP_HOST | No | Email server host |
| SMTP_USER | No | Email username |
| SMTP_PASSWORD | No | Email password |

## Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# Check readiness (database + cache)
curl http://localhost:8000/ready

# Run tests
python -m pytest tests/ -v
```

## Troubleshooting

### Port Already in Use
```bash
# Find process using port
lsof -i :8000
# Kill it
kill -9 <PID>
```

### Database Connection Failed
- Verify PostgreSQL is running
- Check DATABASE_URL format
- Verify user/password

### Frontend Can't Connect to Backend
- Check CORS origins include frontend URL
- Verify backend is running
