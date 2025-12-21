# StatementXL Version 2

A modular, analyst-first SaaS platform for converting financial statement PDFs into populated Excel models.

## Overview

StatementXL is a financial statement normalization engine that:
1. Ingests arbitrary financial PDFs (10-Ks, audited statements, management reports, tax returns)
2. Extracts structured data with full lineage tracking
3. Maps extracted data into user-provided Excel templates while preserving formulas
4. Surfaces ambiguity for analyst-in-the-loop resolution
5. Maintains audit trails linking every cell back to source PDF coordinates

## Phase 1: Core Data Pipeline

This phase implements the extraction pipeline: PDF → structured data with confidence scores and lineage.

### Tech Stack
- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 15 (with pgvector extension)
- **OCR**: pdfplumber (primary), Tesseract (fallback)
- **Table Detection**: Camelot (lattice mode), pdfplumber (stream mode)

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Tesseract OCR installed (`tesseract` on PATH)
- Ghostscript installed (for Camelot)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/StatementXL_Version_2.git
   cd StatementXL_Version_2
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Copy environment file**
   ```bash
   copy .env.example .env  # Windows
   # or
   cp .env.example .env  # Linux/Mac
   ```

5. **Start PostgreSQL and Redis**
   ```bash
   docker-compose up -d
   ```

6. **Run the API server**
   ```bash
   uvicorn backend.main:app --reload
   ```

7. **Access API documentation**
   Open http://localhost:8000/docs in your browser

## API Usage

### Upload PDF

```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@statement.pdf"
```

**Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "statement.pdf",
  "page_count": 10,
  "tables": [
    {
      "page": 1,
      "rows": [
        {
          "cells": [
            {"value": "Revenue", "bbox": [100, 200, 300, 220]},
            {"value": 1500000, "raw": "$1,500,000", "bbox": [350, 200, 500, 220], "confidence": 0.95}
          ]
        }
      ],
      "confidence": 0.92
    }
  ]
}
```

## Running Tests

```bash
pytest tests/ -v --cov=backend --cov-report=term-missing
```

## Project Structure

```
StatementXL_Version_2/
├── backend/
│   ├── api/routes/        # API endpoints
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic
│   ├── repositories/      # Database access
│   ├── schemas/           # Pydantic schemas
│   ├── main.py            # FastAPI application
│   ├── config.py          # Settings management
│   └── database.py        # Database setup
├── tests/                 # Test suite
├── data/                  # Ontology and reference data
├── uploads/               # Uploaded PDFs storage
├── docker-compose.yml     # Docker services
└── requirements.txt       # Python dependencies
```

## License

Proprietary - All rights reserved
