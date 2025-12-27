# StatementXL

**AI-Powered Financial Statement Extraction & Normalization**

Transform PDFs of financial statements into clean, structured Excel workbooks with intelligent table detection, OCR, and template mapping.

## 🚀 Features

- **PDF Processing**: Extract tables from scanned and native PDFs
- **AI-Powered Extraction**: Intelligent table detection using multiple strategies
- **Template Mapping**: Map extracted data to standardized accounting templates
- **Batch Processing**: Process multiple documents in parallel
- **Excel Export**: Generate formatted Excel workbooks with validation
- **Audit Trail**: Track all processing steps and changes

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.11 |
| Frontend | React 18, TypeScript, Vite |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| PDF Engine | Tesseract, Ghostscript, Poppler |

## 📦 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local dev)
- Node.js 20+ (for local dev)

### Docker (Recommended)
```bash
# Clone and start
git clone https://github.com/your-repo/statementxl.git
cd statementxl
docker-compose up --build -d

# Access the app
open http://localhost
```

### Local Development
```bash
# Backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## 🔐 Environment Variables

Create a `.env` file:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/statementxl

# Security
JWT_SECRET_KEY=your-secret-key-here
ENABLE_HSTS=false

# API Keys (optional)
GOOGLE_API_KEY=your-google-api-key
```

## 📚 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit -v

# Integration tests
python -m pytest tests/integration -v

# With coverage
python -m pytest tests/ --cov=backend --cov-report=html
```

## 📁 Project Structure

```
StatementXL/
├── backend/
│   ├── api/routes/       # API endpoints
│   ├── auth/             # JWT authentication
│   ├── middleware/       # Logging, security, rate limiting
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic
│   └── validation/       # Input validators
├── frontend/
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # React components
│   │   └── pages/        # Route pages
│   └── Dockerfile
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   ├── backup.sh
│   └── restore.sh
└── docker-compose.yml
```

## 🔒 Security Features

- JWT authentication with refresh tokens
- Password strength validation
- Rate limiting (brute force protection)
- Input sanitization (XSS prevention)
- Security headers (CSP, HSTS, etc.)
- SQL injection detection

## 📊 Database Backup

```bash
# Backup
./scripts/backup.sh ./backups

# Restore
./scripts/restore.sh ./backups/statementxl_backup_XXXXXX.sql.gz
```

## 📄 License

MIT License - see LICENSE file.

